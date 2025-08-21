import osmnx as ox
import contextily as ctx
import folium
import geopandas as gpd
from shapely import Point, Polygon

# Use the v2 API
ox.settings.use_cache = True
ox.settings.log_console = True

from osmnx.features import features_from_place

place_name = "Düsseldorf, Germany"

def convert_to_metric(frame):
    converted_frame = frame.to_crs(epsg=32632)
    return converted_frame

def convert_to_pseudomerc(frame):
    converted_frame = frame.to_crs(epsg=3857)
    return converted_frame

benches = features_from_place(
    place_name,
    tags={"amenity": "bench"}
)

toilets = features_from_place(
    place_name,
    tags={"amenity": "toilets"}
)

shops = features_from_place(
    place_name,
    tags={"shop": ["convenience", "supermarket", "kiosk", "alcohol"]}
)

parks = features_from_place(
    place_name,
    tags={"leisure": "park"}
)

benches_proj = convert_to_metric(benches)
toilets_proj = convert_to_metric(toilets)
shops_proj = convert_to_metric(shops)
parks_proj = convert_to_metric(parks)

def only_geometry(dataframe):
    return dataframe[["geometry"]]

parks_small = only_geometry(parks_proj)
toilets_small = only_geometry(toilets_proj)
shops_small = only_geometry(shops_proj)

toilet_buffers = toilets_small.copy()
toilet_buffers.geometry = toilet_buffers.buffer(100)

shops_buffers = shops_small.copy()
shops_buffers.geometry = shops_buffers.buffer(100)

toilet_buffers_small = toilet_buffers[["geometry"]].copy()
shops_buffers_small = shops_buffers[["geometry"]].copy()
parks_small = parks_proj[["geometry"]].copy()

benches_near_toilets = gpd.sjoin(benches_proj, toilet_buffers_small, how="inner", predicate="within").reset_index(drop=True)
benches_near_both = gpd.sjoin(benches_near_toilets, shops_buffers_small, how="inner", predicate="within").reset_index(drop=True)
optimal_benches = gpd.sjoin(benches_near_both, parks_small, how="inner", predicate="within").reset_index(drop=True)

# 1. Calculate centroids on the projected CRS (meters, accurate)
centroids_proj = optimal_benches.geometry.centroid

# 2. Create GeoSeries with CRS info
# calculating centroid in the earlier step leaves you with a list of coordinates, but no attached CRS data (e.g. what kind of coordinates these are). This line does the following:
#takes the coordinates in centroids_proj and turns them into a GeoSeries, using the same Coordinate Reference System as benches_near_both
centroids_proj = gpd.GeoSeries(centroids_proj, crs=benches_near_both.crs)

# 3. Transform centroids to lat/lon (EPSG:4326) for mapping
centroids_wgs84 = centroids_proj.to_crs(epsg=4326) #wgs as in World Geodetic System 1984, apparently a standard

# 4. Calculate map center from the lat/lon centroids
map_center = [centroids_wgs84.y.mean(), centroids_wgs84.x.mean()]

# Use previously computed map_center from lat/lon centroids (already set)
m = folium.Map(location=map_center, zoom_start=14, tiles="CartoDB Positron") #tiles controls what background map you use

# Add markers using the lat/lon centroids directly
for point in centroids_wgs84:
    folium.CircleMarker(
        location=[point.y, point.x],
        radius=5,
        color='green',
        fill=True,
        fill_opacity=0.8,
        popup="Optimal Bench"
    ).add_to(m)

toilet_buffers_wgs84 = toilet_buffers.to_crs(epsg=4326)
folium.GeoJson(
    toilet_buffers_wgs84,
    name="Toilet Buffers",
    style_function=lambda feature: {
        'fillColor': 'blue',
        'color': 'blue',
        'weight': 0.5,
        'fillOpacity': 0.1,
    }
).add_to(m)

shops_buffers_wgs84 = shops_buffers.to_crs(epsg=4326)
folium.GeoJson(
    shops_buffers_wgs84,
    name="Shops Buffers",
    style_function=lambda feature: {
        'fillColor': 'yellow',
        'color': 'yellow',
        'weight': 0.5,
        'fillOpacity': 0.1,
    }
).add_to(m)

folium.LayerControl().add_to(m)

# Show the map (in notebook) or save it to an HTML file
m.save("optimal_benches_map.html")