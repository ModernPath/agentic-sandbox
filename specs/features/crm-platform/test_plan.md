# Test plan: CRM platform with agent extensions

Cases are for the build phases in `technical_spec.md` section 8. Each phase is done when its cases pass and the full suite is green.

| Case | Phase | Covers | Expectation |
|---|---|---|---|
| K-1 core tables created once | 1 | P1 | Core migrations apply in order; re-running changes nothing |
| K-2 archive, not delete | 1 | P1 | Archiving hides a record from lists; hard delete needs the operator role and writes an audit row |
| K-3 signal dedupe | 1 | P2 | Same subject and source reference stores one signal |
| K-4 follow fan-out | 1 | P3 | A new signal creates one notification per follower of the subject, none for others |
| K-5 agent writes go through the SDK | 1 | P4 | An agent's direct write to a core table is refused by the table's grants or by a test that counts writes |
| K-6 manifest validation | 2 | P5 | Invalid names, wildcard hosts, unknown scopes, or foreign table prefixes stop loading with a clear message |
| K-7 install approval | 2 | P6 | Agent routes and tools are unavailable until approved; approval is audited with the manifest checksum |
| K-8 scope change re-approval | 2 | P6 | A changed scope set disables the agent until approved again |
| K-9 disable keeps data | 2 | P6 | Disabled agent's tables and records remain; its cards, tools, and pages are hidden |
| K-10 scope enforcement | 2 | P4, P9 | An SDK call outside the granted scope is refused and audited |
| K-11 card list | 3 | P7 | `GET /api/cards` lists core cards and only enabled agents' cards, with sizes |
| K-12 frame isolation | 3 | P9 | A frame cannot read host cookies or DOM (checked by its sandbox attributes and a bridge test); a bridge call to another agent's route is refused |
| K-13 bridge limits | 3 | P9 | Payloads over 64 KB and unknown methods are refused |
| K-14 record panels | 3 | P8 | An account page includes each enabled agent's panel, and only enabled ones |
| K-15 custom fields | 4 | P4, P14 | A declared field stores a typed value; an undeclared key is refused |
| K-16 report definition | 4 | P10 | A report runs through the query API and returns grouped totals; a raw SQL field is refused by validation |
| K-17 import preview and dedupe | 4 | P10 | Preview lists row errors; confirmed import writes only new keys; duplicates update nothing silently |
| K-18 draft approval | 5 | P11, P13 | A draft is not sent until a signed-in user approves; the approval and the send are both audited |
| K-19 outbound egress | 5 | P11 | A connector can call only its declared host; another host is refused |
| K-20 inbound event to signal | 5 | P11, P2 | A connector event becomes a signal once, with its source reference |
| K-21 chat uses core and agent tools | 1–5 | P12 | The chat lists core tools and enabled agents' tools; a write is attributed to the asking user |
| K-22 audit completeness | all | P13 | Each write, install, approval, and import in a scripted scenario has one audit row with actor and subject |

**Exit criteria:** K-1…K-22 pass for the phase being closed; the full root suite passes; a live run on a fresh instance (install one declarative and one developer agent, import a CSV, follow a competitor, see a signal notification, approve one draft) is recorded in `acceptance_results.md`.
