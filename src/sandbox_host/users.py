"""Operator tools for sandbox users. There is no self-registration.

  python -m sandbox_host.users create <username>     (prompts for the password)
  python -m sandbox_host.users disable <username>
  python -m sandbox_host.users enable <username>

The database comes from DATABASE_URL. Passwords are never accepted as arguments.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .passwords import hash_password

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def normalise_username(username: str) -> str:
    value = (username or "").strip().lower()
    if not USERNAME_PATTERN.match(value):
        raise ValueError("Username must be 3-40 lowercase letters, digits, dots, hyphens, or underscores")
    return value


def create_user(engine: Engine, username: str, password: str) -> str:
    name = normalise_username(username)
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO sandbox_users (id, username, password_hash, disabled, created_at)"
                              " VALUES (:id, :username, :hash, 0, :created)"),
                         {"id": user_id, "username": name, "hash": password_hash,
                          "created": datetime.now(timezone.utc).isoformat()})
    except IntegrityError:
        raise ValueError("That username already exists") from None
    return user_id


def set_disabled(engine: Engine, username: str, disabled: bool) -> None:
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE sandbox_users SET disabled = :d WHERE username = :u"),
                              {"d": 1 if disabled else 0, "u": normalise_username(username)})
    if result.rowcount == 0:
        raise ValueError("No such user")


def _engine_from_env() -> Engine:
    from sqlalchemy import create_engine

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return create_engine(url, pool_pre_ping=True)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in {"create", "disable", "enable"}:
        print(__doc__, file=sys.stderr)
        return 2
    action, username = args
    engine = _engine_from_env()
    try:
        if action == "create":
            password = getpass.getpass("Password (at least 12 characters): ")
            if password != getpass.getpass("Repeat password: "):
                print("error: passwords do not match", file=sys.stderr)
                return 1
            create_user(engine, username, password)
        else:
            set_disabled(engine, username, action == "disable")
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{action}: {normalise_username(username)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
