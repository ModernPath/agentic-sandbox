# Technical spec: EMEIA dashboard

## Layout

```text
agents/emeia_dashboard/
  api.py          APIRouter (/overview, /targets, /wins, /market-items, /tool-links) and make_agent_spec()
  store.py        DashboardStore over SQLAlchemy Core text SQL
  models.py       pydantic request models and validation (dates, URLs, ranges)
  migrations/0001_dashboard.sql
  ui/index.html   single page: four sections, forms, progress bars
src/sandbox_blocks/llm.py   + AnthropicLLM (Messages API)
```

Agent name: `emeia-dashboard`. API base: `/api/agents/emeia-dashboard`. UI: `/agents/emeia-dashboard/`.

## Data model (portable SQL: TEXT ids, ISO text dates, REAL numbers)

```sql
CREATE TABLE IF NOT EXISTS emeia_dashboard_targets (
  id TEXT PRIMARY KEY, period TEXT NOT NULL, objective TEXT NOT NULL, key_result TEXT NOT NULL,
  target_value REAL NOT NULL, current_value REAL NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emeia_dashboard_wins (
  id TEXT PRIMARY KEY, customer TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  value REAL, currency TEXT NOT NULL DEFAULT '', won_on TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emeia_dashboard_market_items (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
  source_url TEXT, reviewed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emeia_dashboard_tool_links (
  id TEXT PRIMARY KEY, label TEXT NOT NULL, url TEXT NOT NULL, created_at TEXT NOT NULL);
```

Period is the current quarter by default (computed from UTC date) and can be passed as `?period=`.

## Validation (models.py)

- Targets: `target_value > 0`, `current_value >= 0`, lengths capped (text 200, summary 2000).
- Wins: `won_on` parsed as ISO date and rejected if more than one day in the future; `value >= 0` when given; currency a 3-letter code when given.
- URLs: parsed with `urllib.parse`; scheme must be `http` or `https`; reject control characters; max 2000 characters.

## API

| Method | Path | Behaviour |
|---|---|---|
| GET | `/overview?period=` | `{period, targets:[…with progress], wins:[…], market_items:[reviewed only], tool_links:[…]}` |
| POST | `/targets` | create (201) |
| PATCH | `/targets/{id}` | update `current_value` only (404 if unknown) |
| POST | `/wins` | create (201) |
| POST | `/market-items` | create unreviewed (201); `reviewed` is not accepted from the client |
| PATCH | `/market-items/{id}` | `{reviewed: true}` only |
| POST | `/tool-links` | create (201) |

`GET /market-items?reviewed=false` returns the review queue.

## Market agent

Market items enter through `POST /market-items` from any source: a person, a script, or the research brief agent's output. The dashboard does not import or query the research brief tables, so the two agents stay independent. Deciding which topics to research is a client open item.

## Anthropic adapter

`AnthropicLLM` posts to `https://api.anthropic.com/v1/messages` with headers `x-api-key` and `anthropic-version: 2023-06-01`. Body: `{model, max_tokens, messages:[{role:"user", content: prompt}]}` plus `system` when given. `max_tokens` is required by the API and defaults to 2048. Text is the concatenated `text` of content blocks with type `text`. Selected by `SANDBOX_LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY`; default model `claude-sonnet-5-5`, overridable with `SANDBOX_LLM_MODEL`.

## UI

Single page with inline CSS and JS. Four panels (targets with progress bars, wins, market items with review button, tool links). All rendering uses `textContent`; progress bar width is set from a number clamped to 0–100. Forms validate in the browser for convenience only; the server is authoritative.

## Decisions

- **E1 Separate tables, one agent.** One agent owns the four tables so the migration and API stay in one place.
- **E2 Review flag on market items.** Agent output is never shown to the team until a person reviews it.
- **E3 No delete in this slice.** Mistakes are fixed by correcting values; deletion needs an audit decision with the client.
- **E4 Quarter period.** Default period follows the calendar quarter in UTC; OKRs for the client are quarterly.
