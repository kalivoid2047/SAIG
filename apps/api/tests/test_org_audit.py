from tests.conftest import TestContext


async def test_department_lifecycle(ctx: TestContext):
    token = await ctx.login()

    res = await ctx.client.post(
        "/api/v1/departments", headers=ctx.auth(token), json={"name": "Agronomy"}
    )
    assert res.status_code == 201
    dept_id = res.json()["id"]

    # duplicate (case-insensitive) is rejected
    res = await ctx.client.post(
        "/api/v1/departments", headers=ctx.auth(token), json={"name": "agronomy"}
    )
    assert res.status_code == 409

    res = await ctx.client.get("/api/v1/departments", headers=ctx.auth(token))
    assert [d["name"] for d in res.json()] == ["Agronomy"]

    res = await ctx.client.delete(
        f"/api/v1/departments/{dept_id}", headers=ctx.auth(token)
    )
    assert res.status_code == 204
    res = await ctx.client.get("/api/v1/departments", headers=ctx.auth(token))
    assert res.json() == []


async def test_organization_update_requires_permission(ctx: TestContext):
    viewer_token = await ctx.login("viewer@example.com")
    res = await ctx.client.patch(
        "/api/v1/organization", headers=ctx.auth(viewer_token), json={"name": "Hacked"}
    )
    assert res.status_code == 403

    admin_token = await ctx.login()
    res = await ctx.client.patch(
        "/api/v1/organization", headers=ctx.auth(admin_token), json={"name": "SeedCo East"}
    )
    assert res.status_code == 200
    assert res.json()["name"] == "SeedCo East"


async def test_audit_trail_records_actions(ctx: TestContext):
    token = await ctx.login()
    await ctx.client.post(
        "/api/v1/users",
        headers=ctx.auth(token),
        json={"email": "audited@example.com", "password": "ValidPass123!",
              "fullName": "Audited User"},
    )

    res = await ctx.client.get("/api/v1/audit-logs", headers=ctx.auth(token))
    assert res.status_code == 200
    actions = [entry["action"] for entry in res.json()["data"]]
    assert "auth.login" in actions
    assert "users.create" in actions

    created = next(e for e in res.json()["data"] if e["action"] == "users.create")
    assert created["afterData"]["email"] == "audited@example.com"
    # secrets never reach the audit trail
    assert "password" not in (created["afterData"] or {})
    assert created["requestId"]


async def test_health_endpoints(ctx: TestContext):
    assert (await ctx.client.get("/health/live")).status_code == 200
    res = await ctx.client.get("/health/ready")
    assert res.status_code == 200
    assert res.json()["database"] == "ok"
