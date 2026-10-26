from agent_env import make_embedder
from intelligence_embeddings import GeminiEmbedder
from intelligence_retrieval import KnowledgeService


def test_gemini_keeps_the_existing_floor_and_identity():
    embedder = make_embedder({"GEMINI_API_KEY": "g"})
    assert embedder.min_similarity == 0.55
    assert embedder.config == "gemini-embedding-2:768:retrieval-prefix-v1"


def test_openai_has_its_own_floor_because_its_scores_run_lower():
    embedder = make_embedder({"KNOWLEDGE_EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "o"})
    assert embedder.min_similarity == 0.35
    assert embedder.config == "openai:text-embedding-3-small:768:v1"


def test_floor_is_read_from_the_embedder_but_does_not_change_the_index_identity():
    class Stub:
        min_similarity = 0.2
        config = "stub:768:v1"

    service = KnowledgeService(engine=None, embedder=Stub())
    assert service.min_similarity == 0.2
    assert service.config == "stub:768:v1:paragraph-1600-160-v1"  # stored vectors are the same at any floor
    assert KnowledgeService(engine=None).min_similarity == 0.55
