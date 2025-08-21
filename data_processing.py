import osmnx as ox #type:ignore
import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree#type: ignore
import os.path
import matplotlib.pyplot as plt #type: ignore
import contextily as cx #type: ignore

ox.settings.use_cache = True
ox.settings.log_console = True

from osmnx import features_from_polygon #type:ignore
from shapely.geometry import box

def testplot(gdf):
    to_plot = gdf.to_crs(epsg=3857)
    ax = to_plot.plot(linewidth=0.5, color="black", figsize=(8, 8))
    cx.add_basemap(ax, source=cx.providers["CartoDB"]["Positron"]) #type: ignore
    plt.axis("off")
    plt.show()

PLACE_NAME= "Rhein-Ruhr"
PLACE_NAMES = [
    "Ruhrgebiet, Germany",
    "Düsseldorf, Germany",
    "Leverkusen, Germany",
    "Langenfeld (Rheinland), Germany",
    "Dormagen, Germany",
    "Monheim am Rhein, Germany",
    "Wuppertal, Germany",
    "Velbert, Germany",
    "Ratingen, Germany",
    "Mettmann, Germany",
    "Erkrath, Germany",
    "Solingen, Germany",
    "Köln, Germany",
]

print("Getting region boundaries.")
boundaries = [ox.geocode_to_gdf(place) for place in PLACE_NAMES]
places_gdf = gpd.GeoDataFrame(pd.concat(boundaries, ignore_index=True))

region = places_gdf.union_all()
minx, miny, maxx, maxy = region.bounds
big_rect = box(minx - 2, miny - 2, maxx + 2, maxy + 2)
mask = big_rect.difference(region)

mask_gdf = gpd.GeoDataFrame(geometry=[mask], crs=places_gdf.crs)

big_boundary = places_gdf.dissolve().simplify(tolerance=0.0001)

tags = {
    "amenity": ["bench", "toilets", "kindergarten", "school"],
    "shop": ["convenience", "supermarket", "kiosk", "alcohol"],
    "leisure": ["playground", "schoolyard"],
    "highway": ["primary", "secondary", "tertiary", "motorway", "trunk",
                "primary_link", "secondary_link", "tertiary_link", "motorway_link", "trunk_link", "bus_stop"],
    "public_transport": ["platform"],
    "railway": ["platform"]
}

print("Downloading features within the region.")
boundary_polygon = big_boundary.geometry.iloc[0]
all_features = ox.features.features_from_polygon(boundary_polygon, tags) #Get all features in one big dataframe
print("Reprojecting all_features.")
all_features_projected = all_features.copy().to_crs(epsg=32632) #Reproject the dataframe for distance measurements

#Split up all_features into features
print("Splitting up all_features.")
benches_raw = all_features_projected[all_features_projected["amenity"] == "bench"]
toilets_raw = all_features_projected[all_features_projected["amenity"] == "toilets"]
shops_raw = all_features_projected[all_features_projected["shop"].isin(["convenience", "supermarket", "kiosk", "alcohol"])]
nichtkiffen_raw = all_features_projected[
    (all_features_projected["amenity"].isin(["kindergarten", "school"])) |
    (all_features_projected["leisure"].isin(["playground", "schoolyard"]))
]
streets_raw = all_features_projected[all_features_projected["highway"].isin(["primary", "secondary", "tertiary", "motorway", "trunk", "primary_link", "secondary_link", "tertiary_link", "motorway_link", "trunk_link"])]
platforms_raw = all_features_projected[
    (all_features_projected["public_transport"] == "platform") |
    (all_features_projected["highway"] == "bus_stop") |
    (all_features_projected["railway"] == "platform")
]
print(f"Split up all_features_projected ({all_features_projected.shape[0]} features) into {benches_raw.shape[0]} benches, {toilets_raw.shape[0]} toilets, {shops_raw.shape[0]} shops, {nichtkiffen_raw.shape[0]} nichtkiffen_objects, {streets_raw.shape[0]} streets and {platforms_raw.shape[0]} platforms. Total sum of extracted features: {benches_raw.shape[0] + toilets_raw.shape[0] + shops_raw.shape[0] + nichtkiffen_raw.shape[0] + streets_raw.shape[0] +platforms_raw.shape[0]}.")

#Remove benches underground
print("Removing benches undergound.")
benches = benches_raw[["geometry", "layer"]].copy()
benches["layer"] = pd.to_numeric(benches["layer"], errors="coerce") #make layer column readable
benches = benches[benches["layer"].isnull() | benches["layer"] > 0] #drop benches underground
benches = benches.drop("layer", axis=1)
print(f"benches.shape after removing undergound benches: {benches.shape}")

#Remove benches close to platforms
#buffer and keep as GeoDataFrame
print("Removing platform benches.")
platforms = platforms_raw[["geometry"]].copy()
platforms["geometry"] = platforms.buffer(2)
benches_to_remove = gpd.sjoin( #looks for benches that intersect exclude_areas. Will return a list of matches with duplicate benches in case a bench intersects e.g. a nichtkiffen_area and a platform
    benches,
    platforms,
    how="inner",
    predicate="intersects"
)
benches = benches.drop(benches_to_remove.index) #drop all benches that matches in benches_to_remove
print(f"benches.shape after removing platform benches: {benches.shape}")

