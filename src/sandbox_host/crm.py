"""CRM core rules: accounts (customers, prospects, competitors, partners), opportunities, and tasks.

Every write is audited with the signed-in user as actor. Records are archived, never deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from . import audit

ACCOUNT_TYPES = ("customer", "prospect", "competitor", "partner")
STAGES = ("qualify", "propose", "negotiate", "commit", "won", "lost")
OPEN_STAGES = ("qualify", "propose", "negotiate", "commit")
MAX_AMOUNT_MINOR = 10 ** 12
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S+00:00"


class DuplicateError(ValueError):
    """The name is already used by another account."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FORMAT)


def _clean_name(value: str, low: int, high: int, label: str) -> str:
    name = (value or "").strip()
    if not low <= len(name) <= high:
        raise ValueError(f"{label} must be {low}-{high} characters")
    return name


def _when(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Dates must be ISO 8601, for example 2026-11-14T09:00:00Z") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime(TIME_FORMAT)


def _rows(engine: Engine, sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]


def _one(engine: Engine, sql: str, params: dict) -> dict | None:
    rows = _rows(engine, sql, params)
    return rows[0] if rows else None


def _write(engine: Engine, sql: str, params: dict) -> int:
    with engine.begin() as conn:
        return conn.execute(text(sql), params).rowcount


# accounts
def create_account(engine: Engine, user: str, name: str, kind: str, website: str = "", industry: str = "",
                   country: str = "") -> dict:
    name = _clean_name(name, 2, 120, "Name")
    if kind not in ACCOUNT_TYPES:
        raise ValueError("Type must be customer, prospect, competitor, or partner")
    if len(website or "") > 300 or len(industry or "") > 80 or len(country or "") > 80:
        raise ValueError("A field is too long")
    now = _now()
    row = {"id": str(uuid.uuid4()), "name": name, "name_key": name.lower(), "type": kind,
           "website": (website or "").strip() or None, "industry": industry or "", "country": country or "",
           "owner": user, "archived": 0, "created_at": now, "updated_at": now}
    if _one(engine, "SELECT id FROM crm_accounts WHERE name_key = :k", {"k": row["name_key"]}):
        raise DuplicateError("An account with that name already exists")
    _write(engine, "INSERT INTO crm_accounts (id, name, name_key, type, website, industry, country, owner, archived, "
                   "created_at, updated_at) VALUES (:id, :name, :name_key, :type, :website, :industry, :country, "
                   ":owner, :archived, :created_at, :updated_at)", row)
    audit.record(engine, actor="user:" + user, action="account.created", subject=f"account:{row['id']}",
                 detail={"type": kind})
    return row


def list_accounts(engine: Engine, kind: str | None = None) -> list[dict]:
    if kind and kind not in ACCOUNT_TYPES:
        raise ValueError("Type must be customer, prospect, competitor, or partner")
    if kind:
        return _rows(engine, "SELECT * FROM crm_accounts WHERE archived = 0 AND type = :t ORDER BY name",
                     {"t": kind})
    return _rows(engine, "SELECT * FROM crm_accounts WHERE archived = 0 ORDER BY name")


def archive_account(engine: Engine, user: str, account_id: str) -> bool:
    if not _one(engine, "SELECT id FROM crm_accounts WHERE id = :id AND archived = 0", {"id": account_id}):
        return False
    _write(engine, "UPDATE crm_accounts SET archived = 1, updated_at = :now WHERE id = :id",
           {"id": account_id, "now": _now()})
    audit.record(engine, actor="user:" + user, action="account.archived", subject=f"account:{account_id}")
    return True


# opportunities
def create_opportunity(engine: Engine, user: str, account_id: str, name: str, amount_minor: int,
                       currency: str = "EUR", close_date: str | None = None) -> dict:
    if not _one(engine, "SELECT id FROM crm_accounts WHERE id = :id AND archived = 0", {"id": account_id}):
        raise LookupError("Account not found")
    name = _clean_name(name, 2, 120, "Name")
    if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or not 0 <= amount_minor <= MAX_AMOUNT_MINOR:
        raise ValueError("Amount must be a whole number of cents, 0 or more")
    currency = (currency or "EUR").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("Currency must be a three-letter code")
    now = _now()
    row = {"id": str(uuid.uuid4()), "account_id": account_id, "name": name, "stage": "qualify",
           "amount_minor": amount_minor, "currency": currency, "close_date": _when(close_date), "owner": user,
           "archived": 0, "created_at": now, "updated_at": now}
    _write(engine, "INSERT INTO crm_opportunities (id, account_id, name, stage, amount_minor, currency, close_date, "
                   "owner, archived, created_at, updated_at) VALUES (:id, :account_id, :name, :stage, :amount_minor, "
                   ":currency, :close_date, :owner, :archived, :created_at, :updated_at)", row)
    audit.record(engine, actor="user:" + user, action="opportunity.created", subject=f"opportunity:{row['id']}",
                 detail={"account_id": account_id, "amount_minor": amount_minor})
    return row


def list_opportunities(engine: Engine, stage: str | None = None) -> list[dict]:
    if stage and stage not in STAGES:
        raise ValueError("Unknown stage")
    if stage:
        return _rows(engine, "SELECT * FROM crm_opportunities WHERE archived = 0 AND stage = :s ORDER BY updated_at DESC",
                     {"s": stage})
    return _rows(engine, "SELECT * FROM crm_opportunities WHERE archived = 0 ORDER BY updated_at DESC")


def set_stage(engine: Engine, user: str, opportunity_id: str, stage: str) -> dict:
    if stage not in STAGES:
        raise ValueError("Unknown stage")
    current = _one(engine, "SELECT * FROM crm_opportunities WHERE id = :id AND archived = 0", {"id": opportunity_id})
    if current is None:
        raise LookupError("Opportunity not found")
    now = _now()
    closed = now if stage in ("won", "lost") else None
    _write(engine, "UPDATE crm_opportunities SET stage = :stage, updated_at = :now, closed_at = :closed WHERE id = :id",
           {"id": opportunity_id, "stage": stage, "now": now, "closed": closed})
    audit.record(engine, actor="user:" + user, action="opportunity.stage_changed",
                 subject=f"opportunity:{opportunity_id}", detail={"from": current["stage"], "to": stage})
    return dict(current, stage=stage)


# tasks (activities of kind task)
def add_task(engine: Engine, user: str, subject_id: str, body: str, due_at: str | None = None) -> dict:
    if not _one(engine, "SELECT id FROM crm_accounts WHERE id = :id AND archived = 0", {"id": subject_id}):
        raise LookupError("Account not found")
    body = _clean_name(body, 2, 500, "Task")
    row = {"id": str(uuid.uuid4()), "kind": "task", "subject_id": subject_id, "body": body, "due_at": _when(due_at),
           "done": 0, "owner": user, "created_at": _now(), "completed_at": None}
    _write(engine, "INSERT INTO crm_activities (id, kind, subject_id, body, due_at, done, owner, created_at, "
                   "completed_at) VALUES (:id, :kind, :subject_id, :body, :due_at, :done, :owner, :created_at, "
                   ":completed_at)", row)
    audit.record(engine, actor="user:" + user, action="task.created", subject=f"task:{row['id']}")
    return row


def list_open_tasks(engine: Engine) -> list[dict]:
    return _rows(engine, "SELECT * FROM crm_activities WHERE kind = 'task' AND done = 0 "
                         "ORDER BY due_at IS NULL, due_at")


def complete_task(engine: Engine, user: str, task_id: str) -> dict:
    current = _one(engine, "SELECT * FROM crm_activities WHERE id = :id AND kind = 'task' AND done = 0", {"id": task_id})
    if current is None:
        raise LookupError("Task not found or already done")
    _write(engine, "UPDATE crm_activities SET done = 1, completed_at = :now WHERE id = :id",
           {"id": task_id, "now": _now()})
    audit.record(engine, actor="user:" + user, action="task.completed", subject=f"task:{task_id}")
    return dict(current, done=1)


# summary for the front page
def summary(engine: Engine) -> dict:
    now = _now()
    accounts = _one(engine, "SELECT count(*) AS n FROM crm_accounts WHERE archived = 0", {})["n"]
    open_rows = _one(engine, "SELECT count(*) AS n, COALESCE(SUM(amount_minor), 0) AS total FROM crm_opportunities "
                             "WHERE archived = 0 AND stage IN ('qualify', 'propose', 'negotiate', 'commit')", {})
    won = _one(engine, "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM crm_opportunities "
                       "WHERE archived = 0 AND stage = 'won'", {})["total"]
    quarter_start = _quarter_start(datetime.now(timezone.utc)).strftime(TIME_FORMAT)
    won_quarter = _one(engine, "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM crm_opportunities "
                               "WHERE archived = 0 AND stage = 'won' AND closed_at >= :start",
                       {"start": quarter_start})["total"]
    by_stage_rows = _rows(engine, "SELECT stage, count(*) AS n, COALESCE(SUM(amount_minor), 0) AS total "
                                  "FROM crm_opportunities WHERE archived = 0 AND stage IN "
                                  "('qualify', 'propose', 'negotiate', 'commit') GROUP BY stage")
    by_stage = {r["stage"]: r for r in by_stage_rows}
    stages = [{"stage": st, "count": int(by_stage.get(st, {}).get("n", 0)),
               "amount_minor": int(by_stage.get(st, {}).get("total", 0))} for st in OPEN_STAGES]
    overdue = _one(engine, "SELECT count(*) AS n FROM crm_activities WHERE kind = 'task' AND done = 0 "
                           "AND due_at IS NOT NULL AND due_at < :now", {"now": now})["n"]
    open_tasks = _one(engine, "SELECT count(*) AS n FROM crm_activities WHERE kind = 'task' AND done = 0", {})["n"]
    return {"accounts": accounts, "open_opportunities": open_rows["n"],
            "open_pipeline_minor": open_rows["total"], "won_minor": won, "won_quarter_minor": won_quarter,
            "by_stage": stages, "overdue_tasks": overdue, "open_tasks": open_tasks}


def _quarter_start(moment: datetime) -> datetime:
    month = ((moment.month - 1) // 3) * 3 + 1
    return datetime(moment.year, month, 1, tzinfo=timezone.utc)
