# CLAUDE.md - Axiom RAG Project Configuration

## Code Standards

- Read existing code before modifying
- No over-engineering or speculative features
- Fix only what is requested
- Keep solutions minimal and focused

## Commit Format

```
<type>(<scope>): <subject>

<body - what and why, not how>
```

**Types:** `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`

**Scopes:** `rag`, `ingest`, `api`, `frontend`, `vectorstore`, `memory`, `config`

### Good Commits
```
feat(rag): implement semantic query caching

- Cache query embeddings with TTL
- Return cached answers for >0.95 similarity
- Bypass LLM entirely for cache hits

fix(ingest): prevent duplicate chunks on re-upload

Add content hash check before inserting to ChromaDB.
Skip chunks that already exist in collection.

perf(rag): reduce prefill by adaptive context sizing

- Simple queries: 2-3 docs instead of 5
- Complex queries: keep full 5 docs
- 30-40% latency reduction for simple queries
```

### Bad Commits (NEVER)
```
"Updated files"
"Fixed bug"
"Changes"
"WIP"
"Various improvements"
```

## Project Structure

```
Toon/
├── original_rag/           # Main application
│   ├── backend/            # FastAPI + RAG pipeline
│   ├── frontend/           # React + TypeScript
│   └── docs/               # Technical documentation
└── ARCHIVED/               # Deprecated files
```

## Quick Commands

```bash
# Start backend (port 8001)
cd original_rag/backend && python -m uvicorn api.main:app --port 8001

# Start frontend (port 8080)
cd original_rag/frontend && npm run dev

# Run benchmark
node test-quality.js 8001 original_rag

# Check Ollama models
ollama list
```

## Environment Setup

Required Ollama variables (restart Ollama after setting):

```
OLLAMA_FLASH_ATTENTION=true
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_CTX=4096
```

## Documentation

- [original_rag/README.md](original_rag/README.md) - Developer reference
- [original_rag/docs/](original_rag/docs/) - Architecture and pipeline docs
- [original_rag/CLAUDE.md](original_rag/CLAUDE.md) - RAG-specific configuration
