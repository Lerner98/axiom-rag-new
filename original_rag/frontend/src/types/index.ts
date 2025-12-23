/**
 * TypeScript Types
 * Centralized type definitions for API communication.
 */

// === Chat Types ===

export interface Source {
  filename: string;
  page?: number;
  chunk_id: string;
  relevance_score: number;
  content_preview: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
  isStreaming?: boolean;
}

export interface ChatSession {
  id: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

// === API Response Types ===

export interface ChatResponse {
  message_id: string;
  answer: string;
  sources: Source[];
  session_id: string;
  was_grounded: boolean;
  confidence: number;
  processing_time_ms: number;
}

// V6 TRUE STREAMING: Phase types for SSE events
// Note: Full StreamingPhase type is in chatStore.ts (includes 'idle', 'found_sources', 'complete')
// This is the subset sent over the wire from backend
export type SSEStreamingPhase = 'searching' | 'generating';

export interface StreamEvent {
  type: 'phase' | 'token' | 'sources' | 'done' | 'error';
  // Phase event (V6)
  phase?: SSEStreamingPhase;
  // Token event
  content?: string;
  // Sources event
  sources?: Source[];
  // Done event
  message_id?: string;
  was_grounded?: boolean;
  processing_time_ms?: number;
  // Error event
  message?: string;
  code?: string;
}

// === Collection Types ===

export interface Collection {
  name: string;
  description?: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionDocument {
  id: string;
  filename: string;
  chunk_count: number;
  ingested_at: string;
}

// === Ingestion Types ===

export interface IngestResponse {
  job_id: string;
  status: IngestionStatus;
  documents_count: number;
  collection_name: string;
  message: string;
}

export interface IngestStatusResponse {
  job_id: string;
  status: IngestionStatus;
  progress: number;
  documents_processed: number;
  documents_total: number;
  errors: string[];
  started_at?: string;
  completed_at?: string;
}

export type IngestionStatus = 'queued' | 'processing' | 'completed' | 'failed';

// === Health Types ===

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  services: Record<string, boolean>;
}

// === Error Types ===

export interface APIError {
  error: string;
  code: string;
  details?: Record<string, unknown>;
  timestamp: string;
}
