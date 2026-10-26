import os
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from sandbox_host.migrations import apply_agent_migrations

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="needs disposable PostgreSQL (TEST_DATABASE_URL)")


def test_concurrent_apply_from_two_engines_runs_each_file_once(tmp_path):  # S12
    (tmp_path / "0001_counter.sql").write_text(
        "CREATE TABLE IF NOT EXISTS host_lock_probe (id SERIAL PRIMARY KEY, note TEXT);"
        "INSERT INTO host_lock_probe (note) VALUES ('ran');"
    )
    engines = [create_engine(URL), create_engine(URL)]
    with engines[0].begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS host_lock_probe"))
        conn.execute(text("DROP TABLE IF EXISTS sandbox_schema_migrations"))
    results, errors = [], []

    def run(engine):
        try:
            results.append(apply_agent_migrations(engine, "lock-test", tmp_path))
        except Exception as error:  # surfaced below
            errors.append(error)

    threads = [threading.Thread(target=run, args=(e,)) for e in engines]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sorted(len(r) for r in results) == [0, 1]
    with engines[0].connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM host_lock_probe")).scalar() == 1


def test_failing_migration_rolls_back_its_statements(tmp_path):  # S10 (transactional part)
    (tmp_path / "0001_bad.sql").write_text(
        "CREATE TABLE IF NOT EXISTS host_rollback_probe (id INTEGER);"
        "INSERT INTO missing_table_for_rollback VALUES (1);"
    )
    engine = create_engine(URL)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS host_rollback_probe"))
        conn.execute(text("DROP TABLE IF EXISTS sandbox_schema_migrations"))
    with pytest.raises(Exception):
        apply_agent_migrations(engine, "rollback-test", tmp_path)
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('host_rollback_probe')")).scalar()
        assert exists is None
