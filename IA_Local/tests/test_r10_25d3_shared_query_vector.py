from types import SimpleNamespace

from enterprise_ai.advanced_retrieval import AdvancedRetrievalEngine


class CountingEmbeddings:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


class CountingVectors:
    def __init__(self):
        self.calls = []

    def search(self, kind, query, principal, limit=8):
        self.calls.append((kind, limit))
        return []


class SearchProbe:
    def __init__(self, embeddings, vectors):
        self.embeddings = embeddings
        self.vectors = vectors
        self.calls = []

    def search(
        self,
        principal,
        query,
        limit,
        min_score,
        *,
        query_vector=None,
        candidate_limit=None,
    ):
        self.calls.append(
            {
                "limit": limit,
                "candidate_limit": candidate_limit,
                "query_vector": query_vector,
            }
        )
        self.vectors.search(
            "memory" if len(self.calls) == 1 else "document",
            query_vector,
            principal,
            candidate_limit,
        )
        return []


def test_advanced_retrieval_shares_query_vector_and_candidate_authority():
    embeddings = CountingEmbeddings()
    vectors = CountingVectors()

    memory = SearchProbe(embeddings, vectors)
    documents = SearchProbe(embeddings, vectors)

    engine = AdvancedRetrievalEngine(
        memory,
        documents,
        None,
        {
            "max_memories": 6,
            "max_document_chunks": 8,
            "candidate_factor": 4,
            "memory_candidate_min_score": 0.08,
            "document_candidate_min_score": 0.08,
        },
    )

    principal = SimpleNamespace(company_id="c1", user_id="u1")
    engine.retrieve(principal, "ventas clientes productos")

    assert embeddings.calls == 1

    assert memory.calls[0]["limit"] == 24
    assert memory.calls[0]["candidate_limit"] == 24

    assert documents.calls[0]["limit"] == 32
    assert documents.calls[0]["candidate_limit"] == 32

    assert memory.calls[0]["query_vector"] is documents.calls[0]["query_vector"]


def test_legacy_search_contract_remains_optional():
    import inspect
    from enterprise_ai.memory import MemoryManager
    from enterprise_ai.documents import DocumentService

    memory_sig = inspect.signature(MemoryManager.search)
    document_sig = inspect.signature(DocumentService.search)

    assert memory_sig.parameters["query_vector"].default is None
    assert memory_sig.parameters["candidate_limit"].default is None
    assert document_sig.parameters["query_vector"].default is None
    assert document_sig.parameters["candidate_limit"].default is None
