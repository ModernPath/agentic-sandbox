# AGENTS.md — file_reader

Rules for AI agents and developers working on this agent. Read the root `AGENTS.md` and `agents/AGENTS.md` first.

## What this agent is

Stores uploaded files in the shared database (up to 10 MB each) and reads them: CSV, Excel, Word, PowerPoint, PDF, text, JSON, and images. It answers questions about a document, or describes an image, through the configured model. Files may contain client data.

## Layout

- `service.py`: upload, list, read, describe, ask, panel. Limits and parsing are applied here.
- `sandbox_blocks/files.py` (shared): the reader. Changes to formats or limits belong there, with tests.
- `store.py`: the `file_reader_files` table (content as bytes).
- `tools.py`: read-only tools (`list_files`, `read_file`, `ask_file`, `describe_image`). Uploads are never a model tool.
- `cli.py`: `upload`, `list`, `read`, `ask`, `describe` with JSON output.
- `api.py`: routes over the service.
- `migrations/`: `0001_files.sql`.

## Change rules

- A person uploads. Do not add an upload tool or an unauthenticated upload route.
- Keep the 10 MB limit and the content checks. Never trust the file name or extension alone.
- Document text goes to the model inside the document tag, with the instruction to treat it as data. Keep that wrapper.
- Keep the `file_reader_` table prefix for new tables.
- Personal data in uploads needs a retention rule in the spec before anything else is built on it.
