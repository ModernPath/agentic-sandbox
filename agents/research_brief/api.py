"""HTTP API for research brief. Routes call service.py only; the rules live there."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from sandbox_blocks.llm import build_llm
from sandbox_blocks.readers import build_reader
from sandbox_blocks.search import build_search
from sandbox_host.errors import ServiceUnavailable
from sandbox_host.registry import AgentSpec, CliSpec

from . import service
from .store import BriefStore
from .tools import build_tools

HERE = Path(__file__).resolve().parent
router = APIRouter()


class BriefRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)


def get_store(request: Request) -> BriefStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL to use briefs.")
    return BriefStore(engine)


def _clients(request: Request) -> tuple:
    settings = request.app.state.model_settings
    injected = request.app.state.services.get("research_brief", {})
    search = injected.get("search") or build_search(settings)
    llm = injected.get("llm") or build_llm(settings)
    read_page = injected.get("read_page") or build_reader(settings).read
    return search, llm, read_page


@router.post("/briefs", status_code=201)
def create_brief(payload: BriefRequest, request: Request, store: BriefStore = Depends(get_store)) -> dict:
    search, llm, read_page = _clients(request)
    try:
        return service.run_brief(store, search, llm, read_page, payload.topic)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/briefs")
def list_briefs(store: BriefStore = Depends(get_store)) -> dict:
    return {"briefs": service.list_briefs(store)}


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, store: BriefStore = Depends(get_store)) -> dict:
    try:
        return service.get_brief(store, brief_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("/panel")
def panel_summary(store: BriefStore = Depends(get_store)) -> dict:
    return service.summary_panel(store)


def _chat_tools(ctx):
    return build_tools(BriefStore(ctx.engine), ctx.search_or_none(), ctx.llm_or_none(), ctx.reader_or_none())


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="research-brief",
        title="Research brief",
        description="Search the web, read a few pages, and write a summary with numbered citations.",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=HERE / "ui",
        has_panel=True,
        chat_tools=_chat_tools,
        cli=CliSpec(module="research_brief.cli", commands=("research", "list", "get")),
    )
