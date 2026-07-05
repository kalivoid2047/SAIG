// API contract types — mirror apps/api/saig/modules/iam/schemas.py (camelCase wire format).

export interface RoleSummary {
  id: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  fullName: string;
  organizationId: string;
  departmentId: string | null;
  locale: string;
  timezone: string;
  isActive: boolean;
  lastLoginAt: string | null;
  createdAt: string;
  roles: RoleSummary[];
}

export interface Permission {
  id: string;
  code: string;
  label: string;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  isSystem: boolean;
  permissions: Permission[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
}

export interface Department {
  id: string;
  name: string;
}

export interface AuditLog {
  id: number;
  actorId: string | null;
  action: string;
  entityTable: string | null;
  entityId: string | null;
  beforeData: Record<string, unknown> | null;
  afterData: Record<string, unknown> | null;
  ipAddress: string | null;
  requestId: string | null;
  occurredAt: string;
}

export interface PageMeta {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface Page<T> {
  data: T[];
  meta: PageMeta;
}

// --- Phase 1: field operations & catalog ---------------------------------

export interface Region {
  id: string;
  name: string;
  code: string;
}

export interface Farmer {
  id: string;
  fullName: string;
  nationalId: string | null;
  phone: string | null;
  email: string | null;
  gender: string | null;
  birthYear: number | null;
  cooperative: string | null;
  regionId: string | null;
  consentGivenAt: string | null;
  createdAt: string;
  farmCount: number;
  piiMasked: boolean;
}

export interface ProductionRecord {
  id: string;
  season: string;
  varietyId: string | null;
  areaHa: number;
  yieldKg: number;
  source: string;
}

export interface FieldPlot {
  id: string;
  farmId: string;
  name: string;
  boundary: unknown | null;
  areaHa: number;
}

export interface Farm {
  id: string;
  farmerId: string;
  name: string;
  latitude: number;
  longitude: number;
  regionId: string | null;
  totalAreaHa: number | null;
  fields: FieldPlot[];
}

export interface FarmerDetail extends Farmer {
  farms: Farm[];
  productionRecords: ProductionRecord[];
}

export interface CropCycle {
  id: string;
  fieldId: string;
  varietyId: string;
  season: string;
  status: "planned" | "planted" | "growing" | "harvested" | "failed";
  plantedAt: string | null;
  expectedHarvestAt: string | null;
  actualHarvestAt: string | null;
  actualYieldKg: number | null;
  practices: Record<string, unknown>;
  createdAt: string;
}

export interface Suitability {
  regionId: string;
  score: number;
  rationale: string | null;
}

export interface Variety {
  id: string;
  crop: string;
  name: string;
  code: string;
  maturityDays: number | null;
  yieldPotentialKgHa: number | null;
  droughtTolerance: number | null;
  diseaseTolerance: number | null;
  characteristics: Record<string, unknown>;
  notes: string | null;
  isActive: boolean;
  createdAt: string;
  suitability: Suitability[];
}

export interface FarmFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: string;
    name: string;
    farmerId: string;
    farmerName: string | null;
    regionId: string | null;
    fieldCount: number;
    totalAreaHa: number | null;
  };
}

export interface FarmFeatureCollection {
  type: "FeatureCollection";
  features: FarmFeature[];
}

// --- Phase 2: weather, crop health, inventory, dashboard -----------------

export interface DailyWeather {
  day: string;
  rainfallMm: number | null;
  tempMinC: number | null;
  tempMaxC: number | null;
  humidityPct: number | null;
  windKmh: number | null;
}

export interface WeatherForecast {
  cellKey: string;
  latitude: number;
  longitude: number;
  source: string;
  issuedAt: string | null;
  stale: boolean;
  days: DailyWeather[];
}

export interface AgroIndicators {
  cellKey: string;
  windowDays: number;
  rainfall7dMm: number | null;
  rainfall30dMm: number | null;
  rainfall90dMm: number | null;
  growingDegreeDays: number | null;
  heatStressDays: number;
  dataPoints: number;
  asOf: string | null;
}

export interface Disease {
  id: string;
  name: string;
  crop: string;
  pathogenType: string | null;
  description: string | null;
  treatmentGuide: string | null;
}

export interface DiseaseReport {
  id: string;
  cropCycleId: string;
  diseaseId: string | null;
  reportedBy: string;
  severity: number;
  affectedPct: number;
  status: "reported" | "confirmed" | "treated" | "resolved" | "dismissed";
  latitude: number;
  longitude: number;
  notes: string | null;
  isOutbreak: boolean;
  reportedAt: string;
}

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  latitude: number;
  longitude: number;
  regionId: string | null;
  capacityKg: number | null;
}

