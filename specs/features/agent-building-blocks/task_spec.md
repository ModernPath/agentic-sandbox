# Task spec: agent building blocks

**Status:** Draft for implementation · **Owner:** sandbox baseline · **Product scope:** [architecture](../../architecture-tech-stack.md#agent-sandbox-direction)

## Goal

Give every agent built in this sandbox the same provider-independent building blocks, so a development agent can assemble a new agent or UI by composing blocks instead of calling model or search APIs directly.

The first slice covers:

1. **LLM client** with two providers: Google Gemini and OpenAI GPT (Responses API).
2. **Web search client** with three providers: Gemini Google Search grounding, OpenAI `web_search` tool, and Exa.
3. **Page reader** that fetches one public web page and returns bounded plain text.
4. **Env-driven selection** of provider, model, and search source, with no provider name hard-coded in agent code.
5. **Example agent** (`research_brief`) that uses only the blocks, and an **agent template** plus **instructions** for building new agents.

## Scope

In scope:

- `src/sandbox_blocks/`: configuration, LLM, search, page reader, JSON transport.
- `agents/research_brief/`: example agent and CLI using the blocks, runnable offline with fake clients.
- `templates/agent/`: copyable skeleton (agent module, tests, README contract).
- `docs/building-blocks.md`: how to choose and combine blocks, env variables, how to add a provider.
- `.env.example` entries for the new variables.
- Root `AGENTS.md` section telling development agents to use the blocks.

Out of scope for this slice (planned as the next feature, see the technical spec):

- Shared database layer and a single API/UI host that mounts several agents.
- Authentication, per-client tenancy, and deployment templates.
- Migrating the existing `agents/example-agent` and `agents/secure-agent` to the blocks.
- Tool-calling / agent loops inside the LLM block (the first slice is single-turn generation).
- Streaming responses.

## Behavior

- **B1 LLM selection.** `SANDBOX_LLM_PROVIDER` selects `gemini` (default) or `openai`. `SANDBOX_LLM_MODEL` overrides the model for that provider. An unknown provider fails at startup with a message naming the allowed values.
- **B2 LLM call.** `llm.complete(prompt, system=None)` returns text, provider name, and model name. Provider failures raise `ProviderError` with a message that never contains an API key.
- **B3 Search selection.** `SANDBOX_SEARCH_PROVIDER` selects `gemini`, `openai`, `exa`, or `none` (default `none`). `SANDBOX_SEARCH_MODEL` overrides the model for the Gemini and OpenAI search paths. Requesting search with `none` raises `ConfigurationError`.
- **B4 Search call.** `search.search(query, max_results)` returns a `SearchResponse` with the query, provider name, an optional synthesized answer, and a list of `SearchResult(title, url, snippet)` with duplicate URLs removed.
- **B5 Page reading.** `fetch_page(url)` accepts only `http` and `https` URLs, rejects hosts that resolve to loopback, private, link-local, or reserved addresses, and returns `PageContent(url, title, text)` with text capped at `SANDBOX_FETCH_MAX_CHARS`. Scripts, styles, and markup are removed.
- **B6 Keys.** Keys come only from environment variables: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `EXA_API_KEY`. No key is read from files in the repository.
- **B7 Independence.** Agent code imports only `sandbox_blocks` public names. Provider SDKs and provider-specific request shapes stay inside the block modules.
- **B8 Example.** `research_brief` takes a topic and returns a summary with numbered citations to fetched pages. With fake clients it runs with no network and no keys.

## Acceptance criteria

- All behaviors B1–B8 have tests in `test_plan.md` that run with no network and no real keys.
- Changing `SANDBOX_LLM_PROVIDER` or `SANDBOX_SEARCH_PROVIDER` changes the adapter with no code change in the example agent.
- The template passes its own tests after copying and renaming.
- `docs/building-blocks.md` lists every env variable in `.env.example`.

## References

- OpenAI web search (Responses API): `tools: [{"type": "web_search"}]`, answer in `output[].content[].text`, citations in `url_citation` annotations.
- Exa search: `POST https://api.exa.ai/search`, header `x-api-key`, body `{query, numResults, contents: {text: true}}`, results in `results[]`.
- Gemini Google Search: Interactions API `POST https://generativelanguage.googleapis.com/v1beta/interactions` with `tools: [{"type": "google_search"}]`, citations as `url_citation` annotations on `model_output` text.
