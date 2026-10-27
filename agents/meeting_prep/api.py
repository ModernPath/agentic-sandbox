"""HTTP API for meeting prep, mounted by the sandbox host at /api/agents/meeting-prep. Routes call service.py only."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from sandbox_host.errors import ServiceUnavailable
from sandbox_host.registry import AgentSpec, CliSpec

from . import service
from .models import BriefCreate
from .store import MeetingPrepStore
from .tools import build_tools
from .wiring import build_clients

HERE = Path(__file__).resolve().parent
router = APIRouter()


def get_store(request: Request) -> MeetingPrepStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
    return MeetingPrepStore(engine)


def _clients(request: Request) -> dict:
    state = request.app.state
    return build_clients(os.environ, state.engine, state.services.get("meeting_prep"), state.model_settings)


@router.post("/briefs", status_code=201)
def create_brief(payload: BriefCreate, request: Request, store: MeetingPrepStore = Depends(get_store)) -> dict:
    try:
        return service.prepare_brief(store, payload.model_dump(), **_clients(request))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/briefs")
def list_briefs(store: MeetingPrepStore = Depends(get_store)) -> dict:
    return {"briefs": service.list_briefs(store)}


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, store: MeetingPrepStore = Depends(get_store)) -> dict:
    try:
        return service.get_brief(store, brief_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.delete("/briefs/{brief_id}")
def delete_brief(brief_id: str, store: MeetingPrepStore = Depends(get_store)) -> dict:
    try:
        return {"deleted": service.delete_brief(store, brief_id)}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("/panel")
def panel_summary(store: MeetingPrepStore = Depends(get_store)) -> dict:
    return service.summary_panel(store)


def _chat_tools(ctx):
    clients = build_clients(os.environ, ctx.engine, ctx.injected, ctx.settings)
    if "llm" not in ctx.injected and ctx.shared_llm is not None:
        clients["llm"] = ctx.shared_llm
    return build_tools(MeetingPrepStore(ctx.engine), **clients)


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="meeting-prep",
        title="Meeting prep",
        description="One-page briefs before a sales meeting: recent news with citations, radar signals, "
                    "talking points, and open questions.",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=HERE / "ui",
        has_panel=True,
        chat_tools=_chat_tools,
        cli=CliSpec(module="meeting_prep.cli", commands=("prepare", "list", "get")),
    )
