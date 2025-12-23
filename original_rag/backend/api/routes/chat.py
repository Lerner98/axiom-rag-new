"""
Chat Routes
Handles chat interactions with streaming support.
Includes chat-scoped document management per ADR-007.
"""
import json
import uuid
import logging
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import APIRouter, HTTPException, UploadFile, File
from sse_starlette.sse import EventSourceResponse

from api.models import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    Source,
    StreamDone,
    StreamError,
    # Chat Documents
    ChatDocument,
    DocumentUploadResult,
    DocumentUploadFailed,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDeleteResponse,
    ChatDeleteResponse,
    DocumentPreviewResponse,
)
from config.settings import settings
from rag.pipeline import RAGPipeline
from memory import memory_store
from vectorstore.store import VectorStore
from ingest.service import ingestion_service

logger = logging.getLogger(__name__)

# Supported file types for chat documents
SUPPORTED_FILE_TYPES = {'.pdf', '.txt', '.md', '.docx'}

router = APIRouter(prefix="/chat", tags=["Chat"])

# Lazy-initialized pipeline instance
_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    """Get or create the RAG pipeline instance."""
    global _pipeline
    if _pipeline is None:
        logger.info("Initializing RAG pipeline...")
        _pipeline = RAGPipeline()
        logger.info("RAG pipeline initialized")
    return _pipeline


async def generate_stream(
    message: str,
    session_id: str,
    collection_name: str | None,
    chat_id: str | None = None  # NEW: chat_id for chat-scoped collections
) -> AsyncGenerator[str, None]:
    """
    Generate TRUE streaming response with real-time phase events.
    Yields SSE-formatted events.

    Event sequence (V6 TRUE STREAMING):
    1. phase: "searching" - Pipeline starting, intent classification + retrieval
    2. sources: [...] - Retrieved documents (BEFORE generation starts)
    3. phase: "generating" - LLM generation starting
    4. token: "..." - Each token as it's generated (TRUE streaming)
    5. done: {...} - Stream complete with metadata

    If chat_id is provided, uses chat-scoped collection (chat_{chat_id}).
    Otherwise falls back to collection_name for backward compatibility.
    """
    start_time = datetime.utcnow()
    message_id = str(uuid.uuid4())

    # Determine collection: chat-scoped takes priority
    effective_collection = get_chat_collection_name(chat_id) if chat_id else collection_name

    logger.info(f"Starting TRUE STREAMING for message in collection: {effective_collection}")

    try:
        pipeline = get_pipeline()

        # Stream through the pipeline with TRUE real-time events
        async for chunk in pipeline.astream(message, session_id, effective_collection):
            event_type = chunk.get("type")

            if event_type == "phase":
                # Phase change event - for frontend progress indicator
                phase = chunk.get("phase", "searching")
                yield json.dumps({'type': 'phase', 'phase': phase})
                logger.debug(f"SSE phase: {phase}")

            elif event_type == "token":
                # TRUE streaming token - yield immediately
                yield json.dumps({'type': 'token', 'content': chunk['content']})

            elif event_type == "sources":
                # Sources found - emitted BEFORE generation starts
                sources = []
                for s in chunk.get("sources", []):
                    if isinstance(s, dict):
                        sources.append({
                            "filename": s.get("filename", s.get("source", "unknown")),
                            "chunk_id": s.get("chunk_id", ""),
                            "relevance_score": s.get("relevance_score", 0.0),
                            "content_preview": s.get("content_preview", s.get("page_content", "")[:200]),
                            "page": s.get("page"),
                        })
                yield json.dumps({'type': 'sources', 'sources': sources})
                logger.info(f"SSE sources: {len(sources)} documents")

            elif event_type == "done":
                # Stream complete
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                done = StreamDone(
                    message_id=message_id,
                    was_grounded=chunk.get("is_grounded", True),
                    processing_time_ms=processing_time
                )
                yield json.dumps(done.model_dump())
                logger.info(f"SSE done: {processing_time}ms, grounded={chunk.get('is_grounded')}")

            elif event_type == "error":
                # Error during streaming
                error = StreamError(message=chunk.get("message", "Unknown error"), code="STREAM_ERROR")
                yield json.dumps(error.model_dump())
                logger.error(f"SSE error: {chunk.get('message')}")

    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        error = StreamError(message=str(e), code="STREAM_ERROR")
        yield json.dumps(error.model_dump())


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint.
    Returns complete response with sources.
    """
    start_time = datetime.utcnow()
    session_id = request.session_id or str(uuid.uuid4())

    try:
        pipeline = get_pipeline()

        result = await pipeline.aquery(
            question=request.message,
            session_id=session_id,
            collection_name=request.collection_name,
        )

        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Convert sources to response format
        sources = []
        for s in result.get("sources", []):
            if isinstance(s, dict):
                sources.append(Source(
                    filename=s.get("source", "unknown"),
                    chunk_id=s.get("chunk_id", ""),
                    relevance_score=s.get("relevance_score", 0.0),
                    content_preview=s.get("content_preview", s.get("page_content", "")[:200]),
                    page=s.get("page"),
                ))

        return ChatResponse(
            message_id=str(uuid.uuid4()),
            answer=result["answer"],
            sources=sources,
            session_id=session_id,
            was_grounded=result.get("is_grounded", True),
            confidence=result.get("groundedness_score", 0.0),
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint (legacy).
    Returns Server-Sent Events with tokens and sources.
    Uses collection_name from request for backward compatibility.
    """
    # Safety check: require collection_name to prevent fallback to default
    if not request.collection_name:
        raise HTTPException(
            status_code=400,
            detail="collection_name is required. Use /chat/{chat_id}/stream for chat-scoped requests."
        )

    session_id = request.session_id or str(uuid.uuid4())

    return EventSourceResponse(
        generate_stream(
            message=request.message,
            session_id=session_id,
            collection_name=request.collection_name
        )
    )


