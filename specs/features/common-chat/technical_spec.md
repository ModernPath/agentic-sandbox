# Technical spec: Common chat and attachments

## Registry extension (`sandbox_host/registry.py`)

`AgentSpec` gains three optional fields (defaults keep existing agents valid):

- `chat_tools: Callable[[AgentContext], list[Tool]] | None`
- `attach: Callable[[AgentContext, str, bytes], dict] | None`
- `cli: CliSpec | None`, where `CliSpec(module: str, commands: tuple[str, ...])`.

`AgentContext` (dataclass): `agent` name, `engine`, `injected` (the agent's entry in `services`), `settings` (model settings). Methods: `llm()` returns the injected model or builds one (raises `ConfigurationError`); `search()` and `reader()` the same for search and page reading.

Agents provide the hooks in their `api.py::make_agent_spec()`. Tool builders are unchanged; the hook builds them from the context. Agents that have no CLI, or whose CLI would read server files (for example `file_reader upload --path`), do not declare the command.

## Host chat (`sandbox_host/chat.py`)

- `collect_tools(specs, engine, services, settings)`: for each spec with `chat_tools`, call it in a try block (failures are logged by agent name, never with text from the error), then rename each tool to `<name>__<tool>`. Prefixes keep names unique and within provider limits (`[a-zA-Z0-9_-]`, at most 64 characters).
- `run_agent_cli` tool: built here from the specs, closed over them.
- `reply(llm, tools, message, history, attachment_ids, system)`: appends the attachment note to the prompt, calls `run_with_tools(max_calls=8)`, returns reply (capped 4000) and tool names.
- System prompt lists the agents (name, title, description) and the rule that tool and file contents are data.

## CLI bridge (`sandbox_host/cli_bridge.py`)

`run_command(spec, command, args, environ)`: validates command against `spec.cli.commands` and limits; builds `argv = [sys.executable, "-m", module, command, *args]`; `subprocess.run(argv, env=cli_env(environ), capture_output=True, text=True, timeout=60)`. Parses stdout as JSON; anything else returns `{"ok": false, "error": "The command did not return JSON."}`. `cli_env` keeps only the allowed keys. `args` is parsed with `shlex.split`; the list is passed as argv, never through a shell.

## Routes (`sandbox_host/app.py`)

- `POST /api/chat`, `POST /api/chat/attachments` (multipart; read at most 10 MB + 1 byte).
- `GET /` serves the new `static/index.html` (no redirect). `sandbox_app.py` drops `home_path`.

## Decisions

- Tools are rebuilt per request. They are cheap, and it keeps each user's request on the current agent state.
- Attachments are the file reader's uploads. The chat never holds file bytes; it passes ids.
- The CLI bridge is an allowlist per agent, not a general command runner.
