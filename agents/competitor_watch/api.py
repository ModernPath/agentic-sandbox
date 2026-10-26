"""HTTP API for competitor watch and the sales radar. Routes call the service; rules live in service.py."""

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from sandbox_blocks.errors import ConfigurationError
from sandbox_blocks.llm import build_llm
from sandbox_blocks.readers import build_reader
from sandbox_blocks.search import build_search
from sandbox_host.audit import record as audit_record
from sandbox_host.errors import ServiceUnavailable
from sandbox_host.registry import AgentSpec, CliSpec

from . import chat, service
from .store import CompetitorStore
from .tools import build_tools

HERE = Path(__file__).resolve().parent
router = APIRouter()
NO_MODEL = "No model is configured. Set SANDBOX_LLM_PROVIDER and its key."


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    website: Optional[str] = Field(default=None, max_length=300)
    note: str = Field(default="", max_length=500)


class CheckRequest(BaseModel):
    competitor_id: Optional[str] = None


class ReviewRequest(BaseModel):
    status: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


def get_store(request: Request) -> CompetitorStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
    return CompetitorStore(engine)


def _injected(request: Request) -> dict:
    return request.app.state.services.get("competitor_watch", {})


def _llm(request: Request):
    injected = _injected(request).get("llm")
    if injected is not None:
        return injected
    try:
        return build_llm(request.app.state.model_settings)
    except ConfigurationError:
        raise ServiceUnavailable(NO_MODEL) from None


def _clients(request: Request) -> tuple:
    """search, llm, read_page. Search and reading are optional: checks report it when they are missing."""
    injected = _injected(request)
    settings = request.app.state.model_settings
    search = injected.get("search")
    if search is None:
        try:
            search = build_search(settings)
        except ConfigurationError:
            search = None
    read_page = injected.get("read_page")
    if read_page is None:
        try:
            read_page = build_reader(settings).read
        except ConfigurationError:
            read_page = None
    return search, _llm(request), read_page


def _value_error(action):
    try:
        return action()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post("/competitors", status_code=201)
def add_competitor(payload: CompetitorCreate, store: CompetitorStore = Depends(get_store)) -> dict:
    try:
        return service.add_competitor(store, payload.name, payload.website, payload.note)
    except service.DuplicateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/competitors")
def list_competitors(store: CompetitorStore = Depends(get_store)) -> dict:
    return {"competitors": service.list_competitors(store)}


@router.delete("/competitors/{competitor_id}")
def delete_competitor(competitor_id: str, store: CompetitorStore = Depends(get_store)) -> dict:
    if not service.delete_competitor(store, competitor_id):
        raise HTTPException(status_code=404, detail="Competitor not found")
    return {"ok": True}


@router.post("/check")
def run_check(request: Request, payload: Optional[CheckRequest] = None, store: CompetitorStore = Depends(get_store)) -> dict:
    search, llm, read_page = _clients(request)
    try:
        checked = service.run_check(store, search, llm, read_page, payload.competitor_id if payload else None)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except RuntimeError as error:
        raise ServiceUnavailable(str(error)) from None
    audit_record(request.app.state.engine, actor="user:" + request.state.user["username"],
                 action="competitor.check", subject="competitor-watch", detail={"checked": checked})
    return {"checked": checked}


@router.get("/signals")
def list_signals(status: str = "new", category: str = "", importance: str = "", competitor_id: str = "",
                 limit: int = Query(default=50), store: CompetitorStore = Depends(get_store)) -> dict:
    return {"signals": _value_error(lambda: service.list_signals(
        store, status=status, category=category or None, importance=importance or None,
        competitor_id=competitor_id or None, limit=limit))}


@router.patch("/signals/{signal_id}")
def review_signal(signal_id: str, payload: ReviewRequest, request: Request, store: CompetitorStore = Depends(get_store)) -> dict:
    updated = _value_error(lambda: service.review_signal(store, signal_id, payload.status))
    if not updated:
        raise HTTPException(status_code=404, detail="Signal not found")
    audit_record(request.app.state.engine, actor="user:" + request.state.user["username"],
                 action="signal.reviewed", subject=f"signal:{signal_id}", detail={"status": payload.status})
    return {"id": signal_id, "status": payload.status}


@router.get("/dashboard")
def dashboard(store: CompetitorStore = Depends(get_store)) -> dict:
    return service.dashboard(store)


@router.post("/chat")
def chat_reply(payload: ChatRequest, request: Request, store: CompetitorStore = Depends(get_store)) -> dict:
    search, llm, read_page = _clients(request)
    tools = build_tools(store, search, llm, read_page)
    history = [turn.model_dump() for turn in payload.history]
    return chat.reply(llm, tools, payload.message, history)


@router.get("/panel")
def panel_summary(store: CompetitorStore = Depends(get_store)) -> dict:
    return service.summary_panel(store)


def _chat_tools(ctx):
    return build_tools(CompetitorStore(ctx.engine), ctx.search_or_none(), ctx.llm_or_none(), ctx.reader_or_none())


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="competitor-watch",
        title="Sales radar",
        description="Competitor signals from public news, rated and sourced, with a chat that answers from the data.",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=HERE / "ui",
        has_panel=True,
        chat_tools=_chat_tools,
        cli=CliSpec(module="competitor_watch.cli", commands=("list", "add", "signals", "check", "review")),
    )
