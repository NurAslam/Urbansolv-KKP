import json, uuid, os
import geopandas as gpd
from shapely.geometry import Polygon, shape
from .config import settings

def save_roi_geojson(geom_geojson: dict, name: str | None = None) -> tuple[str, str]:
    roi_id = str(uuid.uuid4())
    path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    feature = {"type":"Feature","properties":{"name": name or roi_id},"geometry": geom_geojson}
    fc = {"type":"FeatureCollection","features":[feature]}
    with open(path, "w") as f:
        json.dump(fc, f)
    return roi_id, path

def bbox_to_polygon_geojson(min_lon, min_lat, max_lon, max_lat) -> dict:
    poly = Polygon([
        (min_lon, min_lat), (max_lon, min_lat),
        (max_lon, max_lat), (min_lon, max_lat),
        (min_lon, min_lat)
    ])
    return json.loads(gpd.GeoSeries([poly], crs=4326).to_json())["features"][0]["geometry"]

def load_roi_gdf(path: str) -> gpd.GeoDataFrame:
    with open(path) as f:
        fc = json.load(f)
    geoms = [shape(feat["geometry"]) for feat in fc["features"]]
    gdf = gpd.GeoDataFrame(fc["features"], geometry=geoms, crs=4326)
    return gdf