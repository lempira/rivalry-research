"""RAG functionality using Google File Search."""

from .file_search_client import (
    get_or_create_store,
    upload_document,
    check_document_exists,
    query_store,
)

__all__ = [
    "get_or_create_store",
    "upload_document",
    "check_document_exists",
    "query_store",
]

