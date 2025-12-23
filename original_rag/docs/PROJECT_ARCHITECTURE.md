# Axiom RAG - Project Architecture

**Generated from:** `original_rag.toon` codebase index
**Date:** 2024-12-23

---

## Project Overview

Axiom RAG is a local-first, self-correcting Retrieval Augmented Generation system built with LangGraph orchestration. The system emphasizes **grounded answers** (no hallucinations) and **intent-aware routing** for optimal response times.

### Key Stats (from Toonify index)
- **Total Files:** 89 Python files
- **Total Functions:** 400+
- **Languages:** Python (backend), TypeScript (frontend)
- **Master Frameworks:** FastAPI, LangGraph, React

---

## 1. The RAG "Brain" (`backend/rag/`)

This directory contains the core intelligence and recent Phase 1 optimizations.

### Core Files

| File | Lines | Purpose |
|------|-------|---------|
| **nodes.py** | ~980 | Command center - Adaptive K, reranking, hallucination bypass |
| **intent_router.py** | ~500 | 3-layer intent classification (Hard Rules → Semantic → LLM) |
| **pipeline.py** | ~280 | LangGraph orchestrator - graph definition and flow control |
| **retriever.py** | ~400 | Hybrid search (Vector + BM25) with RRF fusion |
| **reranker.py** | ~400 | Cross-encoder scoring for document relevance |
| **context_filter.py** | ~150 | Prunes irrelevant documents based on similarity |
| **context_compressor.py** | ~200 | Token reduction (LLMLingua - currently disabled) |
| **intent_handlers.py** | ~300 | Context-aware handlers for followup/simplify/deepen |
| **state.py** | ~100 | RAGState TypedDict schema |
| **prompts.py** | ~150 | LLM prompt templates |

### Recent Optimizations (Phase 1)

Located in `nodes.py`:

1. **Adaptive K Selection** (lines 522-530)
   - Simple queries: K=2 documents (~1200 tokens)
   - Complex queries: K=5 documents (~3000 tokens)
   - Result: 60% prefill reduction for simple queries

2. **Hallucination Bypass** (lines 769-787)
   - Skip LLM hallucination check for simple queries with retrieval score ≥70%
   - Result: 3-5s savings per simple query

### Pipeline Flow

```
User Message
     │
     ▼
┌─────────────────────────────────────┐
│         INTENT CLASSIFIER           │
│  Layer 0: Hard Rules (instant)      │
│  Layer 1: Semantic (<20ms)          │
│  Layer 2: LLM fallback (if needed)  │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────┐
│Greeting│  │ Followup │  │ Question │
│Gratitude│ │ Simplify │  │          │
│Garbage │  │ Deepen   │  │          │
└────┬───┘  └────┬─────┘  └────┬─────┘
     │           │             │
     ▼           ▼             ▼
  Instant    Memory-Based   Full RAG
  Response   Expansion      Pipeline
     │           │             │
     │           │             ▼
     │           │      ┌──────────────┐
     │           │      │ ROUTE QUERY  │
     │           │      │ Simple/Complex│
     │           │      └──────┬───────┘
     │           │             │
     │           │             ▼
     │           │      ┌──────────────┐
     │           │      │HYBRID SEARCH │
     │           │      │Vector + BM25 │
     │           │      └──────┬───────┘
     │           │             │
     │           │             ▼
     │           │      ┌──────────────┐
     │           │      │ GRADE DOCS   │
     │           │      │ Adaptive K   │
     │           │      └──────┬───────┘
     │           │             │
     │           │             ▼
     │           │      ┌──────────────┐
     │           │      │  GENERATE    │
     │           │      │  (LLM)       │
     │           │      └──────┬───────┘
     │           │             │
     │           │             ▼
     │           │      ┌──────────────┐
     │           │      │HALLUCINATION │
     │           │      │   CHECK      │
     │           │      └──────┬───────┘
     │           │             │
     └───────────┴─────────────┘
                  │
                  ▼
           Final Response
```

---

## 2. API Infrastructure (`backend/api/`)

Built on **FastAPI** with streaming SSE support.

### Core Files

| File | Lines | Purpose |
|------|-------|---------|
| **main.py** | ~100 | Application entry point, lifespan management, health checks |
| **routes/chat.py** | ~450 | Chat endpoints, SSE streaming, document management |
| **routes/ingest.py** | ~200 | Document upload and processing |
| **routes/collections.py** | ~150 | Collection CRUD operations |
| **models/requests.py** | ~100 | Pydantic request schemas |
| **models/responses.py** | ~150 | Pydantic response schemas |

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/` | POST | Non-streaming chat |
| `/chat/stream` | POST | SSE streaming chat |
| `/chat/{chat_id}/stream` | POST | Chat-scoped streaming |
| `/chat/{chat_id}/documents` | POST | Upload docs to chat |
| `/ingest/upload` | POST | Global document upload |
| `/health` | GET | System health check |

---

## 3. Document Processing (`backend/ingest/`, `backend/vectorstore/`)

### Ingestion Pipeline

| File | Purpose |
|------|---------|
| **ingest/service.py** | Orchestrates document processing jobs |
| **ingest/loader.py** | PDF, TXT, DOCX, MD file parsing |
| **ingest/chunker.py** | Parent-Child chunking strategy |
| **vectorstore/store.py** | ChromaDB + FastEmbed integration |

### Chunking Strategy

```
Document
    │
    ▼
