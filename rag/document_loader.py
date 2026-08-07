from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader
)


class DocumentLoader:

    def __init__(self, documents_dir):

        self.documents_dir = Path(documents_dir)

    def load(self):

        documents = []

        for file in self.documents_dir.iterdir():

            suffix = file.suffix.lower()

            if suffix == ".pdf":

                loader = PyPDFLoader(str(file))

            elif suffix == ".txt":

                loader = TextLoader(str(file))

            elif suffix == ".docx":

                loader = Docx2txtLoader(str(file))

            else:

                continue

            documents.extend(loader.load())

        return documents