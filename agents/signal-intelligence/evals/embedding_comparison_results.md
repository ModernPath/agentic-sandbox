# Embedding comparison: lexical vs Gemini vs OpenAI (2026-10-24)

Script: `evals/embedding_comparison.py`. Data: `tests/fixtures/knowledge_retrieval.json` (10 synthetic documents about a product, 20 labelled queries). Each run used the real pipeline: content, paragraph chunks, embeddings, hybrid search, on a disposable PostgreSQL 17 database migrated to `0012`.

| Condition | Top-1 | Top-3 | Index identity |
|---|---|---|---|
| Lexical only | 16/20 | 17/20 | `lexical-v1` |
| Gemini, floor 0.55 (existing) | 17/20 | 18/20 | `gemini-embedding-2:768:retrieval-prefix-v1` |
| Gemini, no floor (ranking only) | 17/20 | 18/20 | same |
| OpenAI `text-embedding-3-small`, floor 0.35 | 18/20 | 19/20 | `openai:text-embedding-3-small:768:v1` |
| OpenAI, no floor (ranking only) | 17/20 | 18/20 | same |

## What the numbers mean

- **The floor was the problem, not the embeddings.** OpenAI ranked the correct document first for all three queries it missed in the first run. Its similarity scores were 0.40–0.49, below the fixed 0.55 cutoff that was tuned for Gemini, so every semantic hit was dropped. The floor is now a per-embedder setting.
- **The OpenAI floor (0.35) is provisional.** It was chosen by looking at this same fixture, so the 18/20 figure is optimistic. Treat OpenAI as at least as good as Gemini on this set, not clearly better. One query is noise at this size.
- **No real company content was tested.** The fixture is synthetic. Before switching a client, index their real documents and rerun the script with their labelled queries.
- Stored vectors: 10 per provider, one per document, confirmed in the database.

## Reproduce

```sh
docker exec <postgres> psql -U <user> -d <db> -c "CREATE DATABASE signalscout_intelligence_eval"
DATABASE_URL=<url to that db> alembic upgrade head      # from the repository root
PYTHONPATH=src:agents/signal-intelligence GEMINI_API_KEY=... OPENAI_API_KEY=... \
  python agents/signal-intelligence/evals/embedding_comparison.py \
  --database-url <url to that db> --fixture tests/fixtures/knowledge_retrieval.json
```

## Run 2: public corporate web content, 38 pages, 76 drafted queries

Corpus: 38 public HTML pages from one corporate website (product, release, investor, sustainability and company pages; PDFs and management pages excluded), read with the Exa reader. 138 chunks. Queries: two per page, written by the assistant, not by the client. Not reviewed yet.

| Condition | Top-1 | Top-3 |
|---|---|---|
| Lexical only | 16/76 | 25/76 |
| Gemini, floor 0.55 | 21/76 | 30/76 |
| Gemini, no floor | 21/76 | 30/76 |
| OpenAI, floor 0.35 | 18/76 | 29/76 |
| OpenAI, no floor | 18/76 | 29/76 |

Reading these numbers:
- Both embedding providers beat lexical search clearly. Gemini leads OpenAI by 3 queries at top-1 and 1 at top-3, which is within noise for 76 queries.
- The floor made no difference on this corpus, so the 0.35 OpenAI floor is not a driver here.
- Single-answer labels are too strict for overlapping product pages. Many "misses" may be pages that would also answer the question. A person should review the labels before these numbers are used for a decision.

## Run 2b: same corpus, relevance judged per query (multiple correct pages allowed)

Method: for each of the 76 queries, the top 8 hits from all three conditions were pooled (about 10 candidate pages per query). `gpt-6-luna` judged which candidates actually answer the query. The drafted source page always counts. Average 3.3 relevant pages per query. Rankings were then rescored against those relevant sets.

| Condition | Top-1 (any relevant) | Top-3 (any relevant) |
|---|---|---|
| Lexical only | 23/76 | 51/76 |
| Gemini, floor 0.55 | 44/76 | 56/76 |
| OpenAI, floor 0.35 | 35/76 | 47/76 |

Caveats:
- The judge is an OpenAI model, which may favour OpenAI's rankings. Gemini's lead is therefore not explained by the judge.
- Queries and the first-pass answer keys were written by the assistant, not by the client. Relevance was not reviewed by a person.
- 76 queries on one public website. The earlier synthetic fixture showed the opposite order at a small margin, so the ranking of the two providers is not settled.
