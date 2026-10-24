from __future__ import annotations

import argparse
import asyncio
import re
import sys

from sqlalchemy import func, select

from app.core.auth import hash_password
from app.core.password_policy import generate_password, validate_password
from app.db.audit import add_audit_event
from app.db.models import User
from app.db.session import AsyncSessionLocal

_USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,100}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="On-prem industrial Nexora account provisioning.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-user", help="Issue a local user account with a one-time password"
    )
    create.add_argument("--username", required=True)
    create.add_argument("--role", choices=("admin", "supervisor", "viewer"), default="viewer")

    reset = commands.add_parser(
        "reset-password", help="Reset a user's password and revoke existing sessions"
    )
    reset.add_argument("--username", required=True)

    disable = commands.add_parser(
        "disable-user", help="Disable a user and revoke existing sessions"
    )
    disable.add_argument("--username", required=True)

    commands.add_parser("list-users", help="List usernames, roles, and account status")
    return parser


async def _prepare_database() -> None:
    from app.main import upgrade_database

    await upgrade_database()


async def _create_user(username: str, role: str) -> tuple[int, str]:
    username = username.strip().casefold()
    if role not in {"admin", "supervisor", "viewer"}:
        raise ValueError("Role must be admin, supervisor or viewer")
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError(
            "Username must be 3-100 characters: lowercase letters, numbers, '.', '_' or '-'"
        )

    password = generate_password()
    validate_password(password, username)
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User.id).where(func.lower(User.username) == username))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Username already exists")
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        await db.flush()
        add_audit_event(
            db,
            "user.created_from_cli",
            target_type="user",
            target_id=user.id,
            details={"role": role},
        )
        await db.commit()
        return user.id, password


async def _reset_password(username: str) -> str:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .where(func.lower(User.username) == username.strip().casefold())
            .with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        password = generate_password()
        validate_password(password, user.username)
        user.password_hash = hash_password(password)
        user.must_change_password = True
        user.token_version += 1
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.locked_until = None
        add_audit_event(
            db,
            "user.password_reset_from_cli",
            target_type="user",
            target_id=user.id,
        )
        await db.commit()
        return password


async def _disable_user(username: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .where(func.lower(User.username) == username.strip().casefold())
            .with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        if user.role == "admin" and user.is_active:
            active_admins = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.id != user.id,
                )
            )
            if active_admins.scalar_one() < 1:
                raise ValueError(
                    "Cannot disable the last active administrator for this installation"
                )
        user.is_active = False
        user.token_version += 1
        add_audit_event(
            db,
            "user.disabled_from_cli",
            target_type="user",
            target_id=user.id,
        )
        await db.commit()


async def _list_users() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).order_by(User.id))
        for user in result.scalars().all():
            print(
                f"id={user.id}\tusername={user.username}\trole={user.role}"
                f"\tactive={user.is_active}"
                f"\tmust_change_password={user.must_change_password}"
            )


async def _run(args: argparse.Namespace) -> int:
    await _prepare_database()
    if args.command == "create-user":
        user_id, password = await _create_user(args.username, args.role)
        print(f"Issued user id: {user_id}")
        print(f"Username: {args.username.strip().casefold()}")
        print(f"Temporary password (displayed once): {password}")
        print(
            "The user must change this password at first sign-in. Deliver it through a private channel."
        )
        return 0
    if args.command == "reset-password":
        password = await _reset_password(args.username)
        print(f"Temporary password (displayed once): {password}")
        print(
            "All prior sessions have been revoked; the user must change this password at sign-in."
        )
        return 0
    if args.command == "disable-user":
        await _disable_user(args.username)
        print("User disabled; all prior sessions have been revoked.")
        return 0
    await _list_users()
    return 0


def main() -> int:
    args = _parser().parse_args()
    try:
        return asyncio.run(_run(args))
    except (ValueError, RuntimeError) as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
