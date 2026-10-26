# Acceptance results: Common chat and attachments

**Date:** 2026-10-25 · **Scope:** H1–H8 in `task_spec.md`

## Automated

- `tests/test_common_chat.py`: 18 tests (C-1…C-18). All pass.
- Agent test folders: file reader 10, EMEIA dashboard 7, research brief 6, people search 8: all pass.
- Full root suite: 381 passed, 68 skipped (PostgreSQL-gated).

## Live (local app on 127.0.0.1:8100, real providers from `.env`, throwaway account removed afterwards)

1. **Agent tool.** "Which competitors do we watch?" called `competitor_watch__list_competitors`; the reply listed the competitor.
2. **Command-line tool.** "Use the command-line tool of competitor-watch to list its competitors" called `run_agent_cli`; the reply matched the command's JSON.
3. **Attachment.** `people.csv` uploaded to `/api/chat/attachments` (201, kind csv). A question naming its id called `file_reader__read_file`; the reply listed the columns and the people.
4. **Front page.** Signed in in the browser: chat, attach button, and agent list render.

## Issues and follow-ups

- Model replies still show raw markdown (`**bold**`), as in the radar chat.
- The front page lists every agent, including the older ones (research brief, EMEIA, file reader) that were not chosen as the core product. Decision pending.
- **Not included:** creating new agents from the chat. It writes code into the repository and changes the registry, so it needs an approved step.
- Only Gemini was used live. Anthropic and OpenAI are untested for the chat path.
- The file reader's `read_file` returns table rows for CSVs; large files are capped by the reader.
