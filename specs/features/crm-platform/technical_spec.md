# Technical spec: CRM platform with agent extensions

## 1. Core data model (owned by the host, migrations `core_NNNN`)

| Table | Key columns | Notes |
|---|---|---|
| `crm_accounts` | id, type (`customer`/`prospect`/`competitor`/`partner`), name, website, industry, country, owner_id, archived, created_at, updated_at | A competitor is an account of type `competitor`. |
| `crm_contacts` | id, account_id, name, email, phone, title, owner_id, archived, ... | Contact details are personal data: kept only where the operator enables the contacts module. |
| `crm_opportunities` | id, account_id, name, stage, amount_minor, currency, close_date, owner_id, status, ... | Stages are a configurable list in `crm_settings`. |
| `crm_activities` | id, kind (`note`/`call`/`meeting`/`task`), subject_type, subject_id, body, due_at, done, owner_id, created_at | Timeline source for record pages. |
| `crm_follows` | id, user_id, subject_type (`account`/`topic`), subject_id or topic text, created_at | Unique per user and subject. |
| `crm_signals` | id, subject_type, subject_id, source_kind, source_ref, source_url, title, summary, category, importance, status, created_by (user or agent id), detected_at | `source_url` is http(s) only. Dedupe key: subject + source_ref. |
| `crm_notifications` | id, user_id, signal_id, state (`unread`/`read`), created_at | Created by the core when a signal matches a follow. |
| `crm_drafts` | id, kind, target, body_json, created_by_agent, state (`pending`/`approved`/`rejected`/`sent`), decided_by, decided_at | Outward actions wait here. |
| `crm_custom_fields` | id, entity_type, key, label, field_type, owner_agent, required | Declared by agent manifests. |
| `crm_custom_values` | entity_type, entity_id, field_id, value_json | Core-owned so core queries see custom fields. |
| `crm_audit` | id, actor_type, actor_id, action, subject_type, subject_id, detail_json, at | Append-only. |
| `crm_settings` | key, value_json | Stages, currency, feature switches. |

Agents never write these tables directly. They call the core API (section 4).

## 2. Agent manifest

Each agent ships `manifest.json` next to `api.py`. Example (developer agent):

```json
{
  "name": "competitor-watch",
  "version": "0.3.0",
  "title": "Sales radar",
  "description": "Competitor signals from public news, rated and sourced.",
  "migrations": "migrations",
  "tables": ["competitor_watch_checks", "competitor_watch_findings"],
  "entities": {"account": [{"key": "news_watch", "label": "Watch for news", "type": "bool"}]},
  "events": ["account.created"],
  "tools": ["list_competitors", "check_competitors", "list_signals", "review_signal", "competitor_brief"],
  "cli": {"module": "competitor_watch.cli", "commands": ["list", "add", "signals", "check", "review"]},
  "cards": [{"id": "radar", "size": "large", "path": "/agents/competitor-watch/card"}],
  "pages": [{"path": "/agents/competitor-watch/", "ui": "ui"}],
  "record_panels": [{"entity": "account", "path": "/agents/competitor-watch/panel/{id}"}],
  "scopes": ["crm.accounts.read", "crm.signals.write", "crm.follows.read", "net:news-search-provider"],
  "egress": []
}
```

Declarative agents have the same manifest with `"kind": "declarative"` and no code. Their `reports`, `imports`, and `fields` are data files in the agent folder, validated against a JSON schema written in Phase 2 (not yet created).

**Validation rules:** names match the existing pattern; every table starts with `<name>_`; scopes come from the fixed list in section 5; `egress` lists hosts, never wildcards; cards have `size` `small` or `large`; event names come from the core list. An invalid manifest stops the agent from loading and is shown in the operator's install page.

## 3. Mapping to the code that exists

- `AgentSpec` (`sandbox_host/registry.py`) becomes the code side of the manifest. The manifest is the contract. The host checks that the code's `AgentSpec` matches the manifest before loading routes.
- Today's `chat_tools`, `cli`, and `attach` hooks stay, and the manifest lists them.
- `migrations_dir` stays. The migration tracker already keeps per-agent checksums, so agent migrations are unchanged.
- `ui_dir` and `has_panel` become `pages` and `cards`.
- The competitor watch agent keeps its tables. Its `competitor_watch_competitors` rows move into `crm_accounts` (type `competitor`) and its signals into `crm_signals` in a migration that copies data and then leaves the old tables read-only. The agent's own tables keep only check history.

## 4. Core API for agents (the only write path into core)

A Python SDK `sandbox_host.crm` is the agent-facing surface. Each call checks the calling agent's scopes and writes an audit row.

