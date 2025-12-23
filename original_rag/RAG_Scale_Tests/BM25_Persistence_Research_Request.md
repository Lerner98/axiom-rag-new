# BM25 Index Persistence Issue - Research Request

## Context: Axiom RAG System

We have a production-grade RAG (Retrieval-Augmented Generation) system with hybrid search combining:
- **Vector Search** (semantic similarity via FastEmbed + ChromaDB)
- **BM25 Search** (keyword/lexical matching via rank-bm25 library)
- **RRF Fusion** (Reciprocal Rank Fusion to combine results)

---

## The Problem

**BM25 index is stored in-memory and lost on every backend restart.**

| Component | On Restart | Impact |
|-----------|------------|--------|
| Vector embeddings (ChromaDB) | ✅ Persisted to disk | Works |
| BM25 index (in-memory dict) | ❌ LOST | Degrades to vector-only search |

### Current Implementation (from retriever.py)

```python
class HybridRetriever:
    def __init__(self, vector_store, ...):
        # BM25 indices per collection - IN MEMORY ONLY
        self._indices: Dict[str, BM25Index] = {}
    
    def build_bm25_index(self, collection_name: str, documents: List[Document]) -> None:
        """Build BM25 index for a collection."""
        corpus = [self._tokenize(doc.page_content) for doc in documents]
        bm25 = BM25Okapi(corpus)
        self._indices[collection_name] = BM25Index(bm25=bm25, documents=documents)
```

### What Happens After Restart

1. Backend restarts
2. `self._indices = {}` - empty dict
3. Hybrid search attempts BM25 → finds no index
4. Falls back to vector-only search
5. User loses keyword matching benefits (exact terms, IDs, dates, acronyms)
6. System "works" but with degraded quality

### Actual Log Evidence (After Restart)

```
2025-12-13 16:35:30,959 - api.main - INFO - Starting Axiom RAG v2.0.0
2025-12-13 16:35:58,011 - vectorstore.store - INFO - Using ChromaDB vector store with FastEmbed
2025-12-13 16:36:01,332 - vectorstore.store - INFO - Loading FastEmbed model: BAAI/bge-small-en-v1.5
2025-12-13 16:36:01,435 - vectorstore.store - INFO - FastEmbed model loaded: BAAI/bge-small-en-v1.5
2025-12-13 16:36:01,437 - rag.retriever - INFO - HybridRetriever initialized
2025-12-13 16:36:01,437 - rag.pipeline - INFO - HybridRetriever initialized in pipeline
...
2025-12-13 16:36:03,796 - vectorstore.store - INFO - Initialized ChromaDB collection: chat_rag-value-test
2025-12-13 16:36:03,933 - rag.retriever - DEBUG - Vector search returned 20 results
2025-12-13 16:36:03,933 - rag.retriever - DEBUG - No BM25 index for 'chat_rag-value-test', returning empty results
2025-12-13 16:36:03,933 - rag.retriever - DEBUG - BM25 search returned 0 results
2025-12-13 16:36:03,933 - rag.retriever - INFO - Only vector results available (no BM25 index)
2025-12-13 16:36:03,933 - rag.retriever - INFO - Parent expansion: 20 results → 20 unique parents + 0 non-parent docs
```

**This proves:** Vector works (20 results), BM25 is empty (0 results), system falls back to vector-only.

---

## Complete Test Results (RAG Saturday Tests)

### V5 Intent Classification Tests: 7/7 PASSED

| Test | Intent | Result | Time |
|------|--------|--------|------|
| Greeting | greeting | Bypasses RAG | <1s |
| Gratitude | gratitude | Bypasses RAG | <1s |
| Garbage | garbage | Uses LLM fallback | 6.7s |
| Question | question | Full RAG pipeline | ~24s |
| Followup | followup | Uses memory, no new retrieval | Fast |
| Simplify | simplify | Uses memory, no new retrieval | Fast |
| Deepen | deepen | Uses memory, no new retrieval | Fast |

### RAG Value Proposition Tests: 4/4 PASSED

| Test | Description | Result | Evidence |
|------|-------------|--------|----------|
| Test 1: Multi-Document Search | Correct doc retrieval | ✅ PASS | Git question → doc_a_large.pdf, Container security → doc_b_medium.pdf |
| Test 2: Large Document Precision | Retrieval from any page | ✅ PASS | Pages 24-28 (install), 236-240 (stash), 437-482 (packfiles) |
| Test 3: Repeated Query Speed | Consistent performance | ✅ PASS | ~24-25s per query (LLM-bound, not retrieval-bound) |
| Test 4: Index Persistence | Works after restart | ⚠️ PARTIAL | ChromaDB persists ✅, BM25 lost ❌ (known gap) |

### Document Upload Summary

| Document | Chunks | Topic |
|----------|--------|-------|
| doc_a_large.pdf | 2,863 | Pro Git Book (version control) |
| doc_b_medium.pdf | 528 | NIST SP 800-190 Container Security |
| doc_c_small.pdf | 71 | (smaller doc) |

**Total chunks indexed: 3,462**

### Performance Timing Breakdown

| Component | Time | % of Total |
|-----------|------|------------|
| Vector search | ~500ms | 1.8% |
| Cross-encoder rerank | ~600ms | 2.1% |
| LLM Generation | ~10s | 35% |
| LLM Hallucination Check | ~11s | 39% |
| **Total query time** | **~24-25s** | 100% |

