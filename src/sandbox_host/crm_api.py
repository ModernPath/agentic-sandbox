"""CRM core HTTP routes and chat tools. Both call crm.py; the rules live there."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sandbox_blocks.tools import Tool, tool_from_function

from . import crm
from .errors import ServiceUnavailable

router = APIRouter()


class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: str = Field(min_length=1, max_length=20)
    website: Optional[str] = Field(default=None, max_length=300)
    industry: str = Field(default="", max_length=80)
    country: str = Field(default="", max_length=80)


class OpportunityCreate(BaseModel):
    account_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    amount_minor: int = Field(ge=0, le=crm.MAX_AMOUNT_MINOR)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    close_date: Optional[str] = Field(default=None, max_length=40)


class StageChange(BaseModel):
    stage: str = Field(min_length=1, max_length=20)


class TaskCreate(BaseModel):
    subject_id: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=2, max_length=500)
    due_at: Optional[str] = Field(default=None, max_length=40)


def _engine(request: Request):
    if request.app.state.engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
    return request.app.state.engine


def _user(request: Request) -> str:
    return request.state.user["username"]


def _call(action):
    try:
        return action()
    except crm.DuplicateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/crm/summary")
def get_summary(request: Request) -> dict:
    return crm.summary(_engine(request))


@router.get("/crm/accounts")
def get_accounts(request: Request, type: str = "") -> dict:
    return {"accounts": _call(lambda: crm.list_accounts(_engine(request), type or None))}


@router.post("/crm/accounts", status_code=201)
def post_account(payload: AccountCreate, request: Request) -> dict:
    return _call(lambda: crm.create_account(_engine(request), _user(request), payload.name, payload.type,
                                            payload.website or "", payload.industry, payload.country))


@router.delete("/crm/accounts/{account_id}")
def delete_account(account_id: str, request: Request) -> dict:
    if not crm.archive_account(_engine(request), _user(request), account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"archived": True}


@router.get("/crm/opportunities")
def get_opportunities(request: Request, stage: str = "") -> dict:
    return {"opportunities": _call(lambda: crm.list_opportunities(_engine(request), stage or None))}


@router.post("/crm/opportunities", status_code=201)
def post_opportunity(payload: OpportunityCreate, request: Request) -> dict:
    return _call(lambda: crm.create_opportunity(_engine(request), _user(request), payload.account_id, payload.name,
                                                payload.amount_minor, payload.currency, payload.close_date))


@router.post("/crm/opportunities/{opportunity_id}/stage")
def post_stage(opportunity_id: str, payload: StageChange, request: Request) -> dict:
    return _call(lambda: crm.set_stage(_engine(request), _user(request), opportunity_id, payload.stage))


@router.get("/crm/tasks")
def get_tasks(request: Request) -> dict:
    return {"tasks": crm.list_open_tasks(_engine(request))}


@router.post("/crm/tasks", status_code=201)
def post_task(payload: TaskCreate, request: Request) -> dict:
    return _call(lambda: crm.add_task(_engine(request), _user(request), payload.subject_id, payload.body,
                                      payload.due_at))


@router.post("/crm/tasks/{task_id}/complete")
def post_complete(task_id: str, request: Request) -> dict:
    return _call(lambda: crm.complete_task(_engine(request), _user(request), task_id))


def build_tools(engine, user: str) -> list[Tool]:
    """The CRM core as chat tools. Writes are attributed to the user who asked."""

    def list_accounts(type: str = "") -> dict:
        """List accounts (not archived). type can be customer, prospect, competitor, or partner."""
        return _safe(lambda: {"accounts": crm.list_accounts(engine, type or None)})

    def create_account(name: str, type: str, website: str = "", industry: str = "") -> dict:
        """Create an account. type is customer, prospect, competitor, or partner."""
        return _safe(lambda: crm.create_account(engine, user, name, type, website, industry))

    def list_opportunities(stage: str = "") -> dict:
        """List opportunities (not archived), optionally by stage."""
        return _safe(lambda: {"opportunities": crm.list_opportunities(engine, stage or None)})

    def create_opportunity(account_id: str, name: str, amount_minor: int, currency: str = "EUR") -> dict:
        """Create an opportunity on an account. amount_minor is the amount in cents (or the smallest unit)."""
        return _safe(lambda: crm.create_opportunity(engine, user, account_id, name, amount_minor, currency))

    def set_stage(opportunity_id: str, stage: str) -> dict:
        """Move an opportunity to a stage: qualify, propose, negotiate, commit, won, or lost."""
        return _safe(lambda: crm.set_stage(engine, user, opportunity_id, stage))

    def list_open_tasks() -> dict:
        """List open tasks, earliest due first."""
        return _safe(lambda: {"tasks": crm.list_open_tasks(engine)})

    def add_task(subject_id: str, body: str, due_at: str = "") -> dict:
        """Add a task to an account. due_at is optional ISO 8601, for example 2026-11-14T09:00:00Z."""
        return _safe(lambda: crm.add_task(engine, user, subject_id, body, due_at or None))

    def complete_task(task_id: str) -> dict:
        """Mark an open task as done."""
        return _safe(lambda: crm.complete_task(engine, user, task_id))

    def summary() -> dict:
        """Totals: accounts, open opportunities, open pipeline and won amounts (in minor units), overdue tasks."""
        return _safe(lambda: crm.summary(engine))

    functions = [list_accounts, create_account, list_opportunities, create_opportunity, set_stage,
                 list_open_tasks, add_task, complete_task, summary]
    tools = []
    for fn in functions:
        tool = tool_from_function(fn)
        tools.append(Tool(name="crm__" + tool.name, description=tool.description, parameters=tool.parameters,
                          handler=tool.handler))
    return tools


def _safe(call):
    try:
        return call()
    except crm.DuplicateError as error:
        return {"error": str(error)}
    except (LookupError, ValueError) as error:
        return {"error": str(error)}
