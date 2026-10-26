# Task spec: EMEIA dashboard (first client instance)

**Team:** EMEIA sales team · **Status:** Draft for implementation · **Builds on:** [sandbox host](../sandbox-host/task_spec.md), [agent building blocks](../agent-building-blocks/task_spec.md)

## Goal

A team dashboard on the sandbox host that shows, for the EMEIA sales team in one place:

1. **Team targets** following up on the OKR model (1+QR): objectives, key results, target, current value, owner, period.
2. **New customers and sales wins.**
3. **Market and competitor follow-up**, with items produced by an agent and reviewed by a person.
4. **Links to team tools** (for example the product configurator and the quotation reviewer).

The page is served from the sandbox so it can be published on the company intranet. Data enters manually in this slice; agent-fed items arrive through the same API.

## Client constraints

- **No Gemini.** The client does not license Gemini. Models must come from Anthropic or OpenAI. Gemini stays out of this instance's configuration.
- **Manual data entry first.** Input method for bulk data (Excel upload, text dialog, or a connector to CRM) is undecided with the client. This slice implements form entry only.
- **Intranet publication.** The sandbox must run on the client's infrastructure. Authentication is required before the page is exposed beyond loopback; see open items.

## Scope

In scope:

- `agents/emeia_dashboard/`: store, API, migration, and a single-page UI, registered in `sandbox_app.py`.
- An Anthropic LLM adapter in the building blocks, so the market agent can run on Anthropic (`SANDBOX_LLM_PROVIDER=anthropic`).
- A client configuration note in `.env.example` (provider choice, no Gemini key).

Out of scope (open items, see below):

- Authentication and per-user access.
- Excel or other bulk upload; CRM and tool connectors.
- Scheduled email summaries.
- Automatic generation of market items by an agent (the API accepts items from any source; wiring the research brief agent is a follow-up).
- Editing and deleting entries (only create and update of targets' current value).

## Behavior

- **D1 Sections.** The dashboard has four sections, each backed by its own table: targets, wins, market items, and tool links.
- **D2 Targets.** A target has period (for example `2026-Q4`), objective, key result, target value, current value, unit, and owner. Progress is `current / target` when target is positive, otherwise unknown. Current value can be updated.
- **D3 Wins.** A win has customer, description, optional value and currency, and won-on date (ISO date, not in the future beyond one day).
- **D4 Market items.** A market item has kind (`market` or `competitor`), title, summary, optional source URL, and a review flag `reviewed` (default false). Agent-fed items start unreviewed; a person marks them reviewed. Only reviewed items appear in the page's default view.
- **D5 Tool links.** A tool link has label and URL. Only `http` and `https` URLs are accepted.
- **D6 Overview.** One endpoint returns all four sections for the current period in one response. The page renders from it.
- **D7 Safe rendering.** All text from users or agents is rendered as text. Links are clickable only for `http(s)` URLs.
- **D8 Storage.** Data lives in the shared sandbox database through per-agent migrations.

## Acceptance criteria

- D1–D8 have tests in `test_plan.md`, run without network access and without provider keys.
- The Anthropic adapter passes its request and parsing tests; a live smoke call is recorded separately when a key is available.
- The page loads on the sandbox host, lists all four sections, accepts entries for each, and shows only reviewed market items by default. Browser check recorded in `acceptance_results.md`.

## Open items for the client

1. Bulk data input: Excel upload, text dialog, or CRM connector. Owner: client IT with the sandbox team.
2. Authentication and hosting on the intranet. Owner: client IT (session with their Group IT manager was proposed).
3. Email subscription for a monthly summary: format, sender, and recipients.
4. Which tool links and which competitors and market topics to track.
