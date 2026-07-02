from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_current_user, get_db, require_permission
from saig.modules.iam.schemas import ProfileUpdate, UserCreate, UserOut, UserUpdate
from saig.modules.iam.services.user_service import UserService
from saig.shared.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    params: PageParams = Depends(page_params),
    search: str | None = Query(None, max_length=100),
    current: CurrentUser = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[UserOut]:
    users, total = await UserService(session).list_users(
        current.organization_id, params, search
    )
    return Page.build([UserOut.model_validate(u) for u in users], total, params)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current: CurrentUser = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).create_user(body, current.organization_id, current.id)
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_profile(
    body: ProfileUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).update_profile(current.user, body)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).get_user(user_id, current.organization_id)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdate,
    current: CurrentUser = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).update_user(
        user_id, body, current.organization_id, current.id
    )
    return UserOut.model_validate(user)


@router.post("/{user_id}/activate", response_model=UserOut)
async def activate_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).set_active(
        user_id, True, current.organization_id, current.id
    )
    return UserOut.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await UserService(session).set_active(
        user_id, False, current.organization_id, current.id
    )
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await UserService(session).delete_user(user_id, current.organization_id, current.id)
