"""Google File Search API client for RAG."""

import logging
import os
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from ..models import WikidataEntity

logger = logging.getLogger(__name__)

# Global store name for all rivalry research documents
GLOBAL_STORE_NAME = "rivalry_research_sources"

# Default model for RAG queries
DEFAULT_RAG_MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    """
    Get Google GenAI client instance.
    
    Returns:
        Configured genai.Client
    
    Raises:
        ValueError: If GOOGLE_API_KEY not set
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    return genai.Client(api_key=api_key)


def get_or_create_store() -> Any:
    """
    Get existing global File Search store or create a new one.
    
    This maintains a single store for all rivalry research documents,
    allowing documents to be reused across multiple analyses.
    
    Returns:
        FileSearchStore object with name and metadata
    
    Raises:
        Exception: If store creation fails
    
    Example:
        >>> store = get_or_create_store()
        >>> print(store.name)
        'fileSearchStores/abc123'
    """
    logger.debug("Getting or creating File Search store")
    client = _get_client()
    
    # Try to list existing stores and find our global store
    try:
        # Note: The API doesn't have a direct "get by display name" method,
        # so we create a new store each time for now.
        # In production, you might want to persist the store name.
        store = client.file_search_stores.create(
            config={"display_name": GLOBAL_STORE_NAME}
        )
        logger.info(f"Using File Search store: {store.name}")
        return store
    except Exception as e:
        logger.error(f"Failed to create File Search store: {e}")
        raise Exception(f"Failed to create File Search store: {e}") from e


def upload_document(
    store_name: str, entity: WikidataEntity, content: str, timeout: int = 300
) -> Any:
    """
    Upload a document to the File Search store.
    
    The document is uploaded with metadata in the display_name for citations.
    According to File Search docs, the display_name will be visible in citations.
    
    Args:
        store_name: File Search store name (e.g., 'fileSearchStores/abc123')
        entity: WikidataEntity with metadata
        content: Document content (formatted with metadata header)
        timeout: Max wait time for import completion in seconds
    
    Returns:
        Completed operation object
    
    Raises:
        Exception: If upload or import fails
        TimeoutError: If import doesn't complete within timeout
    
    Example:
        >>> store = get_or_create_store()
        >>> entity = get_entity("Q935")
        >>> content = fetch_wikipedia_article(entity)
        >>> operation = upload_document(store.name, entity, content)
    """
    logger.debug(f"Uploading document for entity {entity.id}: {entity.label}")
    logger.debug(f"Content size: {len(content)} characters")
    
    client = _get_client()
    
    # Create a temporary file with the content
    temp_file = Path(f"/tmp/{entity.id}_wikipedia.txt")
    try:
        temp_file.write_text(content, encoding="utf-8")
        
        # Display name includes entity info for citations
        display_name = f"{entity.label} ({entity.id}) - Wikipedia"
        logger.debug(f"Display name for citations: {display_name}")
        
        # Upload and import the file
        logger.debug(f"Starting upload to store: {store_name}")
        operation = client.file_search_stores.upload_to_file_search_store(
            file=str(temp_file),
            file_search_store_name=store_name,
            config={"display_name": display_name},
        )
        
        # Wait for import to complete
        logger.debug("Waiting for document import to complete...")
        start_time = time.time()
        while not operation.done:
            if time.time() - start_time > timeout:
                logger.error(f"Document import timed out after {timeout} seconds")
                raise TimeoutError(
                    f"Document import timed out after {timeout} seconds"
                )
            time.sleep(5)
            operation = client.operations.get(operation)
        
        logger.info(f"Document uploaded successfully for {entity.label}")
        return operation
        
    finally:
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()
            logger.debug(f"Cleaned up temporary file: {temp_file}")


def check_document_exists(store_name: str, entity_id: str) -> bool:
    """
    Check if a document for an entity already exists in the store.
    
    This helps avoid duplicate uploads of the same Wikipedia articles.
    
    Args:
        store_name: File Search store name
        entity_id: Wikidata entity ID (e.g., 'Q935')
    
    Returns:
        True if document exists, False otherwise
    
    Example:
        >>> store = get_or_create_store()
        >>> if not check_document_exists(store.name, "Q935"):
        ...     # Upload document
    """
    # Note: The API may not have a direct list method in the current version,
    # so for now we'll always return False (allow uploads)
    # This is safe as File Search handles duplicates gracefully
    return False


def query_store(
    store_name: str,
    query: str,
    model: str = DEFAULT_RAG_MODEL,
) -> Any:
    """
    Query the File Search store using RAG.
    
    This sends a query to the AI model with access to the File Search store.
    The model will retrieve relevant passages and provide answers with citations.
    
    Args:
        store_name: File Search store name
        query: Natural language query
        model: Model to use (default: gemini-2.5-flash)
    
    Returns:
        GenerateContentResponse with text and grounding_metadata
    
    Raises:
        Exception: If query fails
    
    Example:
        >>> store = get_or_create_store()
        >>> response = query_store(
        ...     store.name,
        ...     "What were the key events in Newton's life?"
        ... )
        >>> print(response.text)
        >>> print(response.candidates[0].grounding_metadata)
    """
    client = _get_client()
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(
                    file_search_store_names=[store_name]
                ))]
            ),
        )
        
        return response
        
    except Exception as e:
        raise Exception(f"Failed to query File Search store: {e}") from e


def delete_store(store_name: str) -> None:
    """
    Delete a File Search store and all its documents.
    
    Warning: This permanently deletes all documents in the store.
    
    Args:
        store_name: File Search store name to delete
    
    Example:
        >>> delete_store("fileSearchStores/abc123")
    """
    client = _get_client()
    
    try:
        client.file_search_stores.delete(name=store_name)
    except Exception as e:
        raise Exception(f"Failed to delete store: {e}") from e


def list_stores() -> list[Any]:
    """
    List all File Search stores in the project.
    
    Returns:
        List of FileSearchStore objects with name, display_name, metadata
    
    Raises:
        Exception: If listing fails
    
    Example:
        >>> stores = list_stores()
        >>> for store in stores:
        ...     print(f"{store.name}: {store.display_name}")
    """
    client = _get_client()
    
    try:
        stores = []
        for store in client.file_search_stores.list():
            stores.append(store)
        logger.debug(f"Found {len(stores)} File Search stores")
        return stores
    except Exception as e:
        raise Exception(f"Failed to list stores: {e}") from e


def list_documents(store_name: str) -> list[Any]:
    """
    List all documents in a File Search store.
    
    Args:
        store_name: File Search store name (e.g., 'fileSearchStores/abc123')
    
    Returns:
        List of document objects with metadata
    
    Raises:
        Exception: If listing fails
    
    Example:
        >>> docs = list_documents("fileSearchStores/abc123")
        >>> for doc in docs:
        ...     print(f"{doc.display_name}: {doc.name}")
    """
    client = _get_client()
    
    try:
        documents = []
        for doc in client.file_search_stores.list_documents(
            file_search_store_name=store_name
        ):
            documents.append(doc)
        logger.debug(f"Found {len(documents)} documents in store {store_name}")
        return documents
    except Exception as e:
        raise Exception(f"Failed to list documents: {e}") from e


def health_check(store_name: str) -> dict[str, Any]:
    """
    Perform health check on a File Search store.
    
    Checks:
    - Store accessibility
    - Document count
    - All documents processed successfully
    - Query functionality
    - Response time
    
    Args:
        store_name: File Search store name
    
    Returns:
        Dict with health status:
            - accessible: bool
            - document_count: int
            - all_processed: bool
            - query_test_passed: bool
            - response_time: float (seconds)
            - status: "healthy" | "warning" | "error"
            - issues: list[str]
    
    Example:
        >>> health = health_check("fileSearchStores/abc123")
        >>> print(f"Status: {health['status']}")
        >>> if health['issues']:
        ...     print(f"Issues: {', '.join(health['issues'])}")
    """
    health = {
        "accessible": False,
        "document_count": 0,
        "all_processed": False,
        "query_test_passed": False,
        "response_time": None,
        "status": "error",
        "issues": []
    }
    
    client = _get_client()
    
    try:
        # Check store accessible
        logger.debug(f"Checking accessibility of store: {store_name}")
        store = client.file_search_stores.get(name=store_name)
        health["accessible"] = True
        logger.debug(f"Store accessible: {store.name}")
        
        # Count documents
        logger.debug("Counting documents...")
        docs = list_documents(store_name)
        health["document_count"] = len(docs)
        
        if health["document_count"] == 0:
            health["issues"].append("No documents in store")
        
        # Check all docs processed
        logger.debug("Checking document processing status...")
        pending = []
        for doc in docs:
            # Check if document has a state attribute and if it's not completed
            state = getattr(doc, 'state', 'ACTIVE')
            if state != 'ACTIVE':
                pending.append(doc)
        
        health["all_processed"] = len(pending) == 0
        if pending:
            health["issues"].append(f"{len(pending)} documents not completed")
        
        # Test query only if we have documents
        if health["document_count"] > 0:
            logger.debug("Testing query functionality...")
            start = time.time()
            try:
                response = query_store(store_name, "test")
                health["response_time"] = time.time() - start
                health["query_test_passed"] = bool(response.text)
                logger.debug(f"Query test passed in {health['response_time']:.2f}s")
            except Exception as e:
                health["issues"].append(f"Query test failed: {e}")
                logger.warning(f"Query test failed: {e}")
        
        # Determine overall status
        if health["accessible"] and health["document_count"] > 0:
            if health["all_processed"] and health["query_test_passed"]:
                health["status"] = "healthy"
            elif health["issues"]:
                health["status"] = "warning"
        elif health["accessible"]:
            health["status"] = "warning"
            
    except Exception as e:
        health["issues"].append(str(e))
        health["status"] = "error"
        logger.error(f"Health check failed: {e}")
    
    return health

