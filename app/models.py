from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class RoiCreateBBox(BaseModel):
    name: Optional[str] = None
    bbox: BBox

class RoiCreateGeoJSON(BaseModel):
    name: Optional[str] = None
    geojson: dict  # valid Polygon/MultiPolygon GeoJSON (EPSG:4326)

class ROI(BaseModel):
    roi_id: str
    name: Optional[str]
    path: str

class AnalyzeParams(BaseModel):
    year: int = Field(ge=2015, le=2035)
    index: Literal["ndwi", "ndbi"] = "ndwi"
    cloud_pct: int = 15

class AnalyzeResult(BaseModel):
    year: int
    index: str
    area_water_ha: float
    area_land_ha: float
    area_land_in_conservation_ha: float

class IntersectResult(BaseModel):
    roi_id: str
    rdtr_features: int
    total_area_ha: float
    output_path: str