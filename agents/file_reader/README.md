# file_reader

Upload documents and images, then read them or ask questions about them.

- Supported: CSV, Excel, Word, PowerPoint, PDF, text, JSON, PNG, JPEG, WebP. Up to 10 MB each.
- People upload through the API (`POST /api/agents/file-reader/files`) or the CLI.
- Models get read-only tools: list, read, ask, describe.

## CLI

```
python -m file_reader.cli upload --path ./targets.xlsx
python -m file_reader.cli list
python -m file_reader.cli read --id ID
python -m file_reader.cli ask --id ID --question "Which rows are overdue?"
python -m file_reader.cli describe --id ID --prompt "What does this chart show?"
```

Output is one JSON object. See `AGENTS.md` for the rules and the layout.
