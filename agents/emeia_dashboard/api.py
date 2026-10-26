"""HTTP API for the EMEIA dashboard. Routes call service.py only; the rules live there."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sandbox_host.errors import ServiceUnavailable
from sandbox_host.registry import AgentSpec, CliSpec

from . import service
from .models import MarketItemReview, TargetCreate, TargetUpdate, ToolLinkCreate, WinCreate, MarketItemCreate
from .store import DashboardStore
from .tools import build_tools

HERE = Path(__file__).resolve().parent
router = APIRouter()


def get_store(request: Request) -> DashboardStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL to use the dashboard.")
    return DashboardStore(engine)


def _call(action):
    try:
        return action()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/overview")
def overview(period: str | None = Query(default=None, pattern=r"^\d{4}-Q[1-4]$"),
             store: DashboardStore = Depends(get_store)) -> dict:
    return service.overview(store, period)


@router.post("/targets", status_code=201)
def create_target(payload: TargetCreate, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.add_target(store, payload.model_dump()))


@router.patch("/targets/{target_id}")
def update_target(target_id: str, payload: TargetUpdate, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.update_target(store, target_id, payload.current_value))


@router.post("/wins", status_code=201)
def create_win(payload: WinCreate, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.add_win(store, payload.model_dump()))


@router.post("/market-items", status_code=201)
def create_market_item(payload: MarketItemCreate, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.add_market_item(store, payload.model_dump()))


@router.get("/market-items")
def market_items(reviewed: bool = Query(default=False), store: DashboardStore = Depends(get_store)) -> dict:
    return {"items": store.list_market_items(reviewed=reviewed)}


@router.patch("/market-items/{item_id}")
def review_market_item(item_id: str, payload: MarketItemReview, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.approve_market_item(store, item_id))


@router.post("/tool-links", status_code=201)
def create_tool_link(payload: ToolLinkCreate, store: DashboardStore = Depends(get_store)) -> dict:
    return _call(lambda: service.add_tool_link(store, payload.model_dump()))


@router.get("/panel")
def panel_summary(store: DashboardStore = Depends(get_store)) -> dict:
    return service.summary_panel(store)


def _chat_tools(ctx):
    return build_tools(DashboardStore(ctx.engine))


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="emeia-dashboard",
        title="EMEIA dashboard",
        description="Team targets, wins, market and competitor follow-up, and team tool links.",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=HERE / "ui",
        has_panel=True,
        chat_tools=_chat_tools,
        cli=CliSpec(module="emeia_dashboard.cli", commands=("overview", "target-add", "target-update", "win-add",
                                                            "market-add", "market-queue", "link-add")),
    )
