"""
Ingestion Routes
Handles document ingestion from various sources.
"""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional

from api.models import (
    IngestTextRequest,
    IngestURLRequest,
    IngestResponse,
    IngestStatusResponse,
)
from config.settings import settings
from ingest import ingestion_service, DocumentLoader

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/texts", response_model=IngestResponse)
async def ingest_texts(request: IngestTextRequest):
    """
    Ingest text documents.
    """
    collection_name = request.collection_name or settings.collection_name

    # Start ingestion job
    job = await ingestion_service.ingest_texts(
        texts=request.texts,
        metadatas=request.metadatas,
        collection_name=collection_name,
    )

    return IngestResponse(
        job_id=job.job_id,
        status=job.status.value,
        documents_count=len(request.texts),
        collection_name=collection_name,
        message=f"Ingestion job started with {len(request.texts)} texts",
    )


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    collection_name: Optional[str] = Form(None),
):
    """
    Ingest a file (PDF, MD, TXT, DOCX).
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()
    if not DocumentLoader.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {list(DocumentLoader.SUPPORTED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB",
        )

    collection = collection_name or settings.collection_name

    # Save to temp file for processing
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_path = settings.uploads_dir / f"{file.filename}"

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # Start ingestion job
        job = await ingestion_service.ingest_file(
            file_path=temp_path,
            collection_name=collection,
        )

        return IngestResponse(
            job_id=job.job_id,
            status=job.status.value,
            documents_count=1,
            collection_name=collection,
            message=f"File '{file.filename}' queued for ingestion",
        )

    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/url", response_model=IngestResponse)
async def ingest_url(request: IngestURLRequest):
    """
    Ingest content from a URL.
    """
    collection_name = request.collection_name or settings.collection_name

    # Start ingestion job
    job = await ingestion_service.ingest_url(
        url=request.url,
        collection_name=collection_name,
    )

    return IngestResponse(
        job_id=job.job_id,
        status=job.status.value,
        documents_count=1,
        collection_name=collection_name,
        message=f"URL '{request.url}' queued for ingestion",
    )


@router.get("/status/{job_id}", response_model=IngestStatusResponse)
async def get_ingestion_status(job_id: str):
    """
    Get the status of an ingestion job.
    """
    job = ingestion_service.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return IngestStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        documents_processed=job.documents_processed,
        documents_total=job.documents_total,
        errors=job.errors,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
