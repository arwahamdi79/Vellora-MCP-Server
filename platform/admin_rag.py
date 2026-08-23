"""RAG document admin helpers (in-memory + optional rag/ integration)."""

_DOCS = []


def list_documents():
    return list(_DOCS)


def add_document(title: str, content: str):
    _DOCS.append({"title": title, "content": content})
    try:
        from rag.document_loader import ingest_text
        ingest_text(title, content)
    except Exception:
        pass
    return True


def remove_document(index: int):
    if 0 <= index < len(_DOCS):
        return _DOCS.pop(index)
    return None