**Key insight:** Retrieval is fast (<1.5s total). LLM is the bottleneck (75% of time).

## RAG Value Proposition Tests (4/4)
Multi-Document Search: Correctly isolates sources (container security → doc_b, git → doc_a)
Large Document Precision: Retrieves from any page location (early: 24, middle: 237, late: 437)
Repeated Query Speed: RAG retrieval <1.5s, LLM generation dominates at ~21s total
Index Persistence: ChromaDB persists, BM25 does not (known gap)

---

## Technical Details

### Current Architecture

```
INGESTION:
Document → Chunker → FastEmbed (384 dims) → ChromaDB (persisted)
                  → BM25 Index (in-memory only) ← PROBLEM

QUERY:
Query → Vector Search (ChromaDB) ─┐
     → BM25 Search (in-memory) ───┼→ RRF Fusion → Reranker → LLM
                                  │
                    (empty after restart)
```

### Dependencies

- `rank-bm25==0.2.2` - BM25Okapi implementation
- `chromadb` - Vector store (persists to ./data/chroma)
- `fastembed` - Embeddings (BAAI/bge-small-en-v1.5, 384 dimensions)

### Current BM25Index Structure

```python
@dataclass
class BM25Index:
    bm25: BM25Okapi          # The actual BM25 index
    documents: List[Document] # Original documents for retrieval
    doc_count: int           # Number of documents
```

---

## Potential Solutions to Evaluate

### Option 1: Rebuild BM25 on Startup

**Approach:** On backend startup, load all chunks from ChromaDB and rebuild BM25 index.

**Pros:**
- No additional storage
- Always in sync with ChromaDB

**Cons:**
- Startup delay (3,462 chunks = ? seconds)
- Memory spike on startup

**Questions:**
- How long does BM25Okapi take to index 3,000+ documents?
- Is this acceptable startup latency?

### Option 2: Persist BM25 to Disk

**Approach:** Serialize BM25 index to disk (pickle, JSON, or custom format).

**Pros:**
- Fast startup (just load from disk)
- No rebuild needed

**Cons:**
- Must keep in sync with ChromaDB
- Pickle security concerns?
- Additional storage

**Questions:**
- Can BM25Okapi be pickled directly?
- What's the file size for 3,000+ documents?
- How to handle sync issues (ChromaDB updated but BM25 file stale)?

### Option 3: Use a Persistent BM25 Library

**Approach:** Replace rank-bm25 with a library that supports persistence.

**Potential alternatives:**
- Elasticsearch (overkill?)
- Whoosh (pure Python, has persistence)
- SQLite FTS5 (full-text search)
- tantivy-py (Rust-based, fast)

**Questions:**
- What's the simplest drop-in replacement?
- Performance comparison?
- Integration complexity?

### Option 4: Lazy Rebuild per Collection

**Approach:** Rebuild BM25 index on first query to that collection after restart.

**Pros:**
- No startup delay
- Only rebuilds what's needed

**Cons:**
- First query after restart is slow
- User experiences delay

**Questions:**
- Is this acceptable UX?
- How to indicate "rebuilding index" to user?

---

## The Critical Issue Summary

### BM25 Index NOT Persisted

> "BM25 index: Not persisted (rebuilds on restart, vector-only fallback works)"

**What this means:**

Your hybrid search is Vector + BM25. But:

| Component | On Restart | Impact |
|-----------|------------|--------|
| Vector embeddings (ChromaDB) | ✅ Persisted | Works |
| BM25 index (in-memory) | ❌ LOST | Degrades to vector-only |

**After every backend restart:**
- Hybrid search falls back to vector-only
- You lose BM25 keyword matching benefits (exact terms, IDs, dates, acronyms)
- System still "works" but with reduced quality

### Is This Acceptable?

**For development/testing:** Probably fine - you can re-upload docs or restart triggers rebuild on next upload.

**For production:** NOT acceptable - users expect consistent behavior across restarts.

**Bottom line:** After restart, your RAG works but is **weaker** until you either upload a new document (triggers rebuild) or implement BM25 persistence. Flag this for future fix if you want true production-ready hybrid search.

---

## What We Need From Research

1. **Best practice** for BM25 persistence in production RAG systems
2. **Performance benchmarks** for each option with ~3,500 documents
3. **Recommended solution** balancing:
   - Startup time
   - Query latency
   - Implementation complexity
   - Storage requirements
   - Sync reliability

4. **Code example** for the recommended approach
5. **Migration path** - how to implement without breaking existing functionality

---

## Constraints

- Must remain **local-first** (no cloud dependencies)
- Must work with **existing ChromaDB** storage
- Should be **simple to implement** (solo developer)
- Python 3.11+ environment
- Current stack: FastAPI, LangChain, ChromaDB, rank-bm25

---

## Questions for Research

1. Is pickle safe/recommended for BM25Okapi serialization?
2. What's the rebuild time for BM25Okapi with 3,500 documents?
3. Are there better BM25 libraries with built-in persistence?
4. How do production RAG systems (LangChain, LlamaIndex) handle this?
5. Should we consider SQLite FTS5 as a simpler alternative to rank-bm25?
