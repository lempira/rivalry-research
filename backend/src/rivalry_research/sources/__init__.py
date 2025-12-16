"""Source fetchers for biographical content."""

from .credibility import calculate_credibility_score, is_primary_source
from .image_fetcher import fetch_all_images
from .source_aggregator import fetch_sources_for_entity, process_existing_sources
from .source_scanner import (
    scan_raw_sources_directory,
    detect_unprocessed_sources,
    validate_manual_source,
    get_source_statistics,
)
from .validation import (
    calculate_event_confidence,
    compute_sources_summary,
    validate_event_sources,
)
from .wikipedia_fetcher import fetch_wikipedia_source
from .scholar_fetcher import fetch_scholar_sources
from .arxiv_fetcher import fetch_arxiv_sources
from .pdf_extractor import download_pdf, extract_text_from_pdf, extract_pdf_text, fetch_pdf_content, PDFExtractionResult

__all__ = [
    "fetch_wikipedia_source",
    "fetch_scholar_sources",
    "fetch_arxiv_sources",
    "fetch_sources_for_entity",
    "process_existing_sources",
    "scan_raw_sources_directory",
    "detect_unprocessed_sources",
    "validate_manual_source",
    "get_source_statistics",
    "fetch_all_images",
    "calculate_credibility_score",
    "is_primary_source",
    "calculate_event_confidence",
    "validate_event_sources",
    "compute_sources_summary",
    "download_pdf",
    "extract_text_from_pdf",
    "extract_pdf_text",
    "fetch_pdf_content",
    "PDFExtractionResult",
]

