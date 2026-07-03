from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from saig.shared.geo import GeoJSONPolygon


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Regions -----------------------------------------------------------------

class RegionOut(ORMModel):
    id: str
    name: str
    code: str


class RegionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


class RegionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


# --- Farmers ------------------------------------------------------------------

class FarmerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200, alias="fullName")
    national_id: str | None = Field(default=None, max_length=40, alias="nationalId")
    phone: str | None = Field(default=None, max_length=25, pattern=r"^\+?[0-9 ()-]{7,}$")
    email: EmailStr | None = None
    gender: Literal["male", "female", "other", "undisclosed"] | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100, alias="birthYear")
    cooperative: str | None = Field(default=None, max_length=200)
    region_id: str | None = Field(default=None, alias="regionId")
    consent_given: bool = Field(alias="consentGiven")

    @field_validator("consent_given")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("data-processing consent must be recorded at registration")
        return v


class FarmerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200, alias="fullName")
    phone: str | None = Field(default=None, max_length=25, pattern=r"^\+?[0-9 ()-]{7,}$")
    email: EmailStr | None = None
    cooperative: str | None = Field(default=None, max_length=200)
    region_id: str | None = Field(default=None, alias="regionId")


class FarmerOut(ORMModel):
    """List/detail farmer. PII fields are pre-masked by the service when the
    caller lacks farmers:read_pii — masking happens before serialization."""

    id: str
    full_name: str = Field(serialization_alias="fullName")
    national_id: str | None = Field(default=None, serialization_alias="nationalId")
    phone: str | None = None
    email: str | None = None
    gender: str | None = None
    birth_year: int | None = Field(default=None, serialization_alias="birthYear")
    cooperative: str | None = None
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    consent_given_at: datetime | None = Field(
        default=None, serialization_alias="consentGivenAt"
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    farm_count: int = Field(default=0, serialization_alias="farmCount")
    pii_masked: bool = Field(default=True, serialization_alias="piiMasked")


class ProductionRecordCreate(BaseModel):
    season: str = Field(min_length=1, max_length=40)
    variety_id: str | None = Field(default=None, alias="varietyId")
    area_ha: float = Field(gt=0, alias="areaHa")
    yield_kg: float = Field(ge=0, alias="yieldKg")
    source: Literal["declared", "measured", "migrated"] = "declared"


class ProductionRecordOut(ORMModel):
    id: str
    season: str
    variety_id: str | None = Field(default=None, serialization_alias="varietyId")
    area_ha: float = Field(serialization_alias="areaHa")
    yield_kg: float = Field(serialization_alias="yieldKg")
    source: str


# --- Farms & fields ---------------------------------------------------------------

class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    boundary: GeoJSONPolygon | None = None
    area_ha: float | None = Field(default=None, gt=0, alias="areaHa")


class FieldOut(ORMModel):
    id: str
    farm_id: str = Field(serialization_alias="farmId")
    name: str
    boundary: dict | None
    area_ha: float = Field(serialization_alias="areaHa")


class FarmCreate(BaseModel):
    farmer_id: str = Field(alias="farmerId")
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    region_id: str | None = Field(default=None, alias="regionId")
    total_area_ha: float | None = Field(default=None, gt=0, alias="totalAreaHa")


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    region_id: str | None = Field(default=None, alias="regionId")
    total_area_ha: float | None = Field(default=None, gt=0, alias="totalAreaHa")


class FarmOut(ORMModel):
    id: str
    farmer_id: str = Field(serialization_alias="farmerId")
    name: str
    latitude: float
    longitude: float
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    total_area_ha: float | None = Field(default=None, serialization_alias="totalAreaHa")
    fields: list[FieldOut] = []


class FarmerDetailOut(FarmerOut):
    farms: list[FarmOut] = []
    production_records: list[ProductionRecordOut] = Field(
        default_factory=list, serialization_alias="productionRecords"
    )


# --- Soil ---------------------------------------------------------------------------

class SoilSampleCreate(BaseModel):
    sampled_at: date = Field(alias="sampledAt")
    ph: float | None = Field(default=None, ge=0, le=14)
    nitrogen_ppm: float | None = Field(default=None, ge=0, alias="nitrogenPpm")
    phosphorus_ppm: float | None = Field(default=None, ge=0, alias="phosphorusPpm")
    potassium_ppm: float | None = Field(default=None, ge=0, alias="potassiumPpm")
    organic_matter_pct: float | None = Field(
        default=None, ge=0, le=100, alias="organicMatterPct"
    )
    texture: Literal["sand", "loamy_sand", "sandy_loam", "loam",
                     "silt_loam", "clay_loam", "clay"] | None = None
    source: Literal["lab", "field_kit", "estimate"] = "lab"


class SoilSampleOut(ORMModel):
    id: str
    field_id: str = Field(serialization_alias="fieldId")
    sampled_at: date = Field(serialization_alias="sampledAt")
    ph: float | None
    nitrogen_ppm: float | None = Field(default=None, serialization_alias="nitrogenPpm")
    phosphorus_ppm: float | None = Field(default=None, serialization_alias="phosphorusPpm")
    potassium_ppm: float | None = Field(default=None, serialization_alias="potassiumPpm")
    organic_matter_pct: float | None = Field(
        default=None, serialization_alias="organicMatterPct"
    )
    texture: str | None
    source: str


# --- Crop cycles ------------------------------------------------------------------------

class CropCycleCreate(BaseModel):
    variety_id: str = Field(alias="varietyId")
    season: str = Field(min_length=1, max_length=40)
    expected_harvest_at: date | None = Field(default=None, alias="expectedHarvestAt")
    practices: dict = Field(default_factory=dict)


class CropCycleTransition(BaseModel):
    to: Literal["planted", "growing", "harvested", "failed"]
    occurred_on: date | None = Field(default=None, alias="occurredOn")
    actual_yield_kg: float | None = Field(default=None, ge=0, alias="actualYieldKg")


class CropCycleOut(ORMModel):
    id: str
    field_id: str = Field(serialization_alias="fieldId")
    variety_id: str = Field(serialization_alias="varietyId")
    season: str
    status: str
    planted_at: date | None = Field(default=None, serialization_alias="plantedAt")
    expected_harvest_at: date | None = Field(
        default=None, serialization_alias="expectedHarvestAt"
    )
    actual_harvest_at: date | None = Field(default=None, serialization_alias="actualHarvestAt")
    actual_yield_kg: float | None = Field(default=None, serialization_alias="actualYieldKg")
    practices: dict
    created_at: datetime = Field(serialization_alias="createdAt")
