"""Drafts (outward actions wait here for a person) and the audit endpoint. Mounted under /api by the host."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import audit
from .errors import ServiceUnavailable

router = APIRouter()
DRAFT_STATES = ("pending", "approved", "rejected")


class DraftCreate(BaseModel):
    kind: Literal["message"]
    target: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


def _engine(request: Request):
    if request.app.state.engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
    return request.app.state.engine


def _actor(request: Request) -> str:
    return "user:" + request.state.user["username"]


def _draft(engine, draft_id: str):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM sandbox_drafts WHERE id = :id"), {"id": draft_id}).mappings().first()
    return dict(row) if row else None


def _decide(request: Request, draft_id: str, state: str) -> dict:
    engine = _engine(request)
    current = _draft(engine, draft_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if current["state"] != "pending":
        raise HTTPException(status_code=409, detail="This draft has already been decided")
    decided = {"state": state, "decided_by": request.state.user["username"],
               "decided_at": datetime.now(timezone.utc).isoformat()}
    with engine.begin() as conn:
        conn.execute(text("UPDATE sandbox_drafts SET state = :state, decided_by = :decided_by, "
                          "decided_at = :decided_at WHERE id = :id AND state = 'pending'"),
                     dict(decided, id=draft_id))
    audit.record(engine, actor=_actor(request), action=f"draft.{state}", subject=f"draft:{draft_id}",
                 detail={"kind": current["kind"], "target": current["target"]})
    return dict(_draft(engine, draft_id))


@router.get("/audit")
def list_audit(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"events": audit.recent(_engine(request), limit)}


@router.post("/drafts", status_code=201)
def create_draft(payload: DraftCreate, request: Request) -> dict:
    engine = _engine(request)
    row = {"id": str(uuid.uuid4()), "kind": payload.kind, "target": payload.target, "body": payload.body,
           "state": "pending", "created_by": request.state.user["username"],
           "created_at": datetime.now(timezone.utc).isoformat(), "decided_by": None, "decided_at": None}
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO sandbox_drafts (id, kind, target, body, state, created_by, created_at, "
                          "decided_by, decided_at) VALUES (:id, :kind, :target, :body, :state, :created_by, "
                          ":created_at, :decided_by, :decided_at)"), row)
    audit.record(engine, actor=_actor(request), action="draft.created", subject=f"draft:{row['id']}",
                 detail={"kind": payload.kind, "target": payload.target})
    return row


@router.get("/drafts")
def list_drafts(request: Request, state: str = "pending") -> dict:
    if state not in DRAFT_STATES:
        raise HTTPException(status_code=422, detail="state must be pending, approved, or rejected")
    engine = _engine(request)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM sandbox_drafts WHERE state = :state ORDER BY created_at DESC "
                                 "LIMIT 100"), {"state": state}).mappings().all()
    return {"drafts": [dict(r) for r in rows]}


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, request: Request) -> dict:
    return _decide(request, draft_id, "approved")


@router.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: str, request: Request) -> dict:
    return _decide(request, draft_id, "rejected")
