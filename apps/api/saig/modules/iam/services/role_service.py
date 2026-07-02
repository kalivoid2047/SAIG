from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import Permission, Role
from saig.modules.iam.repository import IamRepository
from saig.modules.iam.schemas import RoleCreate, RoleUpdate
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError


class RoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IamRepository(session)
        self.audit = AuditService(session)

    async def list_roles(self, organization_id: str) -> list[Role]:
        return await self.repo.list_roles(organization_id)

    async def list_permissions(self) -> list[Permission]:
        return await self.repo.list_permissions()

    async def create_role(
        self, data: RoleCreate, organization_id: str, actor_id: str
    ) -> Role:
        if await self.repo.get_role_by_name(data.name, organization_id) is not None:
            raise ConflictError("A role with this name already exists.")
        permissions = await self._resolve_permissions(data.permission_codes)
        role = Role(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            permissions=permissions,
        )
        self.session.add(role)
        await self.session.flush()
        self.audit.record(
            "roles.create",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="roles",
            entity_id=role.id,
            after={"name": role.name, "permissions": data.permission_codes},
        )
        await self.session.commit()
        return role

    async def update_role(
        self, role_id: str, data: RoleUpdate, organization_id: str, actor_id: str
    ) -> Role:
        role = await self._get_editable_role(role_id, organization_id)
        before = {"name": role.name,
                  "permissions": [p.code for p in role.permissions]}

        if data.name is not None and data.name != role.name:
            if await self.repo.get_role_by_name(data.name, organization_id) is not None:
                raise ConflictError("A role with this name already exists.")
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        if data.permission_codes is not None:
            role.permissions = await self._resolve_permissions(data.permission_codes)

        self.audit.record(
            "roles.update",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="roles",
            entity_id=role.id,
            before=before,
            after={"name": role.name, "permissions": [p.code for p in role.permissions]},
        )
        await self.session.commit()
        return role

    async def delete_role(self, role_id: str, organization_id: str, actor_id: str) -> None:
        role = await self._get_editable_role(role_id, organization_id)
        in_use = await self.repo.count_users_with_role(role.id)
        if in_use > 0:
            raise DomainError(f"Role is assigned to {in_use} user(s); unassign it first.")
        role.deleted_at = utcnow()
        self.audit.record(
            "roles.delete",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="roles",
            entity_id=role.id,
            before={"name": role.name},
        )
        await self.session.commit()

    async def _get_editable_role(self, role_id: str, organization_id: str) -> Role:
        role = await self.repo.get_role(role_id, organization_id)
        if role is None:
            raise NotFoundError("Role not found.")
        if role.is_system:
            raise DomainError("System roles cannot be modified.")
        return role

    async def _resolve_permissions(self, codes: list[str]) -> list[Permission]:
        permissions = await self.repo.get_permissions_by_codes(codes)
        if len(permissions) != len(set(codes)):
            raise DomainError("One or more permission codes are unknown.")
        return permissions
