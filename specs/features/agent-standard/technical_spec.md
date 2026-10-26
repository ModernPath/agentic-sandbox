# Technical spec: agent standard

## Layout (per agent)

```text
agents/<module>/
  service.py     use cases (pure functions over store + injected clients)
  store.py       persistence through sandbox_host.records and parameterised SQL
  tools.py       TOOLS: list of sandbox_blocks.tools.Tool built from service functions
  cli.py         main(argv, engine=None, services=None) -> int; JSON envelope on stdout
  api.py         HTTP routes calling service functions; error mapping
  migrations/    additive SQL, optional NNNN_name.down.sql
  ui/            page on the shared kit
  tests/         service, tools, cli, api, equivalence
```

## Service signatures (competitor-watch)

- `add_competitor(store, name, website, note) -> dict`
- `list_competitors(store) -> list[dict]`
- `delete_competitor(store, competitor_id) -> bool`
- `run_check(store, search, llm, read_page, competitor_id=None) -> int` (number checked)
- `list_findings(store, reviewed=False) -> list[dict]`
- `review_finding(store, finding_id) -> bool`
- `panel(store) -> dict`

Validation (names, website scheme, lengths) lives in the service and raises `ValueError` with a safe message. The API maps `ValueError` to 422 and duplicates to 409 through a dedicated `DuplicateError`.

## Tools

`TOOLS` is built by `build_tools(store, search, llm, read_page, on_call=None)`. Parameter types come from the function signatures (`tool_from_function`). Descriptions come from the docstrings. Tools never accept a user identifier; this agent has no per-user data.

## CLI

`python -m competitor_watch.cli <command> ...`. Commands: `add --name N [--website U] [--note T]`, `list`, `delete --id ID`, `check [--id ID]`, `findings [--reviewed]`, `review --id ID`. The CLI builds the store from `DATABASE_URL`; `main()` accepts an engine and services for tests. Search and model clients are built from settings when not injected.

## Decisions

- **A1 One service, three callers.** Keeps behaviour in one place; the equivalence tests catch drift.
- **A2 Subagent = CLI call.** Makes every agent callable on its own and keeps failures isolated.
