"""Migration status, up, and rollback for the host and every registered agent.

  python -m sandbox_host.migrate status --app sandbox_app
  python -m sandbox_host.migrate up --app sandbox_app
  python -m sandbox_host.migrate down --app sandbox_app --component <name>

--app names the composition root module (its AGENTS list). DATABASE_URL must be set.
Rollback runs NNNN_name.down.sql for the component's latest applied migration, in one transaction,
and removes its tracking row. Without a down file, rollback is refused.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .app import HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR
from .migrations import TRACKER_DDL, MigrationError, _checksum, _execute_script, apply_agent_migrations


class MigrateError(ValueError):
    """A migration command cannot run. The message says why."""


@dataclass(frozen=True)
class Component:
    name: str
    directory: Path


def up_files(directory: Path) -> list[Path]:
    return sorted(p for p in Path(directory).glob("*.sql") if not p.name.endswith(".down.sql"))


def _applied(engine: Engine, name: str) -> dict[str, str]:
    with engine.begin() as conn:
        conn.execute(text(TRACKER_DDL))
        rows = conn.execute(text("SELECT name, checksum FROM sandbox_schema_migrations WHERE agent = :a ORDER BY name"),
                            {"a": name}).all()
    return {row[0]: row[1] for row in rows}


def status(engine: Engine, components: Sequence[Component]) -> list[dict]:
    report = []
    for component in components:
        applied = _applied(engine, component.name)
        files = up_files(component.directory) if component.directory.is_dir() else []
        names = [f.name for f in files]
        report.append({
            "name": component.name,
            "applied": [n for n in names if n in applied],
            "pending": [n for n in names if n not in applied],
            "mismatched": [f.name for f in files if f.name in applied and applied[f.name] != _checksum(f)],
        })
    return report


def up(engine: Engine, components: Sequence[Component]) -> dict[str, list[str]]:
    applied = {}
    for component in components:
        if component.directory.is_dir():
            applied[component.name] = apply_agent_migrations(engine, component.name, component.directory)
    return applied


def down(engine: Engine, components: Sequence[Component], name: str) -> str:
    component = next((c for c in components if c.name == name), None)
    if component is None:
        raise MigrateError(f"Unknown component: {name}")
    applied = sorted(_applied(engine, name))
    if not applied:
        raise MigrateError(f"Nothing is applied for {name}; nothing to roll back")
    latest = applied[-1]
    down_file = component.directory / (Path(latest).stem + ".down.sql")
    if not down_file.is_file():
        raise MigrateError(f"No rollback file {down_file.name}; cannot revert {latest}")
    try:
        with engine.begin() as conn:
            _execute_script(conn, down_file.read_text(encoding="utf-8"))
            conn.execute(text("DELETE FROM sandbox_schema_migrations WHERE agent = :a AND name = :n"),
                         {"a": name, "n": latest})
    except Exception:  # driver messages can contain data; keep the reason generic
        raise MigrateError(f"Rollback of {latest} failed and was rolled back") from None
    return latest


def components_for(app_module: str) -> list[Component]:
    module = importlib.import_module(app_module)
    components = [Component(HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR)]
    for agent in getattr(module, "AGENTS", []):
        if agent.migrations_dir is not None:
            components.append(Component(agent.name, Path(agent.migrations_dir)))
    return components


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sandbox_host.migrate")
    parser.add_argument("command", choices=["status", "up", "down"])
    parser.add_argument("--app", default="sandbox_app", help="composition root module with AGENTS")
    parser.add_argument("--component", help="component name (required for down)")
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    from sqlalchemy import create_engine

    engine = create_engine(url, pool_pre_ping=True)
    components = components_for(args.app)
    try:
        if args.command == "status":
            for row in status(engine, components):
                print(f"{row['name']}: applied {len(row['applied'])}, pending {len(row['pending'])}"
                      + (f", MISMATCHED {row['mismatched']}" if row["mismatched"] else ""))
                for name in row["pending"]:
                    print(f"  pending: {name}")
        elif args.command == "up":
            for name, applied in up(engine, components).items():
                print(f"{name}: applied {len(applied)}")
        else:
            if not args.component:
                parser.error("down needs --component")
            print(f"rolled back {down(engine, components, args.component)}")
    except (MigrateError, MigrationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
