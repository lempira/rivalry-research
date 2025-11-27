"""Pydantic models for Wikidata entities, relationships, and rivalry analysis."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EntitySearchResult(BaseModel):
    """Search result for entity disambiguation."""

    id: str = Field(..., description="Wikidata entity ID (e.g., 'Q42')")
    label: str = Field(..., description="Primary label/name of the entity")
    description: str | None = Field(None, description="Brief description of the entity")
    match_score: float | None = Field(
        None, description="Search relevance score if available"
    )


class WikidataEntity(BaseModel):
    """Full Wikidata entity with all properties."""

    id: str = Field(..., description="Wikidata entity ID (e.g., 'Q42')")
    label: str = Field(..., description="Primary label in English")
    description: str | None = Field(None, description="Entity description")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    claims: dict[str, Any] = Field(
        default_factory=dict, description="All claims/statements for this entity"
    )
    sitelinks: dict[str, Any] = Field(
        default_factory=dict, description="Links to pages in various Wikimedia projects"
    )
    wikipedia_url: str | None = Field(
        None, description="Direct URL to English Wikipedia article"
    )


class Relationship(BaseModel):
    """Relationship between two Wikidata entities."""

    source_entity_id: str = Field(..., description="Source entity ID (subject)")
    source_entity_label: str = Field(..., description="Source entity label")
    property_id: str = Field(..., description="Property ID (e.g., 'P1327')")
    property_label: str = Field(..., description="Human-readable property name")
    target_entity_id: str | None = Field(
        None, description="Target entity ID if relationship points to another entity"
    )
    target_entity_label: str | None = Field(
        None, description="Target entity label if available"
    )
    qualifiers: list[str] = Field(
        default_factory=list, description="Additional context as list of strings"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or reference data"
    )


class RivalryEntity(BaseModel):
    """Entity involved in a rivalry with biographical context."""

    id: str = Field(..., description="Wikidata entity ID (e.g., 'Q42')")
    label: str = Field(..., description="Primary label/name of the entity")
    description: str | None = Field(None, description="Brief description of the entity")
    birth_date: str | None = Field(None, description="Birth date (YYYY or YYYY-MM-DD format)")
    death_date: str | None = Field(None, description="Death date (YYYY or YYYY-MM-DD format)")
    occupation: list[str] = Field(
        default_factory=list, description="Occupations or professions"
    )
    nationality: str | None = Field(None, description="Nationality or country")


class RivalryFact(BaseModel):
    """Individual fact about a rivalry or conflict."""

    fact: str = Field(..., description="The rivalry fact or incident")
    date: str | None = Field(None, description="Date or time period of the fact")
    sources: list[str] = Field(
        default_factory=list, description="URLs or references for this fact"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1) based on source quality",
    )
    category: str | None = Field(
        None, description="Category (e.g., 'competition', 'conflict', 'controversy')"
    )


class Source(BaseModel):
    """Full metadata for a source document with credibility scoring."""

    source_id: str = Field(..., description="Unique source identifier (e.g., 'src_001')")
    type: str = Field(
        ...,
        description="Source type: academic_paper, news_article, book, encyclopedia, wikipedia, archive, etc.",
    )
    title: str = Field(..., description="Title of the source document")
    authors: list[str] = Field(
        default_factory=list, description="List of author names"
    )
    publication: str | None = Field(
        None, description="Publication venue (journal, newspaper, publisher, etc.)"
    )
    publication_date: str | None = Field(
        None, description="Publication date (YYYY-MM-DD or YYYY)"
    )
    url: str = Field(..., description="URL to the source (for deduplication)")
    doi: str | None = Field(None, description="DOI for academic papers")
    isbn: str | None = Field(None, description="ISBN for books")
    retrieved_at: str = Field(
        ..., description="ISO timestamp when source was retrieved"
    )
    credibility_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Source credibility score (0-1) based on type and reputation",
    )
    is_primary_source: bool = Field(
        default=False,
        description="Whether this is a primary source (firsthand account, original publication)",
    )
    stored_content_path: str | None = Field(
        None, description="Relative path to stored raw content"
    )
    content_hash: str | None = Field(
        None, description="Hash of content for deduplication"
    )


class EventSource(BaseModel):
    """Reference to a source for a specific timeline event."""

    source_id: str = Field(
        ..., description="Reference to source ID in the sources catalog"
    )
    supporting_text: str = Field(
        ...,
        description="The specific text from this source that supports this event",
    )
    page_reference: str | None = Field(
        None, description="Page number, section, or location within the source"
    )


class SourcesSummary(BaseModel):
    """Summary statistics about sources used in an analysis."""

    total_sources: int = Field(..., description="Total number of sources")
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count of sources by type"
    )
    primary_sources: int = Field(default=0, description="Number of primary sources")
    secondary_sources: int = Field(default=0, description="Number of secondary sources")
    average_credibility: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average credibility score across all sources",
    )
    date_range: dict[str, str] | None = Field(
        None,
        description="Publication date range (earliest and latest) if available",
    )


class RivalryAnalysis(BaseModel):
    """Complete analysis of rivalry between two entities."""

    entity1: RivalryEntity = Field(..., description="First entity with biographical data")
    entity2: RivalryEntity = Field(..., description="Second entity with biographical data")
    rivalry_exists: bool = Field(
        ..., description="Whether a rivalry relationship was detected"
    )
    rivalry_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Strength of rivalry (0=none, 1=intense)",
    )
    rivalry_period_start: str | None = Field(
        None, description="When the rivalry began (YYYY format)"
    )
    rivalry_period_end: str | None = Field(
        None, description="When the rivalry ended or was resolved (YYYY format)"
    )
    summary: str = Field(..., description="Natural language summary of the rivalry")
    timeline: list["TimelineEvent"] = Field(
        default_factory=list,
        description="Chronological timeline of rivalry-relevant events only (not full biographies)",
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Direct Wikidata relationships between entities",
    )
    sources: dict[str, Source] = Field(
        default_factory=dict,
        description="Source catalog - dictionary mapping source_id to full Source metadata",
    )
    sources_summary: SourcesSummary | None = Field(
        None, description="Summary statistics about sources used"
    )
    analysis_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the analysis process (model used, sources searched, etc.)",
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of analysis"
    )


class Citation(BaseModel):
    """Citation from RAG grounding metadata."""

    text: str = Field(..., description="The cited passage from the source")
    document_name: str = Field(..., description="Display name from File Search")
    entity_id: str | None = Field(
        None, description="Entity ID this citation is about (e.g., 'Q935')"
    )
    source_url: str | None = Field(
        None, description="URL to the source (Wikipedia, books, papers, etc.)"
    )
    source_type: str = Field(
        default="wikipedia",
        description="Type of source (wikipedia, google_books, academic_paper, etc.)",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Citation confidence score"
    )


class TimelineEvent(BaseModel):
    """Individual event in a rivalry timeline."""

    date: str = Field(
        ..., description="Date or time period (e.g., '1665', '1684-11-05', 'late 1600s')"
    )
    event_type: str = Field(
        ...,
        description="Type of event (achievement, conflict, publication, meeting, debate, etc.)",
    )
    description: str = Field(
        ..., 
        description="Detailed description of the event including setting, context, interactions, responses, and impact. Be specific and capture dramatic elements."
    )
    entity_id: str = Field(
        ...,
        description="Entity this event relates to (entity ID or 'both' for shared events)",
    )
    rivalry_relevance: str = Field(
        default="direct",
        description="Relevance to rivalry: 'direct' (head-to-head conflict), 'parallel' (competing work), 'context' (establishing overlap), 'resolution' (ending/recognition)",
    )
    direct_quotes: list[str] = Field(
        default_factory=list,
        description="Verbatim quotes from participants with attribution (e.g., 'Koch: \"The methods are unreliable\"'). Capture insults, criticisms, or notable statements.",
    )
    sources: list[EventSource] = Field(
        default_factory=list,
        description="References to sources that support this event with supporting text and page references",
    )
    source_count: int = Field(
        default=0, description="Number of sources supporting this event"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this event based on source quality and agreement",
    )
    has_multiple_sources: bool = Field(
        default=False, description="Whether event is corroborated by multiple sources"
    )
    has_primary_source: bool = Field(
        default=False, description="Whether event has at least one primary source"
    )
    validation_notes: str | None = Field(
        None, description="Any caveats or notes about source validation"
    )


class TimelineAnalysis(BaseModel):
    """Timeline analysis for a rivalry pair."""

    entity1_id: str = Field(..., description="First entity ID")
    entity2_id: str = Field(..., description="Second entity ID")
    events: list[TimelineEvent] = Field(
        default_factory=list, description="Timeline events, chronologically sorted"
    )
    overlapping_periods: list[str] = Field(
        default_factory=list,
        description="Time periods when both entities were active/alive",
    )
    earliest_event: str | None = Field(
        None, description="Date of earliest event in timeline"
    )
    latest_event: str | None = Field(None, description="Date of latest event in timeline")


class SourceDocument(BaseModel):
    """Metadata about an uploaded source document."""

    entity_id: str = Field(..., description="Entity this document is about")
    entity_name: str = Field(..., description="Entity name")
    source_type: str = Field(
        ..., description="Type of source (wikipedia, google_books, etc.)"
    )
    source_url: str = Field(..., description="URL to the original source")
    file_search_display_name: str = Field(
        ..., description="Display name used in File Search for citations"
    )
    uploaded_at: datetime = Field(
        default_factory=datetime.now, description="When document was uploaded"
    )
