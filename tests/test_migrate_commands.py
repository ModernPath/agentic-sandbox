from pathlib import Path

import pytest
from sqlalchemy import text

from sandbox_host.migrate import MigrateError, Component, down, status, up
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine


def write(folder: Path, name: str, sql: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(sql)


@pytest.fixture
def components(tmp_path):
    notes = tmp_path / "notes"
    write(notes, "0001_init.sql", "CREATE TABLE notes_items (id INTEGER PRIMARY KEY);")
    write(notes, "0002_tags.sql", "CREATE TABLE notes_tags (item_id INTEGER, tag TEXT);")
    write(notes, "0002_tags.down.sql", "DROP TABLE notes_tags;")
    return [Component("notes", notes)]


def test_status_lists_pending_then_applied(components):  # O-3, O-4
    engine = memory_engine()
    before = status(engine, components)[0]
    assert before["pending"] == ["0001_init.sql", "0002_tags.sql"] and before["applied"] == []
    up(engine, components)
    after = status(engine, components)[0]
    assert after["applied"] == ["0001_init.sql", "0002_tags.sql"] and after["pending"] == []


def test_status_reports_edited_applied_files_without_changing_anything(components):  # O-5
    engine = memory_engine()
    up(engine, components)
    write(components[0].directory, "0001_init.sql", "CREATE TABLE notes_items (id INTEGER PRIMARY KEY, x TEXT);")
    result = status(engine, components)[0]
    assert result["mismatched"] == ["0001_init.sql"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM sandbox_schema_migrations")).scalar() == 2


def test_up_ignores_unknown_components_and_never_applies_down_files(components, tmp_path):  # O-6
    engine = memory_engine()
    up(engine, components + [Component("ghost", tmp_path / "missing")])
    applied = status(engine, components)[0]["applied"]
    assert "0002_tags.down.sql" not in applied
    assert applied == ["0001_init.sql", "0002_tags.sql"]


def test_down_reverts_the_latest_migration_when_a_down_file_exists(components):  # O-7
    engine = memory_engine()
    up(engine, components)
    down(engine, components, "notes")
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        applied = [r[0] for r in conn.execute(text("SELECT name FROM sandbox_schema_migrations WHERE agent='notes'"))]
    assert "notes_tags" not in tables and "notes_items" in tables
    assert applied == ["0001_init.sql"]


def test_down_refuses_without_a_down_file(components):  # O-8
    engine = memory_engine()
    up(engine, [Component("notes", components[0].directory)])
    write(components[0].directory, "0003_extra.sql", "CREATE TABLE notes_extra (id INTEGER);")
    up(engine, components)
    with pytest.raises(MigrateError, match="0003_extra.down.sql"):
        down(engine, components, "notes")


def test_down_refuses_when_nothing_is_applied(components):  # O-9
    with pytest.raises(MigrateError, match="nothing"):
        down(memory_engine(), components, "notes")


def test_down_refuses_unknown_component(components):  # O-10
    with pytest.raises(MigrateError, match="Unknown component"):
        down(memory_engine(), components, "ghost")


def test_up_after_down_reapplies_the_reverted_migration(components):  # O-11
    engine = memory_engine()
    up(engine, components)
    down(engine, components, "notes")
    assert status(engine, components)[0]["pending"] == ["0002_tags.sql"]
    up(engine, components)
    assert status(engine, components)[0]["pending"] == []


def test_pyproject_packages_both_sandbox_packages_and_not_examples():  # O-1
    import tomllib

    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert "sandbox_host" in data["tool"]["setuptools"]["package-data"]
    assert "agents" not in str(data["tool"]["setuptools"]["packages"]["find"])
