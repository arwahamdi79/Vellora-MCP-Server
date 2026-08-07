from .base_rag import BaseRAG
from .retriever import VectorRetriever


class NaiveRAG(BaseRAG):

    def __init__(self, llm):

        super().__init__(llm)

        self.retriever = VectorRetriever()

    @property
    def architecture_name(self):

        return "Naive RAG"

    def retrieve(self, query):

        return self.retriever.retrieve(query)