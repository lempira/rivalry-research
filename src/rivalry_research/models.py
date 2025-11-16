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
        description="Type of event (achievement, conflict, publication, meeting, etc.)",
    )
    description: str = Field(..., description="Description of the event")
    entity_id: str = Field(
        ...,
        description="Entity this event relates to (entity ID or 'both' for shared events)",
    )
    rivalry_relevance: str = Field(
        default="direct",
        description="Relevance to rivalry: 'direct' (head-to-head conflict), 'parallel' (competing work), 'context' (establishing overlap), 'resolution' (ending/recognition)",
    )
    sources: list[str] = Field(
        default_factory=list, description="Citation sources for this event"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this event based on source quality",
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
