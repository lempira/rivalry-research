"""Fetch images for entities from multiple public domain sources."""

import logging
import re
import time
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings
from ..models import EntityImage, WikidataEntity

logger = logging.getLogger(__name__)

# User agent for API compliance
USER_AGENT = "RivalryResearch/0.1.0 (https://github.com/user/rivalry-research)"

# Rate limiting per source
_last_request_times: dict[str, float] = {}
_rate_limits: dict[str, float] = {
    "commons": 0.1,  # 100ms
    "wikipedia": 0.5,  # 500ms
    "loc": 0.2,  # 200ms
    "europeana": 0.5,  # 500ms
}


def _rate_limit(source: str) -> None:
    """Enforce rate limiting between requests for a specific source."""
    now = time.time()
    last_time = _last_request_times.get(source, 0.0)
    min_interval = _rate_limits.get(source, 0.5)
    time_since_last = now - last_time
    if time_since_last < min_interval:
        time.sleep(min_interval - time_since_last)
    _last_request_times[source] = time.time()


def _dedupe_by_url(images: list[EntityImage]) -> list[EntityImage]:
    """Remove duplicate images by URL."""
    seen_urls: set[str] = set()
    deduped: list[EntityImage] = []
    for img in images:
        if img.url not in seen_urls:
            seen_urls.add(img.url)
            deduped.append(img)
    return deduped


def fetch_commons_images(
    entity: WikidataEntity, timeout: float = 10.0
) -> list[EntityImage]:
    """
    Fetch images from Wikimedia Commons via Wikidata P18 property.

    Args:
        entity: WikidataEntity with claims populated
        timeout: Request timeout in seconds

    Returns:
        List of EntityImage objects from Commons
    """
    images: list[EntityImage] = []

    # P18 is the "image" property in Wikidata
    p18_claims = entity.claims.get("P18", [])
    if not p18_claims:
        logger.debug(f"No P18 (image) claim for {entity.id}")
        return images

    for claim in p18_claims:
        try:
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            if datavalue.get("type") != "string":
                continue

            filename = datavalue.get("value", "")
            if not filename:
                continue

            # Build Commons URL - spaces become underscores, then URL encode
            # Use width parameter to ensure non-web formats (TIF, etc.) are converted
            encoded_filename = quote(filename.replace(" ", "_"))
            full_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_filename}?width=1200"
            thumb_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_filename}?width=300"

            images.append(
                EntityImage(
                    url=full_url,
                    thumbnail_url=thumb_url,
                    source="commons",
                    title=filename.replace("_", " "),
                    license="cc-by-sa",  # Most Commons images are CC-BY-SA
                    attribution=f"Wikimedia Commons: {filename}",
                )
            )
            logger.debug(f"Found Commons image for {entity.id}: {filename}")

        except Exception as e:
            logger.warning(f"Error processing P18 claim for {entity.id}: {e}")
            continue

    return images


def fetch_wikipedia_images(
    entity: WikidataEntity, timeout: float = 30.0
) -> list[EntityImage]:
    """
    Fetch images from Wikipedia article infobox.

    Args:
        entity: WikidataEntity with wikipedia_url populated
        timeout: Request timeout in seconds

    Returns:
        List of EntityImage objects from Wikipedia
    """
    images: list[EntityImage] = []

    if not entity.wikipedia_url:
        logger.debug(f"No Wikipedia URL for {entity.id}")
        return images

    _rate_limit("wikipedia")

    try:
        headers = {"User-Agent": USER_AGENT}

        # Use Wikipedia API to get page images
        params = {
            "action": "query",
            "titles": entity.wikipedia_url.split("/wiki/")[-1],
            "prop": "pageimages",
            "piprop": "original|thumbnail",
            "pithumbsize": 300,
            "format": "json",
        }

        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                "https://en.wikipedia.org/w/api.php", headers=headers, params=params
            )
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_data in pages.values():
                if "original" in page_data:
                    original = page_data["original"]
                    thumbnail = page_data.get("thumbnail", {})

                    images.append(
                        EntityImage(
                            url=original.get("source", ""),
                            thumbnail_url=thumbnail.get("source"),
                            source="wikipedia",
                            title=f"Wikipedia image for {entity.label}",
                            license="cc-by-sa",
                            attribution=f"Wikipedia: {entity.label}",
                        )
                    )
                    logger.debug(f"Found Wikipedia image for {entity.id}")

    except Exception as e:
        logger.warning(f"Error fetching Wikipedia images for {entity.id}: {e}")

    return images


