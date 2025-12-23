"""API Routes."""
from .chat import router as chat_router
from .ingest import router as ingest_router
from .collections import router as collections_router

__all__ = ["chat_router", "ingest_router", "collections_router"]
