# Agentic RAG - Production Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (from backend folder)
COPY backend/api/ ./api/
COPY backend/config/ ./config/
COPY backend/ingest/ ./ingest/
COPY backend/memory/ ./memory/
COPY backend/rag/ ./rag/
COPY backend/vectorstore/ ./vectorstore/
COPY backend/main.py .

# Create data directory
RUN mkdir -p /app/data /app/chroma_db

# Environment
ENV PYTHONPATH=/app
ENV VECTOR_PROVIDER=qdrant
ENV COLLECTION_NAME=knowledge_base

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
