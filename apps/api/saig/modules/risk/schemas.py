from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentOut(ORMModel):
    id: str
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    domain: str
    score: int
    band: str
    factors: list[dict]
    assessed_date: date = Field(serialization_alias="assessedDate")
    created_at: datetime = Field(serialization_alias="createdAt")


class RiskBoardDomain(BaseModel):
    domain: str
    score: int
    band: str
    previousScore: int | None = None
    trend: int = 0  # score - previousScore
    factors: list[dict]


class RiskBoardOut(BaseModel):
    assessedDate: date | None = None
    domains: list[RiskBoardDomain]
    highRiskCount: int


class RiskHistoryPoint(BaseModel):
    assessedDate: date
    score: int


class JobResult(BaseModel):
    status: str
    detail: str
    count: int = 0
