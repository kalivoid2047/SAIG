from datetime import timedelta

from sqlalchemy import select

from saig.modules.iam.models import PasswordResetToken, RefreshToken
from saig.shared.database import utcnow
from saig.shared.security import new_opaque_token
from tests.conftest import ADMIN_EMAIL, PASSWORD, TestContext

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
COOKIE = "saig_refresh"


async def test_login_success_sets_tokens(ctx: TestContext):
    res = await ctx.client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["accessToken"]
    assert body["user"]["email"] == ADMIN_EMAIL
    assert COOKIE in res.cookies
    # security headers present
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "x-request-id" in res.headers


async def test_login_wrong_password_is_generic_401(ctx: TestContext):
    res = await ctx.client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": "wrong-pass-1"})
    assert res.status_code == 401
    assert res.headers["content-type"].startswith("application/problem+json")
    assert "Invalid email or password" in res.json()["detail"]


async def test_unknown_email_same_error_as_wrong_password(ctx: TestContext):
    res = await ctx.client.post(LOGIN, json={"email": "ghost@example.com", "password": "x" * 12})
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


async def test_lockout_after_five_failures(ctx: TestContext):
    for _ in range(5):
        res = await ctx.client.post(
            LOGIN, json={"email": ADMIN_EMAIL, "password": "wrong-pass-1"}
        )
        assert res.status_code == 401
    # even the correct password is rejected while locked
    res = await ctx.client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert res.status_code == 423


async def test_refresh_rotates_and_detects_reuse(ctx: TestContext):
    await ctx.login()
    first_cookie = ctx.client.cookies[COOKIE]

    res = await ctx.client.post(REFRESH)
    assert res.status_code == 200
    second_cookie = ctx.client.cookies[COOKIE]
    assert second_cookie != first_cookie

    # Replay the rotated (stolen) token → reuse detection
    ctx.client.cookies.set(COOKIE, first_cookie, path="/api/v1/auth")
    res = await ctx.client.post(REFRESH)
    assert res.status_code == 401

    # The whole family is revoked, so the newest token is dead too
    ctx.client.cookies.set(COOKIE, second_cookie, path="/api/v1/auth")
    res = await ctx.client.post(REFRESH)
    assert res.status_code == 401


async def test_me_returns_permissions(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.get("/api/v1/auth/me", headers=ctx.auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert "users:manage" in body["permissions"]


async def test_me_without_token_is_401(ctx: TestContext):
    res = await ctx.client.get("/api/v1/auth/me")
    assert res.status_code == 401


async def test_logout_revokes_refresh(ctx: TestContext):
    await ctx.login()
    res = await ctx.client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    res = await ctx.client.post(REFRESH)
    assert res.status_code == 401


async def test_forgot_password_never_enumerates(ctx: TestContext):
    known = await ctx.client.post(
        "/api/v1/auth/forgot-password", json={"email": ADMIN_EMAIL}
    )
    unknown = await ctx.client.post(
        "/api/v1/auth/forgot-password", json={"email": "ghost@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


async def test_reset_password_flow_kills_sessions(ctx: TestContext):
    await ctx.login()  # establish a refresh session

    raw, token_hash = new_opaque_token()
    async with ctx.session_factory() as session:
        session.add(
            PasswordResetToken(
                user_id=ctx.admin_id,
                token_hash=token_hash,
                expires_at=utcnow() + timedelta(minutes=30),
            )
        )
        await session.commit()

    new_password = "BrandNewPass42!"
    res = await ctx.client.post(
        "/api/v1/auth/reset-password", json={"token": raw, "newPassword": new_password}
    )
    assert res.status_code == 200

    # Old sessions are revoked
    async with ctx.session_factory() as session:
        tokens = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == ctx.admin_id)
            )
        ).scalars().all()
        assert tokens and all(t.revoked_at is not None for t in tokens)

    # Token is single-use
    res = await ctx.client.post(
        "/api/v1/auth/reset-password", json={"token": raw, "newPassword": "AnotherPass42!"}
    )
    assert res.status_code == 401

    # New password works, old one doesn't
    assert (
        await ctx.client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": PASSWORD})
    ).status_code == 401
    assert (
        await ctx.client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": new_password})
    ).status_code == 200
