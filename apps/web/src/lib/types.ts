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

export interface TokenResponse {
  accessToken: string;
  expiresIn: number;
  user: User;
}

export interface MeResponse {
  user: User;
  permissions: string[];
}
