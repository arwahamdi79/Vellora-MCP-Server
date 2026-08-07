from typing import List
from rag.rag.models import RAGResponse


class RetrievalMetrics:

    @staticmethod
    def retrieval_accuracy(
        response: RAGResponse,
        expected_source: str
    ):

        for chunk in response.retrieved_chunks:

            if expected_source.lower() in chunk.source.lower():

                return 1

        return 0

    @staticmethod
    def average_similarity(
        response: RAGResponse
    ):

        if len(response.retrieved_chunks) == 0:

            return 0

        return sum(

            chunk.similarity_score

            for chunk in response.retrieved_chunks

        ) / len(response.retrieved_chunks)

    @staticmethod
    def latency(
        response: RAGResponse
    ):

        return response.metadata.latency_ms

    @staticmethod
    def confidence(
        response: RAGResponse
    ):

        return response.metadata.confidence

    @staticmethod
    def token_usage(
        response: RAGResponse
    ):

        return response.metadata.tokens_used