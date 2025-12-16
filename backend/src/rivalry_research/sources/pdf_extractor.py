"""PDF download and text extraction utilities."""

import logging
from dataclasses import dataclass

import httpx
import pymupdf

logger = logging.getLogger(__name__)

# Common headers to mimic browser requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RivalryResearch/1.0; +https://github.com/rivalry-research)",
    "Accept": "application/pdf,*/*",
}

# Timeout for PDF downloads (30 seconds)
DOWNLOAD_TIMEOUT = 30.0


@dataclass
class PDFExtractionResult:
    """Result of PDF text extraction."""

    text: str
    page_count: int
    file_size_bytes: int
    success: bool
    error: str | None = None


def download_pdf(url: str, timeout: float = DOWNLOAD_TIMEOUT) -> bytes | None:
    """
    Download a PDF file from a URL.

    Args:
        url: URL to the PDF file
        timeout: Request timeout in seconds

    Returns:
        PDF file bytes, or None if download failed
    """
    logger.debug(f"Downloading PDF from: {url}")

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=DEFAULT_HEADERS)
            response.raise_for_status()

            # Verify we got a PDF
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                logger.warning(f"Response may not be PDF: content-type={content_type}")

            logger.debug(f"Downloaded {len(response.content)} bytes")
            return response.content

    except httpx.TimeoutException:
        logger.warning(f"Timeout downloading PDF from {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error downloading PDF: {e.response.status_code} from {url}")
        return None
    except Exception as e:
        logger.warning(f"Failed to download PDF from {url}: {e}")
        return None


def extract_text_from_pdf(pdf_bytes: bytes) -> PDFExtractionResult:
    """
    Extract text content from PDF bytes.

    Args:
        pdf_bytes: Raw PDF file bytes

    Returns:
        PDFExtractionResult with extracted text and metadata
    """
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        text_parts = []
        for page in doc:
            page_text = page.get_text(sort=True)
            if page_text.strip():
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        page_count = len(doc)
        doc.close()

        logger.debug(f"Extracted {len(full_text)} chars from {page_count} pages")

        return PDFExtractionResult(
            text=full_text,
            page_count=page_count,
            file_size_bytes=len(pdf_bytes),
            success=True,
        )

    except Exception as e:
        logger.warning(f"Failed to extract text from PDF: {e}")
        return PDFExtractionResult(
            text="",
            page_count=0,
            file_size_bytes=len(pdf_bytes),
            success=False,
            error=str(e),
        )


def fetch_pdf_content(url: str) -> tuple[PDFExtractionResult, bytes] | None:
    """
    Download a PDF and extract its text content.

    Convenience function that combines download and extraction.

    Args:
        url: URL to the PDF file

    Returns:
        Tuple of (PDFExtractionResult, pdf_bytes) if successful, None if download failed
    """
    pdf_bytes = download_pdf(url)
    if pdf_bytes is None:
        return None

    return extract_text_from_pdf(pdf_bytes), pdf_bytes