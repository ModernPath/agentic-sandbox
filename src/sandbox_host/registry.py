"""Agent registration: what an agent contributes to the shared host."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from fastapi import APIRouter

from sandbox_blocks.errors import ConfigurationError

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,39}$")


class RegistryError(ValueError):
    """An agent registration is invalid."""


@dataclass(frozen=True)
class CliSpec:
    """An agent's command-line tool. Only the listed commands can be run from the chat."""
    module: str
    commands: tuple = ()


class AgentContext:
    """What an agent gets from the host to build its chat tools and attachment handling."""

    def __init__(self, agent: str, engine, injected: Mapping, settings, shared_llm=None):
        self.agent = agent
        self.engine = engine
        self.injected = dict(injected or {})
        self.settings = settings
        self.shared_llm = shared_llm

    def llm(self):
        from sandbox_blocks.llm import build_llm

        return self.injected.get("llm") or self.shared_llm or build_llm(self.settings)

    def search(self):
        from sandbox_blocks.search import build_search

        return self.injected.get("search") or build_search(self.settings)

    def reader(self):
        from sandbox_blocks.readers import build_reader

        return self.injected.get("read_page") or build_reader(self.settings).read

    def llm_or_none(self):
        return _optional(self.llm)

    def search_or_none(self):
        return _optional(self.search)

    def reader_or_none(self):
        return _optional(self.reader)


def _optional(build):
    try:
        return build()
    except ConfigurationError:
        return None


@dataclass(frozen=True)
class AgentSpec:
    name: str
    title: str
    description: str
    router: APIRouter
    migrations_dir: Optional[Path] = None
    ui_dir: Optional[Path] = None
    has_panel: bool = False
    chat_tools: Optional[Callable[[AgentContext], list]] = None
    attach: Optional[Callable[[AgentContext, str, bytes], dict]] = None
    cli: Optional[CliSpec] = None


def validate_registry(specs: Sequence[AgentSpec]) -> None:
    seen: set[str] = set()
    for spec in specs:
        if not NAME_PATTERN.match(spec.name):
            raise RegistryError(
                f"Agent name {spec.name!r} must be lowercase letters, digits, and hyphens, "
                "start with a letter, and be 2-40 characters"
            )
        if spec.name in seen:
            raise RegistryError(f"Agent name {spec.name!r} is registered more than once (duplicate)")
        seen.add(spec.name)
        if spec.has_panel and not _serves_panel(spec.router):
            raise RegistryError(f"Agent {spec.name!r} declares a panel but serves no GET /panel route")


def _serves_panel(router: APIRouter) -> bool:
    return any(getattr(route, "path", None) == "/panel" and "GET" in getattr(route, "methods", set())
               for route in router.routes)
