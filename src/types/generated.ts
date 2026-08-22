// Auto-generated from Pydantic models — DO NOT EDIT
// Run: python -m scripts.generate_ts_types

export interface ExtractedContent {
  url: any;
  title: string;
  raw_text: string;
  markdown: string;
  metadata: Record<string, any>;
  extracted_at: string;
  extraction_strategy: string;
  content_length: number;
  word_count: number;
  content_type: string;
  transcript_quality: string;
}

export interface DocumentChunk {
  id: string;
  text: string;
  metadata: Record<string, any>;
  token_count: number;
  embedding: any;
  chunk_index: number;
  header_path: any;
}

export interface EnrichedEntity {
  name: string;
  type: string;
  description: string;
  web_info: Array<Record<string, any>>;
  similar_tools: Array<Record<string, any>>;
  source_chunk_id: string;
  source_url: string;
  source_text: string;
  confidence: number;
  mentioned_at: string;
}

export interface ExtractedRelationship {
  source: string;
  target: string;
  relation_type: string;
  description: string;
  confidence: number;
}

export interface CategorizedItem {
  entity: any;
  primary_topic: string;
  topic_confidence: number;
  sub_topics: Array<string>;
  content_type: string;
  type_confidence: number;
  tags: Array<string>;
  summary: string;
  key_points: Array<string>;
  relationships: Array<any>;
  categorized_at: string;
}

export interface ProcessingResult {
  url: any;
  success: boolean;
  error: any;
  extracted_content: any;
  chunks: Array<any>;
  entities: Array<any>;
  categorized_items: Array<any>;
  relationships: Array<any>;
  steps: Array<string>;
  processing_time_ms: number;
  stages_completed: Array<string>;
}
