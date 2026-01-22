"""
Ingestion Service - V2 with Parent-Child Chunking and BM25 Index

Orchestrates document loading, chunking, and storage.

Changes from V1:
- Uses ParentChildChunker by default
- Builds BM25 index on document upload for hybrid search
- Registers chunks with HybridRetriever
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from langchain_core.documents import Document

from config.settings import settings
from vectorstore.store import VectorStore
from .loader import DocumentLoader
from .chunker import ParentChildChunker

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionJob:
    """Represents an ingestion job."""
    job_id: str
    status: JobStatus
    collection_name: str
    documents_total: int = 0
    documents_processed: int = 0
    chunks_created: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    doc_id: Optional[str] = None  # Document ID for chat-scoped documents

    @property
    def progress(self) -> float:
        if self.documents_total == 0:
            return 0.0
        return self.documents_processed / self.documents_total


class IngestionService:
    """
    Service for ingesting documents into vector store.
    
    Features:
    - Parent-child chunking for better retrieval quality
    - BM25 index building for hybrid search
    - Async processing with job tracking
    """

    def __init__(self):
        self._jobs: Dict[str, IngestionJob] = {}
        self._vector_store = None
        self._chunker = ParentChildChunker()
        self._hybrid_retriever = None

    def _get_vector_store(self):
        """Lazy initialization of vector store."""
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store

    def _get_hybrid_retriever(self):
        """Lazy initialization of hybrid retriever."""
        if self._hybrid_retriever is None:
            try:
                from rag.retriever import get_hybrid_retriever
                self._hybrid_retriever = get_hybrid_retriever(self._get_vector_store())
            except Exception as e:
                logger.warning(f"Could not initialize HybridRetriever: {e}")
                self._hybrid_retriever = None
        return self._hybrid_retriever

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """Get job status."""
        return self._jobs.get(job_id)

    def create_job(self, collection_name: str, document_count: int = 1) -> IngestionJob:
        """Create a new ingestion job."""
        job = IngestionJob(
            job_id=str(uuid4()),
            status=JobStatus.QUEUED,
            collection_name=collection_name,
            documents_total=document_count,
        )
        self._jobs[job.job_id] = job
        return job

    async def ingest_file(
        self,
        file_path: str | Path,
        collection_name: Optional[str] = None,
    ) -> IngestionJob:
        """Ingest a file into the vector store."""
        collection = collection_name or settings.collection_name
        job = self.create_job(collection, document_count=1)

        # Start processing in background
        asyncio.create_task(self._process_file(job, file_path))

        return job

    async def _process_file(
        self, 
        job: IngestionJob, 
        file_path: str | Path, 
        doc_id: str | None = None, 
        original_filename: str | None = None
    ):
        """Process a single file with parent-child chunking."""
        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            t_total = time.time()

            path = Path(file_path)
            display_name = original_filename or path.name
            logger.info(f"Processing file: {display_name} for job {job.job_id}")

            # Generate doc_id if not provided
            document_id = doc_id or str(uuid4())

            # TIMING: Load document
            t0 = time.time()
            documents = DocumentLoader.load(path)
            t_load = time.time() - t0
            logger.info(f"⏱️ PDF LOAD: {t_load:.2f}s ({len(documents)} pages)")

            # TIMING: Parent-Child Chunk documents
            t1 = time.time()
            chunks = self._chunker.chunk(documents)
            t_chunk = time.time() - t1
            job.chunks_created = len(chunks)
            logger.info(f"⏱️ CHUNKING (parent-child): {t_chunk:.2f}s ({len(chunks)} child chunks)")

            # TIMING: Add metadata
            t2 = time.time()
            file_size = path.stat().st_size if path.exists() else 0
            for chunk in chunks:
                chunk.metadata['collection'] = job.collection_name
                chunk.metadata['ingested_at'] = datetime.utcnow().isoformat()
                chunk.metadata['doc_id'] = document_id
                chunk.metadata['file_size'] = file_size
                # Override source with original filename if provided (temp file path → real name)
                if original_filename:
                    chunk.metadata['source'] = original_filename
            t_metadata = time.time() - t2
            logger.info(f"⏱️ METADATA: {t_metadata:.2f}s")

            # TIMING: Store in vector database (embedding + storage)
            t3 = time.time()
            vector_store = self._get_vector_store()
            await vector_store.add_documents(chunks, collection_name=job.collection_name)
            t_embed_store = time.time() - t3
            logger.info(f"⏱️ EMBED+STORE: {t_embed_store:.2f}s ({len(chunks)} chunks)")

            # TIMING: Build/Update BM25 index for hybrid search
            t4 = time.time()
            await self._update_bm25_index(job.collection_name, chunks, job)
            t_bm25 = time.time() - t4
            logger.info(f"⏱️ BM25 INDEX: {t_bm25:.2f}s")

            job.documents_processed = 1
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            # Store doc_id for retrieval
            job.doc_id = document_id

            t_total_elapsed = time.time() - t_total
            logger.info(
                f"⏱️ TOTAL: {t_total_elapsed:.2f}s | "
                f"Load:{t_load:.1f}s Chunk:{t_chunk:.1f}s Meta:{t_metadata:.1f}s "
                f"Embed:{t_embed_store:.1f}s BM25:{t_bm25:.1f}s"
            )
            logger.info(f"Job {job.job_id} completed: {job.chunks_created} chunks created for doc_id {document_id}")

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.utcnow()

    async def _update_bm25_index(self, collection_name: str, new_chunks: List[Document], job: Optional[IngestionJob] = None):
        """Update BM25 index with new chunks.

        Args:
            collection_name: Collection to update
            new_chunks: Chunks to add to index
            job: Optional job to record partial failures
        """
        retriever = self._get_hybrid_retriever()
        if retriever is None:
            logger.debug("HybridRetriever not available, skipping BM25 index update")
            return

        try:
            # Add new chunks to existing index (rebuilds if necessary)
            retriever.add_to_bm25_index(collection_name, new_chunks)
            logger.info(f"Updated BM25 index for {collection_name}: +{len(new_chunks)} chunks")
        except Exception as e:
            error_msg = f"BM25 index update failed: {e} - hybrid search may be degraded"
            logger.error(error_msg)
            if job:
                job.errors.append(error_msg)

    async def rebuild_bm25_index(self, collection_name: str):
        """Rebuild BM25 index from all chunks in collection."""
        retriever = self._get_hybrid_retriever()
        if retriever is None:
            logger.warning("HybridRetriever not available, cannot rebuild BM25 index")
            return
        
        try:
            vector_store = self._get_vector_store()
            all_chunks = await vector_store.get_all_chunks(collection_name)
            
            if all_chunks:
                retriever.build_bm25_index(collection_name, all_chunks)
                logger.info(f"Rebuilt BM25 index for {collection_name}: {len(all_chunks)} chunks")
            else:
                retriever.clear_bm25_index(collection_name)
                logger.info(f"Cleared BM25 index for {collection_name} (no chunks)")
        except Exception as e:
            logger.error(f"Failed to rebuild BM25 index: {e}")

    async def ingest_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        collection_name: Optional[str] = None,
    ) -> IngestionJob:
        """Ingest raw texts into the vector store."""
        collection = collection_name or settings.collection_name
        job = self.create_job(collection, document_count=len(texts))

        # Start processing in background
        asyncio.create_task(self._process_texts(job, texts, metadatas))

        return job

    async def _process_texts(
        self,
        job: IngestionJob,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ):
        """Process raw texts with parent-child chunking."""
        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()

            logger.info(f"Processing {len(texts)} texts for job {job.job_id}")

            # Create documents from texts
            documents = []
            for i, text in enumerate(texts):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                metadata['source'] = metadata.get('source', f'text_{i}')
                metadata['file_type'] = 'text'
                documents.append(Document(page_content=text, metadata=metadata))

            # Parent-child chunk documents
            chunks = self._chunker.chunk(documents)
            job.chunks_created = len(chunks)

            # Add collection metadata
            for chunk in chunks:
                chunk.metadata['collection'] = job.collection_name
                chunk.metadata['ingested_at'] = datetime.utcnow().isoformat()

            # Store in vector database
            vector_store = self._get_vector_store()
            await vector_store.add_documents(chunks, collection_name=job.collection_name)

            # Update BM25 index
            await self._update_bm25_index(job.collection_name, chunks, job)

            job.documents_processed = len(texts)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            logger.info(f"Job {job.job_id} completed: {job.chunks_created} chunks from {len(texts)} texts")

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.utcnow()

    async def ingest_url(
        self,
        url: str,
        collection_name: Optional[str] = None,
    ) -> IngestionJob:
        """Ingest content from a URL."""
        collection = collection_name or settings.collection_name
        job = self.create_job(collection, document_count=1)

        # Start processing in background
        asyncio.create_task(self._process_url(job, url))

        return job

    async def _process_url(self, job: IngestionJob, url: str):
        """Process URL content with parent-child chunking."""
        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()

            logger.info(f"Processing URL: {url} for job {job.job_id}")

            # Load from URL
            from langchain_community.document_loaders import WebBaseLoader
            loader = WebBaseLoader(url)
            documents = loader.load()

            # Add metadata
            for doc in documents:
                doc.metadata['source'] = url
                doc.metadata['file_type'] = 'url'

            # Parent-child chunk documents
            chunks = self._chunker.chunk(documents)
            job.chunks_created = len(chunks)

            # Add collection metadata
            for chunk in chunks:
                chunk.metadata['collection'] = job.collection_name
                chunk.metadata['ingested_at'] = datetime.utcnow().isoformat()

            # Store in vector database
            vector_store = self._get_vector_store()
            await vector_store.add_documents(chunks, collection_name=job.collection_name)

            # Update BM25 index
            await self._update_bm25_index(job.collection_name, chunks, job)

            job.documents_processed = 1
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            logger.info(f"Job {job.job_id} completed: {job.chunks_created} chunks from URL")

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.utcnow()

    async def delete_document(self, collection_name: str, doc_id: str):
        """Delete a document and update BM25 index."""
        vector_store = self._get_vector_store()
        deleted_count = await vector_store.delete_by_metadata(
            collection_name,
            {"doc_id": doc_id}
        )
        
        # Update BM25 index
        retriever = self._get_hybrid_retriever()
        if retriever and deleted_count > 0:
            retriever.remove_from_bm25_index(collection_name, [doc_id])
        
        return deleted_count

    async def delete_collection(self, collection_name: str):
        """Delete a collection and its BM25 index."""
        vector_store = self._get_vector_store()
        await vector_store.delete_collection(collection_name)
        
        # Clear BM25 index
        retriever = self._get_hybrid_retriever()
        if retriever:
            retriever.clear_bm25_index(collection_name)


# Global instance
ingestion_service = IngestionService()
