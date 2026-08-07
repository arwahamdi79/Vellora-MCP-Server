from rank_bm25 import BM25Okapi
from typing import List

from .models import RetrievedChunk


class BM25Retriever:

    def __init__(self):

        self.documents = []

        self.metadata = []

        self.bm25 = None

    def build_index(self, chunks):

        self.documents = [
            chunk["content"]
            for chunk in chunks
        ]

        self.metadata = chunks

        tokenized = [
            doc.lower().split()
            for doc in self.documents
        ]

        self.bm25 = BM25Okapi(tokenized)

    def retrieve(
        self,
        query: str,
        top_k: int = 5
    ) -> List[RetrievedChunk]:

        if self.bm25 is None:

            return []

        scores = self.bm25.get_scores(
            query.lower().split()
        )

        ranked = sorted(

            enumerate(scores),

            key=lambda x: x[1],

            reverse=True

        )[:top_k]

        results = []

        for idx, score in ranked:

            meta = self.metadata[idx]

            results.append(

                RetrievedChunk(

                    content=meta["content"],

                    source=meta["source"],

                    doc_type=meta.get(
                        "doc_type",
                        "document"
                    ),

                    similarity_score=float(score),

                    chunk_index=meta["chunk_index"],

                    total_chunks=meta["total_chunks"],

                    retrieved_by="BM25",

                    metadata=meta

                )

            )

        return results