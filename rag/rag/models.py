"""
RAG Data Models
===============

Shared data structures used across all RAG architectures.

Author: Vellora Team
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


# ==========================================================
# Retrieved Chunk
# ==========================================================

@dataclass
class RetrievedChunk:
    """
    Represents one retrieved document chunk.
    """

    content: str
    source: str
    doc_type: str

    similarity_score: float

    chunk_index: int
    total_chunks: int

    retrieved_by: str

    metadata: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Retrieval Metadata
# ==========================================================

@dataclass
class RetrievalMetadata:

    architecture: str

    retrieved_documents: int

    latency_ms: float

    tokens_used: int

    confidence: float

    verified: bool

    timestamp: datetime = field(default_factory=datetime.utcnow)


# ==========================================================
# Final RAG Response
# ==========================================================

@dataclass
class RAGResponse:

    answer: str

    retrieved_chunks: List[RetrievedChunk]

    metadata: RetrievalMetadata