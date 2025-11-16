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

    entity1_id: str = Field(..., description="First entity ID")
    entity1_label: str = Field(..., description="First entity name")
    entity2_id: str = Field(..., description="Second entity ID")
    entity2_label: str = Field(..., description="Second entity name")
    rivalry_exists: bool = Field(
        ..., description="Whether a rivalry relationship was detected"
    )
    rivalry_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Strength of rivalry (0=none, 1=intense)",
    )
    summary: str = Field(..., description="Natural language summary of the rivalry")
    facts: list[RivalryFact] = Field(
        default_factory=list, description="Structured facts about the rivalry"
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Direct Wikidata relationships between entities",
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of analysis"
    )
