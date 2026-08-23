# agent/search_adapter.py
"""
Adapter matching the `search_tool(query, top_k) -> List[Tuple[str, float]]`
interface that grounded_reflect.py (and decompose_search.py) expect, wrapping
the existing rag/ package's VectorRetriever.

Same situation as agent/rag_adapter.py: this is real wiring against the
actual rag/ classes, but untested in this sandbox. VectorRetriever needs a
populated Chroma collection (rag.vector_store.VectorStore) and the
HuggingFace embedding model configured in rag/config.py
(EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"), neither
reachable here - no network path to HuggingFace or a running Chroma index.
grounded_reflect.py's own demo uses fake_search_knowledge_base for exactly
this reason. Swap this in once you're running somewhere those services
exist, and verify it against a real query before trusting it in the demo.
"""

from typing import List, Optional, Tuple

from rag.retriever import VectorRetriever


_retriever: Optional[VectorRetriever] = None


def _get_retriever() -> VectorRetriever:
    global _retriever
    if _retriever is None:
        _retriever = VectorRetriever()
    return _retriever


def search_knowledge_base(query: str, top_k: int = 3) -> List[Tuple[str, float]]:
    """
    Real search_knowledge_base tool: wraps VectorRetriever.retrieve(),
    reshaped from RetrievedChunk objects to the (content, score) tuples
    grounded_reflect.py's _search() expects.
    """
    chunks = _get_retriever().retrieve(query, top_k=top_k)
    return [(chunk.content, chunk.similarity_score) for chunk in chunks]