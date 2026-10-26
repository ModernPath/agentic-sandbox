# Task spec: CRM platform with agent extensions

**Status:** Proposed (design only; no code yet) · **Builds on:** [architecture](../../architecture-tech-stack.md), [agent standard](../agent-standard/task_spec.md), [agent scaffolding](../agent-scaffolding/task_spec.md), [common chat](../common-chat/task_spec.md)
**Decision record:** the product is a CRM with signals, competitor following, and extensible agents. The sales radar and other agents become extensions of it.

## Goal

Each client instance is a CRM. Its core holds a small, stable data model (accounts, contacts, opportunities, activities, follows, signals, notifications). Agents extend that core: they bring their own migrations and tables, add custom fields to core records, react to core events, and contribute tools, a command line, a front-page card, and a full page of their own. A sales person can install an agent that connects Slack, or one that builds a custom report and imports a spreadsheet, without changing the core.

## Who uses it

- **Sales people** use the front page, record pages, the chat, and agent cards. They follow accounts and competitors, review signals, and install agents from a catalogue.
- **Operators** (one or two per client) approve agents' permissions, manage users and secrets, and watch the audit log.
- **Agent authors** are developers, or sales people working through the chat with a developer's review (see "Two ways to build an agent").

## Behaviour

- **P1 Core model.** The core owns these entities, and only the core writes them: accounts (type: customer, prospect, competitor, partner), contacts, opportunities (stage, amount, close date), activities (note, call, meeting, task), follows (a user follows an account or a topic), signals, notifications, drafts, and the audit log. Each carries `owner_id`, timestamps, and an `archived` flag. Deletion is archiving; hard delete is an operator action with an audit entry.
- **P2 Signals.** A signal is something observed about a subject: a news item, a job posting, a price change, an upload row, a Slack message that matters. It has a subject (account or topic), a source (kind, reference, URL when public), a category, an importance, and a status (new, reviewed, dismissed). Any agent may create signals through the core API; each one records the creating agent.
- **P3 Following and notifications.** When a signal is created for an account, every user following that account (or a topic it matches) gets a notification. Notifications are shown in the inbox and on the front page. Following a competitor is the same as following any account.
- **P4 Agents extend, not fork.** An agent may:
  - add custom fields to core entity types (stored in core, typed, declared in its manifest);
  - own tables prefixed with its name, created by its migrations;
  - subscribe to core events (`signal.created`, `account.created`, `opportunity.stage_changed`, `activity.created`);
  - contribute chat tools, a CLI, HTTP routes, a front-page card, a full page, and record panels (small sections on an account or opportunity page);
  - create drafts for outward actions.
  An agent may not read or write another agent's tables, and may not write core tables except through the core API.
- **P5 Manifest.** Every agent declares a manifest: name, version, title, description, entities extended, tables, event subscriptions, tools, CLI commands, cards (size small or large), pages, record panels, scopes requested, and network hosts it will call. The host reads the manifest before the agent loads.
- **P6 Install and permissions.** An operator installs an agent from the catalogue or from the repository. The host shows the manifest's scopes and hosts. The agent loads only after approval. Scopes are per operation (read accounts, write signals, call host X, read secret Y). Changing scopes needs approval again. Disabling an agent hides its cards, pages, and tools and keeps its data. Uninstalling runs its down migrations only when the operator asks, and archives its data first.
- **P7 Front page.** The front page is a grid of cards. Core cards: pipeline by stage, new signals, follows with activity, my open tasks, inbox. Agent cards come from manifests. A large card spans two columns and can hold an agent's own view. A small card holds a number and a short list. Each card links to its full page.
- **P8 Full pages.** Core pages exist for accounts, contacts, opportunities, signals, and the inbox. An agent may own a full page at `/agents/<name>/`. Record pages (account, opportunity) show core fields, the timeline (activities and signals), and the record panels contributed by installed agents.
- **P9 Agent UI isolation.** Cards and pages from agents run in a sandboxed frame (`sandbox="allow-scripts"`, no same-origin access to the host). They talk to the host through a small message API (`read records`, `call my route`, `open record`, `notify`). The host checks each request against the agent's scopes and uses the signed-in user's session. An agent UI cannot read the host's cookies, DOM, or other agents' data.
- **P10 Custom reports and imports.** A report is a declared query: entity, filters, group by, measures, and chart type. It runs through the core query API, never raw SQL. An import takes a file (CSV, XLSX) and a mapping from columns to an entity's fields, shows a preview with row errors, then writes after approval. Dedupe is by a declared key. Import is an outward-facing write, so it needs the user's confirmation.
- **P11 Integrations (for example Slack).** An integration agent holds its secret in the host's secret store, declares its egress host, and sends outbound messages only as drafts. A person approves each draft. Inbound events (for example a Slack message in a watched channel) become signals through the core API.
- **P12 Chat.** The common chat calls core tools (search and create records, follow, log an activity, list signals) and every installed agent's tools. Tool results are data. Writes the chat makes are attributed to the user who asked.
- **P13 Audit.** Every write to core entities, every agent install and permission change, every draft approval, and every import is recorded: actor (user or agent), action, subject, time.
- **P14 Migrations and data ownership.** Core migrations are versioned as `core_NNNN`. Agent migrations are `<agent>_NNNN`, additive, checksummed, with rollback files where safe (existing rules). Custom fields are stored in the core table `crm_custom_values`, so the core's query and search see them without an agent table join.

## Two ways to build an agent

- **Developer agents** are code in `agents/<name>/`, scaffolded and tested as now. They can use anything the manifest allows.
- **Declarative agents** are a manifest plus templates: fields, reports, a card, a record panel, a Slack or webhook connector configured by the operator. No agent code runs. Sales people build these through the chat, and the result is shown as a diff (manifest, fields, report definitions) for an operator to approve.

Declarative agents are the out-of-the-box path for custom reports, uploads, and simple follow-ups. Developer agents cover connectors, parsers, and analysis that need code.

## Out of scope for this design

- Multi-tenant hosting (one instance per client remains the model).
- Entra sign-in and role-based access beyond admin and member (planned later; the permission model is designed to accept roles).
- A marketplace outside the client's repository.
- Billing, email sending, and calendar sync (they would be agents later).

## Acceptance criteria (for the first build, not this design)

- P1–P14 covered by the test plan. Phase order is in `technical_spec.md`.
- One declarative agent (custom report with import) and one developer agent (Slack draft) installed on a fresh instance, with the audit log showing every step.
- The front page shows core and agent cards, and a large card runs in the sandboxed frame without reaching the host.
