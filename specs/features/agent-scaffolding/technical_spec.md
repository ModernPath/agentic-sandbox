# Technical spec: agent scaffolding

## Layout

```text
src/sandbox_host/
  records.py      whitelisted insert/fetch/update helpers over SQLAlchemy text()
  testing.py      memory_engine(), signed_in_client(app), make_user()
  scaffold.py     python -m sandbox_host.scaffold <name>
templates/host_agent/
  README.md.tpl, api.py.tpl, models.py.tpl, store.py.tpl, migrations/0001_init.sql.tpl,
  ui/index.html.tpl, tests/test_api.py.tpl, tests/conftest.py.tpl
docs/agent-development.md
sandbox_app.py    contains the markers  # <scaffold:imports>  and  # <scaffold:agents>
```

Template files end in `.tpl` and are rendered with `string.Template` placeholders: `$name` (kebab-case agent name), `$module` (snake_case), `$Title`, `$table` (snake_case prefix). Rendering writes the file without `.tpl`.

## Names

- Agent name: `^[a-z][a-z0-9-]{1,39}$` (the host's registry rule).
- Module: name with hyphens replaced by underscores. Must not already exist under `agents/`, or as an importable package.
- Table prefix: the module name. Tables are `<module>_<entity>`.

## records helper

```python
insert(engine, table, row: dict) -> dict
fetch_one(engine, table, where: dict) -> dict | None
fetch_many(engine, table, where: dict | None = None, order_by: str = "created_at DESC", limit: int = 100) -> list[dict]
update(engine, table, id_value, values: dict) -> bool
```
`table`, every key of `row`/`where`/`values`, and `order_by` (a column name plus optional DESC) must match `^[a-z_][a-z0-9_]*$`. Values are bound. `limit` is 1–500.

## testing helpers

- `memory_engine()`: SQLite in memory with `StaticPool`.
- `signed_in_client(app)`: applies the host migration, creates a test user, logs in, and returns a client that sends `X-Sandbox-Request`. Works without `with`.
- The existing `tests/host_test_client.py` keeps working and imports from this module.

## Scaffold rules

- The template's tests import `sandbox_host.testing` and `make_agent_spec` from the generated package, so they run unchanged.
- Registration inserts `from <module>.api import make_agent_spec as make_<module>_spec` after `# <scaffold:imports>`, and `    make_<module>_spec(),` after `# <scaffold:agents>`. If a marker is missing, the command fails before writing anything.
