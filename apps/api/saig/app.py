from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saig import __version__
from saig.modules.iam.deps import get_db
from saig.modules.iam.routes import audit, auth, orgs, roles, users
from saig.shared.config import Settings, get_settings
from saig.shared.database import create_engine_and_sessionmaker
from saig.shared.errors import register_error_handlers
from saig.shared.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = session_factory
        yield
        await engine.dispose()

    app = FastAPI(
        title="SAIG API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
    )

    # Make the chosen settings visible to dependencies (tests override this).
    app.dependency_overrides[get_settings] = lambda: settings

    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.cookie_secure)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["authorization", "content-type", "x-request-id"],
    )

    register_error_handlers(app)

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(roles.router, prefix=API_PREFIX)
    app.include_router(orgs.router, prefix=API_PREFIX)
    app.include_router(audit.router, prefix=API_PREFIX)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    async def ready(session: AsyncSession = Depends(get_db)) -> dict:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    return app
