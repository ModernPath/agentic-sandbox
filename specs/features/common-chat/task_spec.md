# Task spec: Common chat and attachments

**Status:** Specified · **Builds on:** [sales radar](../sales-radar/task_spec.md), [file handling](../file-handling/task_spec.md), [agent standard](../agent-standard/task_spec.md)
**Supersedes:** the sales radar as the home page (R9 of sales-radar). The radar stays one click away.

## Goal

The front page is one chat for the whole sandbox. Through it a signed-in user can ask any registered agent to act: the model calls each agent's tools, can run an agent's command-line tool and receive its result, and can work with files the user attaches in the chat.

## Behavior

- **H1 Agents as tools.** Each registered agent may offer chat tools. The chat offers every agent's tools, named `<agent_name>__<tool>` (agent name with hyphens as underscores). An agent without chat tools adds none. An agent whose tools cannot be built (for example, a missing model) is skipped; the chat still works.
- **H2 Command-line tool.** The chat also offers `run_agent_cli(agent, command, args)`. It runs the agent's command-line module with a subprocess and returns the JSON the command printed. Only commands the agent declares are allowed. `args` is a space-separated string split like a shell would, but the process runs without a shell.
- **H3 CLI limits.** At most 12 arguments, each at most 200 characters. The command has a 60-second timeout. Output is capped at 20 000 characters. Only `SANDBOX_*`, provider key variables, `PATH`, `PYTHONPATH`, and `DATABASE_URL` are passed to the command. Non-JSON output becomes a fixed error.
- **H4 Chat turn.** `POST /api/chat` takes `{message, history, attachment_ids}`. Limits: message 1–1000 characters, history at most 20 entries of 2000 characters, at most 5 attachment ids. The response is `{reply, tool_calls}`. The chat stores nothing; the browser keeps the conversation.
- **H5 Attachments.** `POST /api/chat/attachments` takes one file (10 MB max). It is stored by the agent that declares an attachment handler (the file reader). The response is that agent's record: id, filename, kind, size. A chat turn that names attachment ids tells the model which ids are attached, so the file tools can read them. Filenames are user data and are not put into the prompt.
- **H6 Errors.** No configured model → 503 with a fixed message. Attachment with no handler → 404. Too large → 413. Unsupported type → 415. Provider text and stack traces never reach the page.
- **H7 Front page.** `/` serves the chat (conversation, attach button, send), a list of registered agents with links, and the radar summary as a card. No redirect.
- **H8 Safety.** Tool results, file contents, and model output are data. The system prompt says so. Every chat call is a signed-in user's action; no approvals are bypassed. Commands that spend money (research, competitor checks, people search) are allowed only when the agent declares them, and the chat says what it ran.

## Out of scope

- Scaffolding new agents from the chat. It writes code into the repository and changes the registry, so it needs a separate approved step.
- Streaming replies; uploads other than the file reader's types.

## Acceptance criteria

- H1–H8 covered by `test_plan.md`, offline, with fake models.
- Live: one chat turn that calls an agent tool, one that runs an agent CLI command, and one with an attachment, recorded in `acceptance_results.md`.
