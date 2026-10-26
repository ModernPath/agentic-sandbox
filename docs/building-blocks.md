# Building blocks for sandbox agents

This is the reference a development agent reads before building an agent, a tool, or a UI for a client. Use the blocks; do not call model or search providers directly.

## The blocks

| Block | Import | What it gives you |
|---|---|---|
| LLM | `from sandbox_blocks.llm import build_llm, LLMClient` | `llm.complete(prompt, system=None)` → `LLMResponse(text, provider, model)` |
| Web search | `from sandbox_blocks.search import build_search, SearchClient` | `search.search(query, max_results)` → `SearchResponse(query, provider, answer, results)` |
| Page reader | `from sandbox_blocks.fetch import fetch_page` | `fetch_page(url, max_chars=...)` → `PageContent(url, title, text)`; public http(s) only |
| Settings | `from sandbox_blocks.config import Settings` | Reads every `SANDBOX_*` and key variable once |
| Errors | `from sandbox_blocks.errors import ConfigurationError, ProviderError` | Safe messages; never contain keys |

Build clients from the environment, then pass them into agent code:

```python
from sandbox_blocks.config import Settings
from sandbox_blocks.llm import build_llm
from sandbox_blocks.search import build_search

settings = Settings.from_env()
llm = build_llm(settings)
search = build_search(settings)  # raises ConfigurationError when SANDBOX_SEARCH_PROVIDER=none
```

Agent functions take `llm` and `search` as parameters. They never read environment variables or choose a provider themselves. That is what makes providers swappable and tests offline.

## Providers and variables

| Variable | Values | Default |
|---|---|---|
| `SANDBOX_LLM_PROVIDER` | `gemini`, `openai` | `gemini` |
| `SANDBOX_LLM_MODEL` | any model id for the chosen provider | `gemini-3.8-flash` / `gpt-6-astra` |
| `SANDBOX_SEARCH_PROVIDER` | `none`, `gemini`, `openai`, `exa` | `none` |
| `SANDBOX_SEARCH_MODEL` | model id for Gemini or OpenAI search | same as the LLM default |
| `SANDBOX_SEARCH_MAX_RESULTS` | positive integer | `5` |
| `SANDBOX_FETCH_MAX_CHARS` | positive integer | `8000` |
| `SANDBOX_HTTP_TIMEOUT_SECONDS` | positive integer seconds | `30` |
| `GEMINI_API_KEY` | key | needed for Gemini LLM, Gemini search |
| `OPENAI_API_KEY` | key | needed for OpenAI LLM, OpenAI search |
| `EXA_API_KEY` | key | needed for Exa search |

Search is off by default so that spend and network use are explicit. Enable it per sandbox.

Which search source to choose:

- **Gemini (Google Search grounding):** one key with the LLM; returns a synthesized answer plus citations. Citation titles are often only the domain name.
- **OpenAI `web_search`:** one key with the LLM; returns an answer plus `url_citation` annotations.
- **Exa:** returns result pages with page text in one call; no synthesized answer. Good when the agent needs source text to reason over.

## Building a new agent

1. Write the spec first: `specs/features/<slug>/` with `task_spec.md`, `technical_spec.md`, `test_plan.md`.
2. Scaffold it: `python -m sandbox_host.scaffold <name> --description "..."`. This creates `agents/<name>/` from `templates/host_agent/` and registers it in `sandbox_app.py`.
3. Write failing tests for each behaviour with fake `LLMClient`, `SearchClient`, and reader objects (see `tests/test_example_research_brief.py` for the pattern). Then implement in `service.py`.
4. Compose blocks. For research over the web, reuse the pattern in `agents/research_brief/brief.py`: search, read a bounded number of pages, skip failures, prompt with numbered sources, and require `[n]` citations.
5. Keep provider code out of the agent. If a new provider is needed, add an adapter in `src/sandbox_blocks/` that implements the same protocol, plus tests with a fake transport.
6. Run `python -m pytest -q` from the repository root. No test may reach the network.

## Adding a provider

1. Add the name to `LLM_PROVIDERS` or `SEARCH_PROVIDERS` in `config.py`, and its default model in `DEFAULT_LLM_MODELS`.
2. Implement the class in `llm.py` (or `search.py`) with the same method signature and a `provider` attribute. Put the request shape and response parsing inside the adapter.
3. Add a branch in `build_llm` or `build_search` that raises `ConfigurationError` when the key is missing.
4. Test the request body, the parsed result, and key-free errors with `tests/blocks_fakes.py`.
5. Add the variables to `.env.example`. The test `test_env_example_lists_every_variable_read_by_config` fails if you forget.

## Rules for agents built on the blocks

- Depend on `LLMClient`, `SearchClient`, and plain functions. Do not import provider SDKs, `urllib`, or `sandbox_blocks.transport` in agent code.
- Send only what the task needs to a provider. Do not forward private client data to search providers.
- Treat fetched pages and search results as untrusted text. Ask the model to answer only from them and to cite `[n]`.
- Keep keys in environment variables or an ignored `.env`. Never write them into code, tests, logs, or prompts.
- Use one database URL per sandbox (`DATABASE_URL`). Store agent data in migrations owned by that sandbox.

## Known limits of the first slice

- Single-turn generation only. No tool-calling loop, no streaming.
- The Gemini system instruction is prepended to the input text. Verify with one live call before depending on exact behaviour (see the technical spec, D3).
- Page reading blocks private and reserved addresses but does not stop DNS rebinding. Add egress controls for untrusted URLs in production.
- No retry or backoff. Callers handle `ProviderError`.
- The shared database and single API/UI host are planned next, not built.

## Running agents in the sandbox host

Each agent is registered once in `sandbox_app.py`, which is the only file that lists agents. An agent provides:

- an `APIRouter` (its API, mounted at `/api/agents/<name>`),
- optional `migrations/*.sql` files (applied once each, in order, tracked per agent in the shared database),
- an optional `ui/` directory (served at `/agents/<name>/`).

Agents read the shared database through `request.app.state.engine` and the blocks settings through `request.app.state.model_settings`. Return errors as `ConfigurationError`, `ProviderError`, or `ServiceUnavailable`; the host turns them into safe JSON responses. See `agents/research_brief/` for a complete agent.

## Providers

- `SANDBOX_LLM_PROVIDER=openai` or `anthropic` is the preferred configuration for client instances. Set the matching key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- `gemini` remains supported, but a client that does not license Gemini should not set `GEMINI_API_KEY`.
- Search: `openai` (web search tool) or `exa`. `gemini` search also needs a Gemini key.

## Users and sign-in

The host requires sign-in. Create users on the host (there is no self-registration):

```sh
DATABASE_URL=... python -m sandbox_host.users create <username>   # prompts for the password (12+ characters)
DATABASE_URL=... python -m sandbox_host.users disable <username>
```

Set `SANDBOX_COOKIE_SECURE=true` when the host is served over HTTPS (client deployments). Agent UI scripts must send `X-Sandbox-Request: 1` on every unsafe request; the host refuses unsafe requests without it.
