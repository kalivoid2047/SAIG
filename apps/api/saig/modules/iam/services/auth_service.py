import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import PasswordResetToken, RefreshToken, User
from saig.modules.iam.repository import IamRepository
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.config import Settings
from saig.shared.database import new_uuid, utcnow
from saig.shared.errors import AccountLockedError, UnauthorizedError
from saig.shared.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)

logger = logging.getLogger("saig.auth")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.repo = IamRepository(session)
        self.audit = AuditService(session)

    # --- login ---------------------------------------------------------------

    async def login(
        self, email: str, password: str, ip: str | None, user_agent: str | None
    ) -> tuple[str, str, User]:
        """Returns (access_token, raw_refresh_token, user)."""
        user = await self.repo.get_user_by_email(email)

        if user is None:
            # Constant-shape failure: hash anyway to blunt timing-based enumeration.
            verify_password(password, hash_password("invalid-timing-pad"))
            raise UnauthorizedError("Invalid email or password.")

        if user.locked_until and user.locked_until > utcnow():
            raise AccountLockedError(
                "Account temporarily locked due to failed sign-in attempts."
            )

        if not verify_password(password, user.password_hash):
            user.failed_attempts += 1
            if user.failed_attempts >= self.settings.login_max_failures:
                user.locked_until = utcnow() + timedelta(minutes=self.settings.lockout_minutes)
                user.failed_attempts = 0
                self.audit.record(
                    "auth.lockout",
                    actor_id=user.id,
                    organization_id=user.organization_id,
                    ip_address=ip,
                )
            await self.session.commit()
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = utcnow()

        access = create_access_token(user.id, user.organization_id, self.settings)
        raw_refresh = await self._issue_refresh(user.id, family_id=new_uuid(), ip=ip,
                                                user_agent=user_agent)
        self.audit.record(
            "auth.login",
            actor_id=user.id,
            organization_id=user.organization_id,
            ip_address=ip,
        )
        await self.session.commit()
        return access, raw_refresh, user

    # --- refresh rotation -------------------------------------------------------

    async def refresh(
        self, raw_token: str, ip: str | None, user_agent: str | None
    ) -> tuple[str, str, User]:
        token = await self.repo.get_refresh_token(hash_token(raw_token))
        if token is None:
            raise UnauthorizedError("Invalid refresh token.")

        if token.rotated_at is not None:
            # Reuse of an already-rotated token = theft signal: kill the family.
            await self.repo.revoke_family(token.family_id)
            self.audit.record(
                "auth.refresh_reuse_detected",
                actor_id=token.user_id,
                entity_table="refresh_tokens",
                entity_id=token.id,
                ip_address=ip,
            )
            await self.session.commit()
            logger.warning("refresh token reuse detected", extra={"user_id": token.user_id})
            raise UnauthorizedError("Session invalidated. Please sign in again.")

        if token.revoked_at is not None or token.expires_at < utcnow():
            raise UnauthorizedError("Refresh token expired or revoked.")

        user = await self.session.get(User, token.user_id)
        if user is None or user.deleted_at is not None or not user.is_active:
            raise UnauthorizedError("Account unavailable.")

        token.rotated_at = utcnow()
        raw_new = await self._issue_refresh(
            user.id, family_id=token.family_id, ip=ip, user_agent=user_agent
        )
        access = create_access_token(user.id, user.organization_id, self.settings)
        await self.session.commit()
        return access, raw_new, user

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        token = await self.repo.get_refresh_token(hash_token(raw_token))
        if token is not None:
            await self.repo.revoke_family(token.family_id)
            self.audit.record("auth.logout", actor_id=token.user_id)
            await self.session.commit()

    # --- password reset ----------------------------------------------------------

    async def forgot_password(self, email: str) -> None:
        """Always succeeds from the caller's view (no account enumeration)."""
        user = await self.repo.get_user_by_email(email)
        if user is None:
            return
        raw, token_hash = new_opaque_token()
        self.session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=utcnow()
                + timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
        )
        self.audit.record("auth.password_reset_requested", actor_id=user.id,
                          organization_id=user.organization_id)
        await self.session.commit()
        # Email delivery arrives with the notifications module (Phase 1).
        # Until then the token is only logged in development environments.
        if self.settings.app_env == "development":
            logger.info("password reset token for %s: %s", email, raw)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token = await self.repo.get_reset_token(hash_token(raw_token))
        if token is None or token.used_at is not None or token.expires_at < utcnow():
            raise UnauthorizedError("Reset link is invalid or has expired.")
        user = await self.session.get(User, token.user_id)
        if user is None or user.deleted_at is not None:
            raise UnauthorizedError("Reset link is invalid or has expired.")

        user.password_hash = hash_password(new_password)
        user.failed_attempts = 0
        user.locked_until = None
        token.used_at = utcnow()
        await self.repo.revoke_all_for_user(user.id)  # every session dies on reset
        self.audit.record("auth.password_reset", actor_id=user.id,
                          organization_id=user.organization_id)
        await self.session.commit()

    # --- helpers ------------------------------------------------------------------

    async def _issue_refresh(
        self, user_id: str, family_id: str, ip: str | None, user_agent: str | None
    ) -> str:
        raw, token_hash = new_opaque_token()
        self.session.add(
            RefreshToken(
                user_id=user_id,
                family_id=family_id,
                token_hash=token_hash,
                expires_at=utcnow() + timedelta(days=self.settings.refresh_token_ttl_days),
                ip_address=ip,
                user_agent=(user_agent or "")[:400] or None,
            )
        )
        return raw
