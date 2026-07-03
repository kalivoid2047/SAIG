from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-do-not-use-in-production"  # noqa: S105

# apps/api — anchor for the default dev database so it does not depend on
# the process working directory (uvicorn may be launched from the repo root).
API_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{(API_DIR / 'saig_dev.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = DEFAULT_SQLITE_URL

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 7

    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False

    # Relaxed in tests so auth suites can exercise lockout without tripping 429s.
    rate_limit_enabled: bool = True

    login_max_failures: int = 5
    lockout_minutes: int = 15
    password_reset_ttl_minutes: int = 30

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.app_env in ("staging", "production")

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        if self.is_production_like:
            if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be set to a strong value (>=32 chars) in staging/production"
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not permitted in staging/production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in staging/production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
