"""Shared fixtures for Meeting Prep. Tests need PYTHONPATH to include the repository's src and agents folders."""

import sys
from pathlib import Path

import pytest

from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine

AGENT_DIR = Path(__file__).resolve().parents[1]
# The helper module lives next to the tests; make it importable in any run, including combined runs.
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def engine():
    engine = memory_engine()
    apply_agent_migrations(engine, "meeting-prep", AGENT_DIR / "migrations")
    return engine
