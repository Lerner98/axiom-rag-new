"""
API Request Models
Pydantic models for incoming API requests.
"""
from pydantic import BaseModel, Field
from typing import Optional


# === Chat ===

class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation memory")
    collection_name: Optional[str] = Field(default=None, description="Specific collection to query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are the best practices for React state management?",
                "session_id": "user_123_session_456",
                "collection_name": "engineering_docs"
            }
        }


class ChatHistoryRequest(BaseModel):
    """Request to get chat history."""
    session_id: str
    limit: int = Field(default=50, ge=1, le=200)


# === Ingestion ===

class IngestTextRequest(BaseModel):
    """Request to ingest text documents."""
    texts: list[str] = Field(..., min_items=1)
    metadatas: Optional[list[dict]] = Field(default=None)
    collection_name: Optional[str] = Field(default=None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["Document 1 content...", "Document 2 content..."],
                "metadatas": [{"source": "doc1.txt"}, {"source": "doc2.txt"}],
                "collection_name": "my_docs"
            }
        }


class IngestURLRequest(BaseModel):
    """Request to ingest from URL."""
    url: str = Field(..., pattern=r"^https?://")
    collection_name: Optional[str] = Field(default=None)


# === Collections ===

class CreateCollectionRequest(BaseModel):
    """Request to create a new collection."""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)


class DeleteCollectionRequest(BaseModel):
    """Request to delete a collection."""
    name: str
    confirm: bool = Field(default=False, description="Must be true to confirm deletion")


# === Evaluation ===

class EvaluateRequest(BaseModel):
    """Request to evaluate RAG responses."""
    questions: list[str]
    answers: list[str]
    contexts: list[list[str]]
    ground_truths: Optional[list[str]] = Field(default=None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": ["What is RAG?"],
                "answers": ["RAG is Retrieval Augmented Generation..."],
                "contexts": [["RAG combines retrieval with generation..."]]
            }
        }
