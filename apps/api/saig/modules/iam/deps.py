from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import User
from saig.shared.config import Settings, get_settings
from saig.shared.errors import ForbiddenError, UnauthorizedError
from saig.shared.security import decode_access_token

REFRESH_COOKIE = "saig_refresh"


async def get_db(request: Request) -> AsyncSession:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


@dataclass(frozen=True)
class CurrentUser:
    user: User
    permissions: frozenset[str]

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def organization_id(self) -> str:
        return self.user.organization_id


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise UnauthorizedError("Missing bearer token.")
    payload = decode_access_token(auth.removeprefix("Bearer ").strip(), settings)

    user = await session.get(User, payload["sub"])
    if user is None or user.deleted_at is not None or not user.is_active:
        raise UnauthorizedError("Account unavailable.")

    # Permissions resolved per request (roles → permissions), so role changes
    # take effect without re-login (FR-USER-4). `selectin` loading keeps this
    # to two indexed queries.
    permissions = frozenset(p.code for role in user.roles for p in role.permissions)
    return CurrentUser(user=user, permissions=permissions)


def require_permission(code: str):
    async def dependency(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in current.permissions:
            raise ForbiddenError(f"Requires permission '{code}'.")
        return current

    return dependency


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
