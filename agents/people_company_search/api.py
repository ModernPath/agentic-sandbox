"""HTTP API for people and company search. Routes call service.py only.

Not mounted yet: this agent has no registry entry (see AGENTS.md).
"""

import os

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from sandbox_blocks.errors import ConfigurationError
from sandbox_host.errors import AgentInputError, ServiceUnavailable

from . import service
from .cli import build_client

router = APIRouter()


class SearchRequest(BaseModel):
    kind: str = Field(pattern="^(people|company)$")
    query: str = Field(min_length=1, max_length=service.MAX_QUERY)


@router.post("/search")
def search(payload: SearchRequest, request: Request) -> dict:
    agent = request.app.state.services.get("people_company_search")
    if agent is None:
        try:
            agent = build_client(os.environ)
        except ConfigurationError as error:
            raise ServiceUnavailable(str(error)) from None
    try:
        return service.run_search(agent, payload.kind, payload.query)
    except ValueError as error:
        raise AgentInputError(422, str(error)) from None
