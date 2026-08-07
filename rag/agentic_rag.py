from .base_rag import BaseRAG
from .retriever import VectorRetriever
from .config import MAX_ITERATIONS


class AgenticRAG(BaseRAG):

    def __init__(self, llm):

        super().__init__(llm)

        self.retriever = VectorRetriever()

    @property
    def architecture_name(self):

        return "Agentic RAG"

    def _needs_more_context(self, chunks):

        if len(chunks) < 3:
            return True

        avg_score = sum(
            chunk.similarity_score
            for chunk in chunks
        ) / len(chunks)

        return avg_score < 0.80

    def retrieve(self, query):

        current_query = query

        retrieved = []

        iteration = 0

        while iteration < MAX_ITERATIONS:

            chunks = self.retriever.retrieve(
                current_query
            )

            retrieved.extend(chunks)

            if not self._needs_more_context(chunks):

                break

            current_query = (
                current_query
                + " more details"
            )

            iteration += 1

        unique = {}

        for chunk in retrieved:

            key = (
                chunk.source,
                chunk.chunk_index
            )

            if key not in unique:

                unique[key] = chunk

        results = sorted(

            unique.values(),

            key=lambda x: x.similarity_score,

            reverse=True

        )

        return results[:5]