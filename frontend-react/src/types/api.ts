export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface QueryRequest {
  question: string;
  topics?: string[];
  top_k?: number;
  use_reranking?: boolean;
  history?: ChatMessage[];
}

export interface SourceChunk {
  source_name: string;
  format: string;
  page_number?: number;
  section_header?: string;
  content_snippet: string;
  relevance_score: number;
}

export interface QueryResponse {
  answer: string;
  sources: SourceChunk[];
  tokens_used: number;
  retrieval_time_ms: number;
  generation_time_ms: number;
}

export interface IndexedDocument {
  doc_id: string;
  source_name: string;
  filename: string;
  format: string;
  chunk_count: number;
  ingested_at: string;
}

export interface CollectionInfo {
  name: string;
  description: string;
  size: number;
  formats?: string[];
  doc_count?: number;
  documents?: IndexedDocument[];
  metadata?: Record<string, unknown>;
}

// UI-only types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceChunk[];
  streaming?: boolean;
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
}
