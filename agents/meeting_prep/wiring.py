"""Builds meeting prep's clients from the environment: building blocks and peer agents.

Blocks that are not configured are None; the service turns that into a gap message.
"""

from __future__ import annotations

from typing import Mapping, Optional

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError
from sandbox_host.cli_bridge import default_pythonpath

from . import peers


def peer_environ(environ: Mapping[str, str], engine=None) -> dict:
    """The environment for peer commands: the same database as this process, and the agents on the path."""
    env = dict(environ)
    env.setdefault("PYTHONPATH", default_pythonpath())
    if engine is not None:
        env["DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
    return env


def build_clients(environ: Mapping[str, str], engine=None, injected: Optional[Mapping] = None,
                  settings: Optional[Settings] = None) -> dict:
    from sandbox_blocks.llm import build_llm
    from sandbox_blocks.readers import build_reader
    from sandbox_blocks.search import build_search

    injected = dict(injected or {})
    settings = settings or Settings.from_env(environ)
    env = peer_environ(environ, engine)
    return {
        "search": injected["search"] if "search" in injected else _optional(lambda: build_search(settings)),
        "read_page": injected["read_page"] if "read_page" in injected
        else _optional(lambda: build_reader(settings).read),
        "llm": injected["llm"] if "llm" in injected else _optional(lambda: build_llm(settings)),
        "signals": injected.get("signals") or peers.radar_signals(env),
        "notes": injected.get("notes") or peers.read_notes(env),
    }


def _optional(build):
    try:
        return build()
    except ConfigurationError:
        return None
