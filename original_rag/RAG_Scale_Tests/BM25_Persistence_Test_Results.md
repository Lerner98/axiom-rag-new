# BM25 Persistence Test Results

**Date:** 13-12-2025
**Branch:** `feature/bm25-persistence`
**Status:** PASSED

---

## Test Objective

Verify that BM25 index survives backend restarts (V3.1 fix for known gap from RAG Saturday tests).

---

## Test Steps

### Step 1: Start Backend with New retriever.py (V3.1)

```bash
cd backend && python -m uvicorn api.main:app --port 8001 --host 0.0.0.0
```

Health check:
```json
{"status":"healthy","version":"2.0.0","services":{"api":true,"vector_store":true,"llm":true,"memory":true}}
```

### Step 2: Upload Test Document

```bash
curl -s -X POST "http://localhost:8001/chat/bm25-persist-test/documents" \
  -F "files=@RAG_Scale_Tests/doc_c_small.pdf"
```

Response:
```json
{"uploaded":[{"id":"7519bc57-d14b-4ce3-867a-c88e87999c3f","name":"doc_c_small.pdf","chunk_count":71}],"failed":[]}
```

### Step 3: Verify BM25 Index Saved to Disk

```bash
ls -la backend/data/bm25_indices/
```

Output:
```
-rw-r--r-- 1 guyle 197609 119225 Dec 13 20:08 chat_bm25-persist-test.pkl
```

**PROOF:** BM25 index persisted to `chat_bm25-persist-test.pkl` (119KB for 71 chunks)

### Step 4: Query Before Restart

```bash
curl -s -X POST "http://localhost:8001/chat/" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this document about?", "session_id": "bm25-persist-test", "collection_name": "chat_bm25-persist-test"}'
```

Response:
```
Answer: Based on the provided context, I can answer your question.
This document appears to be a collection of sources related to Bitcoin and digital currency...
Sources: 5
```

### Step 5: Restart Backend

Killed backend process and restarted:
```bash
python -m uvicorn api.main:app --port 8001 --host 0.0.0.0
```

Startup logs:
```
2025-12-13 20:09:56,813 - api.main - INFO - Starting Axiom RAG v2.0.0
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

### Step 6: Query AFTER Restart

```bash
curl -s -X POST "http://localhost:8001/chat/" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Bitcoin?", "session_id": "bm25-persist-test", "collection_name": "chat_bm25-persist-test"}'
```

Response:
```
Answer: Based on the provided context, I can answer your question.
This document is about the development of a peer-to-peer electronic cash system, specifically Bitcoin. It proposes a solution to the double-spending problem using a proof-of-work mechanism and timestamps transactions by hashing them into an ongoing chain...
Sources: 5
Grounded: None
```

---

## Log Evidence (Critical Lines)

### BM25 Loaded from Disk:
```
2025-12-13 20:11:09,297 - rag.retriever - INFO - Loaded BM25 index for 'chat_bm25-persist-test' from disk (71 docs)
```

### Hybrid Search Working:
```
2025-12-13 20:11:09,296 - rag.retriever - DEBUG - Vector search returned 20 results
2025-12-13 20:11:09,297 - rag.retriever - DEBUG - BM25 search returned 20 results
2025-12-13 20:11:09,297 - rag.retriever - INFO - RRF fusion returned 32 results
2025-12-13 20:11:09,297 - rag.retriever - INFO - Parent expansion: 32 results → 13 unique parents + 0 non-parent docs
```

---

## Test Summary

| Step | Before (V3) | After (V3.1) |
|------|-------------|--------------|
| Upload doc | BM25 in memory only | BM25 saved to `chat_bm25-persist-test.pkl` |
| Query before restart | Works (BM25 in memory) | Works (BM25 in memory) |
| Restart backend | BM25 LOST | BM25 on disk |
| Query after restart | "No BM25 index" → 0 results | "Loaded BM25 index from disk (71 docs)" → 20 results |
| RRF Fusion | Vector-only fallback | Full hybrid (32 fused results) |

**The BM25 persistence fix is working.** The known gap from RAG Saturday testing is now closed.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/rag/retriever.py` | V3.1 with persistence methods |

### New Methods Added:
- `_get_index_path(collection_name)` - Get pickle file path
- `_save_bm25_index(collection_name)` - Save to disk
- `_load_bm25_index(collection_name)` - Load from disk (lazy)
- `_delete_bm25_index_file(collection_name)` - Delete pickle file

### Modified Methods:
- `build_bm25_index()` - Auto-saves after build
- `add_to_bm25_index()` - Loads from disk before adding
- `remove_from_bm25_index()` - Loads from disk before removing
- `clear_bm25_index()` - Also deletes disk file
- `has_bm25_index()` - Checks disk too
- `get_bm25_doc_count()` - Loads from disk before counting
- `_bm25_search()` - Lazy loads from disk (self-healing)

---

## Persistence Directory

```
backend/data/bm25_indices/
└── chat_bm25-persist-test.pkl  (119KB for 71 chunks)
```

Index file naming: `{collection_name}.pkl` with `/` and `\` sanitized to `_`
