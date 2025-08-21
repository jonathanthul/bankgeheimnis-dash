import osmnx as ox #type: ignore
import pandas as pd #type: ignore
import geopandas as gpd #type: ignore
import numpy as np #type: ignore
import matplotlib.pyplot as plt #type: ignore
import contextily as cx #type: ignore

ox.settings.use_cache = True
ox.settings.log_console = True

from osmnx.features import features_from_place #type: ignore
from shapely.geometry import Point #type: ignore
from scipy.spatial import cKDTree#type: ignore

PLACE_NAME = "Düsseldorf, Germany"
city_name = PLACE_NAME.split(",")[0]

def testplot(gdf):
    to_plot = gdf.to_crs(epsg=3857)
    ax = to_plot.plot(linewidth=0.5, color="black", figsize=(8, 8))
    cx.add_basemap(ax, source=cx.providers["CartoDB"]["Positron"]) #type: ignore
    plt.axis("off")
    plt.show()

boundary_polygon = ox.geocode_to_gdf(PLACE_NAME) #special function to get the boundary of the city

benches = features_from_place(
    PLACE_NAME,
    tags={"amenity": "bench"}
)
toilets = features_from_place(
    PLACE_NAME,
    tags={"amenity": "toilets"}
)
shops = features_from_place(
    PLACE_NAME,
    tags={"shop": ["convenience", "supermarket", "kiosk", "alcohol"]}
)
greens = features_from_place(
    PLACE_NAME,
    tags={"leisure": ["park"]}
)
nichtkiffen = features_from_place(
    PLACE_NAME,
    tags={
        "amenity": ["kindergarten", "school"],
        "leisure": ["playground", "schoolyard"]
    }
)
streets = features_from_place(
    PLACE_NAME,
    tags={"highway": ["primary", "secondary", "tertiary", "motorway", "trunk", "primary_link", "secondary_link", "tertiary_link", "motorway_link", "trunk_link"]}
)
platforms = features_from_place(
    PLACE_NAME,
    tags={"public_transport": "platform", "highway": "bus_stop", "railway": "platform"}
)

benches_proj = benches.to_crs(epsg=32632)
toilets_proj = toilets.to_crs(epsg=32632)
shops_proj = shops.to_crs(epsg=32632)
greens_proj = greens.to_crs(epsg=32632)
streets_proj = streets.to_crs(epsg=32632)
nichtkiffen_proj = nichtkiffen.to_crs(epsg=32632)
platforms_proj = platforms.to_crs(epsg=32632)

### Keep only relevant columns
benches_clean = benches_proj[["geometry", "amenity", "layer"]].copy()
toilets_clean = toilets_proj[["geometry", "amenity"]].copy()
shops_clean = shops_proj[["geometry", "name", "shop", "opening_hours"]].copy()
greens_clean = greens_proj[["geometry", "leisure", "landuse"]].copy()
nichtkiffen_clean = nichtkiffen_proj[["geometry", "amenity", "leisure"]].copy()
streets_clean = streets_proj[["geometry", "highway", "maxspeed", "layer"]].copy()
platforms_clean = platforms_proj[["geometry", "public_transport", "railway", "highway"]].copy()

### Prepare dataframes for filtering
nichtkiffen_area = nichtkiffen_clean.buffer(100) # 100m radius around the geometry
platform_area = platforms_clean.buffer(2) # 2m radius around platforms to exclude benches on them (or next to such points)

streets_clean = streets_clean.copy() # somehow you have to do this
streets_clean["layer"] = pd.to_numeric(streets_clean["layer"], errors="coerce") # the datatype of the series was object, turn it to numbers
streets_clean = streets_clean[streets_clean["layer"].isnull()] # witht the correct datatype, you can filter for NaN values, i.e. streets that aren't above or under ground

benches_clean = benches_clean.copy()
benches_clean["layer"] = pd.to_numeric(benches_clean["layer"], errors="coerce")
benches_clean = benches_clean[benches_clean["layer"].isnull()] # only keep benches that are not above ground or underground
print(f"benches_clean shape after filtering out nonzero-layer benches: {benches_clean.shape}. Geom_types: {benches_clean.geom_type.unique()}")
#benches_clean = benches_clean[benches_clean["geometry"].intersects(platform_area).any()]

