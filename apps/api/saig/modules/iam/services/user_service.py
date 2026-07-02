from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import User
from saig.modules.iam.repository import IamRepository
from saig.modules.iam.schemas import ProfileUpdate, UserCreate, UserUpdate
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError
from saig.shared.pagination import PageParams
from saig.shared.security import hash_password


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IamRepository(session)
        self.audit = AuditService(session)

    async def list_users(
        self, organization_id: str, params: PageParams, search: str | None
    ) -> tuple[list[User], int]:
        return await self.repo.list_users(organization_id, params, search)

    async def get_user(self, user_id: str, organization_id: str) -> User:
        user = await self.repo.get_user(user_id, organization_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def create_user(
        self, data: UserCreate, organization_id: str, actor_id: str
    ) -> User:
        email = data.email.lower()
        if await self.repo.get_user_by_email(email) is not None:
            raise ConflictError("A user with this email already exists.")
        if data.department_id is not None:
            if await self.repo.get_department(data.department_id, organization_id) is None:
                raise NotFoundError("Department not found.")

        roles = await self.repo.get_roles_by_ids(data.role_ids, organization_id)
        if len(roles) != len(set(data.role_ids)):
            raise DomainError("One or more roles do not exist in this organization.")

        user = User(
            organization_id=organization_id,
            department_id=data.department_id,
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            roles=roles,
        )
        self.session.add(user)
        await self.session.flush()
        self.audit.record(
            "users.create",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="users",
            entity_id=user.id,
            after={"email": email, "full_name": data.full_name,
                   "roles": [r.name for r in roles]},
        )
        await self.session.commit()
        return user

    async def update_user(
        self, user_id: str, data: UserUpdate, organization_id: str, actor_id: str
    ) -> User:
        user = await self.get_user(user_id, organization_id)
        before = {"full_name": user.full_name, "department_id": user.department_id,
                  "roles": [r.name for r in user.roles]}

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.department_id is not None:
            if await self.repo.get_department(data.department_id, organization_id) is None:
                raise NotFoundError("Department not found.")
            user.department_id = data.department_id
        if data.role_ids is not None:
            roles = await self.repo.get_roles_by_ids(data.role_ids, organization_id)
            if len(roles) != len(set(data.role_ids)):
                raise DomainError("One or more roles do not exist in this organization.")
            user.roles = roles

        self.audit.record(
            "users.update",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="users",
            entity_id=user.id,
            before=before,
            after={"full_name": user.full_name, "department_id": user.department_id,
                   "roles": [r.name for r in user.roles]},
        )
        await self.session.commit()
        return user

    async def update_profile(self, user: User, data: ProfileUpdate) -> User:
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.locale is not None:
            user.locale = data.locale
        if data.timezone is not None:
            user.timezone = data.timezone
        await self.session.commit()
        return user

    async def set_active(
        self, user_id: str, active: bool, organization_id: str, actor_id: str
    ) -> User:
        user = await self.get_user(user_id, organization_id)
        if user.id == actor_id and not active:
            raise DomainError("You cannot deactivate your own account.")
        user.is_active = active
        if not active:
            # FR-USER-2: deactivation kills sessions.
            await self.repo.revoke_all_for_user(user.id)
        self.audit.record(
            "users.deactivate" if not active else "users.activate",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="users",
            entity_id=user.id,
        )
        await self.session.commit()
        return user

    async def delete_user(self, user_id: str, organization_id: str, actor_id: str) -> None:
        user = await self.get_user(user_id, organization_id)
        if user.id == actor_id:
            raise DomainError("You cannot delete your own account.")
        user.deleted_at = utcnow()
        user.is_active = False
        await self.repo.revoke_all_for_user(user.id)
        self.audit.record(
            "users.delete",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="users",
            entity_id=user.id,
            before={"email": user.email, "full_name": user.full_name},
        )
        await self.session.commit()