def fetch_loc_images(
    entity: WikidataEntity, max_results: int = 5, timeout: float = 15.0
) -> list[EntityImage]:
    """
    Fetch images from Library of Congress.

    Args:
        entity: WikidataEntity with label for search
        max_results: Maximum number of images to return
        timeout: Request timeout in seconds

    Returns:
        List of EntityImage objects from LoC
    """
    images: list[EntityImage] = []

    _rate_limit("loc")

    try:
        headers = {"User-Agent": USER_AGENT}

        # Search LoC prints and photographs
        search_query = quote(entity.label)
        url = f"https://www.loc.gov/pictures/search/?q={search_query}&fo=json&c={max_results}"

        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            for item in results:
                image_info = item.get("image", {})
                if not image_info:
                    continue

                # LoC provides different image sizes
                full_url = image_info.get("full", image_info.get("large", ""))
                thumb_url = image_info.get("thumb", image_info.get("square_thumb", ""))

                if not full_url:
                    continue

                # Ensure URLs are absolute
                if full_url.startswith("//"):
                    full_url = "https:" + full_url
                if thumb_url and thumb_url.startswith("//"):
                    thumb_url = "https:" + thumb_url

                title = item.get("title", "")

                images.append(
                    EntityImage(
                        url=full_url,
                        thumbnail_url=thumb_url if thumb_url else None,
                        source="loc",
                        title=title[:200] if title else f"Library of Congress: {entity.label}",
                        license="public_domain",
                        attribution="Library of Congress",
                    )
                )
                logger.debug(f"Found LoC image for {entity.id}: {title[:50]}")

    except Exception as e:
        logger.warning(f"Error fetching LoC images for {entity.id}: {e}")

    return images


def fetch_europeana_images(
    entity: WikidataEntity, max_results: int = 5, timeout: float = 15.0
) -> list[EntityImage]:
    """
    Fetch images from Europeana.

    Args:
        entity: WikidataEntity with label for search
        max_results: Maximum number of images to return
        timeout: Request timeout in seconds

    Returns:
        List of EntityImage objects from Europeana
    """
    images: list[EntityImage] = []

    settings = get_settings()
    if not settings.europeana_api_key:
        logger.debug("Europeana API key not configured, skipping")
        return images

    _rate_limit("europeana")

    try:
        headers = {"User-Agent": USER_AGENT}

        # Search Europeana for images
        params = {
            "wskey": settings.europeana_api_key,
            "query": entity.label,
            "qf": "TYPE:IMAGE",
            "reusability": "open",  # Only open license images
            "rows": max_results,
            "profile": "rich",
        }

        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                "https://api.europeana.eu/record/v2/search.json",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            for item in items:
                # Get the best available image URL
                edmIsShownBy = item.get("edmIsShownBy", [])
                edmPreview = item.get("edmPreview", [])

                full_url = edmIsShownBy[0] if edmIsShownBy else None
                thumb_url = edmPreview[0] if edmPreview else None

                if not full_url and not thumb_url:
                    continue

                title = item.get("title", [""])[0] if item.get("title") else ""
                rights = item.get("rights", [""])[0] if item.get("rights") else ""

                # Map Europeana rights to simple license
                license_type = "public_domain"
                if "creativecommons.org/licenses/by" in rights:
                    license_type = "cc-by"
                elif "creativecommons.org/licenses/by-sa" in rights:
                    license_type = "cc-by-sa"

                data_provider = item.get("dataProvider", ["Europeana"])[0]

                images.append(
                    EntityImage(
                        url=full_url or thumb_url,
                        thumbnail_url=thumb_url,
                        source="europeana",
                        title=title[:200] if title else f"Europeana: {entity.label}",
                        license=license_type,
                        attribution=f"Europeana / {data_provider}",
                    )
                )
                logger.debug(f"Found Europeana image for {entity.id}: {title[:50]}")

    except Exception as e:
        logger.warning(f"Error fetching Europeana images for {entity.id}: {e}")

    return images


def fetch_all_images(
    entity: WikidataEntity, max_per_source: int = 5
) -> list[EntityImage]:
    """
    Fetch images from all configured sources.

    Sources are fetched in priority order:
    1. Wikimedia Commons (P18) - canonical image
    2. Wikipedia - article images
    3. Library of Congress - historical photos
    4. Europeana - European cultural heritage (if API key configured)

    Args:
        entity: WikidataEntity to fetch images for
        max_per_source: Maximum images per source (except Commons which returns all P18)

    Returns:
        Deduplicated list of EntityImage objects, ordered by source priority
    """
    logger.info(f"Fetching images for {entity.label} ({entity.id})")

    all_images: list[EntityImage] = []

    # 1. Wikimedia Commons (highest priority - canonical images)
    commons_images = fetch_commons_images(entity)
    all_images.extend(commons_images)
    logger.debug(f"Commons: {len(commons_images)} images")

    # 2. Wikipedia article images
    wikipedia_images = fetch_wikipedia_images(entity)
    all_images.extend(wikipedia_images[:max_per_source])
    logger.debug(f"Wikipedia: {len(wikipedia_images)} images")

    # 3. Library of Congress
    loc_images = fetch_loc_images(entity, max_results=max_per_source)
    all_images.extend(loc_images)
    logger.debug(f"LoC: {len(loc_images)} images")

    # 4. Europeana (if configured)
    europeana_images = fetch_europeana_images(entity, max_results=max_per_source)
    all_images.extend(europeana_images)
    logger.debug(f"Europeana: {len(europeana_images)} images")

    # Deduplicate by URL
    deduped = _dedupe_by_url(all_images)

    logger.info(f"Total images for {entity.id}: {len(deduped)} (after dedup)")

    return deduped