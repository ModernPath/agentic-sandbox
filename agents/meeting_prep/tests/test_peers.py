"""Peer calls: meeting prep runs other agents' command-line tools, never their tables (MP-17)."""

import json
import sys

import pytest
from sqlalchemy import create_engine

from meeting_prep import peers
from sandbox_host.cli_bridge import default_pythonpath


@pytest.fixture
def radar_db(tmp_path):
    """A SQLite file with the radar's schema and one signal, set up through the radar's own code (test setup only)."""
    from competitor_watch import service as radar
    from competitor_watch.api import make_agent_spec as radar_spec
    from competitor_watch.store import CompetitorStore
    from sandbox_host.migrations import apply_agent_migrations

    url = f"sqlite+pysqlite:///{tmp_path / 'radar.sqlite'}"
    engine = create_engine(url)
    spec = radar_spec()
    apply_agent_migrations(engine, spec.name, spec.migrations_dir)
    store = CompetitorStore(engine)
    competitor = radar.add_competitor(store, "Acme", None, "")
    store.add_signals(competitor, [{"headline": "Acme launches", "category": "product", "importance": "high",
                                    "summary": "New line", "source_title": "News",
                                    "source_url": "https://news.example/acme"}])
    engine.dispose()
    return url


def environ(url):
    return {"PATH": "", "PYTHONPATH": default_pythonpath(), "DATABASE_URL": url, "SECRET_TOKEN": "x"}


def test_radar_signals_come_from_the_radar_cli(radar_db):
    signals = peers.radar_signals(environ(radar_db))()
    assert [s["headline"] for s in signals] == ["Acme launches"]


def test_a_failing_peer_raises_a_fixed_error(tmp_path):
    with pytest.raises(peers.PeerError) as caught:
        peers.run_peer("competitor_watch.cli", ["signals", "--status", "bogus"], environ(f"sqlite:///{tmp_path}/x.db"))
    assert str(caught.value) == "The other agent's command failed."


def test_a_peer_that_prints_no_json_raises(monkeypatch):
    class Done:
        returncode, stdout, stderr = 0, "not json", ""
    monkeypatch.setattr(peers.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(peers.PeerError, match="did not return JSON"):
        peers.run_peer("x.cli", [], {})


def test_peer_runs_without_a_shell_with_a_filtered_environment(monkeypatch):
    seen = {}

    class Done:
        returncode, stdout, stderr = 0, json.dumps({"ok": True, "result": [1]}), ""

    def fake_run(argv, **kwargs):
        seen.update(kwargs, argv=argv)
        return Done()
    monkeypatch.setattr(peers.subprocess, "run", fake_run)
    assert peers.run_peer("file_reader.cli", ["read", "--id", "f1"], {"DATABASE_URL": "u", "SECRET_TOKEN": "x"}) == [1]
    assert seen["argv"] == [sys.executable, "-m", "file_reader.cli", "read", "--id", "f1"]
    assert seen["shell"] is False and seen["timeout"] == peers.TIMEOUT_SECONDS
    assert "SECRET_TOKEN" not in seen["env"] and seen["env"]["DATABASE_URL"] == "u"


def test_read_notes_uses_file_reader_read(monkeypatch):
    calls = []
    monkeypatch.setattr(peers, "run_peer", lambda module, args, env: calls.append((module, args))
                        or {"id": "f1", "filename": "n.txt", "text": "hello", "mime": "text/plain"})
    assert peers.read_notes({})("f1") == {"id": "f1", "filename": "n.txt", "text": "hello"}
    assert calls == [("file_reader.cli", ["read", "--id", "f1"])]
