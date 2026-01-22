# Codebase Quality Improvements

**Date:** 2025-12-24
**Version:** v1.1.0-quality-hardening

## Overview

This document tracks quality improvements made to bring older, untouched files up to production standards. All changes are non-invasive guards and observability features—no logic changes.

---

## Changes Summary

| Category | File | Change |
|----------|------|--------|
| Resource Management | `memory/store.py` | Added `close()` methods for proper connection cleanup |
| Error Surfacing | `ingest/service.py` | BM25 failures now logged as errors and recorded in job.errors |
| Input Validation | `memory/store.py` | Validate session_id and role parameters |
| Input Validation | `ingest/chunker.py` | Validate chunk_size parameters |
| Docker Alignment | `docker-compose.yml` | Removed qdrant, aligned to chroma provider |
| Health Checks | `api/main.py` | Real service health checks (vector store, LLM, memory) |
| Shutdown Cleanup | `api/main.py` | Proper connection cleanup on app shutdown |
| Observability | `api/main.py` | Lightweight metrics middleware + `/metrics` endpoint |
| UX | `frontend/src/lib/sse.ts` | Better "server offline" error messages |
| UX | `frontend/src/lib/api.ts` | Added `checkServerOnline()` helper |
| Production | `.env` | Set `DEBUG=false` |

---

## Detailed Changes

### 1. Memory Store (`backend/memory/store.py`)

**Problem:** Redis connections were never closed, leading to potential resource leaks.

**Solution:**
```python
# Added to BaseMemoryStore (abstract)
@abstractmethod
async def close(self) -> None:
    """Close any open connections. Call on shutdown."""
    pass

# Redis implementation
async def close(self) -> None:
    if self._client:
        await self._client.close()
        self._client = None

# Factory class
@classmethod
async def close(cls) -> None:
    if cls._instance:
        await cls._instance.close()
        cls._instance = None
```

**Input Validation Added:**
```python
async def add_message(self, session_id: str, role: str, ...):
    if not session_id or not session_id.strip():
        raise ValueError("session_id cannot be empty")
    if role not in ('user', 'assistant'):
        raise ValueError("role must be 'user' or 'assistant'")
```

---

### 2. Ingestion Service (`backend/ingest/service.py`)

**Problem:** BM25 index failures were logged as warnings and silently swallowed. Jobs marked as "completed" even when hybrid search was broken.

**Solution:**
```python
async def _update_bm25_index(self, collection_name: str, new_chunks: List[Document], job: Optional[IngestionJob] = None):
    try:
        retriever.add_to_bm25_index(collection_name, new_chunks)
    except Exception as e:
        error_msg = f"BM25 index update failed: {e} - hybrid search may be degraded"
        logger.error(error_msg)  # Changed from warning
        if job:
            job.errors.append(error_msg)  # Surface to caller
```

---

### 3. Chunker Validation (`backend/ingest/chunker.py`)

**Problem:** Invalid chunk sizes could cause cryptic downstream errors.

**Solution:**
```python
def __init__(self, ...):
    # Validation
    if self.parent_chunk_size <= 0:
        raise ValueError("parent_chunk_size must be positive")
    if self.child_chunk_size <= 0:
        raise ValueError("child_chunk_size must be positive")
    if self.child_chunk_size > self.parent_chunk_size:
        raise ValueError("child_chunk_size cannot exceed parent_chunk_size")
```

---

### 4. Docker Alignment (`backend/docker-compose.yml`)

**Problem:** Docker config referenced `qdrant` but code only supports `chroma`.

**Changes:**
- Removed `qdrant` service
- Changed `VECTOR_PROVIDER=qdrant` → `VECTOR_PROVIDER=chroma`
- Changed `EMBEDDING_PROVIDER=ollama` → `EMBEDDING_PROVIDER=fastembed`
- Removed `depends_on: qdrant`
- Updated volumes: removed `qdrant_data`, added `chroma_data`

---

### 5. Health Checks (`backend/api/main.py`)

**Problem:** Health endpoint returned hardcoded `True` without checking services.

