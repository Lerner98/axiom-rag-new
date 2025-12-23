"""
API Response Models
Pydantic models for API responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# === Common ===

class Source(BaseModel):
    """A source document reference."""
    filename: str
    page: Optional[int] = None
    chunk_id: str
    relevance_score: float = Field(description="Relevance score (higher is better, may vary by backend)")
    content_preview: str = Field(max_length=500)


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    services: dict[str, bool]  # service_name -> is_healthy


# === Chat ===

class ChatResponse(BaseModel):
    """Response from chat endpoint (non-streaming)."""
    message_id: str
    answer: str
    sources: list[Source]
    session_id: str
    was_grounded: bool = Field(description="Whether answer is grounded in sources")
    confidence: float = Field(ge=0, le=1)
    processing_time_ms: int


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: Optional[list[Source]] = None
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    """Response with chat history."""
    session_id: str
    messages: list[ChatMessage]
    total_messages: int


# === Streaming ===

class StreamToken(BaseModel):
    """A single token in streaming response."""
    type: Literal["token"] = "token"
    content: str


class StreamSources(BaseModel):
    """Sources sent during streaming."""
    type: Literal["sources"] = "sources"
    sources: list[Source]


class StreamDone(BaseModel):
    """End of stream marker."""
    type: Literal["done"] = "done"
    message_id: str
    was_grounded: bool
    processing_time_ms: int


class StreamError(BaseModel):
    """Error during streaming."""
    type: Literal["error"] = "error"
    message: str
    code: str


# === Ingestion ===

class IngestResponse(BaseModel):
    """Response from ingestion endpoint."""
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    documents_count: int
    collection_name: str
    message: str


class IngestStatusResponse(BaseModel):
    """Status of an ingestion job."""
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float = Field(ge=0, le=1)
    documents_processed: int
    documents_total: int
    errors: list[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# === Collections ===

class CollectionInfo(BaseModel):
    """Information about a collection."""
    name: str
    description: Optional[str]
    document_count: int
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    """Response listing all collections."""
    collections: list[CollectionInfo]
    total: int


class CollectionDocumentsResponse(BaseModel):
    """Documents in a collection."""
    collection_name: str
    documents: list[dict]  # filename, chunk_count, etc.
    total: int
    page: int
    page_size: int


# === Evaluation ===

class RAGASMetrics(BaseModel):
    """RAGAS evaluation metrics."""
    faithfulness: float = Field(ge=0, le=1, description="Is answer grounded in context?")
    answer_relevancy: float = Field(ge=0, le=1, description="Does answer address question?")
    context_precision: float = Field(ge=0, le=1, description="Are retrieved docs relevant?")
    context_recall: float = Field(ge=0, le=1, description="Did we get all needed info?")
    overall_score: float = Field(ge=0, le=1)


class EvaluateResponse(BaseModel):
    """Response from evaluation endpoint."""
    metrics: RAGASMetrics
    per_question_scores: list[dict]
    interpretation: str  # "Excellent", "Good", "Needs Improvement", "Poor"


# === Chat Documents ===

class ChatDocument(BaseModel):
    """A document attached to a chat."""
    id: str
    name: str
    type: str
    size: int
    chunk_count: int
    uploaded_at: str


class DocumentUploadResult(BaseModel):
    """Result of a single document upload."""
    id: str
    name: str
    chunk_count: int


class DocumentUploadFailed(BaseModel):
    """Failed document upload."""
    name: str
    error: str


class DocumentUploadResponse(BaseModel):
    """Response from document upload endpoint."""
    uploaded: list[DocumentUploadResult]
    failed: list[DocumentUploadFailed]


class DocumentListResponse(BaseModel):
    """Response listing chat documents."""
    documents: list[ChatDocument]
    total_count: int


class DocumentDeleteResponse(BaseModel):
    """Response from document deletion."""
    success: bool
    deleted_chunks: int


class ChatDeleteResponse(BaseModel):
    """Response from chat deletion."""
    success: bool
    deleted_documents: int
    deleted_chunks: int
    memory_cleared: bool


class DocumentPreviewResponse(BaseModel):
    """Response with document content preview."""
    id: str
    name: str
    preview: str
    total_chars: int
    truncated: bool


# === Error ===

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    code: str
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
