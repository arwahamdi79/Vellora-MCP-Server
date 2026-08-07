# rag/simple_rag.py
"""
Simple RAG implementation that doesn't require chromadb.
Useful for testing and development.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class RetrievedChunk:
    content: str
    source: str
    doc_type: str
    similarity_score: float
    chunk_index: int
    total_chunks: int
    retrieved_by: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalMetadata:
    architecture: str
    retrieved_documents: int
    latency_ms: float
    tokens_used: int
    confidence: float
    verified: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RAGResponse:
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    metadata: RetrievalMetadata


class SimpleRAG:
    """
    Simple RAG implementation with mock data for testing.
    """
    
    def __init__(self):
        self.documents = [
            {
                'content': 'Batch approval requires quality tests to pass.',
                'source': 'quality_policy.md',
                'doc_type': 'policy'
            },
            {
                'content': 'Product recall must be approved by QA Manager.',
                'source': 'recall_policy.md',
                'doc_type': 'policy'
            },
            {
                'content': 'Quality tests include purity, potency, and stability.',
                'source': 'quality_guidelines.md',
                'doc_type': 'guideline'
            },
            {
                'content': 'Batch status can be: In Production, Pending QA, Approved, Rejected, Distributed, Recalled.',
                'source': 'batch_management.md',
                'doc_type': 'guide'
            },
            {
                'content': 'Penicillin allergy is a critical contraindication.',
                'source': 'medical_guidelines.md',
                'doc_type': 'medical'
            }
        ]
    
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """Simple keyword-based retrieval."""
        query_lower = query.lower()
        scored = []
        
        for i, doc in enumerate(self.documents):
            score = 0
            content_lower = doc['content'].lower()
            
            # Count keyword matches
            words = query_lower.split()
            for word in words:
                if word in content_lower:
                    score += 1
            
            if score > 0:
                scored.append({
                    'doc': doc,
                    'score': score / len(words) if words else 0,
                    'index': i
                })
        
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        results = []
        for item in scored[:top_k]:
            doc = item['doc']
            results.append(RetrievedChunk(
                content=doc['content'],
                source=doc['source'],
                doc_type=doc['doc_type'],
                similarity_score=item['score'],
                chunk_index=item['index'],
                total_chunks=len(self.documents),
                retrieved_by='Simple Keyword Search',
                metadata={'query': query}
            ))
        
        return results
    
    def process(self, query: str) -> RAGResponse:
        """Process a query and return a response."""
        chunks = self.retrieve(query)
        
        if not chunks:
            return RAGResponse(
                answer="No relevant documents found.",
                retrieved_chunks=[],
                metadata=RetrievalMetadata(
                    architecture="Simple RAG",
                    retrieved_documents=0,
                    latency_ms=0,
                    tokens_used=0,
                    confidence=0,
                    verified=False
                )
            )
        
        # Generate a simple answer
        answer = f"Based on retrieved documents: {chunks[0].content}"
        if len(chunks) > 1:
            answer += f" Also, {chunks[1].content}"
        
        return RAGResponse(
            answer=answer,
            retrieved_chunks=chunks,
            metadata=RetrievalMetadata(
                architecture="Simple RAG",
                retrieved_documents=len(chunks),
                latency_ms=10.0,
                tokens_used=len(answer.split()),
                confidence=0.8,
                verified=True
            )
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            'documents': len(self.documents),
            'type': 'Simple RAG',
            'architecture': 'keyword_based'
        }


def create_rag(rag_type: str = "simple", **kwargs):
    """Factory function to create RAG instances."""
    if rag_type == "simple":
        return SimpleRAG()
    elif rag_type == "hybrid":
        try:
            from .factory import RAGFactory
            return RAGFactory.create('hybrid', kwargs.get('llm'))
        except ImportError:
            return SimpleRAG()
    else:
        return SimpleRAG()