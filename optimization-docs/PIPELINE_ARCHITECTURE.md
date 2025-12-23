# RAG Pipeline Architecture

**Version:** V5 (Intent Classification + Context-Aware Handlers)
**Location:** `original_rag/backend/rag/`
**Status:** Production Ready

## Pipeline Flow Diagram

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. CLASSIFY INTENT                                          │
│    IntentRouter (3-layer hybrid)                            │
│    ├── Layer 0: Hard rules (0ms)                            │
│    ├── Layer 1: Semantic similarity with FastEmbed (~20ms)  │
│    └── Layer 2: LLM fallback (only for ambiguous cases)     │
│                                                             │
│    Outputs: detected_intent, intent_confidence              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. NEEDS RAG?                                               │
│    ├── NO (greeting, gratitude, etc.) → handle_non_rag      │
│    └── YES (question) → continue to route_query             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ROUTE QUERY (FAST - No LLM)                              │
│    Pattern matching for complexity classification:          │
│    ├── complex_patterns: ["compare", "contrast", "vs"]      │
│    ├── Multiple questions (? count > 1)                     │
│    └── Default: simple                                      │
│                                                             │
│    Outputs: query_complexity, skip_rewrite                  │
└─────────────────────────────────────────────────────────────┘
    │
    ├── SUMMARIZE → retrieve_sequential (all chunks, ordered)
    ├── SIMPLE → retrieve (skip rewrite)
    └── COMPLEX → rewrite_query → retrieve
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. RETRIEVE                                                 │
│    HybridRetriever:                                         │
│    ├── Vector search (FastEmbed embeddings)                 │
│    ├── BM25 keyword search                                  │
│    └── RRF fusion (Reciprocal Rank Fusion)                  │
│                                                             │
│    Returns: initial_k (50) candidate documents              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. GRADE DOCUMENTS                                          │
│    Two-stage filtering:                                     │
│                                                             │
│    Stage 1: Context Filter (NEW)                            │
│    ├── FastEmbed similarity to query                        │
│    ├── Removes irrelevant docs (threshold: 0.3)             │
│    └── Prevents context bleed                               │
│                                                             │
│    Stage 2: Cross-Encoder Reranker                          │
│    ├── Scores each doc against query                        │
│    └── Returns final_k (5) documents                        │
│                                                             │
│    Outputs: relevant_documents, sources                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. GENERATE                                                 │
│    Ollama LLM (DeepSeek-R1-Distill-Qwen-14B-Q4_K_M)         │
│    ├── System prompt with instructions                      │
│    ├── Retrieved context (5 documents)                      │
│    └── User question                                        │
│                                                             │
│    This is the BOTTLENECK (~25-45 seconds)                  │
│    - Prefill: Processing 3000+ tokens                       │
│    - Generation: ~50 tokens/second on CPU                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. CHECK HALLUCINATION                                      │
│    Hybrid approach:                                         │
│    ├── Fast: Word/trigram overlap check (~100ms)            │
│    │   ├── Score > 0.8 → Grounded (skip LLM)                │
│    │   ├── Score < 0.3 → Not grounded (skip LLM)            │
│    │   └── 0.3-0.8 → Ambiguous (call LLM)                   │
│    └── Slow: LLM verification (only when needed)            │
│                                                             │
│    Outputs: is_grounded, groundedness_score                 │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. SAVE TO MEMORY                                           │
│    Stores conversation in memory_store                      │
│    Key: session_id                                          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Response to User
```

## Component Details

### 1. Intent Router (`intent_router.py`)

```python
class IntentRouter:
    """3-layer hybrid intent classification."""

    # Layer 0: Hard rules (instant)
    HARD_RULES = {
        "greeting": ["hello", "hi", "hey"],
        "gratitude": ["thanks", "thank you"],
    }

    # Layer 1: Semantic matching with FastEmbed
    INTENT_EXEMPLARS = {
        "question": ["what is", "how does", "explain"],
        "followup": ["tell me more", "elaborate"],
    }

    # Layer 2: LLM fallback (only for low confidence)
```

### 2. Route Query (`nodes.py:route_query`)

```python
async def route_query(self, state: RAGState) -> dict:
    """FAST heuristic-only classification (NO LLM)."""
    question = state["question"].lower()

    complex_patterns = ["compare", "contrast", "vs", "difference"]
    is_complex = (
        any(p in question for p in complex_patterns) or
        question.count("?") > 1
    )

    if is_complex:
        return {"query_complexity": "complex", "skip_rewrite": False}
    else:
        return {"query_complexity": "simple", "skip_rewrite": True}
