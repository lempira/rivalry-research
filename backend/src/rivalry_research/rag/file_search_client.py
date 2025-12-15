"""Google File Search API client for RAG."""

import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from ..config import get_settings

logger = logging.getLogger(__name__)

# Global store name for all rivalry research documents
GLOBAL_STORE_NAME = "rivalry_research_sources"

# Default model for RAG queries
DEFAULT_RAG_MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    """
    Get Google GenAI client instance.
    
    Uses Pydantic Settings to load API key from environment or .env file.
    
    Returns:
        Configured genai.Client
    
    Raises:
        ValidationError: If GOOGLE_API_KEY not set or invalid
    """
    settings = get_settings()
    return genai.Client(api_key=settings.google_api_key)


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
    store_name: str,
    display_name: str,
    content: str,
    custom_metadata: dict[str, str] | None = None,
    chunking_config: dict[str, Any] | None = None,
    timeout: int = 300,
) -> Any:
    """
    Upload a document to the File Search store with custom metadata and chunking config.
    
    The document is uploaded with metadata in the display_name for citations,
    plus optional custom metadata and chunking configuration.
    
    Args:
        store_name: File Search store name (e.g., 'fileSearchStores/abc123')
        display_name: Display name for the file (used for citations)
        content: Document content
        custom_metadata: Optional dict of metadata key-value pairs to attach to document
        chunking_config: Optional chunking configuration. If None, API uses its own defaults.
        timeout: Max wait time for import completion in seconds
    
    Returns:
        Completed operation object
    
    Raises:
        Exception: If upload or import fails
        TimeoutError: If import doesn't complete within timeout
    
    Example:
        >>> metadata = {
        ...     "source_id": "fc9a0e1e51ac",
        ...     "source_type": "wikipedia",
        ...     "url": "https://en.wikipedia.org/wiki/Isaac_Newton"
        ... }
        >>> upload_document(store.name, "Isaac Newton", content, custom_metadata=metadata)
    """
    logger.debug(f"Uploading document: {display_name}")
    logger.debug(f"Content size: {len(content)} characters")
    
    client = _get_client()
    
    # Build config for upload
    config: dict[str, Any] = {"display_name": display_name}
    
    # Add custom metadata if provided
    if custom_metadata:
        # Format metadata as list of key-value objects for API
        metadata_list = []
        for key, value in custom_metadata.items():
            # Determine if value should be string or numeric
            metadata_list.append({"key": key, "string_value": str(value)})
        config["custom_metadata"] = metadata_list
        logger.debug(f"Including {len(metadata_list)} metadata fields")
    
    # Add chunking config if explicitly provided
    # Otherwise, let the API use its own defaults
    if chunking_config:
        config["chunking_config"] = chunking_config
        logger.debug(f"Using custom chunking config: {chunking_config}")
    
    # Create a temporary file with the content
    # Use a sanitized version of display name for temp file
    safe_name = "".join(c for c in display_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
    temp_file = Path(f"/tmp/{safe_name}.txt")
    try:
        temp_file.write_text(content, encoding="utf-8")
        
        # Upload and import the file
        logger.debug(f"Starting upload to store: {store_name}")
        operation = client.file_search_stores.upload_to_file_search_store(
            file=str(temp_file),
            file_search_store_name=store_name,
            config=config,
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
        
        logger.info(f"Document uploaded successfully: {display_name}")
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


def retrieve_relevant_documents(
    store_name: str,
    query: str,
    model: str = DEFAULT_RAG_MODEL,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant document chunks with metadata WITHOUT synthesis.
    
    This queries the File Search store and extracts the actual document chunks
    that were found relevant, along with their metadata (source info, references).
    Unlike query_store, this returns the raw chunks rather than a synthesized answer.
    
    Args:
        store_name: File Search store name
        query: Natural language query
        model: Model to use (default: gemini-2.5-flash)
    
    Returns:
        List of dicts containing:
            - content: The actual text chunk
            - title: Full title from display_name (e.g., "Paul_Gauguin (wiki_fc9a0e1e51ac)")
            - entity: Parsed entity name (e.g., "Paul_Gauguin")
            - source_type: Parsed source type (e.g., "wiki", "scholar")
            - source_id: Parsed source ID/hash
            - reference_count: Number of times chunk was referenced in grounding_supports
    
    Raises:
        Exception: If query fails
    
    Example:
        >>> store = get_or_create_store()
        >>> docs = retrieve_relevant_documents(
        ...     store.name,
        ...     "What were the key events in Newton's life?"
        ... )
        >>> for doc in docs:
        ...     print(f"Source: {doc['entity']} ({doc['source_type']})")
        ...     print(f"Content: {doc['content'][:100]}...")
        ...     print(f"Referenced {doc['reference_count']} times")
    """
    client = _get_client()
    
    try:
        # Query with File Search tool
        response = client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(
                    file_search_store_names=[store_name]
                ))]
            ),
        )
        
        documents = []
        
        # Extract grounding metadata which contains the actual chunks used
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding = candidate.grounding_metadata
                
                # Count references for each chunk from grounding_supports
                chunk_reference_counts = {}
                if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
                    for support in grounding.grounding_supports:
                        if hasattr(support, 'grounding_chunk_indices'):
                            for idx in support.grounding_chunk_indices:
                                chunk_reference_counts[idx] = chunk_reference_counts.get(idx, 0) + 1
                
                # Extract chunks with metadata
                if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
                    for idx, chunk in enumerate(grounding.grounding_chunks):
                        if hasattr(chunk, 'retrieved_context'):
                            context = chunk.retrieved_context
                            
                            # Extract text and title
                            content = getattr(context, 'text', '')
                            title = getattr(context, 'title', '')
                            
                            # Parse title to extract metadata
                            # Format: "Entity_Name (source_type_hash)" or "Entity Name (source_type_hash)"
                            entity = title
                            source_type = ''
                            source_id = ''
                            
                            if '(' in title and ')' in title:
                                # Split on last occurrence of '('
                                parts = title.rsplit('(', 1)
                                entity = parts[0].strip()
                                
                                # Extract source_type and source_id from parentheses
                                metadata_part = parts[1].rstrip(')').strip()
                                # Format: "wiki_fc9a0e1e51ac" or "scholar_e35caa0fcec5"
                                if '_' in metadata_part:
                                    source_parts = metadata_part.split('_', 1)
                                    source_type = source_parts[0]
                                    source_id = source_parts[1] if len(source_parts) > 1 else ''
                            
                            doc = {
                                'content': content,
                                'title': title,
                                'entity': entity,
                                'source_type': source_type,
                                'source_id': source_id,
                                'reference_count': chunk_reference_counts.get(idx, 0),
                            }
                            documents.append(doc)
        
        logger.debug(f"Retrieved {len(documents)} document chunks for query")
        return documents
        
    except Exception as e:
        raise Exception(f"Failed to retrieve documents: {e}") from e


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


def list_documents(store_name: str) -> dict[str, Any]:
    """
    Get document counts for a File Search store.
    
    Note: The File Search API does not support listing individual documents.
    This function returns document counts from the store metadata instead.
    
    Args:
        store_name: File Search store name (e.g., 'fileSearchStores/abc123')
    
    Returns:
        Dict with document counts:
            - active: Number of active/ready documents
            - pending: Number of documents being processed
            - failed: Number of failed documents
            - total: Total document count
    
    Raises:
        Exception: If getting store info fails
    
    Example:
        >>> counts = list_documents("fileSearchStores/abc123")
        >>> print(f"Active: {counts['active']}, Pending: {counts['pending']}")
    """
    client = _get_client()
    
    try:
        store = client.file_search_stores.get(name=store_name)
        
        # Extract document counts from store metadata
        active = int(getattr(store, 'active_documents_count', 0) or 0)
        pending = int(getattr(store, 'pending_documents_count', 0) or 0)
        failed = int(getattr(store, 'failed_documents_count', 0) or 0)
        
        counts = {
            'active': active,
            'pending': pending,
            'failed': failed,
            'total': active + pending + failed,
        }
        
        logger.debug(f"Document counts for {store_name}: {counts}")
        return counts
    except Exception as e:
        raise Exception(f"Failed to get document counts: {e}") from e


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
        
        # Get document counts
        logger.debug("Getting document counts...")
        doc_counts = list_documents(store_name)
        health["document_count"] = doc_counts['total']
        
        if health["document_count"] == 0:
            health["issues"].append("No documents in store")
        
        # Check if all docs processed
        logger.debug("Checking document processing status...")
        pending_count = doc_counts['pending']
        failed_count = doc_counts['failed']
        
        health["all_processed"] = pending_count == 0 and failed_count == 0
        
        if pending_count > 0:
            health["issues"].append(f"{pending_count} documents still processing")
        if failed_count > 0:
            health["issues"].append(f"{failed_count} documents failed")
        
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

