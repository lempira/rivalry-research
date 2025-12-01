export interface Entity {
  id: string;
  label: string;
  description: string;
  birth_date: string;
  death_date: string;
  occupation: string[];
  nationality: string;
}

export interface TimelineEvent {
  date: string;
  event_type: string;
  description: string;
  entity_id: string | "both";
  rivalry_relevance: string;
  direct_quotes: string[];
  sources: any[]; // We can refine this if needed
  source_count: number;
  confidence: number;
  has_multiple_sources: boolean;
  has_primary_source: boolean;
}

export interface RivalryData {
  entity1: Entity;
  entity2: Entity;
  rivalry_exists: boolean;
  rivalry_score: number;
  rivalry_period_start: string;
  rivalry_period_end: string;
  summary: string;
  timeline: TimelineEvent[];
  // Include other fields as needed based on analysis.json
}

