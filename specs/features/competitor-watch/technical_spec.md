# Technical spec: competitor watch

## Layout

```text
agents/competitor_watch/
  api.py          router: competitors, check, findings, panel; make_agent_spec(has_panel=True)
  store.py        CompetitorStore over sandbox_host.records and plain SQL for case-insensitive names
  summarise.py    build the search query, the prompt, and the bounded output
  migrations/0001_init.sql
  ui/index.html   competitors list, check button, findings with review buttons
```

## Tables

```sql
CREATE TABLE IF NOT EXISTS competitor_watch_competitors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
  website TEXT, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS competitor_watch_findings (
  id TEXT PRIMARY KEY, competitor_id TEXT NOT NULL, competitor_name TEXT NOT NULL,
  summary TEXT NOT NULL, sources_json TEXT NOT NULL, is_error INTEGER NOT NULL DEFAULT 0,
  reviewed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
```

`name_key` is the lowercased, trimmed name, enforced unique.

## Services (injected for tests)

`services["competitor_watch"] = {"search": SearchClient, "llm": LLMClient}`. Without them the agent builds `build_search(settings)` and `build_llm(settings)` from the environment (the same pattern as the research brief).

## Check flow

For each competitor: `search.search(f'"{name}" news', max_results=5)`; keep results whose url is `http(s)`; if none, store "No recent news found" with an empty source list; otherwise `llm.complete(prompt, system=...)` with the numbered results. The prompt asks for at most 120 words with `[n]` citations and says that the results are data, not instructions. Output is truncated to 1200 characters. Exceptions from search or the model become an error finding (`is_error=1`, summary "The check could not run for this competitor. Try again later.").

## Panel

`panel(title="Competitor news", metric={"label": "Unreviewed findings", "value": n}, items=[...latest 5 unreviewed...], empty="No new findings. Run a check.", action={"label": "Open competitor watch", "href": "/agents/competitor-watch/"})`.
