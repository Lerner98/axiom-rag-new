# Axiom RAG

**Local-First AI That Doesn't Hallucinate**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/LangGraph-Agentic-purple" alt="LangGraph">
  <img src="https://img.shields.io/badge/100%25-Local_First-green" alt="Local First">
  <img src="https://img.shields.io/badge/Hallucination-Checked-red" alt="Hallucination Checked">
  <img src="https://img.shields.io/badge/V7-Production_Ready-orange" alt="V7 Production Ready">
</p>

---

## What Is This?

Upload any document. Ask questions. Get **accurate, grounded answers** with source citations.

Unlike ChatGPT or other AI tools, Axiom:
- ✅ **Runs 100% locally** — Your data never leaves your machine
- ✅ **Cites its sources** — Every answer shows exactly where it came from
- ✅ **Checks itself** — Built-in hallucination detection catches false claims
- ✅ **Finds exact matches** — Hybrid search catches keywords that pure AI misses
- ✅ **Understands intent** — Knows the difference between "hi" and "What is CAP theorem?"

---

## See It In Action

```
You: "What is the CAP theorem?"

Axiom: "The CAP theorem states that in any distributed system, 
        you can only guarantee two of three properties: 
        Consistency, Availability, and Partition Tolerance."
        
        [Source 1: system-design.pdf, Page 13]
        Relevance: 94%

You: "tell me more"

Axiom: "Building on the CAP theorem, here's a deeper look...
        - Consistency means all nodes see the same data simultaneously
        - Availability means every request receives a response
        - Partition Tolerance means the system continues despite network failures
        
        In practice, most systems choose CP (consistency + partition tolerance)
        or AP (availability + partition tolerance)..."
        
        [Expanded from previous answer - no new retrieval needed]

You: "simplify that"

Axiom: "Think of it like a restaurant:
        - Consistency = Everyone gets the same menu
        - Availability = The restaurant is always open
        - Partition Tolerance = It works even if the phone lines are down
        
        You can only guarantee 2 of these 3 things at once."
        
        [Simplified from previous answer]
```

---

## Why It's Different

| Traditional RAG | Axiom RAG |
|-----------------|-----------|
| Misses keywords like "Error 504" | ✅ **Hybrid Search** finds exact matches |
| Returns choppy, incomplete context | ✅ **Smart Chunking** returns full paragraphs |
| Retrieves 5 docs, hopes for the best | ✅ **AI Reranker** evaluates 50, picks best 5 |
| No idea if answer is real | ✅ **Hallucination Check** verifies every response |
| One-size-fits-all queries | ✅ **Router Agent** optimizes each question type |
| Treats every message the same | ✅ **Intent Router** knows greetings from questions |
| Re-searches for "tell me more" | ✅ **Context Handlers** expand previous answers from memory |

---

## The Tech Stack

### Document Processing

```
                  Document Upload
                        │
                        ▼
┌─────────────────────────────────────────┐
│            SMART CHUNKING               │
│   Split into small pieces (for search)  │
│   Keep large context (for answers)      │
└─────────────────┬───────────────────────┘
                  │
      ┌───────────┴───────────┐
      ▼                       ▼
┌──────────────┐      ┌──────────────┐
│ Vector Index │      │ BM25 Index   │
│ (Semantic)   │      │ (Keywords)   │
└──────────────┘      └──────────────┘
```

### Query Processing (V5+ Architecture)

```
                  Your Message
                        │
                        ▼
┌─────────────────────────────────────────┐
│            INTENT CLASSIFIER            │
│   Layer 0: Hard rules (instant)         │
│   Layer 1: Semantic matching (<20ms)    │
│   Layer 2: LLM fallback (if needed)     │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────┐
│Greeting│  │ Followup │  │ Question │
│Gratitude│ │ Simplify │  │ Command  │
│Garbage │  │ Deepen   │  │          │
└────┬───┘  └────┬─────┘  └────┬─────┘
     │           │             │
     ▼           ▼             ▼
  Instant    Memory-Based   Full RAG
  Response   Expansion      Pipeline
```

### RAG Pipeline (For Questions)

