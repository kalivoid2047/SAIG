from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import AuditLog
from saig.shared.middleware import get_request_id

# Never persisted to the audit trail, even in before/after images.
_REDACTED_FIELDS = {"password", "password_hash", "token_hash", "new_password"}


def _scrub(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    return {k: ("[redacted]" if k in _REDACTED_FIELDS else v) for k, v in data.items()}


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def record(
        self,
        action: str,
        *,
        actor_id: str | None = None,
        organization_id: str | None = None,
        entity_table: str | None = None,
        entity_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                organization_id=organization_id,
                action=action,
                entity_table=entity_table,
                entity_id=entity_id,
                before_data=_scrub(before),
                after_data=_scrub(after),
                ip_address=ip_address,
                request_id=get_request_id(),
            )
        )
