# Test plan: file handling

| Group | Cases | Where |
|---|---|---|
| Reader: CSV, JSON, text, XLSX, DOCX, PPTX, PDF, images | F-1 to F-9 | `tests/test_blocks_files.py` |
| Reader: limits and safety (10 MB, type, content match, zip bomb, corrupt PDF) | F-10 to F-13 | `tests/test_blocks_files.py` |
| Vision request shapes (OpenAI, Azure, Gemini, Anthropic) and MIME rules | V-1 to V-5 | `tests/test_blocks_vision.py` |
| Agent API: upload, limits, read, describe, ask, errors, storage | A-1 to A-12 | `tests/test_example_file_reader.py` |
| Migration on PostgreSQL (`BYTEA`) | full suite with `TEST_DATABASE_URL` | run on PostgreSQL 17 |
| Live: vision and document Q&A per provider; Excel read | — | `acceptance_results.md` |

Exit criteria: all offline cases pass in the full suite; the PostgreSQL run passes; live results recorded for each provider with a key.