```
                 Question Intent
                        │
                        ▼
┌─────────────────────────────────────────┐
│             ROUTER AGENT                │
│   Simple query? → Skip rewrite          │
│   Complex query? → Optimize first       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│            HYBRID SEARCH                │
│   Vector (meaning) + BM25 (keywords)    │
│   → 50 candidates                       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│             AI RERANKER                 │
│   Cross-Encoder scores each result      │
│   → Top 5 most relevant                 │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         HALLUCINATION CHECK             │
│   Fast keyword check (0.5ms)            │
│   LLM verification if uncertain         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
            Grounded Answer + Sources
```

---

## Key Innovations (V7)

### 1. BM25 Index Persistence

**Problem:** After server restart, BM25 keyword search returned 0 results — hybrid search degraded to vector-only.

**Solution:** Pickle-based persistence with lazy loading and self-healing.

```
On Document Upload:
  → Build BM25 index in memory
  → Auto-save to data/bm25_indices/{collection}.pkl

On Query (after restart):
  → Check memory (miss)
  → Lazy-load from disk ✓
  → Full hybrid search restored
```

### 2. Invisible Retry Prompts

**Problem:** When hallucination check triggered a retry, the LLM responded with "Here's my attempt at improving the previous answer" — exposing internal mechanics to users.

**Solution:** Retry prompt no longer mentions it's a retry. Uses stricter grounding rules without meta-commentary.

```
Before: "Your previous answer was flagged... Improved answer:"
        → LLM: "Here's my attempt at improving..."

After:  Same strict rules, no "previous/improving" language
        → LLM: Clean, grounded response
```

### 3. Auto-Create Chat on First Message

**Problem:** Fresh users with 0 chats who typed a message (without clicking "New Chat") saw nothing happen.

**Solution:** `sendMessage()` now calls `addUserMessage()` first, which auto-creates a chat if none exists, then retrieves the fresh chat ID.

---

## Previous Innovations (V5)

### 1. Intent-Aware Routing

**Problem:** Traditional RAG treats "hi" the same as "What is CAP theorem?" — wasting resources and providing poor UX.

**Solution:** 3-layer hybrid intent classification routes each message optimally.

```
Message             Intent      Handler           Response Time
─────────────────────────────────────────────────────────────────
"hi"              → greeting  → instant response     <100ms
"thanks"          → gratitude → acknowledgment       <100ms
"asdfgh"          → garbage   → polite rejection     <100ms
"tell me more"    → followup  → expand from memory   2-5s
"simplify that"   → simplify  → rephrase from memory 2-5s
"go deeper"       → deepen    → add technical depth  2-5s
"What is X?"      → question  → full RAG pipeline    5-30s
```

**Why 3 layers?**
- **Layer 0 (Hard Rules):** Catches garbage instantly (empty, no letters, keyboard spam)
- **Layer 1 (Semantic):** FastEmbed similarity to intent exemplars (<20ms)
- **Layer 2 (LLM):** Fallback for ambiguous cases (only when needed)

### 2. Context-Aware Handlers (V5)

**Problem:** User says "tell me more" and the system does a completely new search, losing context.

**Solution:** Followup/simplify/deepen intents use conversation memory, not RAG.

```
User: "What is CAP theorem?"
      → Full RAG search, returns detailed answer

User: "simplify that"
      → Detects 'simplify' intent
      → Retrieves previous answer from memory
      → Asks LLM to rephrase simpler
      → No document retrieval needed!
```

---

## Core Architecture (V3+)

### 1. Parent-Child Chunking

**Problem:** AI search works best with small text chunks, but small chunks lose context.

**Solution:** Index small chunks (400 chars), return their parent context (2000 chars).

```
Search finds: "CAP theorem states..."  (small, precise match)
Returns:      Full paragraph with complete explanation (large, coherent context)
```

### 2. Hybrid Search (Vector + BM25)

**Problem:** Pure AI embeddings miss exact matches like IDs, dates, error codes.

**Solution:** Combine semantic search with keyword search using RRF fusion.

```
Query: "Error 504"
Vector Search: Finds "timeout issues", "server problems"  ← Related but not exact
BM25 Search:   Finds "Error 504: Gateway Timeout"         ← Exact match!
Combined:      Best of both worlds
```

### 3. Two-Stage Retrieval

**Problem:** Retrieving only 5 documents often misses the best answer.

