import ee
from .config import settings

import os
import json
import ee
from .config import settings

def init_ee():
    """
    Inisialisasi Earth Engine:
    - Prioritas: EE_KEY_FILE (JSON key) + EE_PROJECT
    - Fallback: user auth lokal (browser), tetap usahakan pass project
    """
    try:
        if not settings.EE_PROJECT:
            raise RuntimeError("EE_PROJECT belum diset. Isi di .env (EE_PROJECT=your-gcp-project-id).")

        # Opsi utama: pakai file JSON key service account
        if settings.EE_KEY_FILE:
            if not os.path.exists(settings.EE_KEY_FILE):
                raise RuntimeError(f"EE_KEY_FILE tidak ditemukan: {settings.EE_KEY_FILE}")

            with open(settings.EE_KEY_FILE, "r") as f:
                key_json = json.load(f)

            sa_email = key_json.get("client_email")
            if not sa_email:
                raise RuntimeError("JSON key invalid: client_email tidak ada.")

            creds = ee.ServiceAccountCredentials(sa_email, key_data=json.dumps(key_json))
            ee.Initialize(credentials=creds, project=settings.EE_PROJECT)
            return

        try:
            ee.Initialize(project=settings.EE_PROJECT)
        except Exception:
            ee.Authenticate()  
            ee.Initialize(project=settings.EE_PROJECT)

    except Exception as e:
        
        raise RuntimeError(f"Error initializing Earth Engine: {type(e).__name__}: {e}") from None


def s2_sr_collection(year: int, roi_eom: ee.Geometry, cloud_pct: int):
    start = f"{year}-01-01"; end = f"{year}-12-31"
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterDate(start, end)
           .filterBounds(roi_eom)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct)))
    # mask awan via scl
    def mask_scl(img):
        scl = img.select('SCL')
        bad = (scl.eq(3)  # shadow
               .Or(scl.eq(8))  # cloud med prob
               .Or(scl.eq(9))  # cloud high prob
               .Or(scl.eq(10)) # cirrus
               .Or(scl.eq(11)))# snow
        return img.updateMask(bad.Not())
    col = col.map(mask_scl)
    # fallback jika kosong (khusus 2015 dsb)
    if col.size().getInfo() == 0 and year == 2015:
        col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
               .filterDate("2015-07-01", "2015-12-31")
               .filterBounds(roi_geom))
    return col

def annual_median(year: int, roi_geom: ee.Geometry, cloud_pct: int):
    col = s2_sr_collection(year, roi_geom, cloud_pct)
    median = col.median().clip(roi_geom)
    return median

def ndwi(img: ee.Image) -> ee.Image:
    # (B3 - B8)/(B3 + B8)
    green = img.select('B3').resample('bilinear').reproject('EPSG:4326', None, 20)
    nir   = img.select('B8').resample('bilinear').reproject('EPSG:4326', None, 20)
    return green.subtract(nir).divide(green.add(nir)).rename('ndwi')

def ndbi(img: ee.Image) -> ee.Image:
    # (B11 - B8)/(B11 + B8)
    swir1 = img.select('B11').resample('bilinear').reproject('EPSG:4326', None, 20)
    nir   = img.select('B8' ).resample('bilinear').reproject('EPSG:4326', None, 20)
    return swir1.subtract(nir).divide(swir1.add(nir)).rename('ndbi')

def area_stats_ndwi(image: ee.Image, roi_geom: ee.Geometry) -> tuple[float,float]:
    m = ndwi(image)
    water = m.gt(0)
    land  = m.lte(0)
    area = ee.Image.pixelArea()
    w = water.multiply(area).reduceRegion(ee.Reducer.sum(), roi_geom, 20, maxPixels=1e11)
    l = land .multiply(area).reduceRegion(ee.Reducer.sum(), roi_geom, 20, maxPixels=1e11)
    wv = w.get('ndwi').getInfo() or 0
    lv = l.get('ndwi').getInfo() or 0
    return wv/10000.0, lv/10000.0  # to Ha