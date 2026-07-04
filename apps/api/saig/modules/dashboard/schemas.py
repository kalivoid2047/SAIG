from pydantic import BaseModel


class DashboardKpis(BaseModel):
    activeFarmers: int
    activeCropCycles: int
    harvestedCycles: int
    seedVarieties: int
    warehouses: int
    totalStockKg: float
    lotsExpiringSoon: int
    openDiseaseReports: int
    activeOutbreaks: int
    pendingTransfers: int
    openOrders: int
    activeRoutes: int
