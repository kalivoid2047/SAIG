from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import (
    AuditLog,
    Department,
    Organization,
    PasswordResetToken,
    Permission,
    RefreshToken,
    Role,
    User,
)
from saig.shared.database import utcnow
from saig.shared.pagination import PageParams


class IamRepository:
    """Persistence adapter for the IAM bounded context.

    Every user/role/department accessor is organization-scoped: tenant
    isolation lives here, not in callers (security architecture §2.2).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- users -----------------------------------------------------------

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_user(self, user_id: str, organization_id: str) -> User | None:
        stmt = select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
            User.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_users(
        self, organization_id: str, params: PageParams, search: str | None = None
    ) -> tuple[list[User], int]:
        conditions = [User.organization_id == organization_id, User.deleted_at.is_(None)]
        if search:
            like = f"%{search.lower()}%"
            conditions.append(
                or_(func.lower(User.full_name).like(like), User.email.like(like))
            )
        count = (
            await self.session.execute(select(func.count(User.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        users = list((await self.session.execute(stmt)).scalars().all())
        return users, count

    # --- roles / permissions ----------------------------------------------

    async def get_role(self, role_id: str, organization_id: str) -> Role | None:
        stmt = select(Role).where(
            Role.id == role_id,
            Role.organization_id == organization_id,
            Role.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_roles_by_ids(self, role_ids: list[str], organization_id: str) -> list[Role]:
        if not role_ids:
            return []
        stmt = select(Role).where(
            Role.id.in_(role_ids),
            Role.organization_id == organization_id,
            Role.deleted_at.is_(None),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_roles(self, organization_id: str) -> list[Role]:
        stmt = (
            select(Role)
            .where(Role.organization_id == organization_id, Role.deleted_at.is_(None))
            .order_by(Role.is_system.desc(), Role.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_role_by_name(self, name: str, organization_id: str) -> Role | None:
        stmt = select(Role).where(
            Role.organization_id == organization_id,
            Role.name == name,
            Role.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_permissions(self) -> list[Permission]:
        return list(
            (await self.session.execute(select(Permission).order_by(Permission.code)))
            .scalars()
            .all()
        )

    async def get_permissions_by_codes(self, codes: list[str]) -> list[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_users_with_role(self, role_id: str) -> int:
        from saig.modules.iam.models import user_roles

        stmt = select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role_id)
        return (await self.session.execute(stmt)).scalar_one()

    # --- refresh tokens -----------------------------------------------------

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke_family(self, family_id: str) -> None:
        stmt = select(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
        for token in (await self.session.execute(stmt)).scalars():
            token.revoked_at = utcnow()

    async def revoke_all_for_user(self, user_id: str) -> None:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
        for token in (await self.session.execute(stmt)).scalars():
            token.revoked_at = utcnow()

    # --- password reset -------------------------------------------------------

    async def get_reset_token(self, token_hash: str) -> PasswordResetToken | None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- organization / departments -------------------------------------------

    async def get_organization(self, organization_id: str) -> Organization | None:
        stmt = select(Organization).where(
            Organization.id == organization_id, Organization.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_departments(self, organization_id: str) -> list[Department]:
        stmt = (
            select(Department)
            .where(
                Department.organization_id == organization_id,
                Department.deleted_at.is_(None),
            )
            .order_by(Department.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_department(self, department_id: str, organization_id: str) -> Department | None:
        stmt = select(Department).where(
            Department.id == department_id,
            Department.organization_id == organization_id,
            Department.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- audit -------------------------------------------------------------

    async def list_audit_logs(
        self,
        organization_id: str,
        params: PageParams,
        action: str | None = None,
        actor_id: str | None = None,
        entity_table: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        conditions = [AuditLog.organization_id == organization_id]
        if action:
            conditions.append(AuditLog.action == action)
        if actor_id:
            conditions.append(AuditLog.actor_id == actor_id)
        if entity_table:
            conditions.append(AuditLog.entity_table == entity_table)
        count = (
            await self.session.execute(select(func.count(AuditLog.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        logs = list((await self.session.execute(stmt)).scalars().all())
        return logs, count