platform_mask = lambda bench_geom: not bench_geom.intersects(platform_area).any() # applied to a geometry series, returns a series of the same length (mask) that contains True wherever the geometry value intersected any platform area
benches_clean = benches_clean[benches_clean.geometry.apply(platform_mask)] # keeps all benches that don't intersect a platform area
print(f"benches_clean shape after masking out benches intersecting platforms: {benches_clean.shape}. Geom_types: {benches_clean.geom_type.unique()}")

benches_clean.geometry = benches_clean.geometry.centroid #there are a few benches that aren't points. for your purposes, you make them into points using centroids
print(f"benches_clean shape after converting to centroids: {benches_clean.shape}. Geom_types: {benches_clean.geom_type.unique()}")

toilets_clean.geometry = toilets_clean.geometry.centroid
print(f"toilets_clean shape after converting to centroids: {toilets_clean.shape}. Geom_types: {toilets_clean.geom_type.unique()}")

shops_clean.geometry = shops_clean.geometry.centroid
print(f"shops_clean shape after converting to centroids: {shops_clean.shape}. Geom_types: {shops_clean.geom_type.unique()}")

greens_union = greens_clean.geometry.union_all() #Group the areas into one big object

#print(f"\n nichtkiffen_area type: {nichtkiffen_area.type}")
nichtkiffen_union = nichtkiffen_area.geometry.union_all()
streets_union = streets_clean.geometry.union_all()

#####################
### Build final table
#####################

final_table = benches_clean[["geometry"]].copy() #start with list of all eligible benches
print(f"Created final_table, shape: {final_table.shape}")

# Distance calculations for closest points
def to_array(df): # helper function to turn a gpd dataframe into an array of coordinates
    return np.array([(geom.x, geom.y) for geom in df.geometry])

bench_coords = to_array(benches_clean)
toilet_coords = to_array(toilets_clean)
shop_coords = to_array(shops_clean)

# use K-dimensional tree method to find the toilets and shops closest to each entry in bench_coords
toilet_distance, toilet_index = cKDTree(toilet_coords).query(bench_coords, k=1)
shop_distance, shop_index = cKDTree(shop_coords).query(bench_coords, k=1)
# result are four numpy arrays that you want to reintegrate into a gpd dataframe

if toilet_distance is not None and toilet_index is not None and shop_distance is not None and shop_index is not None:
    print(f"Successfully calculated toilet and shop distance using cKDTree.")
else:
    print("Error calculating toilet and shop distance using cKDTree.")

final_table = final_table.assign( #add a number of series to the table
    #series name = value
    toilet_distance = toilet_distance,
    toilet_index = toilet_index, #helper series to add toilet location
    shop_distance = shop_distance, 
    shop_index = shop_index #helper series to add shop location
)
print(f"Added toilet_distance, toilet_index, shop_distance and shop_index columns to final_table. Shape: {final_table.shape}")

final_table = final_table.assign(
    toilet_loc = final_table["toilet_index"].apply( #create a column called toilet_loc
        lambda index: toilets_clean.to_crs(epsg=4326)["geometry"].iloc[index] #fill it with values obtained by applying this function: for each row, check the index and look up the geometry of that index in the toilets_clean dataframe
    ),
    shop_loc = final_table["shop_index"].apply(
        lambda index: shops_clean.to_crs(epsg=4326)["geometry"].iloc[index] #important to change crs for later consistency
    ),
    shop_name = final_table["shop_index"].apply(
        lambda index: shops_clean["name"].iloc[index]
    ),
    shop_hours = final_table["shop_index"].apply(
        lambda index: shops_clean["opening_hours"].iloc[index]
    ),
    in_green_space = final_table["geometry"].intersects(greens_union),
    kiffen_erlaubt = ~final_table["geometry"].intersects(nichtkiffen_union),
    street_distance = final_table.geometry.distance(streets_union)
)

final_table = final_table.drop(["toilet_index", "shop_index"], axis=1)

#####################
### Export GeoJSON files
#####################

benches_wgs84 = final_table.to_crs(epsg=4326)
file_name = city_name + "_benches.geojson"
benches_wgs84.to_file(file_name, driver="GeoJSON")

nichtkiffen_wgs84 = nichtkiffen_area.to_crs(epsg=4326)
file_name = city_name + "_nichtkiffen.geojson"
nichtkiffen_wgs84.to_file(file_name, driver="GeoJSON")