┌─────────────────────────────────────┐
│         PARENT-CHILD CHUNKING       │
│                                     │
│  Parent: 2000 chars (sent to LLM)   │
│  Child:  400 chars (indexed)        │
│                                     │
│  Search finds CHILD → Returns PARENT│
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│         DUAL INDEXING               │
│                                     │
│  Vector Index: Semantic similarity  │
│  BM25 Index:   Keyword matching     │
│                                     │
│  Combined via RRF fusion            │
└─────────────────────────────────────┘
```

---

## 4. Memory & State (`backend/memory/`)

| File | Purpose |
|------|---------|
| **store.py** | SQLite-based conversation memory |

### Session Isolation

- Each query gets unique `session_id`
- Each chat gets unique `collection_name` (chat_{chat_id})
- Prevents memory bleed between conversations

---

## 5. Frontend (`frontend/src/`)

**Stack:** React + TypeScript + Vite + Tailwind + Shadcn UI

### Core Files

| File | Lines | Purpose |
|------|-------|---------|
| **stores/chatStore.ts** | ~450 | Zustand state management |
| **components/chat/ChatArea.tsx** | ~200 | Main chat interface |
| **components/chat/MessageList.tsx** | ~150 | Message rendering |
| **components/chat/ChatInput.tsx** | ~100 | User input handling |

### UI Components (`components/ui/`)

Extensive Shadcn component library including:
- Button, Input, Dialog, Dropdown
- Card, Tabs, Toast, Tooltip
- Command palette (cmdk)
- File upload components

---

## 6. Configuration (`backend/config/`)

| File | Purpose |
|------|---------|
| **settings.py** | Pydantic settings with env var support |

### Key Settings

```python
# LLM
LLM_PROVIDER = "ollama"
OLLAMA_MODEL = "llama3.1:8b"

# Embeddings
EMBEDDING_PROVIDER = "fastembed"
FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"

# Vector Store
VECTOR_PROVIDER = "chroma"

# Retrieval (Phase 1 Optimizations)
RETRIEVAL_FINAL_K = 5  # Adaptive: 2 for simple, 5 for complex

# Performance
OLLAMA_KV_CACHE_TYPE = "q8_0"
OLLAMA_FLASH_ATTENTION = true
OLLAMA_NUM_CTX = 4096
```

---

## 7. Testing & Benchmarks (`backend/`)

| File | Purpose |
|------|---------|
| **benchmark_e2e.py** | Full E2E benchmark with document ingestion |
| **benchmark_quality.py** | Quality verification with output analysis |
| **test_latency.py** | Quick latency spot-check |
| **tests/test_rag.py** | Unit tests |

---

## 8. Archive (`archive/`)

Historical versions preserved for debugging and diffing:
- `nodes.py` versions 1-10
- `pipeline.py` versions 1-6
- Various backup configurations

**Note:** Consider moving to separate git branch after Phase 2 stabilization to keep production codebase lean.

---

## Current Performance (Phase 1)

| Metric | Value |
|--------|-------|
| Quality | 100% (6/6 tests) |
| Avg RAG Latency | 25.1s |
| Simple Query Avg | 23.8s (K=2) |
| Complex Query Avg | 37.2s (K=5) |
| Best Case | 4.5s |
| Worst Case | 46.1s |

### Bottleneck Analysis

- ✅ Retrieval/prefill optimized (Adaptive K)
- ✅ Hallucination check optimized (bypass for simple)
- ⏳ LLM generation speed is remaining bottleneck

---

## Phase 2 Roadmap

1. **Model Routing** - Use 3B model for simple queries, 8B for complex
2. **Semantic Caching** - Cache repeat query answers
3. **Response Streaming** - Reduce perceived latency

---

## File Tree (Key Paths)

```
original_rag/
├── backend/
│   ├── rag/
│   │   ├── nodes.py           # Core logic + Phase 1 optimizations
│   │   ├── pipeline.py        # LangGraph orchestration
│   │   ├── intent_router.py   # 3-layer intent classification
│   │   ├── retriever.py       # Hybrid search
│   │   └── reranker.py        # Cross-encoder scoring
│   ├── api/
│   │   ├── main.py            # FastAPI app
│   │   └── routes/chat.py     # Chat endpoints
│   ├── vectorstore/store.py   # ChromaDB integration
│   ├── ingest/service.py      # Document processing
│   ├── memory/store.py        # Conversation memory
│   └── config/settings.py     # Configuration
├── frontend/
│   ├── src/
│   │   ├── stores/chatStore.ts
│   │   └── components/chat/
│   └── package.json
├── test-docs/                  # Test documents
├── BENCHMARK_RESULTS.md        # Performance documentation
└── README.md                   # Project overview
```
