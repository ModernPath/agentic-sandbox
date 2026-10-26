# Test plan: Common chat and attachments

Offline. Fake models (scripted tool calls), fake agents, and real CLI subprocesses against a temporary SQLite file. File: `tests/test_common_chat.py`.

| Case | Covers | Expectation |
|---|---|---|
| C-1 tools from every agent | H1 | Chat offers `alpha__greet` and `beta__shout`; agent with no tools adds nothing; `run_agent_cli` present |
| C-2 reply and tool names | H4 | Reply text and called tool names returned; history forwarded to the model |
| C-3 validation | H4 | Too many history entries → 422; message over 1000 → 422; 6 attachment ids → 422 |
| C-4 no model | H6 | 503 with a fixed message mentioning the model |
| C-5 broken agent skipped | H1 | An agent whose tools raise does not stop the chat; other tools present |
| C-6 CLI env allowlist | H3 | Only the allowed keys pass; unrelated variables are dropped |
| C-7 command allowlist | H2 | Undeclared command → error; no subprocess started |
| C-8 argument limits | H3 | 13 arguments or a 201-character argument → error |
| C-9 real CLI run | H2 | `list` on a temp database returns `{"ok": true, "result": []}` |
| C-10 literal arguments | H2 | Shell metacharacters reach argparse as text (no shell); result is a JSON error, not an effect |
| C-11 CLI through the chat | H2 | `run_agent_cli` tool returns the agent's JSON |
| C-12 attachment upload | H5 | `POST /api/chat/attachments` → 201 with id, filename, kind |
| C-13 attachment with no handler | H6 | 404 |
| C-14 attachment too large | H6 | 413 |
| C-15 attached file read by the model | H5 | Prompt names the id; `file_reader__read_file` with that id returns the table |
| C-16 unsupported type | H6 | 415 with a safe message |
| C-17 front page | H7 | `/` returns the chat page (contains `chat-log`) with no redirect |

Exit criteria: C-1…C-17 pass; the full suite passes; the three live checks in `acceptance_results.md`.
