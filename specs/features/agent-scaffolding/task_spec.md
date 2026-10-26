# Task spec: agent scaffolding (agent-extendable sandbox)

**Status:** Implemented for the core workflow; see acceptance results for what remains · **Builds on:** [sandbox host](../sandbox-host/task_spec.md), [sandbox sign-in](../sandbox-auth/task_spec.md), [building blocks](../agent-building-blocks/task_spec.md)

## Goal

A developer (or a development agent) can add a new agent with a data model, API, and UI by running one command and then implementing the domain logic test-first. The sandbox provides the conventions, shared helpers, a test kit, and written instructions, so new agents look and behave like the existing ones.

## Behavior

- **S1 Scaffold command.** `python -m sandbox_host.scaffold <agent-name>` creates `agents/<module>/` from `templates/host_agent/`, substituting the names, and registers the agent in `sandbox_app.py`. It refuses to overwrite an existing folder and refuses invalid names.
- **S2 Template.** The generated agent contains a router, a pydantic model, a store, a SQL migration, a UI page, a README contract, and tests. The generated tests pass before the developer changes anything.
- **S3 Store helper.** `sandbox_host.records` provides insert, fetch-one, fetch-many, and update for a whitelisted table name and column names. Values are always bound parameters. Identifiers that are not simple names are rejected.
- **S4 Test kit.** `sandbox_host.testing` provides an in-memory engine, a signed-in test client for a host with agents, and a helper that creates a test user. Agents' tests import these instead of writing their own.
- **S5 Instructions.** `docs/agent-development.md` gives the workflow: spec, scaffold, failing test, implementation, registration, verification, browser check. The root `AGENTS.md` points to it.
- **S6 Conventions.** Each agent has its own tables prefixed with its module name, its own migration folder, ids as text UUIDs, timestamps as ISO-8601 UTC text, and no cross-agent table access.

## Acceptance criteria

- S1–S6 are covered by tests in `test_plan.md`.
- A scaffolded agent passes its generated tests and appears on the host's index after registration.
- The instructions name every convention the tests enforce.
