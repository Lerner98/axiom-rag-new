"""
Agentic RAG - FastAPI Application
Main entry point for the API server.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from config.settings import settings
from api.routes import chat_router, ingest_router, collections_router
from api.models import HealthResponse, ErrorResponse

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
    
    # TODO: Initialize services
    # - Vector store connection
    # - LLM client
    # - Memory backend
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    # TODO: Cleanup connections


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
    # TODO: Actually check service health
    services = {
        "api": True,
        "vector_store": True,  # TODO: Check Qdrant/Chroma connection
        "llm": True,  # TODO: Check LLM availability
        "memory": True,  # TODO: Check memory backend
    }
    
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
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
