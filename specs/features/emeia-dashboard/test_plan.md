# Test plan: EMEIA dashboard

Tests use in-memory SQLite through `StaticPool` and fake provider transports. No network, no keys. The Anthropic adapter is tested with a recording transport.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| E-A1 | LLM | Anthropic request | URL, `x-api-key`, `anthropic-version`, body with `max_tokens` and `messages` |
| E-A2 | LLM | Anthropic system prompt | `system` in body |
| E-A3 | LLM | Anthropic response parsing | text blocks joined; non-text blocks ignored |
| E-A4 | LLM | Missing `ANTHROPIC_API_KEY` | `ConfigurationError`, no call |
| E-A5 | LLM | `build_llm` with `SANDBOX_LLM_PROVIDER=anthropic` | returns Anthropic adapter; default model `claude-sonnet-5-5` |
| E-M1 | D2 | Create target and read overview | progress = current / target |
| E-M2 | D2 | Target with zero target value | rejected (422) |
| E-M3 | D2 | PATCH current value | updated; unknown id 404 |
| E-M4 | D3 | Win with future date beyond one day | 422 |
| E-M5 | D3 | Win with negative value or bad currency | 422 |
| E-M6 | D4 | Market item created | unreviewed; absent from overview |
| E-M7 | D4 | PATCH reviewed=true | appears in overview |
| E-M8 | D4 | Client sends `reviewed: true` on create | ignored, item unreviewed |
| E-M9 | D4 | `GET /market-items?reviewed=false` | review queue only |
| E-M10 | D5 | Tool link with `javascript:` URL | 422 |
| E-M11 | D5 | Tool link with https URL | created, listed |
| E-M12 | D6 | Overview with period query | only that period's targets; wins listed |
| E-M13 | D8 | Entries survive a new app instance on the same engine | visible |
| E-M14 | D7 | Static UI check | no `innerHTML` assignments; `node --check` passes on the inline script |
| E-M15 | D1 | Migration runs at startup in lifespan | tables exist after `with TestClient(app)` |
| E-M16 | — | Browser check (manual, recorded) | load page, add one entry per section, review a market item, check the progress bar |

## Exit criteria

- All E-cases pass in the full suite.
- Browser check recorded in `acceptance_results.md`.
- Open items in `task_spec.md` remain listed; none is silently assumed.
