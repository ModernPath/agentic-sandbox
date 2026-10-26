# Test plan: sales home and shared UI kit

| ID | Behavior | Case | Expected |
|---|---|---|---|
| H-1 | H1 | `panel()` with 7 items | 5 items kept |
| H-2 | H1 | `panel()` with an `href` of `//evil.example` or `javascript:` | href dropped (None) |
| H-3 | H1 | `panel()` text longer than 200 characters | trimmed to 200 |
| H-4 | H1 | Dashboard `GET /panel` | returns title, metric, items, empty, action keys |
| H-5 | H1 | Agent with `has_panel=True` but no `/panel` route | host refuses to start (registry error) |
| H-6 | H2 | `/api/agents` entries | include `has_panel` |
| H-7 | H2 | `/` signed in | the home HTML loads `/static/sandbox.js` and `/static/sandbox.css` |
| H-8 | H3 | `sandbox.js` contains `api`, `signOut`, and no `innerHTML` assignment | static check |
| H-9 | H3 | `sandbox.js` passes `node --check` | syntax check |
| H-10 | H4 | `/static/sandbox.css` without a session | 200 |
| H-11 | H5 | Panel of one agent when another agent has records | only its own records |
| H-12 | — | Browser: home shows cards and panels; sign-out works | manual, recorded |
