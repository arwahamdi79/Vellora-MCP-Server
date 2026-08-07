from chromadb import PersistentClient
from .config import CHROMA_DB_DIR, COLLECTION_NAME
from .embedding_model import EmbeddingModel


class VectorStore:

    def __init__(self):

        self.client = PersistentClient(path=str(CHROMA_DB_DIR))

        self.embedding_model = EmbeddingModel()

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME
        )

    def add_documents(self, chunks):

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for i, chunk in enumerate(chunks):

            ids.append(f"chunk_{i}")

            documents.append(chunk["content"])

            embeddings.append(
                self.embedding_model.encode(
                    chunk["content"]
                ).tolist()
            )

            metadatas.append(
                {
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "doc_type": chunk.get("doc_type", "document"),
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"]
                }
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def similarity_search(self, query, top_k=5):

        embedding = self.embedding_model.encode(query).tolist()

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )

        return results