# === Agentic RAG Backend Dockerfile ===

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (all modules directly, no src/ folder)
COPY api/ ./api/
COPY config/ ./config/
COPY ingest/ ./ingest/
COPY memory/ ./memory/
COPY rag/ ./rag/
COPY vectorstore/ ./vectorstore/
COPY main.py .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8001

# Run the API
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
