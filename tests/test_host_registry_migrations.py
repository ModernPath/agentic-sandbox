import pytest
from fastapi import APIRouter
from sqlalchemy import create_engine, text

from sandbox_host.migrations import MigrationError, apply_agent_migrations
from sandbox_host.registry import AgentSpec, RegistryError, validate_registry


def spec(name, **kwargs):
    return AgentSpec(name=name, title=name.title(), description="d", router=APIRouter(), **kwargs)


def memory_engine():
    return create_engine("sqlite+pysqlite:///:memory:")


def write(directory, name, sql):
    (directory / name).write_text(sql)


@pytest.mark.parametrize("bad", ["Research", "has space", "1starts-with-digit", "x", "a" * 41])
def test_registry_rejects_invalid_names(bad):  # S5
    with pytest.raises(RegistryError):
        validate_registry([spec(bad)])


def test_registry_rejects_duplicate_names():  # S6
    with pytest.raises(RegistryError, match="duplicate"):
        validate_registry([spec("notes"), spec("notes")])


def test_apply_runs_files_in_order_and_records_checksums(tmp_path):  # S7
    write(tmp_path, "0001_a.sql", "CREATE TABLE t_a (id INTEGER);")
    write(tmp_path, "0002_b.sql", "CREATE TABLE t_b (id INTEGER);")
    engine = memory_engine()

    applied = apply_agent_migrations(engine, "notes", tmp_path)

    assert applied == ["0001_a.sql", "0002_b.sql"]
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT agent, name, checksum FROM sandbox_schema_migrations ORDER BY name")).all()
        assert [(r[0], r[1]) for r in rows] == [("notes", "0001_a.sql"), ("notes", "0002_b.sql")]
        assert all(len(r[2]) == 64 for r in rows)
        conn.execute(text("SELECT count(*) FROM t_b")).all()


def test_second_apply_executes_nothing(tmp_path):  # S8
    write(tmp_path, "0001_a.sql", "CREATE TABLE t_a (id INTEGER);")
    engine = memory_engine()
    apply_agent_migrations(engine, "notes", tmp_path)
    assert apply_agent_migrations(engine, "notes", tmp_path) == []


def test_edited_applied_file_stops_with_clear_error(tmp_path):  # S9
    write(tmp_path, "0001_a.sql", "CREATE TABLE t_a (id INTEGER);")
    engine = memory_engine()
    apply_agent_migrations(engine, "notes", tmp_path)
    write(tmp_path, "0001_a.sql", "CREATE TABLE t_a (id INTEGER, extra TEXT);")

    with pytest.raises(MigrationError, match="0001_a.sql.*changed"):
        apply_agent_migrations(engine, "notes", tmp_path)


def test_failing_migration_is_not_recorded(tmp_path):  # S10
    write(tmp_path, "0001_bad.sql", "CREATE TABLE t_ok (id INTEGER); INSERT INTO missing_table VALUES (1);")
    engine = memory_engine()

    with pytest.raises(MigrationError):
        apply_agent_migrations(engine, "notes", tmp_path)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM sandbox_schema_migrations")).scalar() == 0


def test_same_file_names_are_tracked_per_agent(tmp_path):  # S11
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    write(first, "0001_init.sql", "CREATE TABLE a_items (id INTEGER);")
    write(second, "0001_init.sql", "CREATE TABLE b_items (id INTEGER);")
    engine = memory_engine()

    assert apply_agent_migrations(engine, "agent-a", first) == ["0001_init.sql"]
    assert apply_agent_migrations(engine, "agent-b", second) == ["0001_init.sql"]
