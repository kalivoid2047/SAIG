"""Idempotent seed: permission catalog, system roles, default org, first admin.

Usage:
    python -m saig.scripts.seed [--email admin@seedco.example] [--password <pw>]

Safe to re-run: existing rows are updated/kept, never duplicated. The admin
password is only set when the admin user is first created.
"""

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.models import Organization, Permission, Role, User
from saig.modules.iam.permissions import PERMISSION_CATALOG, SYSTEM_ROLES
from saig.shared.config import get_settings
from saig.shared.database import create_engine_and_sessionmaker
from saig.shared.security import hash_password

DEFAULT_ORG = {"name": "SeedCo", "slug": "seedco"}


async def sync_permissions(session: AsyncSession) -> dict[str, Permission]:
    existing = {
        p.code: p for p in (await session.execute(select(Permission))).scalars()
    }
    for code, label in PERMISSION_CATALOG.items():
        if code in existing:
            existing[code].label = label
        else:
            perm = Permission(code=code, label=label)
            session.add(perm)
            existing[code] = perm
    await session.flush()
    return existing


async def sync_system_roles(
    session: AsyncSession, org: Organization, perms: dict[str, Permission]
) -> dict[str, Role]:
    stmt = select(Role).where(Role.organization_id == org.id, Role.deleted_at.is_(None))
    existing = {r.name: r for r in (await session.execute(stmt)).scalars()}
    roles: dict[str, Role] = {}
    for name, codes in SYSTEM_ROLES.items():
        role = existing.get(name)
        if role is None:
            role = Role(organization_id=org.id, name=name, is_system=True,
                        description=f"System role: {name}")
            session.add(role)
        role.permissions = [perms[c] for c in codes]
        roles[name] = role
    await session.flush()
    return roles


async def main(email: str, password: str | None) -> None:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    async with session_factory() as session:
        perms = await sync_permissions(session)

        org = (
            await session.execute(
                select(Organization).where(Organization.slug == DEFAULT_ORG["slug"],
                                           Organization.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if org is None:
            org = Organization(**DEFAULT_ORG)
            session.add(org)
            await session.flush()
            print(f"Created organization '{org.name}' ({org.id})")

        roles = await sync_system_roles(session, org, perms)

        admin = (
            await session.execute(
                select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if admin is None:
            generated = password or secrets.token_urlsafe(12)
            admin = User(
                organization_id=org.id,
                email=email.lower(),
                password_hash=hash_password(generated),
                full_name="System Administrator",
                roles=[roles["Administrator"]],
            )
            session.add(admin)
            print(f"Created admin user: {email}")
            if password is None:
                print(f"Generated password: {generated}")
                print("Store it now — it is not shown again.")
        else:
            if roles["Administrator"] not in admin.roles:
                admin.roles = [*admin.roles, roles["Administrator"]]
            print(f"Admin user already exists: {email} (password unchanged)")

        await session.commit()
    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="admin@seedco.example")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.email, args.password))
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
