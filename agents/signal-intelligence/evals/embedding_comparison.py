"""Compare retrieval with lexical-only, Gemini embeddings, and OpenAI embeddings.

Runs the real knowledge pipeline (content -> chunks -> embeddings -> hybrid search) on a
disposable, migrated PostgreSQL database given by --database-url. Documents and queries come
from a labelled fixture: each document lists queries that should find it.

Keys come from the environment; only scores are printed.
  python evals/embedding_comparison.py --database-url postgresql+psycopg://... \
      --fixture ../../tests/fixtures/knowledge_retrieval.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def search_titles(knowledge, query: str) -> list[str]:
    result = knowledge.search(query, purpose="inspection", persist=False)
    seen, titles = set(), []
    for hit in result.get("hits", []):
        title = hit.get("title")
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def drain_index(knowledge) -> dict:
    """Index until nothing is pending; return totals across batches."""
    indexed = failed = 0
    for _ in range(100):
        batch = knowledge.index_pending(limit=4)
        indexed += batch.get("indexed", 0)
        failed += batch.get("batch_failed", 0)
        if batch.get("indexed", 0) == 0 and batch.get("batch_failed", 0) == 0:
            break
    return {"indexed": indexed, "batch_failed": failed}


def stored_vectors(engine, config: str) -> int:
    from sqlalchemy import text

    with engine.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM knowledge_embedding WHERE config = :config"),
                                {"config": config}).scalar())


def score(knowledge, documents) -> dict:
    cases = [(doc["title"], query) for doc in documents for query in doc["queries"]]
    top1 = top3 = 0
    misses = []
    for expected, query in cases:
        titles = search_titles(knowledge, query)
        if titles[:1] == [expected]:
            top1 += 1
        if expected in titles[:3]:
            top3 += 1
        else:
            misses.append({"query": query, "expected": expected, "top": titles[:3]})
    return {"queries": len(cases), "top1": top1, "top3": top3, "misses": misses}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    from sqlalchemy import create_engine, text

    from agent_env import OPENAI_MIN_SIMILARITY
    from intelligence_embeddings import GeminiEmbedder
    from intelligence_retrieval import KnowledgeService
    from intelligence_service import IntelligenceService
    from memory.memory import IntelligenceStore
    from sandbox_blocks.embeddings import OpenAIEmbedder

    documents = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    engine = create_engine(args.database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE knowledge_chunk, knowledge_document, knowledge_embedding CASCADE"))
    service = IntelligenceService(IntelligenceStore(engine))
    for doc in documents:
        service.add_content({"title": doc["title"], "text": doc["text"], "channel": "eval"})

    results = {}
    lexical = KnowledgeService(engine)
    results["lexical"] = {"config": lexical.config, "index": drain_index(lexical), **score(lexical, documents)}
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    providers = []
    if gemini_key:
        providers.append(("gemini", GeminiEmbedder(gemini_key, "gemini-embedding-2")))
    if openai_key:
        openai_embedder = OpenAIEmbedder(api_key=openai_key, dimensions=768)
        openai_embedder.min_similarity = OPENAI_MIN_SIMILARITY
        providers.append(("openai", openai_embedder))
    for name, embedder in providers:
        knowledge = KnowledgeService(engine, embedder=embedder)
        index = drain_index(knowledge)
        results[f"{name} (floor {knowledge.min_similarity})"] = {
            "config": knowledge.config, "index": index, **score(knowledge, documents)}
        # Ranking only: no similarity floor, so the score shows the embeddings, not the threshold.
        knowledge.min_similarity = 0.0
        results[f"{name} (no floor)"] = {"config": knowledge.config, "index": index, **score(knowledge, documents)}

    for name, row in results.items():
        print(f"{name}: top1 {row['top1']}/{row['queries']}  top3 {row['top3']}/{row['queries']}  "
              f"indexed {row['index'].get('indexed')} failed {row['index'].get('batch_failed')}  "
              f"stored vectors {stored_vectors(engine, row['config'])}  config {row['config']}")
        for miss in row["misses"]:
            print(f"    miss: {miss['query']!r} expected {miss['expected']!r} top3 {miss['top']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
