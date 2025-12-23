# Docker Deployment Documentation

> **Last Tested:** 13-12-2025
> **Status:** VERIFIED - All Services Running

---

## Quick Start

### Local Development (Using Host Ollama)

```bash
# Ensure Ollama is running on your host machine
ollama serve

# From the backend directory
cd backend
docker-compose up -d --build
```

### Full Containerized (Including Ollama with GPU)

```bash
# From the backend directory (without override file)
cd backend
rm docker-compose.override.yml  # If exists
docker-compose up -d --build
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network: rag-network                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Frontend   │    │     API      │    │    Qdrant    │       │
│  │   (React)    │───▶│  (FastAPI)   │───▶│ (Vector DB)  │       │
│  │   :3000      │    │   :8001      │    │ :6333/:6334  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                             │                                    │
│                             ▼                                    │
│                      ┌──────────────┐    ┌──────────────┐       │
│                      │    Redis     │    │   Ollama*    │       │
│                      │   (Cache)    │    │    (LLM)     │       │
│                      │   :6379      │    │   :11434     │       │
│                      └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

* Ollama can run in container OR on host (via docker-compose.override.yml)
```

---

## Service Configuration

### Container Details

| Service | Image | Port(s) | Purpose |
|---------|-------|---------|---------|
| api | Custom (Dockerfile) | 8001 | FastAPI backend with RAG pipeline |
| frontend | Custom (Dockerfile) | 3000 | React/Vite frontend |
| qdrant | qdrant/qdrant:latest | 6333, 6334 | Vector database |
| redis | redis:alpine | 6379 | Conversation memory cache |
| ollama | ollama/ollama:latest | 11434 | LLM inference (optional) |

### Environment Variables

```yaml
# API Service
environment:
  - DEBUG=false
  - API_HOST=0.0.0.0
  - API_PORT=8001
  - LLM_PROVIDER=ollama
  - OLLAMA_BASE_URL=http://ollama:11434        # Container Ollama
  # OR: OLLAMA_BASE_URL=http://host.docker.internal:11434  # Host Ollama
  - OLLAMA_MODEL=llama3
  - EMBEDDING_PROVIDER=ollama
  - OLLAMA_EMBEDDING_MODEL=nomic-embed-text
  - VECTOR_PROVIDER=qdrant
  - QDRANT_URL=http://qdrant:6333
  - MEMORY_BACKEND=redis
  - REDIS_URL=redis://redis:6379
```

---

## Local Development Override

### File: `backend/docker-compose.override.yml`

This file allows using Ollama running on the Windows host instead of a containerized version.

```yaml
# Override for local development - uses host Ollama instead of container
# This file is in .gitignore and won't be committed

services:
  api:
    # Use host.docker.internal to reach Ollama running on Windows host
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    # Override depends_on to remove ollama
    depends_on:
      - qdrant
      - redis
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # Keep ollama service but make it a no-op (just exits immediately)
  ollama:
    image: alpine:latest
    command: ["echo", "Using host Ollama"]
    deploy: {}
    restart: "no"
```

### Why Use Host Ollama?

1. **Faster iteration**: No need to rebuild/restart container for model changes
2. **Better GPU support**: Direct GPU access without Docker GPU passthrough
3. **Shared models**: Use models already downloaded on host
4. **Resource efficiency**: Avoid duplicate GPU memory usage

---

## Build Process

### Build Command

```bash
cd backend
docker-compose up -d --build
```

### Build Duration

- **First build**: ~20 minutes (due to sentence-transformers/PyTorch dependencies)
- **Subsequent builds**: ~2-3 minutes (cached layers)

### Heavy Dependencies

The following packages significantly increase build time:

| Package | Size | Purpose |
|---------|------|---------|
| sentence-transformers | ~500MB | Cross-encoder reranking |
| torch (transitive) | ~2GB | ML framework |
| fastembed | ~100MB | Fast embeddings |

---

## Deployment Test Results (13-12-2025)

### Container Status

