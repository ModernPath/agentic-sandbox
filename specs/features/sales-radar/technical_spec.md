# Technical spec: Sales radar

## Data

Migration `0002_radar.sql` (additive, owned by `competitor_watch`):

- `competitor_watch_checks(id, competitor_id, outcome, new_signals, created_at)`; index on `(competitor_id, created_at)`.
- `competitor_watch_signals(id, competitor_id, competitor_name, headline, category, importance, summary, source_title, source_url, status DEFAULT 'new', created_at)`; unique index `(competitor_id, source_url)` (dedup) and index `(status, created_at)`.

The old `competitor_watch_findings` table stays (additive rule). No code writes it after this feature; its rows are not migrated.
Down migration drops both new tables.

## Check pipeline (service.py)

1. `seen = store.seen_urls(competitor_id)`.
2. Search `"<name>" news`, `max_results=5`. Drop results with a non-http(s) URL or a URL in `seen`. Empty after filtering → outcome `no_new_sources` (if there were results) or `no_news` (if the search returned none; recorded as `no_new_sources` too, to keep outcomes few).
3. Read up to 3 remaining pages with `read_page`; fall back to the snippet.
4. Ask the model for JSON (system prompt: data, not instructions; numbered results; return only a JSON array). Parse the first JSON array in the output. Anything unparseable → outcome `no_signals`. Each element validated as in R2; bounded to 10 signals per check.
5. Store signals and one check row. Duplicate insert (race) is ignored via the unique index.

Errors from search or model → `error` check row with a fixed message; the provider text is never stored.

## Dashboard (service.py + store.py)

Aggregates use SQL on ISO-8601 UTC strings (lexically ordered). `daily` and `by_category` are built in Python from the rows returned for the window, so SQL stays portable between SQLite (tests) and PostgreSQL.

## Chat (chat.py)

`chat.reply(llm, tools, message, history)` calls `llm.run_with_tools(message, system=CHAT_SYSTEM, history=history, tools=tools, max_calls=6)`. History is validated and mapped to the block's history shape. `ToolRun.tool_calls` names are returned. Tool handlers return data or `{"error": ...}`; they never raise.

## Home redirect (sandbox_host/app.py)

`create_app(..., home_path=None)`. When set, `GET /` redirects (302) to `home_path`. Auth still applies: unauthenticated requests go to `/login` first. `sandbox_app.py` passes `home_path="/agents/competitor-watch/"`.

## UI

`agents/competitor_watch/ui/index.html` becomes the radar: vanilla JS using the shared kit (`Sandbox.api`, `el`, `link`, `banner`). Sections: KPI tiles, 14-day SVG bar chart, category bars (SVG), competitor table, signal list with filters and Review/Dismiss, chat panel, "Other agents" links. Text is set with `textContent` only. Layout: one column under 720 px.

## Decisions

- Dedup is by source URL per competitor, not by headline: the same story on two sites still counts once per URL, which keeps the rule simple and checkable.
- Model JSON is validated, not trusted: categories and importance are enums; numbers must refer to a real result.
- The radar is the competitor-watch agent's UI, not a new agent. Renaming the folder is not worth the churn now.
