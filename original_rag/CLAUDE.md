# CLAUDE.md - RAG Pipeline Configuration

## Current Baseline

| Metric | Value | Status |
|--------|-------|--------|
| Model | llama3.1:8b (4.9GB) | Active |
| VRAM | 6GB | Minimum |
| Pass Rate | 8/8 tests | PASS |
| Latency | ~34s avg | Target: <20s |

## Critical Rules

These rules emerged from production bugs and performance issues. Do not bypass without understanding the consequences.

1. **LLMLingua Compression** - DISABLED for context < 2000 tokens
   - Overhead (14s) exceeds prefill savings at small context sizes
   - Re-enable when context regularly exceeds 2000+ tokens
   - Code preserved in `rag/context_compressor.py`

2. **Session Isolation** - ALWAYS use unique `session_id` per query
   - Prevents memory/context bleed between queries
   - Without this, answers from one user session can leak into another
   - Test scripts must generate: `session-{timestamp}-{random}`

3. **Intent Fallback** - Force conversation intents to QUESTION when no history exists
   - Intents like FOLLOWUP, SIMPLIFY, DEEPEN require prior context
   - If no chat history exists, these must fall back to QUESTION
   - Without this fix, standalone queries skip RAG entirely
   - Implementation: `rag/nodes.py:classify_intent()` lines 153-169

4. **Model Selection** - NEVER use reasoning models (DeepSeek-R1, QwQ, etc.)
   - Models with `<think>` tags cause 200-350s latency per query
   - The extended reasoning provides no benefit for RAG retrieval tasks
   - Use standard completion models only (llama3.1, mistral, etc.)

5. **Hallucination Check** - Always verify answers against retrieved context
   - Fast path: deterministic word/trigram overlap check
   - Slow path: LLM verification for ambiguous cases
   - Never skip this step - it's the primary quality gate

## Latency Analysis

Current 34s average breakdown:

| Phase | Time | % | Optimization Target |
|-------|------|---|---------------------|
| Pipeline (intent, retrieval, rerank) | ~2s | 6% | Already optimized |
| LLM Prefill (context processing) | ~25s | 73% | PRIMARY TARGET |
| LLM Generation (tokens out) | ~7s | 21% | Secondary |

The prefill phase (73%) is the dominant bottleneck. All high-impact optimizations target this.

## Optimization Roadmap

### Priority 1: Semantic Caching [HIGH IMPACT] [NOT IMPLEMENTED]

Bypass LLM entirely for repeat/similar queries.

- Embed incoming query using existing FastEmbed
- Compare against cached (query, answer) pairs
- Return cached answer if similarity > 0.95
- Expected impact: <100ms for cache hits vs 34s baseline
- Infrastructure exists: FastEmbed already loaded for intent router

Implementation approach:
```
1. Add query cache table (session_id, query_embedding, answer, timestamp)
2. Before RAG pipeline, check cache similarity
3. Cache hit → return immediately
4. Cache miss → run pipeline, cache result
```

### Priority 2: Adaptive Context Size [MEDIUM IMPACT] [NOT IMPLEMENTED]

Reduce prefill by retrieving fewer documents for simple queries.

- Simple queries (single concept, short): 2-3 docs
- Complex queries (multi-part, comparative): 5 docs
- Query complexity already classified by intent router
- Expected impact: 30-40% prefill reduction for simple queries

Implementation approach:
```
1. Add complexity scoring to route_query node
2. Map complexity → retrieval count (low=2, medium=3, high=5)
3. Pass count to retriever
```

### Priority 3: LLMLingua for Large Context [MEDIUM IMPACT] [DISABLED]

Re-enable compression when context exceeds threshold.

- Currently disabled due to 14s overhead
- Break-even point: ~2000 tokens
- Code ready in `rag/context_compressor.py`
- Enable conditionally: `if token_count > 2000: compress()`

## Key Files

| File | Purpose |
|------|---------|
| `rag/nodes.py` | Pipeline nodes, intent fallback fix (line 153-169) |
| `rag/context_compressor.py` | LLMLingua (disabled, ready for large context) |
| `rag/context_filter.py` | Context bleed prevention |
| `rag/intent_router.py` | 3-layer hybrid classification (hard rules → semantic → LLM) |
| `rag/hallucination.py` | Answer verification against context |
| `test-quality.js` | Benchmark with session isolation |

## Pipeline Architecture

```
Query → Intent Classification → [Non-RAG | RAG Path]
                                       ↓
                             Query Routing (simple/complex)
                                       ↓
                             Hybrid Retrieval (Vector + BM25 + RRF)
                                       ↓
                             Parent Expansion (400 → 2000 char)
                                       ↓
                             Cross-Encoder Reranking
                                       ↓
                             LLM Generation
                                       ↓
                             Hallucination Check
                                       ↓
                             Response + Citations
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | ollama | LLM backend |
| `OLLAMA_MODEL` | llama3.1:8b | Generation model |
| `EMBEDDING_PROVIDER` | fastembed | Embedding backend |
| `VECTOR_PROVIDER` | chroma | Vector store |
| `MEMORY_BACKEND` | sqlite | Session storage |
