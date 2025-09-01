import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Earth Engine
    EE_PROJECT: str = ""          # wajib diisi
    EE_SERVICE_ACCOUNT: str = ""  # opsional (akan dibaca dari JSON key juga)
    EE_KEY_FILE: str = ""         # path ke JSON key (disarankan)

    # Data lokal
    RDTR_PATH: str = "./Kawasan_Konservasi/Kawasan_Konservasi.shp"
    STORAGE_DIR: str = "./data"
    ROI_DIR: str = "./data/rois"
    INTERSECT_DIR: str = "./data/intersections"
    DEFAULT_UTM_EPSG: int = 32749

    class Config:
        env_file = ".env"

settings = Settings()
os.makedirs(settings.ROI_DIR, exist_ok=True)
os.makedirs(settings.INTERSECT_DIR, exist_ok=True)
