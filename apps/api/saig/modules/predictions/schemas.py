from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ModelVersionOut(ORMModel):
    id: str
    model_name: str = Field(serialization_alias="modelName")
    version: str
    status: str
    metrics: dict
    training_rows: int | None = Field(default=None, serialization_alias="trainingRows")
    promoted_at: datetime | None = Field(default=None, serialization_alias="promotedAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class YieldPredictionOut(ORMModel):
    id: str
    crop_cycle_id: str = Field(serialization_alias="cropCycleId")
    predicted_yield_kg_ha: float = Field(serialization_alias="predictedYieldKgHa")
    pi_low_kg_ha: float = Field(serialization_alias="piLowKgHa")
    pi_high_kg_ha: float = Field(serialization_alias="piHighKgHa")
    confidence: float
    low_confidence: bool = Field(serialization_alias="lowConfidence")
    created_at: datetime = Field(serialization_alias="createdAt")


class YieldRescoreRequest(BaseModel):
    crop_cycle_ids: list[str] | None = Field(default=None, alias="cropCycleIds")


class DemandForecastOut(ORMModel):
    period_month: date = Field(serialization_alias="periodMonth")
    forecast_qty_kg: float = Field(serialization_alias="forecastQtyKg")
    pi_low_kg: float = Field(serialization_alias="piLowKg")
    pi_high_kg: float = Field(serialization_alias="piHighKg")
    confidence: float
    seasonal_component: float | None = Field(
        default=None, serialization_alias="seasonalComponent"
    )


class DemandSeriesOut(BaseModel):
    regionId: str
    varietyId: str
    modelVersion: str
    points: list[DemandForecastOut]


class JobResult(BaseModel):
    status: str
    detail: str
    count: int = 0