**Solution:** Real service checks:
```python
@app.get("/health")
async def health_check():
    services = {"api": True}

    # Check vector store
    try:
        vs = VectorStore()
        services["vector_store"] = True
    except Exception:
        services["vector_store"] = False

    # Check LLM (Ollama)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            services["llm"] = resp.status_code == 200
    except Exception:
        services["llm"] = False

    # Check memory backend
    try:
        await memory_store.list_sessions()
        services["memory"] = True
    except Exception:
        services["memory"] = False

    return {"status": "healthy" if all(services.values()) else "degraded", ...}
```

---

### 6. Shutdown Cleanup (`backend/api/main.py`)

**Problem:** Connections not closed on app shutdown.

**Solution:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

    # Shutdown - close connections
    logger.info("Shutting down...")
    try:
        from memory.store import MemoryStore
        await MemoryStore.close()
    except Exception as e:
        logger.warning(f"Error closing memory store: {e}")
```

---

### 7. Metrics Endpoint (`backend/api/main.py`)

**New Feature:** Lightweight request metrics for observability.

```python
class SimpleMetrics:
    """Non-invasive request metrics."""

    def record_request(self, path: str, latency_ms: float, is_error: bool = False):
        normalized = self._normalize_path(path)
        self.request_count[normalized] += 1
        self.latency_sum[normalized] += latency_ms
        if is_error:
            self.error_count[normalized] += 1

    def get_summary(self) -> dict:
        return {
            "uptime_seconds": ...,
            "total_requests": ...,
            "total_errors": ...,
            "endpoints": {
                "/chat/{id}/stream": {"requests": 42, "errors": 1, "avg_latency_ms": 1234.5},
                ...
            }
        }

# Middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start_time) * 1000
    metrics.record_request(request.url.path, latency_ms, response.status_code >= 400)
    return response

# Endpoint
@app.get("/metrics")
async def get_metrics():
    return metrics.get_summary()
```

**Example Response:**
```json
{
  "uptime_seconds": 3600.5,
  "total_requests": 150,
  "total_errors": 3,
  "endpoints": {
    "/chat/{id}/stream": {
      "requests": 45,
      "errors": 1,
      "avg_latency_ms": 2341.23
    },
    "/chat/{id}/documents": {
      "requests": 30,
      "errors": 0,
      "avg_latency_ms": 156.78
    },
    "/health": {
      "requests": 75,
      "errors": 2,
      "avg_latency_ms": 45.12
    }
  }
}
```

---

### 8. Frontend Server Offline Detection

**Problem:** Generic "Failed to fetch" errors when server is offline.

**Solution (sse.ts):**
```typescript
try {
  response = await fetch(url, {...});
} catch (fetchError) {
  throw new Error('Server is offline. Please check if the backend is running.');
}

if (!response.ok) {
  if (response.status === 503) {
    throw new Error('Server is temporarily unavailable. Please try again.');
  }
  throw new Error(`Server error: ${response.status}`);
}
```

**Solution (api.ts):**
```typescript
// Helper function
export async function checkServerOnline(): Promise<{
  online: boolean;
  status?: 'healthy' | 'degraded';
  services?: Record<string, boolean>;
}> {
  try {
    const health = await api.health();
    return { online: true, status: health.status, services: health.services };
  } catch {
    return { online: false };
  }
}
```

---

### 9. Production Config (`.env`)

**Change:** `DEBUG=true` → `DEBUG=false`

**Impact:**
- Logging level: DEBUG → INFO
- Error responses: No stack traces exposed
- Uvicorn: Auto-reload disabled

---

## New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Real service health status |
| `/metrics` | GET | Request counts, errors, latencies |

---

## Testing Recommendations

1. **Health Check:** `curl http://localhost:8001/health`
2. **Metrics:** `curl http://localhost:8001/metrics`
3. **Server Offline:** Stop backend, send chat message → should show "Server is offline" not "Failed to fetch"
4. **Input Validation:** Try empty session_id → should get clear error

---

## Files Modified

```
backend/
├── api/main.py              # Health checks, metrics, shutdown
├── memory/store.py          # close() methods, validation
├── ingest/service.py        # BM25 error surfacing
├── ingest/chunker.py        # Chunk size validation
├── docker-compose.yml       # Qdrant → Chroma alignment
├── .env                     # DEBUG=false

frontend/
├── src/lib/sse.ts           # Server offline detection
├── src/lib/api.ts           # checkServerOnline() helper
```
