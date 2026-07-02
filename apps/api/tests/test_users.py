from tests.conftest import PASSWORD, TestContext

USERS = "/api/v1/users"


async def test_create_get_update_delete_user(ctx: TestContext):
    token = await ctx.login()

    res = await ctx.client.post(
        USERS,
        headers=ctx.auth(token),
        json={"email": "Field.Officer@example.com", "password": "ValidPass123!",
              "fullName": "Field Officer"},
    )
    assert res.status_code == 201
    created = res.json()
    assert created["email"] == "field.officer@example.com"  # normalized lowercase
    user_id = created["id"]

    res = await ctx.client.get(f"{USERS}/{user_id}", headers=ctx.auth(token))
    assert res.status_code == 200

    res = await ctx.client.patch(
        f"{USERS}/{user_id}", headers=ctx.auth(token), json={"fullName": "Renamed Officer"}
    )
    assert res.status_code == 200
    assert res.json()["fullName"] == "Renamed Officer"

    res = await ctx.client.delete(f"{USERS}/{user_id}", headers=ctx.auth(token))
    assert res.status_code == 204

    res = await ctx.client.get(f"{USERS}/{user_id}", headers=ctx.auth(token))
    assert res.status_code == 404


async def test_duplicate_email_conflict(ctx: TestContext):
    token = await ctx.login()
    payload = {"email": "dup@example.com", "password": "ValidPass123!", "fullName": "Dup"}
    assert (
        await ctx.client.post(USERS, headers=ctx.auth(token), json=payload)
    ).status_code == 201
    res = await ctx.client.post(USERS, headers=ctx.auth(token), json=payload)
    assert res.status_code == 409


async def test_weak_password_rejected_by_validation(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        USERS,
        headers=ctx.auth(token),
        json={"email": "weak@example.com", "password": "short", "fullName": "Weak"},
    )
    assert res.status_code == 422
    assert any(e["path"] == "password" for e in res.json()["errors"])


async def test_cannot_deactivate_or_delete_self(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        f"{USERS}/{ctx.admin_id}/deactivate", headers=ctx.auth(token)
    )
    assert res.status_code == 422
    res = await ctx.client.delete(f"{USERS}/{ctx.admin_id}", headers=ctx.auth(token))
    assert res.status_code == 422


async def test_deactivation_kills_existing_access_token(ctx: TestContext):
    admin_token = await ctx.login()
    viewer_token = await ctx.login("viewer@example.com")

    res = await ctx.client.post(
        f"{USERS}/{ctx.viewer_id}/deactivate", headers=ctx.auth(admin_token)
    )
    assert res.status_code == 200

    # The still-unexpired JWT no longer grants access
    res = await ctx.client.get("/api/v1/auth/me", headers=ctx.auth(viewer_token))
    assert res.status_code == 401

    # And the viewer cannot sign in again
    res = await ctx.client.post(
        "/api/v1/auth/login", json={"email": "viewer@example.com", "password": PASSWORD}
    )
    assert res.status_code == 401


async def test_profile_self_service(ctx: TestContext):
    token = await ctx.login("viewer@example.com")
    res = await ctx.client.patch(
        f"{USERS}/me",
        headers=ctx.auth(token),
        json={"fullName": "Viewer Renamed", "timezone": "Africa/Nairobi"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["fullName"] == "Viewer Renamed"
    assert body["timezone"] == "Africa/Nairobi"


async def test_pagination_and_search(ctx: TestContext):
    token = await ctx.login()
    for i in range(3):
        await ctx.client.post(
            USERS,
            headers=ctx.auth(token),
            json={"email": f"page{i}@example.com", "password": "ValidPass123!",
                  "fullName": f"Paged User {i}"},
        )
    res = await ctx.client.get(
        USERS, headers=ctx.auth(token), params={"page": 1, "pageSize": 2, "search": "paged"}
    )
    body = res.json()
    assert body["meta"]["totalItems"] == 3
    assert body["meta"]["totalPages"] == 2
    assert len(body["data"]) == 2
