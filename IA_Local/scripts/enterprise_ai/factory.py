from __future__ import annotations

from typing import Optional

from .config import load_config
from .context_engine import ContextEngine
from .database import Database
from .documents import DocumentService
from .memory import MemoryManager
from .observability import configure_logging
from .providers import EmbeddingProvider, LLMProvider, build_embedding_provider, build_llm_provider
from .service import EnterpriseAIService
from .structured_data import StructuredDataService
from .vector_store import VectorStore, build_vector_store


class Components:
    def __init__(self, cfg, db, llm, embeddings, vectors, memory, datasets, documents, context, service, logger):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.embeddings = embeddings
        self.vectors = vectors
        self.memory = memory
        self.datasets = datasets
        self.documents = documents
        self.context = context
        self.service = service
        self.logger = logger


def build_components(root=None, *, llm: Optional[LLMProvider] = None, embeddings: Optional[EmbeddingProvider] = None, vectors: Optional[VectorStore] = None) -> Components:
    cfg = load_config(root)
    logger = configure_logging(cfg)
    db = Database(cfg.database_path)
    llm = llm or build_llm_provider(cfg.section("llm"))
    emb_cfg = cfg.section("embeddings")
    embeddings = embeddings or build_embedding_provider(emb_cfg)
    vectors = vectors or build_vector_store(cfg.section("vector"))
    memory = MemoryManager(db, embeddings, vectors)
    datasets = StructuredDataService(db, llm)
    documents = DocumentService(cfg, db, embeddings, vectors, datasets)
    context = ContextEngine(memory, documents, datasets, cfg.section("retrieval"))
    service = EnterpriseAIService(cfg, db, llm, memory, context)
    return Components(cfg, db, llm, embeddings, vectors, memory, datasets, documents, context, service, logger)
