# CLAUDE.md - Backend (FastAPI + RAG Pipeline)

## Architecture

```
backend/
├── api/              # FastAPI routes and models
│   ├── routes/       # Endpoint handlers (chat, ingest, collections)
│   ├── models/       # Pydantic request/response schemas
│   └── main.py       # App initialization, CORS, routers
├── rag/              # RAG pipeline (LangGraph)
│   ├── pipeline.py   # Graph compilation and execution
│   ├── nodes.py      # Pipeline nodes (intent, retrieve, generate, etc.)
│   ├── retriever.py  # Hybrid search (Vector + BM25 + RRF)
│   ├── reranker.py   # Cross-encoder reranking
│   └── intent_router.py  # 3-layer intent classification
├── ingest/           # Document processing
│   ├── service.py    # Ingestion orchestration
│   ├── chunker.py    # Parent-child chunking (2000/400 chars)
│   └── loader.py     # File parsing (PDF, TXT, MD, DOCX)
├── vectorstore/      # ChromaDB operations
├── memory/           # Session storage (SQLite)
└── config/           # Settings and environment
```

## Key Patterns

### Lazy Initialization
```python
_pipeline: RAGPipeline | None = None

def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
```

### SSE Streaming
```python
async def generate_stream(...) -> AsyncGenerator[str, None]:
    # Phase events: searching → sources → generating → tokens → done
    yield f"event: phase\ndata: {json.dumps({'phase': 'searching'})}\n\n"
    yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
    yield f"event: phase\ndata: {json.dumps({'phase': 'generating'})}\n\n"
    async for token in stream:
        yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
    yield f"event: done\ndata: {json.dumps(metadata)}\n\n"
```

### Collection Naming
```python
# Chat-scoped: chat_{chat_id}
# Global: collection_name (legacy)
effective_collection = f"chat_{chat_id}" if chat_id else collection_name
```

## Critical Rules

1. **Always async** - All database and LLM operations use `async/await`
2. **Session isolation** - Every query needs unique `session_id`
3. **Chat-scoped collections** - Documents belong to chats (ADR-007)
4. **Type hints everywhere** - Pydantic models for all API contracts
5. **No reasoning models** - DeepSeek-R1, QwQ cause 200-350s latency

## Error Handling

```python
# API errors - consistent format
raise HTTPException(
    status_code=400,
    detail={"error": "invalid_request", "message": "..."}
)

# Internal errors - log and generic response
except Exception as e:
    logger.error(f"Pipeline failed: {e}")
    raise HTTPException(500, {"error": "internal", "message": "Processing failed"})
```

## Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_rag.py -v

# E2E context test
python test_e2e_context.py
```

## Key Files

| File | Purpose |
|------|---------|
| `api/routes/chat.py` | Chat endpoint, SSE streaming |
| `api/routes/ingest.py` | Document upload, processing |
| `rag/nodes.py` | Pipeline nodes, intent fallback, hallucination |
| `rag/retriever.py` | Hybrid search (Vector + BM25 + RRF) |
| `rag/reranker.py` | Cross-encoder scoring (ms-marco-MiniLM) |
| `rag/intent_router.py` | 3-layer classification (rules → semantic → LLM) |
| `ingest/chunker.py` | Parent-child chunking (2000/400 chars) |
| `config/settings.py` | All configuration with defaults |

## Adding New Features

1. **New endpoint**: Add route in `api/routes/`, models in `api/models/`
2. **New pipeline node**: Add to `rag/nodes.py`, wire in `rag/pipeline.py`
3. **New retrieval method**: Extend `rag/retriever.py`
4. **New file type**: Add parser in `ingest/loader.py`

## Performance Notes

- Retrieval: k=20 vector + k=20 BM25 → RRF fusion → top 50 → rerank to 5
- Chunking: 400 char children for retrieval, 2000 char parents for LLM context
- Reranking: Cross-encoder (ms-marco-MiniLM-L-6-v2) is 10-50x faster than LLM grading
- FastEmbed: ONNX runtime, 10x faster than Ollama embeddings for batch ingestion
