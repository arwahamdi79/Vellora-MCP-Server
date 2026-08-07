from langchain.text_splitter import RecursiveCharacterTextSplitter

from .config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP
)


class ChunkProcessor:

    def __init__(self):

        self.splitter = RecursiveCharacterTextSplitter(

            chunk_size=CHUNK_SIZE,

            chunk_overlap=CHUNK_OVERLAP

        )

    def split(self, documents):

        chunks = self.splitter.split_documents(
            documents
        )

        processed = []

        total = len(chunks)

        for i, chunk in enumerate(chunks):

            processed.append(

                {

                    "content": chunk.page_content,

                    "source": chunk.metadata.get(
                        "source",
                        "Unknown"
                    ),

                    "page": chunk.metadata.get(
                        "page",
                        0
                    ),

                    "chunk_index": i,

                    "total_chunks": total,

                    "doc_type": "document"

                }

            )

        return processed