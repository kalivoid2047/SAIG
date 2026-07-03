from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.crophealth.repository import CropHealthRepository
from saig.modules.crophealth.schemas import (
    DiseaseCreate,
    DiseaseOut,
    DiseaseReportCreate,
    DiseaseReportOut,
    DiseaseReportTransition,
)
from saig.modules.crophealth.service import CropHealthService
from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.shared.pagination import Page, PageParams, page_params

diseases_router = APIRouter(prefix="/diseases", tags=["crop-health"])
reports_router = APIRouter(prefix="/disease-reports", tags=["crop-health"])
gis_router = APIRouter(prefix="/gis", tags=["crop-health"])


@diseases_router.get("", response_model=list[DiseaseOut])
async def list_diseases(
    current: CurrentUser = Depends(require_permission("crops:read")),
    session: AsyncSession = Depends(get_db),
) -> list[DiseaseOut]:
    diseases = await CropHealthService(session).list_diseases(current.organization_id)
    return [DiseaseOut.model_validate(d) for d in diseases]


@diseases_router.post("", response_model=DiseaseOut, status_code=status.HTTP_201_CREATED)
async def create_disease(
    body: DiseaseCreate,
    current: CurrentUser = Depends(require_permission("crops:manage")),
    session: AsyncSession = Depends(get_db),
) -> DiseaseOut:
    disease = await CropHealthService(session).create_disease(
        body, current.organization_id, current.id
    )
    return DiseaseOut.model_validate(disease)


@reports_router.get("", response_model=Page[DiseaseReportOut])
async def list_reports(
    params: PageParams = Depends(page_params),
    report_status: str | None = Query(None, alias="status"),
    disease_id: str | None = Query(None, alias="diseaseId"),
    current: CurrentUser = Depends(require_permission("crops:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[DiseaseReportOut]:
    reports, total = await CropHealthRepository(session).list_reports(
        current.organization_id, params, report_status, disease_id
    )
    return Page.build([DiseaseReportOut.model_validate(r) for r in reports], total, params)


@reports_router.post("", response_model=DiseaseReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: DiseaseReportCreate,
    current: CurrentUser = Depends(require_permission("crops:report")),
    session: AsyncSession = Depends(get_db),
) -> DiseaseReportOut:
    report, _outbreak = await CropHealthService(session).create_report(
        body, current.organization_id, current.id
    )
    return DiseaseReportOut.model_validate(report)


@reports_router.post("/{report_id}/transitions", response_model=DiseaseReportOut)
async def transition_report(
    report_id: str,
    body: DiseaseReportTransition,
    current: CurrentUser = Depends(require_permission("crops:confirm")),
    session: AsyncSession = Depends(get_db),
) -> DiseaseReportOut:
    report = await CropHealthService(session).transition_report(
        report_id, body.to, current.organization_id, current.id
    )
    return DiseaseReportOut.model_validate(report)


@reports_router.post("/{report_id}/confirm-disease/{disease_id}", response_model=DiseaseReportOut)
async def confirm_disease(
    report_id: str,
    disease_id: str,
    current: CurrentUser = Depends(require_permission("crops:confirm")),
    session: AsyncSession = Depends(get_db),
) -> DiseaseReportOut:
    report = await CropHealthService(session).confirm_disease(
        report_id, disease_id, current.organization_id, current.id
    )
    return DiseaseReportOut.model_validate(report)


@gis_router.get("/disease-heatmap")
async def disease_heatmap(
    current: CurrentUser = Depends(require_permission("crops:read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Active disease reports as GeoJSON weighted by severity (map layer)."""
    reports = await CropHealthRepository(session).heatmap_points(current.organization_id)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(r.longitude), float(r.latitude)],
                },
                "properties": {
                    "id": r.id,
                    "severity": r.severity,
                    "status": r.status,
                    "isOutbreak": r.is_outbreak,
                    "affectedPct": float(r.affected_pct),
                },
            }
            for r in reports
        ],
    }
