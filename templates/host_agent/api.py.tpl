"""HTTP API for $Title, mounted by the sandbox host at /api/agents/$name. Routes call service.py only."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from sandbox_host.errors import ServiceUnavailable
from sandbox_host.registry import AgentSpec

from . import service
from .models import ItemCreate, ItemUpdate
from .store import $ClassStore

HERE = Path(__file__).resolve().parent
router = APIRouter()


def get_store(request: Request) -> $ClassStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
    return $ClassStore(engine)


@router.post("/items", status_code=201)
def create_item(payload: ItemCreate, store: $ClassStore = Depends(get_store)) -> dict:
    try:
        return service.create_item(store, payload.title, payload.body)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/items")
def list_items(store: $ClassStore = Depends(get_store)) -> dict:
    return {"items": service.list_items(store)}


@router.get("/items/{item_id}")
def get_item(item_id: str, store: $ClassStore = Depends(get_store)) -> dict:
    try:
        return service.get_item(store, item_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.patch("/items/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, store: $ClassStore = Depends(get_store)) -> dict:
    try:
        service.set_status(store, item_id, payload.status)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return {"id": item_id, "status": payload.status}


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="$name",
        title="$Title",
        description="$description",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=HERE / "ui",
    )