export interface StockLot {
  id: string;
  varietyId: string;
  lotNumber: string;
  producedAt: string;
  expiresAt: string;
  germinationPct: number | null;
}

export interface StockBalance {
  warehouseId: string;
  lotId: string;
  varietyId: string;
  lotNumber: string;
  expiresAt: string;
  balanceKg: number;
  expiringSoon: boolean;
}

export interface StockTransfer {
  id: string;
  fromWarehouseId: string;
  toWarehouseId: string;
  lotId: string;
  quantityKg: number;
  receivedKg: number | null;
  status: "pending" | "dispatched" | "received" | "cancelled";
  varianceNote: string | null;
  createdAt: string;
}

export interface DashboardKpis {
  activeFarmers: number;
  activeCropCycles: number;
  harvestedCycles: number;
  seedVarieties: number;
  warehouses: number;
  totalStockKg: number;
  lotsExpiringSoon: number;
  openDiseaseReports: number;
  activeOutbreaks: number;
  pendingTransfers: number;
  openOrders: number;
  activeRoutes: number;
  projectedProductionKg: number;
  yieldPredictionCount: number;
  highRiskCount: number;
}

export interface Vehicle {
  id: string;
  registration: string;
  capacityKg: number;
  status: "available" | "on_route" | "maintenance" | "retired";
  driverId: string | null;
}

export interface OrderItem {
  id: string;
  varietyId: string;
  quantityKg: number;
  unitPrice: number | null;
}

export interface Order {
  id: string;
  customerName: string;
  regionId: string | null;
  destinationLat: number;
  destinationLng: number;
  status: "pending" | "confirmed" | "fulfilled" | "cancelled";
  requestedDate: string | null;
  createdAt: string;
  items: OrderItem[];
}

export interface RouteStop {
  id: string;
  orderId: string;
  stopSequence: number;
  eta: string | null;
}

export interface RoutePlan {
  id: string;
  originWarehouseId: string;
  vehicleId: string | null;
  driverId: string | null;
  status: "draft" | "planned" | "dispatched" | "completed" | "cancelled";
  plannedDate: string;
  totalDistanceKm: number | null;
  optimizerMeta: Record<string, unknown> | null;
  stops: RouteStop[];
}

export interface Delivery {
  id: string;
  orderId: string;
  routePlanId: string | null;
  status: "pending" | "assigned" | "in_transit" | "delivered" | "failed";
  deliveredAt: string | null;
  createdAt: string;
}

// --- Phase 3: predictions ----------------------------------------------------

export interface ModelVersion {
  id: string;
  modelName: string;
  version: string;
  status: "trained" | "evaluated" | "promoted" | "retired";
  metrics: Record<string, number>;
  trainingRows: number | null;
  promotedAt: string | null;
  createdAt: string;
}

export interface YieldPrediction {
  id: string;
  cropCycleId: string;
  predictedYieldKgHa: number;
  piLowKgHa: number;
  piHighKgHa: number;
  confidence: number;
  lowConfidence: boolean;
  createdAt: string;
}

export interface DemandForecastPoint {
  periodMonth: string;
  forecastQtyKg: number;
  piLowKg: number;
  piHighKg: number;
  confidence: number;
  seasonalComponent: number | null;
}

export interface DemandSeries {
  regionId: string;
  varietyId: string;
  modelVersion: string;
  points: DemandForecastPoint[];
}

export interface JobResult {
  status: string;
  detail: string;
  count: number;
}

export interface RiskFactor {
  factor: string;
  weight: number;
  value: number;
  contribution: number;
}

export interface RiskDomain {
  domain: string;
  score: number;
  band: "low" | "medium" | "high";
  previousScore: number | null;
  trend: number;
  factors: RiskFactor[];
}

export interface RiskBoard {
  assessedDate: string | null;
  domains: RiskDomain[];
  highRiskCount: number;
}

export interface RiskHistoryPoint {
  assessedDate: string;
  score: number;
}

export interface RouteFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "LineString"; coordinates: [number, number][] };
    properties: { id: string; status: string; stops: number; distanceKm: number };
  }[];
}

export interface DiseaseFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      id: string;
      severity: number;
      status: string;
      isOutbreak: boolean;
      affectedPct: number;
    };
  }[];
}

export interface TokenResponse {
  accessToken: string;
  expiresIn: number;
  user: User;
}

export interface MeResponse {
  user: User;
  permissions: string[];
}
