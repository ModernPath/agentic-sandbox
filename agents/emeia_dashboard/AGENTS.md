# AGENTS.md — emeia_dashboard

Rules for AI agents and developers working on this agent. Read the root `AGENTS.md` and `agents/AGENTS.md` first.

## What this agent is

The EMEIA sales team's dashboard: team OKR targets with progress, new customers and wins, market and competitor findings that a person approves, and team tool links. Data enters by form, by command line, or by tool. Output is the page on the intranet, with email summaries planned later.

## Layout

- `service.py`: overview, targets, wins, market items, review, tool links, and the panel. Rules come from `models.py`.
- `models.py`: validation rules (ranges, dates, safe URLs, quarter format). Change rules here, with tests.
- `store.py`: the `emeia_dashboard_*` tables.
- `tools.py`: show the overview, add and update targets, add wins, add market items for review, list the review queue. There is no approve tool.
- `cli.py`: subcommands with JSON output, including `market-approve`, which a person runs.
- `api.py`: routes over the service.
- `migrations/`: `0001_dashboard.sql`.
- `ui/index.html`: the page.

## Change rules

- Model-created market items are unreviewed. Never add a model tool, route, or command that approves them without a person.
- Period bounds, currency codes, and future dates are checked by `models.py`. Keep the checks there.
- Client data (targets, wins, customer names) stays on the client's instance. Do not put it in fixtures or docs.
- Keep the `emeia_dashboard_` table prefix for new tables.
