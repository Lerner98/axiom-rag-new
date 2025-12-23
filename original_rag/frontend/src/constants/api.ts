/**
 * API Constants
 * Centralized API configuration.
 */

// === API Configuration ===
export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8001',
  timeout: 30000, // 30 seconds
  retries: 3,
} as const;

// === API Endpoints ===
export const API_ENDPOINTS = {
  // Health
  health: '/health',

  // Chat
  chat: '/chat',
  chatStream: '/chat/stream',
  chatHistory: (sessionId: string) => `/chat/history/${sessionId}`,

  // Chat-scoped (ADR-007)
  chatStreamScoped: (chatId: string) => `/chat/${chatId}/stream`,
  chatDocuments: (chatId: string) => `/chat/${chatId}/documents`,
  chatDocument: (chatId: string, docId: string) => `/chat/${chatId}/documents/${docId}`,
  chatDocumentPreview: (chatId: string, docId: string) => `/chat/${chatId}/documents/${docId}/preview`,
  chatDelete: (chatId: string) => `/chat/${chatId}`,

  // Ingestion
  ingestTexts: '/ingest/texts',
  ingestFile: '/ingest/file',
  ingestUrl: '/ingest/url',
  ingestStatus: (jobId: string) => `/ingest/status/${jobId}`,

  // Collections
  collections: '/collections',
  collection: (name: string) => `/collections/${name}`,
  collectionDocuments: (name: string) => `/collections/${name}/documents`,
} as const;

// === Error Codes ===
export const ERROR_CODES = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  STREAM_ERROR: 'STREAM_ERROR',
} as const;

// === File Upload ===
export const FILE_UPLOAD = {
  maxSizeMB: 50,
  maxSizeBytes: 50 * 1024 * 1024,
  acceptedTypes: {
    'application/pdf': ['.pdf'],
    'text/plain': ['.txt'],
    'text/markdown': ['.md'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  },
  acceptedExtensions: ['.pdf', '.txt', '.md', '.docx'],
} as const;

// === Local Storage Keys ===
export const STORAGE_KEYS = {
  sessionId: 'rag_session_id',
  theme: 'rag_theme',
  sidebarCollapsed: 'rag_sidebar_collapsed',
  selectedCollection: 'rag_selected_collection',
} as const;

// === Ingestion Status ===
export const INGESTION_STATUS = {
  QUEUED: 'queued',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;