streets_wgs84 = streets_clean.to_crs(epsg=4326)
file_name = city_name + "_streets.geojson"
streets_wgs84.to_file(file_name, driver="GeoJSON")

greens_wgs84 = greens_clean.to_crs(epsg=4326)
file_name = city_name + "_greens.geojson"
greens_wgs84.to_file(file_name, driver="GeoJSON")

boundary_wgs84 = boundary_polygon.to_crs(epsg=4326)
file_name = city_name + "_boundary.geojson"
boundary_wgs84.to_file(file_name, driver="GeoJSON")



'''
What you want in the table:
1. Location of the benches (geometry)
2. Distance of benches to closest toilet (float)
3. Location of closest toilet (geometry)
4. Distance to closest shop (float)
5. Location of closest shop (geometry)
6. Name of closest shop (str)
7. Opening hours of closest shop (str)
8. Is this bench in a green space? (bool)
9. Is this bench at least 100m away from a nichtkiffen spot? (bool)
10. Distance to closest big street (float)
11. All green spaces
11. All nichtkiffen-areas
11. the border of the city currently shown

benches_clean.geometry = benches_clean.geometry.centroid #calculate centroid for the 82 non-point benches in the dataframe
toilets_clean.geometry = toilets_clean.geometry.centroid #calculate centroid for the non-point toilets (?) in the dataframe
shops_clean.geometry = shops_clean.geometry.centroid

#calculating centroid doesn't make sense for streets or areas like nichtkiffen. You need to think of a differernt way to calculate that

def to_array(df):
    return np.array([(geom.x, geom.y) for geom in df.geometry])

bench_coords = to_array(benches_clean)
toilet_coords = to_array(toilets_clean)
shops_coords = to_array(shops_clean)

toilet_distance, toilet_index = cKDTree(toilet_coords).query(bench_coords, k=1)
shop_distance, shop_index = cKDTree(shops_coords).query(bench_coords, k=1)
#all four variables above are numpy arrays

print("Toilet index:\n")
print(toilet_index)
print(type(toilet_index))
print("\n")

print(toilet_distance, toilet_index)

#print("Toilets clean:")
#print(toilets_clean)

#print("Toilet coords:")
#print(toilet_coords) #somehow cKDTree should be returning the index of the closest thing, which you should be able to use to fetch the coordinates from some other table?

print(shops_clean)

bench_data = benches_clean.assign(
    toilet_distance=toilet_distance,
    toilet_index=toilet_index, #assign the index so you can turn it into the location in the next step
    shop_distance=shop_distance,
    shop_index=shop_index,
)

bench_data["toilet_loc"] = bench_data["toilet_index"].apply(
    lambda index: toilets_clean["geometry"].iloc[index]
)
bench_data["shop_loc"] = bench_data["shop_index"].apply(
    lambda index: shops_clean["geometry"].iloc[index]
)
bench_data["shop_hours"] = bench_data["shop_index"].apply(
    lambda index: shops_clean["opening_hours"].iloc[index]
)

bench_data = bench_data.drop(["toilet_index", "shop_index"], axis=1)

print(bench_data.info())

benches_clean["toilet_distance"], benches_clean["shop_distance"] = toilet_distance, shop_distance

nichtkiffen_union = nichtkiffen_clean.union_all() #makes it into a multi-polygon
benches_clean["nichtkiffen_distance"] = benches_clean.geometry.distance(nichtkiffen_union)

streets_union = streets_clean.union_all()
benches_clean["street_distance"] = benches_clean.geometry.distance(streets_union)

#print(benches_clean)
benches_wgs84 = benches_clean.to_crs(epsg=4326)

file_name = city_name + "_benches.geojson"
benches_wgs84.to_file(file_name, driver="GeoJSON")

#somehow, some benches still remain as lines in the final file. Example: schoolyard Ecke Goethe-/Lindemannstraße
#wäre nice wenn du pro Bank auch noch Infos zur nächsten Toilette, Shops etc speicherst die du dann als Tooltip anzeigen kannst
#vielleicht ne option, Bushaltestellenbänke u.Ä. rauszufiltern?
#nichtkiffen_distance should also take into account train stations and sports facilities. Right now it makes it shows all the benches at Düsseldorf Hbf
#die street distance is irgendwie komisch. Das müsstest du noch mal richtig überprüfen, evtl hast du nicht das richtige Datenset runter geladen

'''