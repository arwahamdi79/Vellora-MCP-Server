"""
Embedding Model Wrapper
"""

from sentence_transformers import SentenceTransformer
from typing import List

from .config import EMBEDDING_MODEL


class EmbeddingModel:

    _instance = None

    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance.model = SentenceTransformer(
                EMBEDDING_MODEL
            )

        return cls._instance

    def encode(self, text: str):

        return self.model.encode(
            text,
            normalize_embeddings=True
        )

    def encode_batch(self, texts: List[str]):

        return self.model.encode(
            texts,
            normalize_embeddings=True
        )