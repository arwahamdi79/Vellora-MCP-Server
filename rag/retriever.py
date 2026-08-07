from .models import RetrievedChunk
from .vector_store import VectorStore
from .config import TOP_K


class VectorRetriever:

    def __init__(self):

        self.vector_store = VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K
    ):

        results = self.vector_store.similarity_search(
            query,
            top_k
        )

        chunks = []

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, distance in zip(
            docs,
            metas,
            distances
        ):

            chunks.append(

                RetrievedChunk(

                    content=doc,

                    source=meta["source"],

                    doc_type=meta["doc_type"],

                    similarity_score=1 - distance,

                    chunk_index=meta["chunk_index"],

                    total_chunks=meta["total_chunks"],

                    retrieved_by="Vector Search",

                    metadata=meta

                )

            )

        return chunks