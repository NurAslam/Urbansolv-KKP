import geopandas as gpd
from shapely.geometry import shape
from .config import settings

# RDTR/konservasi dimuat sekali dan disimpan
_RDTR_GDF: gpd.GeoDataFrame | None = None

def load_rdtr() -> gpd.GeoDataFrame:
    global _RDTR_GDF
    if _RDTR_GDF is None:
        gdf = gpd.read_file(settings.RDTR_PATH)
        if gdf.crs is None:
            gdf.set_crs(4326, inplace=True)  # asumsi
        _RDTR_GDF = gdf.to_crs(4326)
    return _RDTR_GDF

def intersect_roi_with_rdtr(roi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rdtr = load_rdtr()
    roi_gdf = roi_gdf.to_crs(4326)
    inter = gpd.overlay(rdtr, roi_gdf[['geometry']], how='intersection', keep_geom_type=False)
    # Hitung luas (Ha) pada CRS metrik (UTM 49S)
    inter_m = inter.to_crs(settings.DEFAULT_UTM_EPSG)
    inter['area_ha'] = inter_m.geometry.area / 10000.0
    return inter
