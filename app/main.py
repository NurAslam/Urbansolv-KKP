from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from shapely.geometry import shape, box, mapping
import geopandas as gpd
import json, os

import ee
from .config import settings
from .models import *
from .storage import save_roi_geojson, bbox_to_polygon_geojson, load_roi_gdf
from .gee_utils import init_ee, annual_median, area_stats_ndwi, ndwi, ndbi
from .rdtr_utils import intersect_roi_with_rdtr

app = FastAPI(title="Geo Backend - ROI, Indeks, RDTR")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INIT ---
init_ee()  # GEE siap di start-up

@app.get("/status")
def health():
    return {"status": "ok"}

@app.get("/roi")
def list_rois():
    import os, json
    from .config import settings
    items = []
    for fname in os.listdir(settings.ROI_DIR):
        if fname.endswith(".geojson"):
            roi_id = fname.replace(".geojson", "")
            items.append({
                "roi_id": roi_id,
                "download": f"/roi/{roi_id}/download"
            })
    return {"count": len(items), "items": items}


# ---------- ROI CRUD ----------
@app.post("/roi/bbox", response_model=ROI)
def create_roi_bbox(payload: RoiCreateBBox):
    g = bbox_to_polygon_geojson(**payload.bbox.dict())
    roi_id, path = save_roi_geojson(g, payload.name)
    return ROI(roi_id=roi_id, name=payload.name, path=path)

@app.post("/roi/geojson", response_model=ROI)
def create_roi_geojson(payload: RoiCreateGeoJSON):
    try:
        geom = shape(payload.geojson)
        if geom.is_empty:
            raise ValueError("Geometry kosong")
        if geom.geom_type not in ("Polygon","MultiPolygon"):
            raise ValueError("Harus Polygon/MultiPolygon")
    except Exception as e:
        raise HTTPException(400, f"GeoJSON tidak valid: {e}")
    roi_id, path = save_roi_geojson(payload.geojson, payload.name)
    return ROI(roi_id=roi_id, name=payload.name, path=path)

@app.get("/roi/{roi_id}")
def get_roi(roi_id: str):
    path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    if not os.path.exists(path):
        raise HTTPException(404, "ROI tidak ditemukan")
    with open(path) as f:
        return json.load(f)

@app.get("/roi/{roi_id}/download")
def download_roi(roi_id: str):
    path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    if not os.path.exists(path): raise HTTPException(404, "ROI tidak ditemukan")
    return FileResponse(path, media_type="application/geo+json", filename=f"{roi_id}.geojson")

# ---------- ANALISIS ----------
@app.post("/roi/{roi_id}/analyze", response_model=AnalyzeResult)
def analyze_roi(roi_id: str, params: AnalyzeParams):
    roi_path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    if not os.path.exists(roi_path):
        raise HTTPException(404, "ROI tidak ditemukan")
    roi_gdf = load_roi_gdf(roi_path)
    geom = ee.Geometry(roi_gdf.unary_union.__geo_interface__)

    img = annual_median(params.year, geom, params.cloud_pct)

    # luas air/darat berbasis NDWI (baku)
    area_water_ha, area_land_ha = area_stats_ndwi(img, geom)

    # Darat ∩ Konservasi (opsional cepat memakai vektor RDTR yang dioverlay)
    inter = intersect_roi_with_rdtr(roi_gdf)
    area_land_in_cons_ha = float(inter['area_ha'].sum()) if not inter.empty else 0.0

    return AnalyzeResult(
        year=params.year,
        index=params.index,
        area_water_ha=round(area_water_ha, 2),
        area_land_ha=round(area_land_ha, 2),
        area_land_in_conservation_ha=round(area_land_in_cons_ha, 2)
    )

# ---------- NDWI / NDBI preview as simple stats (optionally return URL tile later) ----------
@app.get("/roi/{roi_id}/index")
def index_preview(roi_id: str, year: int, index: str = "ndwi", cloud_pct: int = 15):
    roi_path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    if not os.path.exists(roi_path):
        raise HTTPException(404, "ROI tidak ditemukan")
    roi_gdf = load_roi_gdf(roi_path)
    geom = ee.Geometry(roi_gdf.unary_union.__geo_interface__)
    img = annual_median(year, geom, cloud_pct)

    if index.lower() == "ndbi":
        band = ndbi(img)
        vis = {'min': -0.3, 'max': 0.3, 'palette': ['#f7fbff','#6baed6','#08306b']}
    else:
        band = ndwi(img)
        vis = {'min': -0.3, 'max': 0.7, 'palette': ['#fee5d9','#74c476','#006d2c']}

    mp = band.getMapId(vis)
    # Frontend dapat konsumsi mp['tile_fetcher'].url_format sebagai TileLayer
    return {
        "year": year,
        "index": index.lower(),
        "tile_url": mp['tile_fetcher'].url_format,
        "mapid": mp['mapid'],
        "token": mp['token']
    }

# ---------- INTERSECTION ----------
@app.post("/roi/{roi_id}/intersection", response_model=IntersectResult)
def roi_intersection_rdtr(roi_id: str):
    roi_path = os.path.join(settings.ROI_DIR, f"{roi_id}.geojson")
    if not os.path.exists(roi_path):
        raise HTTPException(404, "ROI tidak ditemukan")
    roi_gdf = load_roi_gdf(roi_path)
    inter = intersect_roi_with_rdtr(roi_gdf)
    out_path = os.path.join(settings.INTERSECT_DIR, f"{roi_id}_rdtr.geojson")
    inter.to_file(out_path, driver="GeoJSON")
    total_ha = float(inter['area_ha'].sum()) if not inter.empty else 0.0
    return IntersectResult(
        roi_id=roi_id,
        rdtr_features=0 if inter is None else len(inter),
        total_area_ha=round(total_ha, 2),
        output_path=out_path
    )

@app.get("/intersection/{roi_id}/download")
def download_intersection(roi_id: str):
    path = os.path.join(settings.INTERSECT_DIR, f"{roi_id}_rdtr.geojson")
    if not os.path.exists(path): raise HTTPException(404, "Intersection belum dibuat")
    return FileResponse(path, media_type="application/geo+json", filename=f"{roi_id}_rdtr.geojson")
