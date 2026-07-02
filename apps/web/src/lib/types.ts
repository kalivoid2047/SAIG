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

export interface TokenResponse {
  accessToken: string;
  expiresIn: number;
  user: User;
}

export interface MeResponse {
  user: User;
  permissions: string[];
}
