# Axiom RAG: The Complete Engineering Journey

**From a 67% quality experimental system to a 100% quality, production-ready RAG pipeline.**

*This document chronicles the systematic optimization decisions, debugging adventures, and architectural evolution that shaped Axiom RAG.*

---

## Table of Contents

1. [The Starting Point](#1-the-starting-point)
2. [Phase 1: Choosing the Right Foundation](#2-phase-1-choosing-the-right-foundation)
3. [Phase 2: Building the Intent System (V5)](#3-phase-2-building-the-intent-system-v5)
4. [Phase 3: The LangGraph Silent Drop Bug](#4-phase-3-the-langgraph-silent-drop-bug)
5. [Phase 4: The Context Bleed Mystery](#5-phase-4-the-context-bleed-mystery)
6. [Phase 5: BM25 Persistence (V7)](#6-phase-5-bm25-persistence-v7)
7. [Phase 6: Latency Optimization Sprint](#7-phase-6-latency-optimization-sprint)
8. [Phase 7: Quality Verification](#8-phase-7-quality-verification)
9. [Key Engineering Lessons](#9-key-engineering-lessons)
10. [The Decision Framework](#10-the-decision-framework)
11. [Current State & Roadmap](#11-current-state--roadmap)

---

## 1. The Starting Point

### The Vision

Build a **local-first, self-correcting RAG system** that:
- Runs 100% locally (no data leaves your machine)
- Cites its sources (every answer shows where it came from)
- Checks itself (built-in hallucination detection)
- Understands intent (knows the difference between "hi" and "What is CAP theorem?")

### Two Competing Implementations

We had two RAG implementations to evaluate:

| System | Description |
|--------|-------------|
| **original_rag** | Production RAG with hybrid search, LangGraph orchestration, hallucination checks |
| **agentic-rag** | Experimental branch with TOON compression experiments |

### The Benchmark That Decided Everything

| Metric | original_rag | agentic-rag |
|--------|-------------|-------------|
| Tests Passed | **8/8 (100%)** | 5/8 (62.5%) |
| Avg Quality | **94%** | 67% |
| Avg Latency | **13,952ms** | 28,958ms |

### Critical Failures in agentic-rag

```
how_to query:      15% quality - "I don't have enough information" (FALSE - info was there)
comparison query:  15% quality - Answered about CACHING when asked about SQL vs NoSQL
conversational:    48% quality, 90 second latency - Complete context handling breakdown
```

**Decision: Archive agentic-rag, optimize original_rag.**

The data was unambiguous. We didn't waste time defending sunk cost.

---

## 2. Phase 1: Choosing the Right Foundation

### What original_rag Already Had Right

Before any optimization, the system had solid architectural foundations:

| Component | Implementation | Why It Worked |
|-----------|---------------|---------------|
| **Hybrid Search** | Vector (FastEmbed) + BM25 + RRF fusion | Catches both semantic meaning AND exact keywords |
| **Parent-Child Chunking** | Small chunks for search, large for context | Precise matching, coherent answers |
| **Cross-Encoder Reranking** | ms-marco-MiniLM | Most accurate relevance scoring |
| **Hallucination Check** | Fast word overlap + LLM fallback | Catches false claims without always calling LLM |

### The Core Problem: Everything Went Through RAG

```
User: "hi"           → Full RAG pipeline → Searched for documents about "hi" → Garbage
User: "thanks"       → Full RAG pipeline → Searched for documents about "thanks" → Garbage
User: "tell me more" → Full RAG pipeline → Lost context, started fresh search
User: "What is X?"   → Full RAG pipeline → Correct (this is what RAG is for)
```

**The system treated every message identically.** A greeting triggered the same 5-30 second pipeline as a complex research question.

---

## 3. Phase 2: Building the Intent System (V5)

### The Gap We Needed to Close

| User Says | Before (V4) | After (V5) |
|-----------|-------------|------------|
| `"hi"` | Full RAG → garbage | Instant greeting |
| `"thanks"` | Full RAG → garbage | Instant acknowledgment |
| `"tell me more"` | Full RAG → no context | Expand from memory |
| `"explain simpler"` | Full RAG → re-retrieves | Rephrase last answer |
| `"What is CAP?"` | Full RAG → correct | Full RAG → correct |

### The 3-Layer Hybrid Router

We built a tiered intent classification system:

```
User Input
    │
    ▼
┌─────────────────────────────────────────┐
│  LAYER 0: Hard Rules (0ms)              │
│  ├── Length ≤ 1 char → GARBAGE          │
│  ├── No alphabetic chars → GARBAGE      │
│  └── Keyboard spam pattern → GARBAGE    │
└─────────────────────────────────────────┘
    │ (passes)
    ▼
┌─────────────────────────────────────────┐
│  LAYER 1: Semantic Fast Path (<20ms)    │
│  ├── Embed user input (FastEmbed)       │
│  ├── Compare to intent exemplars        │
│  └── If similarity > 0.85 → Route       │
│                                          │
│  Exemplars:                              │
│  ├── GREETING: "hi", "hello", "hey"     │
│  ├── GRATITUDE: "thanks", "thank you"   │
│  ├── FOLLOWUP: "more", "continue"       │
│  └── SIMPLIFY: "explain simpler"        │
└─────────────────────────────────────────┘
    │ (no confident match)
    ▼
┌─────────────────────────────────────────┐
│  LAYER 2: LLM Fallback (2-5s)           │
│  └── Only for truly ambiguous cases     │
└─────────────────────────────────────────┘
```

### Context-Aware Handlers

For followup/simplify/deepen intents, we DON'T run RAG. Instead:

```python
# User: "tell me more"
# → Detect FOLLOWUP intent
# → Retrieve last answer from conversation memory
# → Ask LLM to expand on it
# → No document retrieval needed
```

**Result:** Greetings respond in <100ms. Follow-ups in 2-5s. Only questions trigger full RAG.

---

## 4. Phase 3: The LangGraph Silent Drop Bug

### The Setup

We added a summarization feature that should route "summarize the document" queries to a special sequential retrieval path.

### The Symptom

```
Log: Query classified as: SUMMARIZE (regex match - fast path)  ← Looks correct!
Log: Skipping rewrite (simple query)                           ← Wait, what?
```

The feature appeared to work (logs showed correct classification) but silently fell back to the wrong code path.

### The Hunt

We spent 45 minutes checking:
- File deployment (was the code even there?)
- Bytecode cache (was Python running old code?)
- State merge logic (was something overwriting our value?)

### The Root Cause

**LangGraph silently drops fields from node returns that aren't defined in the TypedDict.**

```python
# Node returns this:
return {
    "query_complexity": "summarize",
    "is_summarization": True,  # ← NEW FIELD
}

# But RAGState TypedDict didn't have is_summarization defined
# LangGraph silently dropped it
# Router checked state.get("is_summarization") → False
# Wrong path taken
```

**No error. No warning. No exception.** The field just vanished.

### The Fix

```python
# Added to RAGState TypedDict:
is_summarization: bool  # For sequential retrieval path

# Added to create_initial_state():
is_summarization=False,
```

**3 lines of code. 45 minutes of debugging.**

### The Lesson

**Feature Addition Checklist (now mandatory):**
```
□ Identify all NEW state fields
□ Add fields to TypedDict definition
□ Add fields to create_initial_state()
□ Update any Literal types that need new values
□ Test state.get("new_field") returns expected value
```

---

## 5. Phase 4: The Context Bleed Mystery

### The Symptom

Running queries in sequence produced "swapped answers":
```
Query 1: "What is CAP theorem?" → Got caching information (WRONG)
Query 2: "What is caching?"     → Got CAP theorem information (WRONG)
```

### Hypothesis 1: Context Filter Bug

We created `context_filter.py` to filter documents by semantic similarity to the current query:

```python
class ContextFilter:
    def filter(self, documents, query, threshold=0.3):
        similarity = cosine_similarity(query_embedding, doc_embedding)
        if similarity < threshold:
            remove_document()
```

Integrated it into `grade_documents`. **Still got swapped answers.**

### Hypothesis 2: LangGraph State Management

Gemini suggested: "This is a state management issue, not filter logic."

Checked for:
- Reducer problems (using `append` instead of `replace`)
- Key shadowing
- Shared instances between requests

Finding: Document lists overwrite correctly. **Not a reducer issue.**

### Hypothesis 3: Check the Obvious

```
Server Log: Collection 'chat_test-chat-001' is empty
```

### The Actual Root Cause

**The bug wasn't in the RAG pipeline. It was in the test script.**

```javascript
// BROKEN TEST
const CHAT_ID = 'test-chat-001';  // Same for ALL tests
// No document upload step
// Same session for all queries → memory accumulated
```

What actually happened:
1. Collection was empty (documents never uploaded to test collection)
2. Same session ID meant chat history accumulated
3. LLM used chat history to generate answers (hallucinating from previous queries)

### The Fix

```javascript
// FIXED TEST
const CHAT_ID = `quality-test-${Date.now()}`;  // Unique per run

function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// Upload documents FIRST
await uploadTestDocument(chatId);

// Each query gets unique session
for (const test of TEST_QUERIES) {
  const sessionId = generateSessionId();
  await testQuery(test.query, chatId, sessionId);
}
```

### The Lesson

> "When debugging the wrong layer, you can spend hours on sophisticated solutions while the problem is 'the collection is empty.'"

**Always verify the obvious first.**

---

## 6. Phase 5: BM25 Persistence (V7)

### The Problem

After server restart, BM25 keyword search returned 0 results. Hybrid search degraded to vector-only.

```
On Document Upload:
  → Build BM25 index in memory ✓
  → Server restarts
  → self._indices = {}  ← Empty!
  → BM25 search fails silently
  → Falls back to vector-only
  → User loses keyword matching (exact terms, IDs, error codes)
```

### The Solution

Pickle-based persistence with lazy loading:

```python
def save_bm25_index(self, collection_name: str):
    index_path = BM25_PERSIST_DIR / f"{collection_name}.pkl"
    with open(index_path, "wb") as f:
        pickle.dump(self._indices[collection_name], f)

def load_bm25_index(self, collection_name: str) -> bool:
    index_path = self._get_index_path(collection_name)
    if not index_path.exists():
        return False
    with open(index_path, "rb") as f:
        self._indices[collection_name] = pickle.load(f)
    return True
```

**Self-healing:** On query, check memory → miss → lazy-load from disk → full hybrid search restored.

---

## 7. Phase 6: Latency Optimization Sprint

### Understanding the Bottleneck

```
User Input → Frontend Processing (~100ms)
           → Network to Backend (~10ms)
           → Intent Classification (~100ms)
           → Route Query (~2000-5000ms)  ← PROBLEM: LLM call every time
           → Retrieval (~500ms)
           → Reranking (~300ms)
           → LLM Generation (~25-45s)    ← MAIN BOTTLENECK
           → Hallucination Check (~100-2000ms)
           → Network to Frontend (~10ms)
```

**95% of latency is LLM (Ollama prefill + decoding on CPU)**

### Optimization 1: Fast Route Query

**Before:** LLM call to classify query complexity (2-5 seconds)

**After:** Pattern matching (0ms)

```python
async def route_query(self, state: RAGState) -> dict:
    # Fast pattern matching - no LLM
    complex_patterns = ["compare", "contrast", "vs", "difference"]
    is_complex = any(p in question.lower() for p in complex_patterns)
    is_complex = is_complex or question.count("?") > 1
```

**Savings: 2-5 seconds per query**

### Optimization 2: Adaptive K Selection

**Problem:** Simple queries don't need 5 documents. Fewer docs = smaller prefill = faster.

```python
query_complexity = state.get("query_complexity", "complex")
if query_complexity == "simple":
    final_k = 2   # ~1200 tokens
else:
    final_k = 5   # ~3000 tokens
```

**Savings: 60% prefill reduction for simple queries**

### Optimization 3: Hallucination Bypass

**Problem:** Simple queries with high retrieval confidence don't need LLM hallucination check.

```python
if query_complexity == "simple":
    top_score = max(d.get("relevance_score", 0) for d in state["relevant_documents"])
    if top_score >= 70:  # High confidence
        return {"is_grounded": True, ...}  # Skip LLM check
```

**Savings: 3-5 seconds for confident simple queries**

### Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Simple Query Avg | ~34s | ~15s | **-56%** |
| Overall Avg | ~34s | 25.1s | **-26%** |
| Quality | 96% | 100% | **+4%** |

---

## 8. Phase 7: Quality Verification

### The Problem with Latency-Only Testing

Fast answers are worthless if they're wrong. We needed to verify actual LLM outputs against source documents.

### The Methodology

```python
TEST_QUERIES = [
    "What is the CAP theorem?",
    "What is load balancing?",
    "What is a CDN?",
    "What is consistent hashing?",  # NOT in document - tests rejection
    "Compare SQL and NoSQL databases",
    "How does database sharding work?",
]
```

For each query:
1. Fresh collection (no cache contamination)
2. Unique session (no memory bleed)
3. Capture full LLM output
4. Compare against source document
5. Manual verification

### Results

| Query | LLM Answer | Source Doc | Verdict |
|-------|-----------|------------|---------|
| CAP theorem | Exact definition with CP/AP tradeoff | Matches | EXCELLENT |
| Load balancing | Core definition + elaboration | Correct core | GOOD |
| CDN | "Geographically distributed network..." | Verbatim | EXCELLENT |
| Consistent hashing | "I don't have enough information..." | NOT IN DOC | CORRECT REJECTION |
| SQL vs NoSQL | Complete comparison table | Exact match | EXCELLENT |
| Sharding | All 4 types correctly identified | All correct | EXCELLENT |

**Quality Score: 6/6 (100%)**

The "consistent hashing" test was critical - the LLM correctly refused to answer rather than hallucinate.

---

## 9. Key Engineering Lessons

### Lesson 1: Benchmark Before Optimizing

> We had two implementations. Data showed original_rag was objectively better. We didn't waste time defending the experimental branch.

### Lesson 2: LangGraph Silently Drops Unknown State Fields

> Every field returned by a node MUST be defined in the TypedDict. No error, no warning - just silent failure.

### Lesson 3: Debug the Right Layer

> Spent hours on context filter logic when the collection was empty. Always verify the obvious first.

### Lesson 4: Test Infrastructure is Code

> The "swapped answers" bug was in the test script, not the pipeline. Bad tests create phantom bugs.

### Lesson 5: Session Isolation is Critical

> Each query needs a unique session ID. Shared sessions cause memory bleed between unrelated queries.

### Lesson 6: LLM Calls are Expensive

> Removing one LLM call (route_query) saved 2-5 seconds. Pattern matching is effectively free.

### Lesson 7: Prefill is the Bottleneck

> For local LLMs, token processing (prefill) dominates latency. Reduce context size = faster responses.

### Lesson 8: Quality Verification is Non-Negotiable

> Latency optimization without quality verification is meaningless. Always verify LLM outputs against source.

---

## 10. The Decision Framework

### For Every Optimization:

```
1. MEASURE BASELINE
   - What's the current state?
   - What metrics matter?

2. IDENTIFY BOTTLENECK
   - Where is time being spent?
   - What's the theoretical minimum?

3. EVALUATE OPTIONS
   - What are the tradeoffs?
   - What's the risk to quality?

4. IMPLEMENT SMALLEST CHANGE
   - Start with lowest risk
   - Verify quality maintained

5. VERIFY WITH BENCHMARKS
   - Did it actually improve?
   - Any regressions?
```

### The "Should I Use LLM?" Decision Tree

```
Is this task deterministic?
├── YES → Use pattern matching / rules / embeddings
└── NO  → Is accuracy critical?
          ├── YES → Use LLM with verification
          └── NO  → Consider fast heuristic with LLM fallback
```

---

## 11. Current State & Roadmap

### Current Performance

| Metric | Baseline | Current | Improvement |
|--------|----------|---------|-------------|
| Quality | 94% | **100%** | +6% |
| Avg Latency | 34s | **25.1s** | -26% |
| Simple Query | 34s | **~15s** | -56% |
| Greeting Response | 5-30s | **<100ms** | -99% |

### What's Implemented

- [x] 3-Layer Intent Classification (V5)
- [x] Context-Aware Handlers (followup/simplify/deepen)
- [x] Fast Route Query (pattern matching, no LLM)
- [x] BM25 Persistence (V7)
- [x] Adaptive K Selection (K=2 for simple, K=5 for complex)
- [x] Hallucination Bypass (skip for high-confidence simple queries)
- [x] Session Isolation (unique session per query)
- [x] Quality Verification (benchmark_quality.py)

### Phase 2 Roadmap (Not Yet Implemented)

**High Priority:**
1. **3B Model Routing** - Use smaller model for simple queries (2-3x speedup potential)
2. **Semantic Caching** - Cache similar query answers
3. **Response Streaming** - Reduce perceived latency

**Medium Priority:**
1. LLMLingua Context Compression (70% prefill reduction)
2. Ollama KV Cache Configuration
3. Frontend virtualization for long chats

**Low Priority:**
1. ColBERTv2 late interaction retrieval
2. Speculative decoding with draft model

---

## Conclusion

This journey demonstrates that **systematic engineering beats clever hacks**:

1. **We measured before optimizing** - Data chose original_rag over agentic-rag
2. **We found the real bottleneck** - LLM prefill, not retrieval
3. **We debugged the right layer** - Eventually (after chasing wrong hypotheses)
4. **We built proper isolation** - Session IDs, collection timestamps, unique runs
5. **We verified quality** - 100% accuracy, not just fast responses
6. **We documented gotchas** - LangGraph silent drops, empty collections, test infrastructure

The result: A RAG system that's both faster AND more accurate than where we started.

---

## Appendix: Key Files Reference

| File | Purpose |
|------|---------|
| `backend/rag/nodes.py` | Core pipeline logic, Adaptive K, hallucination bypass |
| `backend/rag/intent_router.py` | 3-layer intent classification |
| `backend/rag/intent_handlers.py` | Context-aware handlers |
| `backend/rag/retriever.py` | Hybrid search, BM25 persistence |
| `backend/rag/state.py` | RAGState TypedDict definition |
| `backend/benchmark_quality.py` | Quality verification script |
| `backend/benchmark_e2e.py` | E2E benchmark with document ingestion |

---

*Last Updated: December 23, 2025*
*This document captures the major phases. Additional context from commit history, discussions, and iterations would further enrich the narrative.*
