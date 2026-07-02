from tests.conftest import VIEWER_EMAIL, TestContext

USERS = "/api/v1/users"


async def test_viewer_can_read_but_not_manage(ctx: TestContext):
    token = await ctx.login(VIEWER_EMAIL)

    res = await ctx.client.get(USERS, headers=ctx.auth(token))
    assert res.status_code == 200

    res = await ctx.client.post(
        USERS,
        headers=ctx.auth(token),
        json={"email": "new@example.com", "password": "ValidPass123!", "fullName": "New"},
    )
    assert res.status_code == 403
    assert res.json()["type"].endswith("/forbidden")


async def test_viewer_cannot_read_audit_logs(ctx: TestContext):
    token = await ctx.login(VIEWER_EMAIL)
    res = await ctx.client.get("/api/v1/audit-logs", headers=ctx.auth(token))
    assert res.status_code == 403


async def test_role_change_takes_effect_without_new_login(ctx: TestContext):
    admin_token = await ctx.login()
    viewer_token = await ctx.login(VIEWER_EMAIL)

    # Viewer starts without manage rights
    res = await ctx.client.post(
        USERS,
        headers=ctx.auth(viewer_token),
        json={"email": "x1@example.com", "password": "ValidPass123!", "fullName": "X"},
    )
    assert res.status_code == 403

    # Admin grants the Administrator role to the viewer
    roles = (await ctx.client.get("/api/v1/roles", headers=ctx.auth(admin_token))).json()
    admin_role_id = next(r["id"] for r in roles if r["name"] == "Administrator")
    res = await ctx.client.patch(
        f"{USERS}/{ctx.viewer_id}",
        headers=ctx.auth(admin_token),
        json={"roleIds": [admin_role_id]},
    )
    assert res.status_code == 200

    # Same (still valid) access token now carries the new permission
    res = await ctx.client.post(
        USERS,
        headers=ctx.auth(viewer_token),
        json={"email": "x2@example.com", "password": "ValidPass123!", "fullName": "X2"},
    )
    assert res.status_code == 201


async def test_org_isolation_returns_404_not_403(ctx: TestContext):
    other_admin_token = await ctx.login("admin2@example.com")
    # Cross-org lookup must not leak existence
    res = await ctx.client.get(f"{USERS}/{ctx.viewer_id}", headers=ctx.auth(other_admin_token))
    assert res.status_code == 404

    # And the listing only contains own-org users
    res = await ctx.client.get(USERS, headers=ctx.auth(other_admin_token))
    emails = [u["email"] for u in res.json()["data"]]
    assert VIEWER_EMAIL not in emails
    assert emails == ["admin2@example.com"]