#Add nichtkiffen column. Create nichtkiffen mutlipolygon for export.
print("Adding nichtkiffen column.")
nichtkiffen = nichtkiffen_raw[["geometry"]].copy()
nichtkiffen["geometry"] = nichtkiffen.buffer(101)
# left join: keep all benches, attach matching nichtkiffen indices
benches["kiffen_erlaubt"] = ~benches.index.isin(
    gpd.sjoin(benches, nichtkiffen, how="inner", predicate="intersects").index
)
#gpd.sjoin(..., how="inner") returns all benches that intersect some nichtkiffen polygon
#.index grabs their indexes, not sure as what type
#benches.index.isin(...) compares indices from benches to other indices and (I guess) returns a Boolean series with "True" if a benches index is found in the argument

#Add information about closest toilets and shops.
print("Calculating closest toilet and shop.")
toilets = toilets_raw[["geometry"]].copy()
shops = shops_raw[["geometry", "name", "opening_hours"]].copy()
# Buffer and keep them as GeoDataFrames
#Helper function to find closest point and attach distance and associated values. First argument is a dataframe that you want to get distance measurements in, second argument is the dataframe containing the objects you're measuring the distance to. Third argument is a list of attributes you want to keep, referred to by their column names in target_gdf. Fourth argument is a name for the type of object contained in target_gdf.
def nearest_with_attributes(source_gdf, target_gdf, target_attrs, feature_name="feature"):
    if source_gdf.crs != target_gdf.crs: 
        print("nearest_with_attributes warning: CRS mismatch")
        return None
       
    #Extract coordinates as arrays
    source_coords = np.array([(geom.x, geom.y) for geom in source_gdf.geometry])
    target_coords = np.array([(geom.x, geom.y) for geom in target_gdf.geometry])
    #zip() takes two tuples and joins them together as pairs of the nth item of each tuple

    #Split the target_data into a tree automatically
    tree = cKDTree(target_coords)

    #Query nearest. Returns two arrays of length(source_gdf): One with distance measures, one with indexes (or row positions) from target_gdf.
    dist, idx = tree.query(source_coords, k=1)
    
    # Attach results
    source_gdf[f"{feature_name}_dist"] = dist
    for attr in target_attrs:
        if attr == target_gdf.geometry.name: #In case you want to keep the geometry of the target.
            nearest_geoms = gpd.GeoSeries(target_gdf.iloc[idx].geometry, crs=target_gdf.crs).to_crs(epsg=4326)
            #target_gdf.iloc[idx] returns a DataFrame (I think) of the length of the array idx, containing for each element of idx the full row with that index from targeet_gdf. The rest of the code makes sure it's a GeoSeries in the correct CRS for Dash.
            source_gdf[f"{feature_name}_lon"] = nearest_geoms.x.values
            source_gdf[f"{feature_name}_lat"] = nearest_geoms.y.values
        else: #If it's not the geometry attribute, just copy it.
            source_gdf[f"{feature_name}_{attr}"] = target_gdf.iloc[idx][attr].values

    return source_gdf

#Ensure points by calculating centroids.
benches["geometry"] = benches.geometry.centroid.where(
    benches.geom_type != "Point", benches.geometry
)
toilets["geometry"] = toilets.geometry.centroid.where(
    toilets.geom_type != "Point", toilets.geometry
)
shops["geometry"] = shops.geometry.centroid.where(
    shops.geom_type != "Point", shops.geometry
)
#Add columns for closest toilet and shop as well as extra info to the benches dataframe.
benches = nearest_with_attributes(benches, toilets, ["geometry"], feature_name="toilet")
benches = nearest_with_attributes(benches, shops, ["geometry", "name", "opening_hours"], feature_name="shop")

#Add street distance column. This tages ages when running.
print("Calculating street_distance.")
streets = streets_raw[["geometry", "layer"]].copy()
streets["layer"] = pd.to_numeric(streets["layer"], errors="coerce") #make layer column readable
streets = streets[streets["layer"].isnull()]#only keep surface-level-streets
street_union = streets.geometry.union_all()
benches["street_dist"] = benches.geometry.distance(street_union)

#Export GeoJSON files.
# Make sure target directory exists (relative to your working dir)
print("Exporting files.")
directory = os.path.join(os.getcwd(), "geojson")
os.makedirs(directory, exist_ok=True)
# Build path
city_name = PLACE_NAME.split(",")[0].lower()

file_name = os.path.join(directory, f"{city_name}_benches.geojson")
benches_wgs84 = benches.to_crs(epsg=4326)
benches_wgs84.to_file(file_name, driver="GeoJSON")
print(f"Wrote {str(file_name)}.")

file_name = os.path.join(directory, f"{city_name}_nichtkiffen.geojson")
nichtkiffen_poly = gpd.GeoDataFrame(geometry=[nichtkiffen.union_all().simplify(tolerance=2, preserve_topology=True)], crs=nichtkiffen.crs) #Dissolve into multipolygon and smooth it out to make it a simpler geometry.
nichtkiffen_wgs84 = nichtkiffen_poly.to_crs(epsg=4326)
nichtkiffen_wgs84.to_file(file_name, driver="GeoJSON")
print(f"Wrote {str(file_name)}.")

#file_name = os.path.join(directory, f"{city_name}_boundary.geojson")
#boundary_simplified = gpd.GeoDataFrame(geometry=[boundary_polygon.simplify(tolerance=3, preserve_topology=True)], crs=benches.crs)
##referral to benches.crs feels hacky but I really can't deal with this shit right now
#boundary_wgs84 = boundary_simplified.to_crs(epsg=4326)
#boundary_wgs84.to_file(file_name, driver="GeoJSON")

file_name = os.path.join(directory, f"{city_name}_mask.geojson")
#referral to benches.crs feels hacky but I really can't deal with this shit right now
mask_wgs84 = mask_gdf.to_crs(epsg=4326)
mask_wgs84.to_file(file_name, driver="GeoJSON")
print(f"Wrote {str(file_name)}.")