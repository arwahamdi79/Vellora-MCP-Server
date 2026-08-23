# agent/rag_adapter.py
"""
Wires the existing `rag` package (rag.factory.RAGFactory) into the agent as
a pluggable component.

This module does NOT instantiate embeddings or an LLM itself - both are
injected by the caller. This sandbox has no network path to HuggingFace
(EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2" in rag/config.py)
or to any LLM API, so `PolicyRAG` below is real wiring against the actual
rag/ classes but is untested in this environment. It should be exercised in
CI/staging where those services are reachable before the demo is treated as
proof it works end-to-end.

Usage at agent startup (real environment, not runnable here):

    from langchain_anthropic import ChatAnthropic  # or whichever LLM client
    from rag.ingest import RAGIngestionPipeline
    from agent.rag_adapter import build_rag

    llm = ChatAnthropic(model="claude-...")
    chunks = RAGIngestionPipeline().build()          # needed for hybrid's BM25 index
    policy_rag = build_rag(llm, rag_type="hybrid", bm25_chunks=chunks)

    agent = VelloraAgent(rag=policy_rag)
"""

from typing import Any, List, Optional

from rag.factory import RAGFactory
from rag.models import RAGResponse


class PolicyRAG:
    """
    Stable `.ask(query) -> RAGResponse` interface over whichever RAG
    architecture (naive/hybrid/agentic) backs it, so agent.py doesn't need
    to know which one is configured.
    """

    def __init__(self, llm: Any, rag_type: str = 'hybrid', bm25_chunks: Optional[List[dict]] = None):
        self.rag_type = rag_type
        self._rag = RAGFactory.create(rag_type, llm, bm25_chunks=bm25_chunks)

    def ask(self, query: str) -> RAGResponse:
        return self._rag.process(query)


def build_rag(llm: Any, rag_type: str = 'hybrid', bm25_chunks: Optional[List[dict]] = None) -> PolicyRAG:
    """
    Factory entry point the agent calls once at startup.

    `llm` must be a LangChain-compatible chat model (anything with
    `.invoke(prompt)`, per rag/generator.py's LLMGenerator).
    `bm25_chunks` (only needed for rag_type='hybrid') come from
    `RAGIngestionPipeline.build()` in rag/ingest.py - the same chunks used to
    populate the vector store, reused here for keyword search.
    """
    return PolicyRAG(llm=llm, rag_type=rag_type, bm25_chunks=bm25_chunks)