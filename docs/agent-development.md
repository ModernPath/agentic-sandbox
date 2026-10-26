# Building an agent on the sandbox

This is the workflow for a developer or a development agent. The sandbox provides the host, the database, sign-in, the building blocks, and a scaffold. You provide the domain: the data, the rules, and the screens.

Read `AGENTS.md` (root) and `agents/AGENTS.md` first. They are the rules; this page is the walkthrough.

## 1. Write the spec

Create `specs/features/<agent>/` with three files, before any behaviour:

- `task_spec.md`: intended behaviour, scope, acceptance criteria.
- `technical_spec.md`: data model, API, material decisions.
- `test_plan.md`: the cases you will test, with exit criteria.

Reconcile with the product documents in `specs/` first.

## 2. Scaffold

```sh
python -m sandbox_host.scaffold <agent-name> --description "What it does"
```

This creates `agents/<module>/` with the standard: `service.py`, `tools.py`, `cli.py`, `api.py`, `store.py`, `models.py`, migrations (with a rollback file), the UI page, `README.md` and `AGENTS.md` for the agent, and tests including the standard test that API, tools, and CLI agree. It also registers the agent in `sandbox_app.py`. It refuses to overwrite an existing folder. The generated tests pass as they are.

Run them from the repository root:

```sh
PYTHONPATH=src:agents python -m pytest -q agents/<module>/tests
```

## 3. Implement test-first

For each behaviour in the test plan:

1. Write a failing test. Confirm it fails for the expected reason.
2. Make the smallest change that passes.
3. Refactor while green.

Use `sandbox_host.testing` (`memory_engine`, `signed_in_client`) for API tests. They run offline and sign in as a test user.

## 4. Conventions the tests enforce

- **Table names** start with the agent's module name: `<module>_<entity>`. Migrations live in the agent's `migrations/` folder and run once each, in order.
- **Storage** goes through `sandbox_host.records` (`insert`, `fetch_one`, `fetch_many`, `update`) or plain SQL with bound parameters. Never build SQL from user input. Identifiers must be simple lowercase names.
- **Ids** are text UUIDs. **Timestamps** are ISO-8601 UTC text. **JSON** is stored as text.
- **Cross-agent access:** an agent does not read or write another agent's tables. Share data through the API or a shared service.
- **Sign-in:** every API and page is behind the host's sign-in. Do not add public routes without a spec entry.
- **Unsafe requests** from the UI (POST, PATCH, PUT, DELETE) send the header `X-Sandbox-Request: 1`. The host refuses them without it.
- **Errors** are safe JSON: `{"error": "..."}` or FastAPI's `detail`. Never return stack traces, keys, or raw provider messages.
- **Models and keys:** use `sandbox_blocks` (LLM, search, page reader, embeddings, files) through `Settings.from_env()`. Do not import provider SDKs or hard-code model names.
- **Personal data:** none by default. Anything that stores personal data needs a retention decision in the spec first.

## 5. Register and verify

- The scaffold registers the agent. Check `sandbox_app.py` after adding routers or changing the spec's name.
- Run the whole suite: `python -m pytest -q` from the repository root.
- Start the host and check the UI in a browser: sign in, use the main flow, sign out. Record the result in the agent's `acceptance_results.md`.

## 6. Document

Update the agent's `README.md` contract: purpose, inputs, outputs, data, side effects, blocks used, configuration.

## 7. Make it usable from the common chat

The front page chat calls every agent's tools. To take part, set these on `AgentSpec` in `api.py`:

- `chat_tools=_chat_tools`: a function `ctx -> list[Tool]` that builds the agent's tools from `ctx.engine`, `ctx.llm_or_none()`, `ctx.search_or_none()`, and `ctx.reader_or_none()`. Tool names become `<agent>__<tool>`. Tool docstrings are what the model reads: say what each tool does and what its arguments mean.
- `cli=CliSpec(module="<agent>.cli", commands=(...))`: the commands the chat may run through `run_agent_cli`. Commands run as a subprocess with no shell and a 60-second timeout. Leave out any command that reads a server path or approves something.
- `attach=_attach` (only for an agent that stores files): `(ctx, filename, data) -> record`. Raise `AgentInputError` for 413, 415, and 422 cases.

Tests: check the tool names and that a refused command gets a fixed message. Spec: `specs/features/common-chat/`.

## Where things are

| What | Where |
|---|---|
| Host, registry, sign-in | `src/sandbox_host/` |
| Storage helper, test kit | `src/sandbox_host/records.py`, `src/sandbox_host/testing.py` |
| Model access, tools, search, readers, embeddings, files | `src/sandbox_blocks/` |
| Agent template | `templates/host_agent/` |
| Scaffold command | `python -m sandbox_host.scaffold` |
| Operator commands | `python -m sandbox_host.users` (create, disable, enable) |
| Host agents | `agents/research_brief`, `agents/emeia_dashboard`, `agents/file_reader`, `agents/competitor_watch` |
| Signal intelligence (SignalScout agent) | `agents/signal-intelligence` |

## Operating the sandbox

- **Install:** from the repository root, `pip install -e .` (or `pip install .` for a fixed copy). This installs `sandbox_host` and `sandbox_blocks`.
- **Migrations:** `python -m sandbox_host.migrate status --app sandbox_app` shows applied, pending, and mismatched migrations for the host and every agent. `up` applies pending migrations. `down --component <name>` reverts the latest applied migration, only if a matching `NNNN_name.down.sql` exists.
- **Container:** `Dockerfile.host` builds the host image. `compose.sandbox.yaml` runs it with PostgreSQL. Set `SANDBOX_DB_PASSWORD` (and optionally `SANDBOX_PORT`, `SANDBOX_COOKIE_SECURE`) in `.env`, then `docker compose -f compose.sandbox.yaml up -d --build`.
- **Users:** create them with `python -m sandbox_host.users create <name>` (or inside the container with `docker compose exec host ...`).
