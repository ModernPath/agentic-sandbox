# Acceptance results: file handling

**Date:** 2026-10-24 · **Scope:** F-1 to F-13 (reader), A-1 to A-12 (agent API), V-1 to V-5 (vision) — see [test_plan.md](test_plan.md)

## Automated

- Full suite against PostgreSQL 17 (`pgvector/pgvector:pg17`): **296 passed**, 0 skipped. This includes the agent's `BYTEA` table on PostgreSQL.
- Reader, API, and vision tests run offline with fake clients and generated files.

## Live (file-reader API on PostgreSQL, real models; keys from `.env`, not printed)

| Check | OpenAI `gpt-6-luna` | Azure `gpt-6-luna` | Gemini `gemini-3.8-flash` |
|---|---|---|---|
| Upload PNG | 201 | 201 | 201 |
| Describe image ("dominant colour") | Pass: "Red" | Pass: "Red" | Pass: "Red" |
| Upload CSV and ask a question | Pass: "The value for Wins is 4." | Pass: "4" | Pass: "...the value for Wins is 4." |
| Upload XLSX and read it | Pass: sheet rows returned | Pass | Pass |

Anthropic vision: offline test only (no key in `.env`).

## Not done or not verified

- **Anthropic** vision and text: no live call yet.
- **Real PDFs and Office files with complex layouts:** tests use generated files. Scanned PDFs have no text and no OCR, so they return empty text; OCR is out of scope for now.
- **UI:** the file reader has no page yet, only the API.
- **Delete:** no delete endpoint. Uploads stay until the database is cleaned, per the decision to keep storage lightweight.
- **Docker build:** the lock files now include the document libraries, but the image was not built here.
