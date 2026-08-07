import time
from abc import ABC, abstractmethod

from .generator import LLMGenerator
from .verifier import SelfRAGVerifier
from .models import (
    RAGResponse,
    RetrievalMetadata
)


class BaseRAG(ABC):

    def __init__(self, llm):

        self.generator = LLMGenerator(llm)

        self.verifier = SelfRAGVerifier()

    @abstractmethod
    def retrieve(self, query):

        pass

    @property
    @abstractmethod
    def architecture_name(self):

        pass

    def process(self, query):

        start = time.time()

        chunks = self.retrieve(query)

        if len(chunks) == 0:

            metadata = RetrievalMetadata(

                architecture=self.architecture_name,

                retrieved_documents=0,

                latency_ms=0,

                tokens_used=0,

                confidence=0,

                verified=False

            )

            return RAGResponse(

                answer="No relevant documents found.",

                retrieved_chunks=[],

                metadata=metadata

            )

        answer = self.generator.generate_answer(

            query,

            chunks

        )

        verification = self.verifier.verify(

            answer,

            chunks

        )

        latency = (time.time() - start) * 1000

        metadata = RetrievalMetadata(

            architecture=self.architecture_name,

            retrieved_documents=len(chunks),

            latency_ms=latency,

            tokens_used=len(answer.split()),

            confidence=verification["confidence"],

            verified=verification["verified"]

        )

        return RAGResponse(

            answer=answer,

            retrieved_chunks=chunks,

            metadata=metadata

        )