@router.post("/{chat_id}/stream")
async def chat_stream_scoped(chat_id: str, request: ChatRequest):
    """
    Chat-scoped streaming endpoint (ADR-007).
    Returns Server-Sent Events with tokens and sources.
    Uses chat's own collection (chat_{chat_id}) for document retrieval.
    """
    session_id = request.session_id or chat_id  # Default session_id to chat_id

    return EventSourceResponse(
        generate_stream(
            message=request.message,
            session_id=session_id,
            collection_name=None,  # Not used when chat_id provided
            chat_id=chat_id
        )
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str, limit: int = 50):
    """
    Get chat history for a session.
    """
    messages = await memory_store.get_history(session_id, limit=limit)
    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages)
    )


@router.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """
    Clear chat history for a session.
    """
    await memory_store.clear_history(session_id)
    return {"message": f"History cleared for session {session_id}"}


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT-SCOPED DOCUMENT ENDPOINTS (ADR-007)
# ═══════════════════════════════════════════════════════════════════════════════

def get_chat_collection_name(chat_id: str) -> str:
    """Get the collection name for a chat. Format: chat_{chat_id}"""
    return f"chat_{chat_id}"


# Lazy-initialized vector store for document operations
_vector_store = None


def get_vector_store():
    """Get or create the vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


@router.post("/{chat_id}/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    chat_id: str,
    files: List[UploadFile] = File(...)
):
    """
    Upload one or more documents to the chat's collection.
    Creates collection if it doesn't exist.
    """
    collection_name = get_chat_collection_name(chat_id)
    uploaded = []
    failed = []

    for file in files:
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()

        # Validate file type
        if ext not in SUPPORTED_FILE_TYPES:
            failed.append(DocumentUploadFailed(
                name=filename,
                error=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_FILE_TYPES)}"
            ))
            continue

        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Generate doc_id for this document
                doc_id = str(uuid.uuid4())

                # Use ingestion service with chat's collection
                job = ingestion_service.create_job(collection_name, document_count=1)
                await ingestion_service._process_file(job, tmp_path, doc_id=doc_id, original_filename=filename)

                if job.status.value == "completed":
                    uploaded.append(DocumentUploadResult(
                        id=doc_id,
                        name=filename,
                        chunk_count=job.chunks_created
                    ))
                else:
                    failed.append(DocumentUploadFailed(
                        name=filename,
                        error=job.errors[0] if job.errors else "Unknown error"
                    ))
            finally:
                # Cleanup temp file
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")
            failed.append(DocumentUploadFailed(
                name=filename,
                error=str(e)
            ))

    return DocumentUploadResponse(uploaded=uploaded, failed=failed)


@router.get("/{chat_id}/documents", response_model=DocumentListResponse)
async def list_documents(chat_id: str):
    """
    List all documents belonging to this chat.
    """
    collection_name = get_chat_collection_name(chat_id)
    vector_store = get_vector_store()

    try:
        docs = await vector_store.list_documents(collection_name)
        return DocumentListResponse(
            documents=[
                ChatDocument(
                    id=d.doc_id,
                    name=d.name,
                    type=d.file_type,
                    size=d.size,
                    chunk_count=d.chunk_count,
                    uploaded_at=d.uploaded_at
                )
                for d in docs
            ],
            total_count=len(docs)
        )
    except Exception as e:
        logger.error(f"Failed to list documents for chat {chat_id}: {e}")
        return DocumentListResponse(documents=[], total_count=0)


@router.delete("/{chat_id}/documents/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(chat_id: str, doc_id: str):
    """
    Delete a single document and all its chunks.
    """
    collection_name = get_chat_collection_name(chat_id)
    vector_store = get_vector_store()

    try:
        deleted_count = await vector_store.delete_by_metadata(
            collection_name,
            {"doc_id": doc_id}
        )
        return DocumentDeleteResponse(
            success=deleted_count > 0,
            deleted_chunks=deleted_count
        )
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id} from chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(chat_id: str):
    """
    Delete chat, its message history, and ALL documents.
    """
    collection_name = get_chat_collection_name(chat_id)
    vector_store = get_vector_store()

    deleted_docs = 0
    deleted_chunks = 0
    memory_cleared = False

    try:
        # Get document count before deletion
        docs = await vector_store.list_documents(collection_name)
        deleted_docs = len(docs)
        deleted_chunks = sum(d.chunk_count for d in docs)

        # Delete the collection
        await vector_store.delete_collection(collection_name)
    except Exception as e:
        logger.warning(f"Failed to delete collection for chat {chat_id}: {e}")

    try:
        # Clear memory history
        await memory_store.clear_history(chat_id)
        memory_cleared = True
    except Exception as e:
        logger.warning(f"Failed to clear memory for chat {chat_id}: {e}")

    return ChatDeleteResponse(
        success=True,
        deleted_documents=deleted_docs,
        deleted_chunks=deleted_chunks,
        memory_cleared=memory_cleared
    )


@router.get("/{chat_id}/documents/{doc_id}/preview", response_model=DocumentPreviewResponse)
async def get_document_preview(
    chat_id: str,
    doc_id: str,
    max_chars: int = 5000
):
    """
    Get a preview of document content.
    """
    collection_name = get_chat_collection_name(chat_id)
    vector_store = get_vector_store()

    try:
        chunks = await vector_store.get_chunks_by_doc_id(collection_name, doc_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get document name from first chunk metadata
        doc_name = chunks[0].metadata.get('source', 'unknown') if chunks else 'unknown'

        # Concatenate chunk content
        full_content = "\n\n".join(c.page_content for c in chunks)
        total_chars = len(full_content)

        # Truncate if needed
        truncated = total_chars > max_chars
        preview = full_content[:max_chars] if truncated else full_content

        return DocumentPreviewResponse(
            id=doc_id,
            name=doc_name,
            preview=preview,
            total_chars=total_chars,
            truncated=truncated
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preview for document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
