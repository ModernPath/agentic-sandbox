# Technical spec: sales home and shared UI kit

## Host changes

- `AgentSpec` gains `has_panel: bool = False`. The host mounts nothing new; the agent's router defines `GET /panel`, and the host only checks that agents with `has_panel` define it.
- `_describe(agent)` adds `"has_panel": agent.has_panel`, so the home knows which cards to load.
- `/static` is mounted from `src/sandbox_host/static/` (`StaticFiles`). `PUBLIC_PATHS` gets a prefix rule: paths starting with `/static/` skip sign-in.
- `static/sandbox.css` and `static/sandbox.js` are new. `static/index.html` is replaced by the home page; `login.html` links the shared stylesheet.

## Panel contract (helper)

`sandbox_host/panels.py` provides `panel(title, *, metric=None, items=(), empty="Nothing yet.", action=None)` and validates it: at most 5 items, string fields trimmed and capped at 200 characters, `href` must start with `/` and not `//`. Agents call this helper so every panel has the same shape.

## Shared kit

- `sandbox.js` attaches `window.Sandbox`. `api(method, path, body)` uses `fetch` with the header `X-Sandbox-Request: 1` on every call, JSON bodies, and returns parsed JSON. On 401 it navigates to `/login?next=<current path>`.
- Rendering uses `textContent` and `createElement` only. Links are created only for `href` values that start with `/` or `http(s)://`.
- `sandbox.css` defines colour tokens for light and dark mode, the header, cards, lists, buttons, banners, and focus outlines.

## Home

The home fetches `/api/agents`, then each panel with `has_panel` in parallel. Each card has a title, the metric, up to 5 items with links, the action link, or the empty text. Failed panels show "Could not load this summary" inside their own card.
