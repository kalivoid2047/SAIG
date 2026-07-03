from tests.conftest import VIEWER_EMAIL, TestContext

VARIETIES = "/api/v1/varieties"


async def test_variety_crud_and_duplicate_code(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        VARIETIES, headers=ctx.auth(token),
        json={"crop": "maize", "name": "Pioneer 401", "code": "mz-401",
              "maturityDays": 120, "yieldPotentialKgHa": 6500,
              "droughtTolerance": 2, "diseaseTolerance": 4},
    )
    assert res.status_code == 201, res.text
    variety = res.json()
    assert variety["code"] == "MZ-401"  # normalized uppercase

    res = await ctx.client.post(
        VARIETIES, headers=ctx.auth(token),
        json={"crop": "maize", "name": "Dup", "code": "MZ-401"},
    )
    assert res.status_code == 409

    res = await ctx.client.patch(
        f"{VARIETIES}/{variety['id']}", headers=ctx.auth(token),
        json={"droughtTolerance": 3, "isActive": False},
    )
    assert res.status_code == 200
    assert res.json()["droughtTolerance"] == 3

    # inactive varieties are hidden by default, shown on request
    res = await ctx.client.get(VARIETIES, headers=ctx.auth(token))
    assert res.json() == []
    res = await ctx.client.get(
        VARIETIES, headers=ctx.auth(token), params={"includeInactive": True}
    )
    assert len(res.json()) == 1


async def test_viewer_reads_but_cannot_manage(ctx: TestContext):
    admin_token = await ctx.login()
    await ctx.client.post(
        VARIETIES, headers=ctx.auth(admin_token),
        json={"crop": "wheat", "name": "Highland", "code": "WH-201"},
    )
    viewer_token = await ctx.login(VIEWER_EMAIL)
    res = await ctx.client.get(VARIETIES, headers=ctx.auth(viewer_token))
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = await ctx.client.post(
        VARIETIES, headers=ctx.auth(viewer_token),
        json={"crop": "x", "name": "x", "code": "X1"},
    )
    assert res.status_code == 403


async def test_suitability_matrix(ctx: TestContext):
    token = await ctx.login()
    region = (await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": "Eastern", "code": "EAST"}
    )).json()
    variety = (await ctx.client.post(
        VARIETIES, headers=ctx.auth(token),
        json={"crop": "maize", "name": "V", "code": "V-1"},
    )).json()

    res = await ctx.client.put(
        f"{VARIETIES}/{variety['id']}/suitability", headers=ctx.auth(token),
        json=[{"regionId": region["id"], "score": 4, "rationale": "Good rainfall match"}],
    )
    assert res.status_code == 200
    assert res.json()["suitability"][0]["score"] == 4

    # unknown region rejected
    res = await ctx.client.put(
        f"{VARIETIES}/{variety['id']}/suitability", headers=ctx.auth(token),
        json=[{"regionId": "00000000-0000-0000-0000-000000000000", "score": 3}],
    )
    assert res.status_code == 404

    # replace semantics: empty list clears the matrix
    res = await ctx.client.put(
        f"{VARIETIES}/{variety['id']}/suitability", headers=ctx.auth(token), json=[]
    )
    assert res.status_code == 200
    assert res.json()["suitability"] == []
