# Task spec: file handling for agents (draft, not started)

**Status:** Implemented and tested; see [acceptance results](acceptance_results.md). Answers: database storage, vision with the same model as the LLM block, 10 MB limit, no personal data by default. **Builds on:** [agent building blocks](../agent-building-blocks/task_spec.md)

## Goal

Make reading files a core capability that any agent can call, the same way it calls search or the page reader. Users upload a file; an agent reads it and gets text, tables, or images it can reason over.

## Formats in scope (first pass)

| Format | Read as |
|---|---|
| Images (PNG, JPEG, WebP) | Sent to a vision-capable model as image input; returns a description or extracted text |
| CSV, TSV | Parsed table: header plus rows, with a row cap |
| Excel (XLSX) | Per-sheet tables with a row cap; formulas read as values |
| PDF | Text per page; scanned pages flagged for vision |
| Word (DOCX) | Paragraphs and tables as text |
| PowerPoint (PPTX) | Slide text and speaker notes per slide |
| Plain text, Markdown | Text |
| JSON | Parsed value, pretty-printed with a size cap |

## Proposed behaviour

- **F1 Upload.** Files are stored per sandbox, with size and type checks before any parsing. Limits are configurable.
- **F2 Read tool.** One block, `read_file(file_id, max_chars)`, returns a normalised result: kind, text or table rows, page or sheet counts, and a truncation flag.
- **F3 Vision.** Images go to the model through the LLM block. Vision support is checked against the chosen provider and model before the call.
- **F4 Safety.** Parsing runs with limits (size, pages, rows, time). Macros and external links in Office files are not followed. Model and file text is treated as data, never as instructions.
- **F5 Provider neutral.** Agents depend on the read tool, not on any parsing library or provider file API.

## Decisions (from the client's answers)

- **Storage:** files live in the shared sandbox database (`BYTEA` on PostgreSQL), with the 10 MB limit enforced on upload. Lightweight use is expected.
- **Vision:** images are sent to the same provider and model as the LLM block (`SANDBOX_LLM_PROVIDER`, `SANDBOX_LLM_MODEL`). Every LLM provider in the sandbox must support image input before it is used for vision; a provider that does not is rejected with a clear error.
- **Size:** maximum 10 MB per file.
- **Personal data:** none is expected by default. The sandbox does not add personal-data detection; a client that uploads personal data must agree a retention and processing rule first.
