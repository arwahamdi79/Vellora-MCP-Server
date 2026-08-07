"""
Self-RAG Verification
"""

from typing import List
from .models import RetrievedChunk


class SelfRAGVerifier:

    def __init__(self):

        pass

    def verify_retrieval(
        self,
        chunks: List[RetrievedChunk]
    ) -> bool:

        if len(chunks) == 0:

            return False

        best_score = max(

            chunk.similarity_score
            for chunk in chunks

        )

        return best_score >= 0.70

    def verify_grounding(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> bool:

        answer = answer.lower()

        matched = 0

        for chunk in chunks:

            words = chunk.content.lower().split()

            overlap = sum(
                1
                for word in words
                if word in answer
            )

            if overlap > 5:

                matched += 1

        return matched > 0

    def verify(
        self,
        answer,
        chunks
    ):

        retrieval_ok = self.verify_retrieval(chunks)

        grounding_ok = self.verify_grounding(
            answer,
            chunks
        )

        confidence = 0.0

        if retrieval_ok:

            confidence += 0.5

        if grounding_ok:

            confidence += 0.5

        return {

            "verified": retrieval_ok and grounding_ok,

            "confidence": confidence,

            "retrieval_ok": retrieval_ok,

            "grounding_ok": grounding_ok

        }