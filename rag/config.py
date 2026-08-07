from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DOCUMENTS_DIR = BASE_DIR / "documents"

CHROMA_DB_DIR = BASE_DIR / "chroma_db"

COLLECTION_NAME = "vellora_documents"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

TOP_K = 5

CHUNK_SIZE = 700

CHUNK_OVERLAP = 100

SIMILARITY_THRESHOLD = 0.70

MAX_ITERATIONS = 3