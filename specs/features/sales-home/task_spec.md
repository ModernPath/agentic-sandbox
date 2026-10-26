# Task spec: sales home and shared UI kit

**Status:** Implementing · **Builds on:** [sandbox host](../sandbox-host/task_spec.md), [sandbox sign-in](../sandbox-auth/task_spec.md)

## Goal

The sandbox opens on a sales home page. It shows one card per agent, and each card holds a live summary (the agent's panel). Clicking a card opens that agent's own page. All pages share one stylesheet and one request helper, so layout, errors, and sign-out look and behave the same everywhere.

## Behavior

- **H1 Panels.** An agent can declare `has_panel=True`. Its API then serves `GET /api/agents/<name>/panel` returning `{title, metric, items, empty, action}`:
  - `title`: short heading.
  - `metric`: `{label, value}` or `null`.
  - `items`: up to 5 entries `{title, meta, href}`; `href` is an in-sandbox path or `null`.
  - `empty`: text shown when there are no items.
  - `action`: `{label, href}` or `null`.
- **H2 Home.** `/` shows the sales home: the signed-in user's name, a card per registered agent, and each card's panel. A card whose panel fails shows a short error without hiding the others.
- **H3 Shared kit.** `/static/sandbox.css` and `/static/sandbox.js` are served to any page. The JavaScript exposes `Sandbox.api(method, path, body)` (sends the sandbox header, redirects to sign-in on 401, throws an error with the server's message otherwise), `Sandbox.render(...)` helpers for cards, lists, and banners, and `Sandbox.signOut()`.
- **H4 Static files are public.** `/static/*` needs no session, so the login page can use the same stylesheet.
- **H5 Panel data is the agent's own.** A panel only reads the agent's tables and returns summaries; it never exposes records from another agent.

## Out of scope

- Customising the home per user, drag-and-drop layout, charts.
- Migrating the existing agent pages to the kit (planned; they keep working).

## Acceptance criteria

- H1–H5 covered by tests (`test_plan.md`).
- The browser shows the home with panels for the existing agents, and the sign-out works from the home.
