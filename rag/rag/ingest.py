"""
Build Vector Database
"""

from .document_loader import DocumentLoader
from .chunking import ChunkProcessor
from .vector_store import VectorStore
from .config import DOCUMENTS_DIR


class RAGIngestionPipeline:

    def __init__(self):

        self.loader = DocumentLoader(
            DOCUMENTS_DIR
        )

        self.chunker = ChunkProcessor()

        self.vector_store = VectorStore()

    def build(self):

        print("Loading Documents...")

        documents = self.loader.load()

        print(f"Loaded {len(documents)} documents")

        print("Chunking Documents...")

        chunks = self.chunker.split(
            documents
        )

        print(f"Generated {len(chunks)} chunks")

        print("Creating Embeddings...")

        self.vector_store.add_documents(
            chunks
        )

        print("Vector Database Ready!")

        return chunks


if __name__ == "__main__":

    pipeline = RAGIngestionPipeline()

    pipeline.build()