```

### 3. Context Filter (`context_filter.py`)

```python
class ContextFilter:
    """Prevents context bleed by filtering irrelevant documents."""

    def filter(self, documents, query, threshold=0.3):
        embeddings = _get_embeddings()  # FastEmbed
        query_embedding = embeddings.embed([query])

        filtered = []
        for doc in documents:
            doc_embedding = embeddings.embed([doc["content"]])
            similarity = cosine_similarity(query_embedding, doc_embedding)

            if similarity >= threshold:
                filtered.append(doc)

        return FilterResult(documents=filtered, ...)
```

### 4. Hybrid Retriever (`retriever.py`)

```python
class HybridRetriever:
    """Vector + BM25 with RRF fusion."""

    async def retrieve(self, query, collection, k=50):
        # Vector search
        vector_results = await self.vectorstore.similarity_search(query, k)

        # BM25 search
        bm25_results = self.bm25_search(query, k)

        # RRF fusion
        return self.rrf_fusion(vector_results, bm25_results, k)
```

### 5. Hallucination Check (`nodes.py:check_hallucination`)

```python
async def check_hallucination(self, state: RAGState) -> dict:
    """Hybrid: Fast deterministic + LLM fallback."""

    # Fast check first
    score = self._fast_groundedness_check(answer, documents)

    if score > 0.8:
        return {"is_grounded": True, "skip_llm_check": True}
    elif score < 0.3:
        return {"is_grounded": False, "skip_llm_check": True}
    else:
        # Ambiguous - call LLM
        return await self._llm_groundedness_check(answer, documents)
```

## State Schema (`state.py`)

```python
class RAGState(TypedDict):
    # Input
    question: str
    session_id: str
    collection_name: str

    # Intent Classification
    detected_intent: Optional[str]
    intent_confidence: float

    # Router
    query_complexity: Optional[Literal["simple", "complex", "conversational"]]
    skip_rewrite: bool

    # Retrieval
    retrieved_documents: list[Document]  # 50 candidates
    relevant_documents: list[Document]   # 5 final

    # Generation
    answer: Optional[str]
    sources: list[dict]

    # Validation
    is_grounded: bool
    groundedness_score: float

    # Control
    iteration: int
    max_iterations: int

    # Metadata (append reducers)
    errors: Annotated[list[str], add]
    processing_steps: Annotated[list[str], add]
```

## Timing Breakdown

| Stage | Time | Percentage |
|-------|------|------------|
| Intent Classification | ~100ms | <1% |
| Route Query | ~10ms | <1% |
| Retrieval (Vector+BM25) | ~500ms | 2% |
| Context Filter | ~200ms | <1% |
| Reranking | ~300ms | 1% |
| **LLM Generation** | **25-45s** | **95%** |
| Hallucination Check | 100-2000ms | 1-6% |
| Memory Save | ~10ms | <1% |

## API Endpoints

### Chat Stream (Main)
```
POST /chat/{chat_id}/stream
Content-Type: application/json

{
  "message": "What is the CAP theorem?",
  "session_id": "optional-session-id"
}

Response: Server-Sent Events
data: {"type": "token", "content": "The CAP "}
data: {"type": "token", "content": "theorem "}
data: {"type": "sources", "sources": [...]}
data: {"type": "done", "is_grounded": true}
```

### Document Upload
```
POST /chat/{chat_id}/documents
Content-Type: multipart/form-data

files: [file1.pdf, file2.txt]

Response:
{
  "uploaded": [{"id": "...", "name": "...", "chunk_count": 22}],
  "failed": []
}
```

## Collection Naming

```
chat_{chat_id}  →  Documents for this chat
                   e.g., chat_quality-test-1234567890

session_{session_id}  →  Memory/history storage
                         e.g., session_user-abc-123
```

## Configuration (`config/settings.py`)

```python
# Retrieval
retrieval_initial_k = 50    # Candidates from vector search
retrieval_final_k = 5       # Documents sent to LLM
relevance_threshold = 0.3   # Minimum score to include

# LLM
llm_provider = "ollama"
ollama_model = "deepseek-r1:14b"
ollama_base_url = "http://localhost:11434"

# Intent Router
semantic_confidence_threshold = 0.75
```

## Future Optimizations

### 1. LLMLingua Integration (Created, Not Integrated)
```python
# context_compressor.py - reduces 4000 → 1200 tokens
compressor = ContextCompressor(target_ratio=0.3)
compressed = compressor.compress(documents, query)
# Expected: 70% reduction in prefill time
```

### 2. Ollama Prefix Caching
```
Current prompt order:
[User Query] + [Chat History] + [Documents] + [System]

Optimal for caching:
[System] + [Documents] + [User Query]
```

### 3. ColBERTv2 Reranking
Replace cross-encoder with late interaction model for faster reranking.
