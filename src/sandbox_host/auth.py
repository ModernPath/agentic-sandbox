"""Sessions, login throttling, and request guarding for the sandbox host.

Sessions are opaque random tokens; only their SHA-256 is stored. A session lasts 12 hours
and is refused after 2 hours without use. Login is throttled per username in memory
(5 failures in 15 minutes); this limit is per process.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .passwords import DUMMY_HASH, verify_password

SESSION_COOKIE = "sandbox_session"
SESSION_MAX_AGE = timedelta(hours=12)
SESSION_IDLE_LIMIT = timedelta(hours=2)
SESSION_TOUCH_INTERVAL = timedelta(minutes=1)
THROTTLE_FAILURES = 5
THROTTLE_WINDOW = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(engine: Engine, username: str, password: str) -> Optional[dict]:
    """Return the user row when the credentials are valid and the account is enabled."""
    name = (username or "").strip().lower()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, username, password_hash, disabled FROM sandbox_users"
                                " WHERE username = :u"), {"u": name}).mappings().first()
    stored = row["password_hash"] if row else DUMMY_HASH
    valid = verify_password(password or "", stored)
    if row is None or not valid or row["disabled"]:
        return None
    return {"id": row["id"], "username": row["username"]}


def create_session(engine: Engine, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO sandbox_sessions (token_hash, user_id, created_at, last_seen_at, expires_at)"
                          " VALUES (:h, :u, :c, :c, :e)"),
                     {"h": _hash_token(token), "u": user_id, "c": now.isoformat(),
                      "e": (now + SESSION_MAX_AGE).isoformat()})
    return token


def session_user(engine: Engine, token: Optional[str]) -> Optional[dict]:
    """The signed-in user for this token, or None if the session is missing, expired, idle, or disabled."""
    if not token:
        return None
    digest = _hash_token(token)
    now = _now()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT s.user_id, s.last_seen_at, s.expires_at, u.username, u.disabled"
                                " FROM sandbox_sessions s JOIN sandbox_users u ON u.id = s.user_id"
                                " WHERE s.token_hash = :h"), {"h": digest}).mappings().first()
        if row is None:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        last_seen = datetime.fromisoformat(row["last_seen_at"])
        if row["disabled"] or now >= expires or now - last_seen > SESSION_IDLE_LIMIT:
            conn.execute(text("DELETE FROM sandbox_sessions WHERE token_hash = :h"), {"h": digest})
            return None
        if now - last_seen >= SESSION_TOUCH_INTERVAL:
            conn.execute(text("UPDATE sandbox_sessions SET last_seen_at = :t WHERE token_hash = :h"),
                         {"t": now.isoformat(), "h": digest})
    return {"id": row["user_id"], "username": row["username"]}


def delete_session(engine: Engine, token: Optional[str]) -> None:
    if token:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sandbox_sessions WHERE token_hash = :h"), {"h": _hash_token(token)})


class LoginThrottle:
    def __init__(self, failures: int = THROTTLE_FAILURES, window: timedelta = THROTTLE_WINDOW):
        self.failures = failures
        self.window = window
        self._lock = threading.Lock()
        self._attempts: dict[str, deque] = defaultdict(deque)

    def _recent(self, username: str) -> deque:
        cutoff = _now() - self.window
        attempts = self._attempts[username]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        return attempts

    def blocked(self, username: str) -> bool:
        with self._lock:
            return len(self._recent(username)) >= self.failures

    def record_failure(self, username: str) -> None:
        with self._lock:
            self._recent(username).append(_now())

    def clear(self, username: str) -> None:
        with self._lock:
            self._attempts.pop(username, None)
