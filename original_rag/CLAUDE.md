# CLAUDE.md - RAG Pipeline Configuration

## Current Baseline

| Metric | Value | Status |
|--------|-------|--------|
| Model | llama3.1:8b (4.9GB) | Active |
| VRAM | 6GB | Minimum |
| Pass Rate | 8/8 tests | PASS |
| Latency | ~34s avg | Target: <20s |

## Critical Rules

1. **LLMLingua Compression** - DISABLED for context < 2000 tokens
   - Overhead (14s) exceeds prefill savings at small context
   - Code preserved in `context_compressor.py` for future use

2. **Session Isolation** - ALWAYS use unique `session_id` per query
   - Prevents memory/context bleed between queries
   - Test script generates: `session-{timestamp}-{random}`

3. **Intent Fallback** - If no chat history, force `FOLLOWUP` → `QUESTION`
   - Prevents standalone queries from skipping RAG
   - Implementation: `nodes.py:classify_intent()`

4. **Model Selection** - NEVER use reasoning models (DeepSeek-R1, etc.)
   - `<think>` tags cause 200-350s latency per query
   - Use standard completion models only

## Latency Breakdown

Current 34s average:

| Phase | Time | % |
|-------|------|---|
| Pipeline (intent, retrieval, rerank) | ~2s | 6% |
| LLM Prefill (context processing) | ~25s | 73% |
| LLM Generation (tokens out) | ~7s | 21% |

### Optimization Roadmap

1. **Semantic Caching** - Target: <100ms for similar queries
   - Embed query, check similarity to cached Q&A pairs
   - Bypass LLM for >0.95 similarity matches

2. **Adaptive Context** - Reduce prefill for simple queries
   - Simple: 2-3 docs
   - Complex: 5 docs

3. **Model Routing** - Route simple queries to faster model

## Key Files

| File | Purpose |
|------|---------|
| `rag/nodes.py` | Pipeline nodes, intent fallback |
| `rag/context_compressor.py` | LLMLingua (disabled) |
| `rag/context_filter.py` | Context bleed prevention |
| `rag/intent_router.py` | 3-layer hybrid classification |
| `test-quality.js` | Benchmark with session isolation |

## Pipeline Architecture

```
Query → Intent Classification → [Non-RAG | RAG Path]
                                       ↓
                             Query Routing (simple/complex)
                                       ↓
                             Hybrid Retrieval (Vector + BM25)
                                       ↓
                             Parent Expansion
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