```
NAME                IMAGE                  STATUS    PORTS
backend-api-1       backend-api            Up        0.0.0.0:8001->8001/tcp
backend-frontend-1  backend-frontend       Up        0.0.0.0:3000->3000/tcp
backend-ollama-1    alpine:latest          Exited    (no-op, using host)
backend-qdrant-1    qdrant/qdrant:latest   Up        0.0.0.0:6333-6334->6333-6334/tcp
backend-redis-1     redis:alpine           Up        0.0.0.0:6379->6379/tcp
```

### Health Check Results

#### API Health (`GET http://localhost:8001/health`)

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "api": true,
    "vector_store": true,
    "llm": true,
    "memory": true
  }
}
```

#### Qdrant Health (`GET http://localhost:6333`)

```
Response: 200 OK (empty body = healthy)
```

#### Frontend (`GET http://localhost:3000`)

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Axiom RAG</title>
    ...
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

#### Host Ollama (`GET http://localhost:11434/api/tags`)

```json
{
  "models": [
    {"name": "llama3:latest", ...},
    {"name": "nomic-embed-text:latest", ...},
    {"name": "llava:latest", ...}
  ]
}
```

### API Startup Logs

```
api-1  | INFO:     Started server process [1]
api-1  | INFO:     Waiting for application startup.
api-1  | 2025-12-13 05:10:36,425 - api.main - INFO - Starting Axiom RAG v2.0.0
api-1  | 2025-12-13 05:10:36,432 - api.main - INFO - Initializing RAG pipeline...
api-1  | INFO:     Application startup complete.
api-1  | INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

---

## Commands Reference

### Start Services

```bash
# Start all services (foreground)
docker-compose up

# Start all services (background)
docker-compose up -d

# Start with rebuild
docker-compose up -d --build
```

### Stop Services

```bash
# Stop services (keep containers)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f frontend
```

### Container Status

```bash
docker-compose ps
```

### Health Checks

```bash
# API
curl http://localhost:8001/health

# Qdrant
curl http://localhost:6333

# Host Ollama
curl http://localhost:11434/api/tags
```

---

## Troubleshooting

### API Can't Connect to Ollama

**Symptom:** `llm: false` in health check

**Solutions:**
1. Ensure Ollama is running on host: `ollama serve`
2. Check override file exists: `backend/docker-compose.override.yml`
3. Verify `host.docker.internal` resolves:
   ```bash
   docker exec backend-api-1 ping host.docker.internal
   ```

### GPU Not Available in Container

**Symptom:** Slow inference, CPU-only mode

**Solutions:**
1. Install NVIDIA Container Toolkit
2. Verify docker-compose.yml has GPU reservation:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```
3. Use host Ollama instead (recommended for Windows)

### Build Fails on PyTorch

**Symptom:** Memory errors during pip install

**Solutions:**
1. Increase Docker memory limit (Settings > Resources > Memory)
2. Use `--no-cache` flag: `docker-compose build --no-cache`
3. Consider CPU-only PyTorch variant

### Frontend Can't Reach API

**Symptom:** Network errors in browser console

**Solutions:**
1. Verify API is running: `curl http://localhost:8001/health`
2. Check CORS settings in API
3. Verify `VITE_API_URL=http://localhost:8001` in frontend environment

---

## Volume Mounts

| Volume | Container Path | Purpose |
|--------|---------------|---------|
| `./data` | `/app/data` | Document storage |
| `qdrant_data` | `/qdrant/storage` | Vector database |
| `redis_data` | `/data` | Redis persistence |
| `ollama_data` | `/root/.ollama` | Ollama models |

---

## Network Configuration

All services are on the `rag-network` bridge network:

```yaml
networks:
  rag-network:
    driver: bridge
```

Internal service names resolve automatically:
- `api` → API container
- `qdrant` → Qdrant container
- `redis` → Redis container
- `ollama` → Ollama container (or no-op if using host)
- `frontend` → Frontend container

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/docker-compose.yml` | Main compose configuration |
| `backend/docker-compose.override.yml` | Local dev override (gitignored) |
| `backend/Dockerfile` | API container build |
| `frontend/Dockerfile` | Frontend container build |
| `Dockerfile` (root) | Production build from root |
| `docker-compose.yml` (root) | Minimal production compose |

---

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Web UI |
| API | http://localhost:8001 | REST API |
| API Docs | http://localhost:8001/docs | Swagger UI |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector DB UI |
| Ollama | http://localhost:11434 | LLM API |
