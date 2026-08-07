from .naive_rag import NaiveRAG
from .hybrid_rag import HybridRAG
from .agentic_rag import AgenticRAG


class RAGFactory:

    @staticmethod
    def create(

        rag_type,

        llm,

        **kwargs

    ):

        rag_type = rag_type.lower()

        if rag_type == "naive":

            return NaiveRAG(llm)

        if rag_type == "hybrid":

            return HybridRAG(

                llm,

                kwargs.get("bm25_chunks")

            )

        if rag_type == "agentic":

            return AgenticRAG(llm)

        raise ValueError(

            f"Unknown RAG type: {rag_type}"

        )