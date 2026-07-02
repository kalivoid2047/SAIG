from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import (
    REFRESH_COOKIE,
    CurrentUser,
    client_ip,
    get_current_user,
    get_db,
)
from saig.modules.iam.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from saig.modules.iam.services.auth_service import AuthService
from saig.shared.config import Settings, get_settings
from saig.shared.errors import UnauthorizedError
from saig.shared.ratelimit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw: str, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("login", times=5, seconds=900))],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    service = AuthService(session, settings)
    access, raw_refresh, user = await service.login(
        body.email, body.password, client_ip(request), request.headers.get("user-agent")
    )
    _set_refresh_cookie(response, raw_refresh, settings)
    return TokenResponse(
        accessToken=access,
        expiresIn=settings.access_token_ttl_seconds,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("refresh", times=10, seconds=60))],
)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise UnauthorizedError("No refresh token.")
    service = AuthService(session, settings)
    access, raw_new, user = await service.refresh(
        raw, client_ip(request), request.headers.get("user-agent")
    )
    _set_refresh_cookie(response, raw_new, settings)
    return TokenResponse(
        accessToken=access,
        expiresIn=settings.access_token_ttl_seconds,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    service = AuthService(session, settings)
    await service.logout(request.cookies.get(REFRESH_COOKIE))
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=MeResponse)
async def me(current: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(current.user),
        permissions=sorted(current.permissions),
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot", times=5, seconds=900))],
)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    await AuthService(session, settings).forgot_password(body.email)
    return MessageResponse(message="If the account exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    await AuthService(session, settings).reset_password(body.token, body.new_password)
    return MessageResponse(message="Password updated. Please sign in.")
