# AGENTS.md — agents/

Every agent that runs on the Agentic Sandbox host lives here, one folder per agent. Read the root `AGENTS.md` first.

## The standard (required)

Each agent folder is `agents/<module>/` with these files:

- `service.py`: the use cases and all business rules. Plain functions over the store and injected clients. No HTTP, no printing.
- `store.py`: persistence through `sandbox_host.records` or parameterised SQL. Table names start with `<module>_`.
- `tools.py`: `build_tools(...)` returns `sandbox_blocks.tools.Tool` objects built from the service functions, with typed parameters and docstrings.
- `cli.py`: `main(argv, engine=None) -> int`. Subcommands print one JSON object: `{"ok": true, "result": ...}` or `{"ok": false, "error": ...}`. Exit 0, 1, or 2. This is how other agents call this agent as a subagent.
- `api.py`: `router` and `make_agent_spec()`. Routes call `service.py` only and map errors to status codes.
- `migrations/`: `NNNN_name.sql`, additive. Add `NNNN_name.down.sql` when the rollback is safe. Never edit an applied file.
- `ui/index.html`: uses `/static/sandbox.css` and `/static/sandbox.js`.
- `tests/`: offline tests, including a standard test that API, tools, and CLI agree.
- `AGENTS.md` and `README.md`: the agent's own rules and contract.

Common chat hooks, on `AgentSpec` in `api.py::make_agent_spec()` (add them unless the agent has no useful actions): `chat_tools` (builds the tools from an `AgentContext`; the chat calls them as `<agent>__<tool>`), `cli` (a `CliSpec` allowlist of commands the chat may run; list only commands that are safe to run unattended, and never an upload from a server path), and `attach` (an upload handler, only for an agent that stores files).

Optional, when the agent needs them: `skills/*.md` (guidance loaded into a model prompt), `chat.py` (a conversation layer over the tools, with an offline fallback), `subagents/`, and `evals/` (cases, graders, and a runner that records cost and quality; required once the agent makes model calls that affect users).

## Working here

- Start from the scaffold: `python -m sandbox_host.scaffold <name> --description "..."`. Do not copy an old agent by hand.
- Put rules in `service.py`. The API, tools, and CLI must stay thin.
- Register the agent in `sandbox_app.py` (the scaffold does this). Agents with a dashboard summary set `has_panel=True` and serve `GET /panel` using `sandbox_host.panels.panel`.
- Model and search calls use `sandbox_blocks` through `Settings.from_env()`. Read the model name and keys from the environment.
- Run the agent's tests and the full suite before finishing.

## Existing agents

| Folder | Status |
|---|---|
| `research_brief` | Host agent. Standard service, tools, CLI, and tests. |
| `emeia_dashboard` | Host agent. Standard service, tools, CLI, and tests. |
| `file_reader` | Host agent. Standard service, tools, CLI, and tests. No UI yet (`ui_dir=None`). |
| `people_company_search` | Standard service, tools, JSON CLI, and tests. Stateless, so no migrations yet; API not mounted (decision pending, see its AGENTS.md). |
| `competitor_watch` | The sales radar. Pilot of the standard: service, tools, CLI, API, migrations with rollback. |
| `signal-intelligence` | SignalScout's intelligence agent. Its own project; changes are coordinated with SignalScout. |
