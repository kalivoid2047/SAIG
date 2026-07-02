from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import Department, Organization
from saig.modules.iam.repository import IamRepository
from saig.modules.iam.schemas import DepartmentCreate, OrganizationUpdate
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, NotFoundError


class OrgService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IamRepository(session)
        self.audit = AuditService(session)

    async def get_organization(self, organization_id: str) -> Organization:
        org = await self.repo.get_organization(organization_id)
        if org is None:
            raise NotFoundError("Organization not found.")
        return org

    async def update_organization(
        self, organization_id: str, data: OrganizationUpdate, actor_id: str
    ) -> Organization:
        org = await self.get_organization(organization_id)
        before = {"name": org.name, "settings": org.settings}
        if data.name is not None:
            org.name = data.name
        if data.settings is not None:
            org.settings = data.settings
        self.audit.record(
            "org.update",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="organizations",
            entity_id=org.id,
            before=before,
            after={"name": org.name, "settings": org.settings},
        )
        await self.session.commit()
        return org

    async def list_departments(self, organization_id: str) -> list[Department]:
        return await self.repo.list_departments(organization_id)

    async def create_department(
        self, data: DepartmentCreate, organization_id: str, actor_id: str
    ) -> Department:
        existing = await self.repo.list_departments(organization_id)
        if any(d.name.lower() == data.name.lower() for d in existing):
            raise ConflictError("A department with this name already exists.")
        dept = Department(organization_id=organization_id, name=data.name)
        self.session.add(dept)
        await self.session.flush()
        self.audit.record(
            "departments.create",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="departments",
            entity_id=dept.id,
            after={"name": dept.name},
        )
        await self.session.commit()
        return dept

    async def delete_department(
        self, department_id: str, organization_id: str, actor_id: str
    ) -> None:
        dept = await self.repo.get_department(department_id, organization_id)
        if dept is None:
            raise NotFoundError("Department not found.")
        dept.deleted_at = utcnow()
        self.audit.record(
            "departments.delete",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="departments",
            entity_id=dept.id,
            before={"name": dept.name},
        )
        await self.session.commit()
