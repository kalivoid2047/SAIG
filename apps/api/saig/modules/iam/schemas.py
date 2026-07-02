from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=10, max_length=200, alias="newPassword")


class MessageResponse(BaseModel):
    message: str


# --- Users ---------------------------------------------------------------

class RoleSummary(ORMModel):
    id: str
    name: str


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str = Field(serialization_alias="fullName")
    organization_id: str = Field(serialization_alias="organizationId")
    department_id: str | None = Field(default=None, serialization_alias="departmentId")
    locale: str
    timezone: str
    is_active: bool = Field(serialization_alias="isActive")
    last_login_at: datetime | None = Field(default=None, serialization_alias="lastLoginAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    roles: list[RoleSummary]


class MeResponse(BaseModel):
    user: UserOut
    permissions: list[str]


class TokenResponse(BaseModel):
    accessToken: str
    expiresIn: int
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=1, max_length=200, alias="fullName")
    department_id: str | None = Field(default=None, alias="departmentId")
    role_ids: list[str] = Field(default_factory=list, alias="roleIds")


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200, alias="fullName")
    department_id: str | None = Field(default=None, alias="departmentId")
    role_ids: list[str] | None = Field(default=None, alias="roleIds")


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200, alias="fullName")
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=60)


# --- Roles ---------------------------------------------------------------

class PermissionOut(ORMModel):
    id: str
    code: str
    label: str


class RoleOut(ORMModel):
    id: str
    name: str
    description: str | None
    is_system: bool = Field(serialization_alias="isSystem")
    permissions: list[PermissionOut]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    permission_codes: list[str] = Field(default_factory=list, alias="permissionCodes")


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    permission_codes: list[str] | None = Field(default=None, alias="permissionCodes")


# --- Organization / departments -------------------------------------------

class OrganizationOut(ORMModel):
    id: str
    name: str
    slug: str
    settings: dict


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    settings: dict | None = None


class DepartmentOut(ORMModel):
    id: str
    name: str


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


# --- Audit ---------------------------------------------------------------

class AuditLogOut(ORMModel):
    id: int
    actor_id: str | None = Field(default=None, serialization_alias="actorId")
    action: str
    entity_table: str | None = Field(default=None, serialization_alias="entityTable")
    entity_id: str | None = Field(default=None, serialization_alias="entityId")
    before_data: dict | None = Field(default=None, serialization_alias="beforeData")
    after_data: dict | None = Field(default=None, serialization_alias="afterData")
    ip_address: str | None = Field(default=None, serialization_alias="ipAddress")
    request_id: str | None = Field(default=None, serialization_alias="requestId")
    occurred_at: datetime = Field(serialization_alias="occurredAt")
