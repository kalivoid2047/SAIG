from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DiseaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    crop: str = Field(min_length=1, max_length=60)
    pathogen_type: Literal["fungal", "bacterial", "viral", "pest", "nutritional", "unknown"] | None = Field(  # noqa: E501
        default=None, alias="pathogenType"
    )
    description: str | None = Field(default=None, max_length=5000)
    treatment_guide: str | None = Field(default=None, max_length=5000, alias="treatmentGuide")


class DiseaseOut(ORMModel):
    id: str
    name: str
    crop: str
    pathogen_type: str | None = Field(default=None, serialization_alias="pathogenType")
    description: str | None
    treatment_guide: str | None = Field(default=None, serialization_alias="treatmentGuide")


class DiseaseReportCreate(BaseModel):
    crop_cycle_id: str = Field(alias="cropCycleId")
    disease_id: str | None = Field(default=None, alias="diseaseId")
    severity: int = Field(ge=1, le=5)
    affected_pct: float = Field(ge=0, le=100, alias="affectedPct")
    notes: str | None = Field(default=None, max_length=2000)


class DiseaseReportTransition(BaseModel):
    to: Literal["confirmed", "treated", "resolved", "dismissed"]


class DiseaseReportOut(ORMModel):
    id: str
    crop_cycle_id: str = Field(serialization_alias="cropCycleId")
    disease_id: str | None = Field(default=None, serialization_alias="diseaseId")
    reported_by: str = Field(serialization_alias="reportedBy")
    severity: int
    affected_pct: float = Field(serialization_alias="affectedPct")
    status: str
    latitude: float
    longitude: float
    notes: str | None
    is_outbreak: bool = Field(serialization_alias="isOutbreak")
    reported_at: datetime = Field(serialization_alias="reportedAt")
