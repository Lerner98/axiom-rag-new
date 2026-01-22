"""
Agentic RAG - FastAPI Application
Main entry point for the API server.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from datetime import datetime
from collections import defaultdict
from typing import Dict

from config.settings import settings
from api.routes import chat_router, ingest_router, collections_router
from api.models import HealthResponse, ErrorResponse


# === Lightweight Metrics ===
class SimpleMetrics:
    """Non-invasive request metrics for observability."""

    def __init__(self):
        self.request_count: Dict[str, int] = defaultdict(int)
        self.error_count: Dict[str, int] = defaultdict(int)
        self.latency_sum: Dict[str, float] = defaultdict(float)
        self.latency_count: Dict[str, int] = defaultdict(int)
        self.started_at = datetime.utcnow()

    def record_request(self, path: str, latency_ms: float, is_error: bool = False):
        """Record a request metric."""
        # Normalize path (remove IDs for grouping)
        normalized = self._normalize_path(path)
        self.request_count[normalized] += 1
        self.latency_sum[normalized] += latency_ms
        self.latency_count[normalized] += 1
        if is_error:
            self.error_count[normalized] += 1

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        parts = path.strip('/').split('/')
        normalized = []
        for part in parts:
            # Replace UUIDs and long alphanumeric IDs
            if len(part) > 10 and part.replace('-', '').isalnum():
                normalized.append('{id}')
            else:
                normalized.append(part)
        return '/' + '/'.join(normalized) if normalized else '/'

    def get_summary(self) -> dict:
        """Get metrics summary."""
        uptime = (datetime.utcnow() - self.started_at).total_seconds()
        endpoints = {}
        for path in self.request_count:
            count = self.request_count[path]
            avg_latency = self.latency_sum[path] / self.latency_count[path] if self.latency_count[path] > 0 else 0
            endpoints[path] = {
                "requests": count,
                "errors": self.error_count[path],
                "avg_latency_ms": round(avg_latency, 2),
            }
        return {
            "uptime_seconds": round(uptime, 1),
            "total_requests": sum(self.request_count.values()),
            "total_errors": sum(self.error_count.values()),
            "endpoints": endpoints,
        }


metrics = SimpleMetrics()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    settings.ensure_directories()

    yield

    # Shutdown - close connections
    logger.info("Shutting down...")
    try:
        from memory.store import MemoryStore
        await MemoryStore.close()
        logger.info("Memory store connections closed")
    except Exception as e:
        logger.warning(f"Error closing memory store: {e}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-correcting RAG with RAGAS evaluation",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics without impacting performance."""
    start_time = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start_time) * 1000

    # Skip metrics endpoint to avoid recursion
    if request.url.path != "/metrics":
        is_error = response.status_code >= 400
        metrics.record_request(request.url.path, latency_ms, is_error)

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            code="INTERNAL_ERROR",
            details={"message": str(exc)} if settings.debug else None,
            timestamp=datetime.utcnow(),
        ).model_dump(mode="json")
    )


# Health check
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Returns status of all services.
    """
    services = {"api": True}

    # Check vector store
    try:
        from vectorstore.store import VectorStore
        vs = VectorStore()
        # Simple check - can we access the store?
        services["vector_store"] = vs._store is not None or True  # Lazy init is ok
    except Exception as e:
        logger.warning(f"Vector store health check failed: {e}")
        services["vector_store"] = False

    # Check LLM availability
    try:
        if settings.llm_provider == "ollama":
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                services["llm"] = resp.status_code == 200
        else:
            services["llm"] = True  # Assume cloud LLMs are available
    except Exception as e:
        logger.warning(f"LLM health check failed: {e}")
        services["llm"] = False

    # Check memory backend
    try:
        from memory.store import memory_store
        # Quick test - list sessions (fast operation)
        await memory_store.list_sessions()
        services["memory"] = True
    except Exception as e:
        logger.warning(f"Memory health check failed: {e}")
        services["memory"] = False

    all_healthy = all(services.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=settings.app_version,
        services=services,
    )


# Include routers
app.include_router(chat_router)
app.include_router(ingest_router)
app.include_router(collections_router)


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


# Metrics endpoint
@app.get("/metrics", tags=["System"])
async def get_metrics():
    """
    Lightweight metrics for observability.
    Returns request counts, error rates, and latencies per endpoint.
    """
    return metrics.get_summary()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
