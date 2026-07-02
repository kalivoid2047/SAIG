from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from saig.app import create_app
from saig.modules.iam.models import Organization, User
from saig.scripts.seed import sync_permissions, sync_system_roles
from saig.shared.config import Settings
from saig.shared.database import Base, create_engine_and_sessionmaker
from saig.shared.security import hash_password

ADMIN_EMAIL = "admin@example.com"
VIEWER_EMAIL = "viewer@example.com"
PASSWORD = "CorrectHorse9!"

# Hash once per run: Argon2id is intentionally slow, tests reuse one hash.
PASSWORD_HASH = hash_password(PASSWORD)


@dataclass
class TestContext:
    __test__ = False  # not a test case despite the name

    client: AsyncClient
    session_factory: object
    org_id: str
    org2_id: str
    admin_id: str
    viewer_id: str
    admin2_id: str

    async def login(self, email: str = ADMIN_EMAIL, password: str = PASSWORD) -> str:
        res = await self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert res.status_code == 200, res.text
        return res.json()["accessToken"]

    @staticmethod
    def auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def ctx(tmp_path) -> TestContext:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        jwt_secret="test-secret-0123456789-0123456789-0123456789",
        rate_limit_enabled=False,
        cookie_secure=False,
    )
    app = create_app(settings)
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # httpx's ASGITransport does not run lifespan; provide state directly.
    app.state.engine = engine
    app.state.session_factory = session_factory

    async with session_factory() as session:
        perms = await sync_permissions(session)

        org = Organization(name="Test Org", slug="test-org")
        org2 = Organization(name="Other Org", slug="other-org")
        session.add_all([org, org2])
        await session.flush()

        roles = await sync_system_roles(session, org, perms)
        roles2 = await sync_system_roles(session, org2, perms)

        admin = User(
            organization_id=org.id, email=ADMIN_EMAIL, password_hash=PASSWORD_HASH,
            full_name="Test Admin", roles=[roles["Administrator"]],
        )
        viewer = User(
            organization_id=org.id, email=VIEWER_EMAIL, password_hash=PASSWORD_HASH,
            full_name="Test Viewer", roles=[roles["Viewer"]],
        )
        admin2 = User(
            organization_id=org2.id, email="admin2@example.com", password_hash=PASSWORD_HASH,
            full_name="Other Admin", roles=[roles2["Administrator"]],
        )
        session.add_all([admin, viewer, admin2])
        await session.commit()
        org_id, org2_id = org.id, org2.id
        admin_id, viewer_id, admin2_id = admin.id, viewer.id, admin2.id

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    context = TestContext(
        client=client, session_factory=session_factory,
        org_id=org_id, org2_id=org2_id,
        admin_id=admin_id, viewer_id=viewer_id, admin2_id=admin2_id,
    )
    yield context
    await client.aclose()
    await engine.dispose()
