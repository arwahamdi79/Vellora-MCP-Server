from .base_rag import BaseRAG
from .retriever import VectorRetriever
from .bm25_retriever import BM25Retriever


class HybridRAG(BaseRAG):

    def __init__(
        self,
        llm,
        bm25_chunks=None
    ):

        super().__init__(llm)

        self.vector = VectorRetriever()

        self.bm25 = BM25Retriever()

        if bm25_chunks:

            self.bm25.build_index(
                bm25_chunks
            )

    @property
    def architecture_name(self):

        return "Hybrid RAG"

    def retrieve(self, query):

        vector_results = self.vector.retrieve(
            query
        )

        bm25_results = self.bm25.retrieve(
            query
        )

        merged = {}

        for chunk in vector_results + bm25_results:

            key = (
                chunk.source,
                chunk.chunk_index
            )

            if key not in merged:

                merged[key] = chunk

            else:

                merged[key].similarity_score = max(

                    merged[key].similarity_score,

                    chunk.similarity_score

                )

        results = sorted(

            merged.values(),

            key=lambda x: x.similarity_score,

            reverse=True

        )

        return results[:5]