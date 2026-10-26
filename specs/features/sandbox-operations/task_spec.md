# Task spec: sandbox operations (packaging, migrations, container)

**Status:** Implemented; see acceptance results · **Builds on:** [agent scaffolding](../agent-scaffolding/task_spec.md), [sandbox host](../sandbox-host/task_spec.md)

## Goal

A client sandbox can be installed, migrated, and run without repository-specific tricks: one installable package, a migration status and rollback command, and a container for the host with a Compose file.

## Behavior

- **O1 Packaging.** `pip install .` (or `pip install -e .`) from the repository root installs `sandbox_host`, `sandbox_blocks`, and their dependencies. An agent folder can import them without `PYTHONPATH`.
- **O2 Migration status.** `python -m sandbox_host.migrate status --app sandbox_app` lists, for the host and each registered agent, the applied migrations, pending migrations, and any checksum mismatch. It changes nothing.
- **O3 Migrate.** `python -m sandbox_host.migrate up --app sandbox_app` applies pending migrations for all components, in the same order the host applies them.
- **O4 Rollback.** `python -m sandbox_host.migrate down --app sandbox_app --component <name>` reverts the most recent applied migration of one component, only if it has a matching `NNNN_name.down.sql` file. Without a down file it refuses. The down file runs in one transaction and removes the tracking row.
- **O5 Container.** `Dockerfile.host` builds an image that runs the host with the sandbox composition root. It runs as a non-root user and reads its configuration from environment variables only.
- **O6 Compose.** `compose.sandbox.yaml` runs PostgreSQL (pgvector) and the host. The host waits for a healthy database and runs migrations at startup (through the normal host startup). Only the host port is published, on loopback by default.

## Acceptance criteria

- O1–O4 covered by tests (`test_plan.md`); O1 also checked by installing into a fresh virtual environment.
- O5–O6 checked by building the image and validating the Compose file, and by running the container once against PostgreSQL and signing in.
