from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.fieldops.schemas import (
    CropCycleCreate,
    CropCycleOut,
    CropCycleTransition,
    FarmCreate,
    FarmerCreate,
    FarmerDetailOut,
    FarmerOut,
    FarmerUpdate,
    FarmOut,
    FarmUpdate,
    FieldCreate,
    FieldOut,
    ProductionRecordCreate,
    ProductionRecordOut,
    RegionCreate,
    RegionOut,
    RegionUpdate,
    SoilSampleCreate,
    SoilSampleOut,
)
from saig.modules.fieldops.services import CropService, FarmerService, FarmService, RegionService
from saig.modules.iam.deps import CurrentUser, get_current_user, get_db, require_permission
from saig.shared.pagination import Page, PageParams, page_params

regions_router = APIRouter(prefix="/regions", tags=["regions"])
farmers_router = APIRouter(prefix="/farmers", tags=["farmers"])
farms_router = APIRouter(tags=["farms"])
crops_router = APIRouter(tags=["crops"])
gis_router = APIRouter(prefix="/gis", tags=["gis"])


# --- Regions ---------------------------------------------------------------------

@regions_router.get("", response_model=list[RegionOut])
async def list_regions(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[RegionOut]:
    regions = await RegionService(session).list_regions(current.organization_id)
    return [RegionOut.model_validate(r) for r in regions]


@regions_router.post("", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
async def create_region(
    body: RegionCreate,
    current: CurrentUser = Depends(require_permission("regions:manage")),
    session: AsyncSession = Depends(get_db),
) -> RegionOut:
    region = await RegionService(session).create_region(body, current.organization_id, current.id)
    return RegionOut.model_validate(region)


@regions_router.patch("/{region_id}", response_model=RegionOut)
async def update_region(
    region_id: str,
    body: RegionUpdate,
    current: CurrentUser = Depends(require_permission("regions:manage")),
    session: AsyncSession = Depends(get_db),
) -> RegionOut:
    region = await RegionService(session).update_region(
        region_id, body, current.organization_id, current.id
    )
    return RegionOut.model_validate(region)


@regions_router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    region_id: str,
    current: CurrentUser = Depends(require_permission("regions:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await RegionService(session).delete_region(region_id, current.organization_id, current.id)


# --- Farmers ----------------------------------------------------------------------

def _farmer_out(farmer, include_pii: bool) -> FarmerOut:
    out = FarmerOut.model_validate(farmer)
    out.farm_count = len(farmer.farms) if farmer.farms is not None else 0
    out.pii_masked = not include_pii
    return out


@farmers_router.get("", response_model=Page[FarmerOut])
async def list_farmers(
    params: PageParams = Depends(page_params),
    search: str | None = Query(None, max_length=100),
    region_id: str | None = Query(None, alias="regionId"),
    current: CurrentUser = Depends(require_permission("farmers:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[FarmerOut]:
    include_pii = "farmers:read_pii" in current.permissions
    farmers, total = await FarmerService(session).list_farmers(
        current.organization_id, params, search, region_id, include_pii
    )
    return Page.build([_farmer_out(f, include_pii) for f in farmers], total, params)


@farmers_router.post("", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
async def create_farmer(
    body: FarmerCreate,
    current: CurrentUser = Depends(require_permission("farmers:create")),
    session: AsyncSession = Depends(get_db),
) -> FarmerOut:
    farmer = await FarmerService(session).create_farmer(body, current.organization_id, current.id)
    return _farmer_out(farmer, include_pii=True)


@farmers_router.get("/{farmer_id}", response_model=FarmerDetailOut)
async def get_farmer(
    farmer_id: str,
    current: CurrentUser = Depends(require_permission("farmers:read")),
    session: AsyncSession = Depends(get_db),
) -> FarmerDetailOut:
    include_pii = "farmers:read_pii" in current.permissions
    service = FarmerService(session)
    farmer = await service.get_farmer(
        farmer_id, current.organization_id, include_pii, current.id
    )
    records = await service.repo.list_production_records(farmer_id)
    out = FarmerDetailOut.model_validate(farmer)
    out.farm_count = len(farmer.farms)
    out.pii_masked = not include_pii
    out.production_records = [ProductionRecordOut.model_validate(r) for r in records]
    return out


@farmers_router.patch("/{farmer_id}", response_model=FarmerOut)
async def update_farmer(
    farmer_id: str,
    body: FarmerUpdate,
    current: CurrentUser = Depends(require_permission("farmers:update")),
    session: AsyncSession = Depends(get_db),
) -> FarmerOut:
    farmer = await FarmerService(session).update_farmer(
        farmer_id, body, current.organization_id, current.id
    )
    return _farmer_out(farmer, include_pii="farmers:read_pii" in current.permissions)


@farmers_router.delete("/{farmer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_farmer(
    farmer_id: str,
    current: CurrentUser = Depends(require_permission("farmers:delete")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await FarmerService(session).delete_farmer(farmer_id, current.organization_id, current.id)


@farmers_router.get("/{farmer_id}/production-records", response_model=list[ProductionRecordOut])
async def list_production_records(
    farmer_id: str,
    current: CurrentUser = Depends(require_permission("farmers:read")),
    session: AsyncSession = Depends(get_db),
) -> list[ProductionRecordOut]:
    records = await FarmerService(session).list_production_records(
        farmer_id, current.organization_id
    )
    return [ProductionRecordOut.model_validate(r) for r in records]


@farmers_router.post(
    "/{farmer_id}/production-records",
    response_model=ProductionRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_production_record(
    farmer_id: str,
    body: ProductionRecordCreate,
    current: CurrentUser = Depends(require_permission("farmers:update")),
    session: AsyncSession = Depends(get_db),
) -> ProductionRecordOut:
    record = await FarmerService(session).add_production_record(
        farmer_id, body, current.organization_id, current.id
    )
    return ProductionRecordOut.model_validate(record)


# --- Farms & fields ------------------------------------------------------------------

@farms_router.get("/farms", response_model=list[FarmOut])
async def list_farms(
    farmer_id: str | None = Query(None, alias="farmerId"),
    current: CurrentUser = Depends(require_permission("farms:read")),
    session: AsyncSession = Depends(get_db),
) -> list[FarmOut]:
    farms = await FarmService(session).list_farms(current.organization_id, farmer_id)
    return [FarmOut.model_validate(f) for f in farms]


@farms_router.post("/farms", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
async def create_farm(
    body: FarmCreate,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> FarmOut:
    farm = await FarmService(session).create_farm(body, current.organization_id, current.id)
    return FarmOut.model_validate(farm)


@farms_router.get("/farms/{farm_id}", response_model=FarmOut)
async def get_farm(
    farm_id: str,
    current: CurrentUser = Depends(require_permission("farms:read")),
    session: AsyncSession = Depends(get_db),
) -> FarmOut:
    farm = await FarmService(session).get_farm(farm_id, current.organization_id)
    return FarmOut.model_validate(farm)


@farms_router.patch("/farms/{farm_id}", response_model=FarmOut)
async def update_farm(
    farm_id: str,
    body: FarmUpdate,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> FarmOut:
    farm = await FarmService(session).update_farm(
        farm_id, body, current.organization_id, current.id
    )
    return FarmOut.model_validate(farm)


@farms_router.delete("/farms/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_farm(
    farm_id: str,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await FarmService(session).delete_farm(farm_id, current.organization_id, current.id)


@farms_router.post(
    "/farms/{farm_id}/fields", response_model=FieldOut, status_code=status.HTTP_201_CREATED
)
async def add_field(
    farm_id: str,
    body: FieldCreate,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> FieldOut:
    field = await FarmService(session).add_field(
        farm_id, body, current.organization_id, current.id
    )
    return FieldOut.model_validate(field)


@farms_router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(
    field_id: str,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await FarmService(session).delete_field(field_id, current.organization_id, current.id)


@farms_router.get("/fields/{field_id}/soil-samples", response_model=list[SoilSampleOut])
async def list_soil_samples(
    field_id: str,
    current: CurrentUser = Depends(require_permission("farms:read")),
    session: AsyncSession = Depends(get_db),
) -> list[SoilSampleOut]:
    samples = await FarmService(session).list_soil_samples(field_id, current.organization_id)
    return [SoilSampleOut.model_validate(s) for s in samples]


@farms_router.post(
    "/fields/{field_id}/soil-samples",
    response_model=SoilSampleOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_soil_sample(
    field_id: str,
    body: SoilSampleCreate,
    current: CurrentUser = Depends(require_permission("farms:manage")),
    session: AsyncSession = Depends(get_db),
) -> SoilSampleOut:
    sample = await FarmService(session).add_soil_sample(
        field_id, body, current.organization_id, current.id
    )
    return SoilSampleOut.model_validate(sample)


# --- Crop cycles ------------------------------------------------------------------------

@crops_router.get("/crop-cycles", response_model=Page[CropCycleOut])
async def list_crop_cycles(
    params: PageParams = Depends(page_params),
    cycle_status: str | None = Query(None, alias="status"),
    season: str | None = Query(None, max_length=40),
    field_id: str | None = Query(None, alias="fieldId"),
    current: CurrentUser = Depends(require_permission("crops:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[CropCycleOut]:
    cycles, total = await CropService(session).list_cycles(
        current.organization_id, params, cycle_status, season, field_id
    )
    return Page.build([CropCycleOut.model_validate(c) for c in cycles], total, params)


@crops_router.get("/crop-cycles/{cycle_id}", response_model=CropCycleOut)
async def get_crop_cycle(
    cycle_id: str,
    current: CurrentUser = Depends(require_permission("crops:read")),
    session: AsyncSession = Depends(get_db),
) -> CropCycleOut:
    cycle = await CropService(session).get_cycle(cycle_id, current.organization_id)
    return CropCycleOut.model_validate(cycle)


@crops_router.post(
    "/fields/{field_id}/crop-cycles",
    response_model=CropCycleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_crop_cycle(
    field_id: str,
    body: CropCycleCreate,
    current: CurrentUser = Depends(require_permission("crops:manage")),
    session: AsyncSession = Depends(get_db),
) -> CropCycleOut:
    cycle = await CropService(session).create_cycle(
        field_id, body, current.organization_id, current.id
    )
    return CropCycleOut.model_validate(cycle)


@crops_router.post("/crop-cycles/{cycle_id}/transitions", response_model=CropCycleOut)
async def transition_crop_cycle(
    cycle_id: str,
    body: CropCycleTransition,
    current: CurrentUser = Depends(require_permission("crops:manage")),
    session: AsyncSession = Depends(get_db),
) -> CropCycleOut:
    cycle = await CropService(session).transition(
        cycle_id, body, current.organization_id, current.id
    )
    return CropCycleOut.model_validate(cycle)


# --- GIS ------------------------------------------------------------------------------

@gis_router.get("/farms")
async def gis_farms(
    min_lat: float | None = Query(None, alias="minLat", ge=-90, le=90),
    min_lng: float | None = Query(None, alias="minLng", ge=-180, le=180),
    max_lat: float | None = Query(None, alias="maxLat", ge=-90, le=90),
    max_lng: float | None = Query(None, alias="maxLng", ge=-180, le=180),
    current: CurrentUser = Depends(require_permission("farms:read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Farm locations as a GeoJSON FeatureCollection for the map layer."""
    bbox = None
    if None not in (min_lat, min_lng, max_lat, max_lng):
        bbox = (min_lat, min_lng, max_lat, max_lng)
    farms = await FarmService(session).repo.list_farms(current.organization_id, bbox=bbox)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(f.longitude), float(f.latitude)],
                },
                "properties": {
                    "id": f.id,
                    "name": f.name,
                    "farmerId": f.farmer_id,
                    "farmerName": f.farmer.full_name if f.farmer else None,
                    "regionId": f.region_id,
                    "fieldCount": len(f.fields),
                    "totalAreaHa": float(f.total_area_ha) if f.total_area_ha else None,
                },
            }
            for f in farms
        ],
    }
