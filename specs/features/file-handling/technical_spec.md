# Technical spec: file handling

## Layout

```text
src/sandbox_blocks/files.py          read_document(): formats, limits, safety (no provider calls)
src/sandbox_blocks/llm.py            complete_with_image() on every LLM adapter
agents/file_reader/
  api.py          upload, read, describe (vision), ask (document Q&A)
  store.py        FileStore: BYTEA content in the shared database
  migrations/0001_files.sql
src/sandbox_host/errors.py           AgentInputError(status, message) -> JSON response
```

Libraries (pinned in `pyproject.toml`, hashed in both lock files): openpyxl (Excel), python-docx (Word), python-pptx (PowerPoint), pypdf (PDF), python-multipart (uploads).

## Reader (`read_document`)

- Size is checked first (10 MB). Office files are also checked by declared unpacked size (50 MB) before parsing, to stop zip bombs.
- Type comes from the extension and is confirmed by content: image magic bytes, `%PDF`, or the zip signature for Office files.
- Excel is opened read-only with cached values; formulas are not evaluated. Word, PowerPoint, and PDF are read as text only. Macros and external links are not followed.
- Rows (`max_rows`, default 500) and text (`max_chars`, default 200 000) are capped; results carry a `truncated` flag.
- Parser exceptions are converted to `FileError` with a generic message.

## Vision

`complete_with_image(prompt, image, mime, system)` on each adapter:

- OpenAI and Azure: Responses API, `input` with `input_text` and `input_image` (data URL).
- Gemini: Interactions API, `input` with `{"type": "image", "data": <base64>, "mime_type"}`.
- Anthropic: Messages API, `image` block with `base64` source.

Only `image/png`, `image/jpeg`, and `image/webp` are accepted. Vision uses the configured LLM provider and model, as decided.

## API decisions

- Uploads are read in one bounded read (`MAX_FILE_BYTES + 1`); larger files get 413 before parsing.
- Unsupported types get 415; content that does not match, or cannot be parsed, gets 422.
- Responses never include raw file bytes. Text in `GET /files/{id}` is capped at 20 000 characters.
- Document questions send the extracted text inside a document tag with a system instruction to treat it as data.