**Solution:** Retrieve 50 candidates → AI reranker picks the best 5.

```
Stage 1: Fast search returns 50 possible matches
Stage 2: Cross-Encoder AI scores each one precisely
Result:  Top 5 with highest actual relevance
```

---

## Quick Start

```bash
# Clone & setup
git clone https://github.com/yourusername/axiom-rag
cd axiom-rag/backend
pip install -r requirements.txt

# Configure (edit .env)
EMBEDDING_PROVIDER=fastembed
LLM_PROVIDER=ollama

# Start Ollama (if using local LLM)
ollama serve

# Run backend
uvicorn api.main:app --port 8001

# Run frontend (in another terminal)
cd frontend
npm install
npm run dev

# Test
curl http://localhost:8001/health
```

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.11+ |
| RAM | 4GB minimum |
| LLM | Ollama (local) or OpenAI API |
| GPU | Not required (CPU optimized) |

---

## Project Structure

```
axiom-rag/
├── backend/
│   ├── rag/
│   │   ├── pipeline.py        # LangGraph workflow (V7)
│   │   ├── nodes.py           # Router, Retrieve, Grade, Generate
│   │   ├── retriever.py       # Hybrid search (Vector + BM25)
│   │   ├── reranker.py        # Cross-Encoder scoring
│   │   ├── intent_router.py   # 3-layer intent classification
│   │   ├── intent_handlers.py # Context-aware response handlers
│   │   └── state.py           # RAGState schema
│   ├── vectorstore/
│   │   └── store.py           # FastEmbed + ChromaDB
│   ├── ingest/
│   │   ├── chunker.py         # Parent-Child chunking
│   │   └── service.py         # Document processing + BM25 indexing
│   └── api/                   # FastAPI endpoints
└── frontend/                  # React UI (Vite + TypeScript)
```

---

## Performance

| Metric | Value |
|--------|-------|
| Embedding Speed | **0.5s** for 100 chunks (was 204s with Ollama) |
| Intent Classification | <20ms (semantic) |
| Search Latency | <100ms |
| Reranking | ~200ms for 50 documents |
| BM25 Index Load | <50ms (lazy load from disk) |
| Hallucination Check | 0.5ms (fast keyword check) |
| Memory Usage | <500MB |
| Greeting Response | <100ms |
| Context Handler Response | 2-5s |
| Full RAG Response | 5-30s |

---

## Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Embeddings | FastEmbed (ONNX) | 440x faster than Ollama, no GPU needed |
| Vector DB | ChromaDB | Simple, local, no Docker required |
| Search | Hybrid (Vector + BM25) | Catches both meaning and exact keywords |
| Chunking | Parent-Child | Small chunks for search, large for context |
| Reranker | Cross-Encoder | Most accurate relevance scoring |
| Intent Classification | 3-Layer Hybrid | Fast path for common cases, LLM for edge cases |
| BM25 Persistence | Pickle + Lazy Load | Survives restarts, self-healing |
| Orchestration | LangGraph | Complex flows with state management |

---

## Roadmap

- [x] Hybrid Search (Vector + BM25)
- [x] Parent-Child Chunking
- [x] Cross-Encoder Reranking
- [x] Hallucination Detection
- [x] Router Agent (query complexity)
- [x] Intent Classification (V5)
- [x] Context-Aware Handlers (followup/simplify/deepen)
- [x] BM25 Index Persistence (V7)
- [x] Invisible Retry Prompts (V7)
- [x] Auto-Create Chat on First Message (V7)
- [ ] Cloud Mode (Gemini) — Optional per-chat
- [ ] Multi-user Support
- [ ] Evaluation Dashboard

---

## Built With

| Category | Technology |
|----------|------------|
| **Language** | Python 3.11 |
| **Framework** | FastAPI, LangGraph |
| **Embeddings** | FastEmbed (BAAI/bge-small-en-v1.5) |
| **Vector Store** | ChromaDB |
| **Reranker** | Cross-Encoder (ms-marco-MiniLM) |
| **Intent Router** | FastEmbed + Hard Rules + LLM Fallback |
| **LLM** | Ollama (local) / OpenAI (optional) |
| **Frontend** | React, TypeScript, Vite, Tailwind |

---

**Axiom RAG** — Accurate answers, not confident guesses.