- `accounts.get(id)`, `accounts.search(query, type)`, `accounts.create(...)`, `accounts.update(id, fields)`
- `contacts.*`, `opportunities.*`, `activities.add(subject, kind, body)` (same shape)
- `signals.create(subject, source, title, summary, category, importance)`: dedupes, then fans out notifications to followers
- `follows.for_subject(subject)`
- `custom.get(entity, id)`, `custom.set(entity, id, key, value)` (only keys the agent declared)
- `drafts.create(kind, target, body)`: returns a draft id; nothing is sent
- `events.subscribe(name, handler)`: handlers run after the originating request commits, with a timeout, and failures are logged to the audit trail

Agents may also define their own queries over their own tables, through normal SQLAlchemy and `sandbox_host.records`.

Read access to core records from agents is by scope: `crm.accounts.read`, `crm.signals.read`, and so on. No raw SQL against core tables.

## 5. Scopes and governance

- Fixed list: `crm.<entity>.read`, `crm.<entity>.write`, `crm.signals.write`, `crm.drafts.create`, `net:<host-alias>`, `secret:<NAME>`, `chat.tools`, `cli.run`, `import.write` (needs a user's confirmation per import).
- Install approval: an operator sees the scopes, egress hosts, tables, and migrations before the first run. Approval is recorded in the audit log with the manifest's checksum.
- Drafts: an agent can create a draft; only a signed-in user can approve it. Approval is an audit row. Sending happens in the agent that owns the draft kind, after approval.
- Secrets: values come from the environment file, named per agent (`SECRET_<AGENT>_<NAME>`). Agents receive them only if their manifest lists `secret:<NAME>`. Never logged.
- Personal data: contacts and free-text notes are kept until archived. Retention settings per entity are a Phase 4 item.

## 6. UI composition

- **Front page** (`/`): fetches `GET /api/cards`, which lists core cards and each enabled agent's cards with size and path. Core cards are rendered by the host. Agent cards are loaded in sandboxed frames at their `path`.
- **Frame bridge**: each frame gets `window.sandbox` through a fixed `postMessage` protocol with request ids. Methods: `records.get`, `records.list`, `route.call` (only the agent's own routes), `navigate` (only core and own pages), `notify`. The host validates origin, scope, and payload size (64 KB), and answers with the signed-in user's rights.
- **Record pages** (`/crm/accounts/{id}` and so on): core sections (fields, timeline, signals, opportunities, contacts) plus record panels from enabled agents, each in its own frame.
- **Agent full pages** (`/agents/<name>/`): served from the agent's `ui` folder with a strict content security policy: scripts and styles from the same origin only, no inline handlers, and `frame-ancestors` set to the host. They use the shared kit for host calls.
- **Mobile**: a card uses one column below 720 px. A large card's frame height comes from the agent's declared minimum, with a host-enforced maximum.

## 7. Two authoring modes

- **Developer agent.** Scaffolded from `templates/host_agent/` and extended with the manifest. Reviewed in the repository like any code change.
- **Declarative agent.** Created from the chat. A sales person describes the need ("a monthly report of open pipeline by region, and a way to import the regional CSVs"). The chat drafts the manifest, fields, report definitions, and import mapping. The operator reviews a diff and installs it. No code runs; the engine interprets the declarations, and the engine is the reviewed part.

The declarative engine supports: custom fields, report definitions (entity, filters, group by, measures, chart), import mappings with a dedupe key, and cards and record panels built from report definitions. Anything else needs a developer agent.

## 8. Phases

1. **Core model and audit.** Core tables, SDK, audit, follows, signals, notifications. Migrate the sales radar's data.
2. **Manifest and install.** Manifest validation, scopes, install approval page, enable and disable.
3. **Cards and frames.** Front page cards, sandboxed frames, bridge protocol, record panels.
4. **Declarative agents.** Fields, reports, imports with preview, and the chat-drafted manifest.
5. **Connectors.** Drafts with approval, first outbound connector (Slack), first inbound connector (a watched channel into signals).

Each phase ends with the acceptance checks in `test_plan.md`.

## 9. Open decisions

1. Declarative agents from the chat in Phase 4, or a developer-only path first? (Recommendation: Phase 4 with the review step above.)
2. Frame isolation for agent UIs: sandboxed frames with a bridge (recommended) or same-origin trusted code for developer agents only. The bridge costs a little more work up front.
3. Whether the signal-intelligence project moves onto the core model. It has its own signal and opportunity tables; migrating it is a separate decision.
4. Roles beyond admin and member, for example a sales manager who approves imports.
