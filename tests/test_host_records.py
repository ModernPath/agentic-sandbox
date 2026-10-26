import pytest
from sqlalchemy import text

from sandbox_host.records import fetch_many, fetch_one, insert, update
from sandbox_host.testing import memory_engine


@pytest.fixture
def engine():
    engine = memory_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE demo_items (id TEXT PRIMARY KEY, title TEXT, created_at TEXT, done INTEGER)"))
    return engine


def test_insert_and_fetch_round_trip_with_bound_values(engine):  # G-1
    insert(engine, "demo_items", {"id": "a", "title": "x'); DROP TABLE demo_items; --", "created_at": "2026-01-01", "done": 0})
    row = fetch_one(engine, "demo_items", {"id": "a"})
    assert row["title"] == "x'); DROP TABLE demo_items; --"
    assert fetch_one(engine, "demo_items", {"id": "missing"}) is None


@pytest.mark.parametrize("table", ["demo_items; DROP TABLE demo_items", "demo items", "Demo", ""])
def test_unsafe_table_names_are_refused(engine, table):  # G-2
    with pytest.raises(ValueError):
        fetch_many(engine, table)


def test_unsafe_column_names_are_refused(engine):  # G-3
    with pytest.raises(ValueError):
        fetch_one(engine, "demo_items", {"id OR 1=1": "a"})
    with pytest.raises(ValueError):
        insert(engine, "demo_items", {"id; --": "a"})


def test_update_reports_unknown_ids(engine):  # G-4
    insert(engine, "demo_items", {"id": "a", "title": "x", "created_at": "2026-01-01", "done": 0})
    assert update(engine, "demo_items", "a", {"done": 1}) is True
    assert fetch_one(engine, "demo_items", {"id": "a"})["done"] == 1
    assert update(engine, "demo_items", "nope", {"done": 1}) is False


def test_fetch_many_is_newest_first_and_limits_are_enforced(engine):  # G-5
    for i in range(3):
        insert(engine, "demo_items", {"id": f"i{i}", "title": str(i), "created_at": f"2026-01-0{i + 1}", "done": 0})
    assert [r["id"] for r in fetch_many(engine, "demo_items")] == ["i2", "i1", "i0"]
    assert len(fetch_many(engine, "demo_items", limit=2)) == 2
    with pytest.raises(ValueError):
        fetch_many(engine, "demo_items", limit=0)
    with pytest.raises(ValueError):
        fetch_many(engine, "demo_items", limit=501)


def test_signed_in_client_works_without_with_block():  # G-6
    from sandbox_host.app import create_app
    from sandbox_host.config import HostSettings
    from sandbox_host.testing import signed_in_client

    client = signed_in_client(create_app(HostSettings.from_env({})))
    assert client.get("/api/agents").status_code == 200
