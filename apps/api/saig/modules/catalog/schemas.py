from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SuitabilityEntry(BaseModel):
    region_id: str = Field(alias="regionId")
    score: int = Field(ge=1, le=5)
    rationale: str | None = Field(default=None, max_length=2000)


class SuitabilityOut(ORMModel):
    region_id: str = Field(serialization_alias="regionId")
    score: int
    rationale: str | None


class VarietyCreate(BaseModel):
    crop: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    maturity_days: int | None = Field(default=None, gt=0, le=400, alias="maturityDays")
    yield_potential_kg_ha: float | None = Field(
        default=None, gt=0, alias="yieldPotentialKgHa"
    )
    drought_tolerance: int | None = Field(default=None, ge=1, le=5, alias="droughtTolerance")
    disease_tolerance: int | None = Field(default=None, ge=1, le=5, alias="diseaseTolerance")
    characteristics: dict = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=5000)


class VarietyUpdate(BaseModel):
    crop: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    maturity_days: int | None = Field(default=None, gt=0, le=400, alias="maturityDays")
    yield_potential_kg_ha: float | None = Field(
        default=None, gt=0, alias="yieldPotentialKgHa"
    )
    drought_tolerance: int | None = Field(default=None, ge=1, le=5, alias="droughtTolerance")
    disease_tolerance: int | None = Field(default=None, ge=1, le=5, alias="diseaseTolerance")
    characteristics: dict | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = Field(default=None, alias="isActive")


class VarietyOut(ORMModel):
    id: str
    crop: str
    name: str
    code: str
    maturity_days: int | None = Field(default=None, serialization_alias="maturityDays")
    yield_potential_kg_ha: float | None = Field(
        default=None, serialization_alias="yieldPotentialKgHa"
    )
    drought_tolerance: int | None = Field(default=None, serialization_alias="droughtTolerance")
    disease_tolerance: int | None = Field(default=None, serialization_alias="diseaseTolerance")
    characteristics: dict
    notes: str | None
    is_active: bool = Field(serialization_alias="isActive")
    created_at: datetime = Field(serialization_alias="createdAt")
    suitability: list[SuitabilityOut] = []
