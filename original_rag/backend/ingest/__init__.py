"""
Document Ingestion Module
Handles loading, chunking, and embedding documents.
"""
from .loader import DocumentLoader, load_document
from .chunker import TextChunker, chunk_documents
from .service import IngestionService, ingestion_service

__all__ = [
    "DocumentLoader",
    "load_document",
    "TextChunker",
    "chunk_documents",
    "IngestionService",
    "ingestion_service",
]
