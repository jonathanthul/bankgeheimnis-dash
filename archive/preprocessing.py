import osmnx as ox
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt

ox.settings.use_cache = True
ox.settings.log_console = True

from osmnx.features import features_from_place
from shapely.geometry import Point
from scipy.spatial import cKDTree

PLACE_NAME = "Düsseldorf, Germany"

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
parks = features_from_place(
    PLACE_NAME,
    tags={"leisure": "park"}
)
streets = features_from_place(
    PLACE_NAME,
    tags={"highway": ["primary", "secondary", "motorway"]}
)

benches_proj = benches.to_crs(epsg=32632)
toilets_proj = toilets.to_crs(epsg=32632)
shops_proj = shops.to_crs(epsg=32632)
parks_proj = parks.to_crs(epsg=32632)
streets_proj = streets.to_crs(epsg=32632)

benches_clean = benches_proj[["geometry", "amenity"]]
toilets_clean = toilets_proj[["geometry", "amenity"]]
shops_clean = shops_proj[["geometry", "shop"]]
parks_clean = parks_proj[["geometry", "leisure"]]
streets_clean = streets_proj[["geometry", "highway", "maxspeed"]]

toilets_buffer_100 = toilets_clean.copy()
toilets_buffer_100.geometry = toilets_buffer_100.geometry.buffer(100)
toilets_buffer_300 = toilets_clean.copy()
toilets_buffer_300.geometry = toilets_buffer_300.geometry.buffer(300)

shops_buffer_100 = shops_clean.copy()
shops_buffer_100.geometry = shops_buffer_100.geometry.buffer(100)
shops_buffer_300 = shops_clean.copy()
shops_buffer_300.geometry = shops_buffer_300.geometry.buffer(300)

streets_buffer_10 = streets_clean.copy()
streets_buffer_10.geometry = streets_buffer_10.geometry.buffer(10)

benches_clean = benches_clean.assign(
    toilet_100=benches_clean.geometry.apply(
        lambda bench_geom: toilets_buffer_100.geometry.intersects(bench_geom).any() #type: ignore
    ),
    toilet_300=benches_clean.geometry.apply(
        lambda bench_geom: toilets_buffer_300.geometry.intersects(bench_geom).any()
    ),
    shops_100=benches_clean.geometry.apply(
        lambda bench_geom: shops_buffer_100.geometry.intersects(bench_geom).any()
    ),
    shops_300=benches_clean.geometry.apply(
        lambda bench_geom: shops_buffer_300.geometry.intersects(bench_geom).any()
    ),
        streets_10=benches_clean.geometry.apply(
        lambda bench_geom: streets_buffer_10.geometry.intersects(bench_geom).any()
    )
)
'''The code above expresses this: Take benches_clean and assign the following list of columsn to it. For the column called "toilet_100", take the geometry column from benches clean and apply the following function to its values to obtain the values for the new column. This function maps elements of its domain, called bench_geom here, to the value you get when you check if the geometry cell of any row in toilets_buffer_100 contains it.'''

benches_wgs84 = benches_clean.to_crs(epsg=4326)
benches_wgs84.to_file("benches.geojson", driver="GeoJSON")