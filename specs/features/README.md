# Feature specifications

Product-wide documents stay in `specs/`: [Phase 1 PRD](../phase-1-prd.md), [architecture](../architecture-tech-stack.md), [design](../design/index.html), and the [cross-feature security review](../security-review-2026-09-29.md). Each feature folder has `task_spec.md` (behaviour and acceptance), `technical_spec.md` (design), and `test_plan.md` (cases). Results live in `acceptance_results.md` where a review has run.

## Platform direction

| Feature | Status |
|---|---|
| [CRM platform with agent extensions](crm-platform/task_spec.md) | Proposed; design only. Five alternative architectures compared in [alternatives](crm-platform/alternatives.md) |

## Sandbox platform

| Feature | Status |
|---|---|
| [Sandbox host](sandbox-host/task_spec.md) | Built |
| [Sandbox sign-in](sandbox-auth/task_spec.md) | Built |
| [Sandbox operations](sandbox-operations/task_spec.md) | Built |
| [Sales home](sales-home/task_spec.md) | Replaced by the common chat as the front page |
| [Sales radar](sales-radar/task_spec.md) | Built; live run recorded (see acceptance_results) |
| [Common chat and attachments](common-chat/task_spec.md) | Built; live run recorded. Front page |
| [Agent building blocks](agent-building-blocks/task_spec.md) | Built |
| [Agent standard](agent-standard/task_spec.md) | Pilot applied to host agents |
| [Agent scaffolding](agent-scaffolding/task_spec.md) | Built |
| [File handling](file-handling/task_spec.md) | Built |
| [Page readers](page-readers/task_spec.md) | Built |

## Agents

| Agent | Feature spec | Status |
|---|---|---|
| research_brief | [Company knowledge RAG](company-knowledge-rag/task_spec.md) and [agent standard](agent-standard/task_spec.md) | Migrated to the standard |
| emeia_dashboard | [EMEIA dashboard](emeia-dashboard/task_spec.md) | Migrated to the standard |
| file_reader | [File handling](file-handling/task_spec.md) | Migrated; no UI yet |
| competitor_watch | [Competitor watch](competitor-watch/task_spec.md), [sales radar](sales-radar/task_spec.md) | The sales radar; pilot of the standard |
| meeting_prep | [Meeting prep](meeting-prep/task_spec.md) | Built offline and checked on a local host; live run with a model pending |
| people_company_search | [Exa people and company search](exa-people-company-search/task_spec.md) | Migrated; stateless, API not mounted |
| signal-intelligence | [Intelligence agent](intelligence-agent/task_spec.md), [intelligence UI](intelligence-ui/task_spec.md) | Its own project |

## Inherited SignalScout application

These describe the monitoring app in `src/signalscout/`, which is not on the sandbox host. `agents/signal-intelligence` depends on its schema, so it stays until decided.

| Feature | Status |
|---|---|
| [Application core](application-core/task_spec.md) | Inherited; no acceptance record |
| [Monitoring profile](monitoring-profile/task_spec.md) | Inherited |
| [Signal collection](signal-collection/task_spec.md) | Inherited |
| [Signal feed and triage](signal-feed-triage/task_spec.md) | Inherited |
| [Agent workspace](agent-workspace/task_spec.md) | Inherited |

## Retired

| Feature | Status |
|---|---|
| [Reading list](reading-list/task_spec.md) | Retired; agent code removed, record kept |
