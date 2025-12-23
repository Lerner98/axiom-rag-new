# Gemini's Optimization Recommendations

**Source:** Chat with Gemini during optimization session
**Date:** 2025-12-23

## Summary of Recommendations

### 1. Architectural Optimizations

#### 1.1 Speculative RAG (Drafting)
- Use tiny model (Phi-3 or distilled Llama) to generate "draft" in parallel with retrieval
- Use larger model only to verify/refine the draft
- Reduces "Time to First Token" (TTFT)

#### 1.2 Prompt Compression (LLMLingua)
- If parent expansion returns large chunks, LLM spends time processing input tokens
- LLMLingua strips away non-essential tokens before they hit the LLM
- Can compress context by 3x to 5x with zero loss in accuracy

**Important:** Use Question-Aware Compression (LongLLMLingua)
- Don't just compress based on perplexity
- Look at Question + Document together
- Only delete parts irrelevant to the specific query

#### 1.3 Request Hedging & Parallelism
- Current logic is linear: Retrieve -> Grade -> Generate
- Trigger generate speculatively with top 1 document while reranker grades others
- Often the first result is sufficient

### 2. Retrieval & Database Performance

#### 2.1 Asynchronous Retrieval
- Ensure Vector Search and BM25 run in parallel using `asyncio.gather`

#### 2.2 Small-to-Big Retrieval
- Instead of parent expansion (which adds DB lookups)
- Store "child" chunks with a summary of the parent
- Retrieve context in a single query rather than two-step lookup

#### 2.3 ColBERTv2 / Late Interaction
- Standard vectors lose nuance of specific keywords
- ColBERT calculates similarity between every word in query and document
- Replaces Reranker step entirely
- As accurate as LLM reranker but runs in milliseconds

### 3. Deployment-Level Optimizations (Ollama)

| Strategy | Impact | Effort |
|----------|--------|--------|
| KV Caching | High | Low (Enable in Ollama) |
| Model Quantization | High | Low (Switch to Q4_K_M or Q3_K_S) |
| vLLM / TGI | Very High | Medium (Replace Ollama) |

**Note:** Ollama is great for dev, but for production RAG, vLLM allows Continuous Batching.

### 4. Query Transformations

#### Query Decomposition
Instead of just "rewriting", use Query Decomposition:

Example: "Compare the performance of SGOV vs SHY over the last year"

Split into parallel sub-queries:
1. "SGOV performance last 12 months"
2. "SHY performance last 12 months"

Run both searches in parallel (`asyncio.gather`), then merge results.

### 5. Engineering Tier List (2025)

| Feature | Current System | Elite Level |
|---------|----------------|-------------|
| Routing | Heuristic (Regex) | Semantic Router (Vector) |
| Context | Full Parent Chunks | Compressed (LLMLingua) |
| Search | Hybrid (Vector+BM25) | Late Interaction (ColBERTv2) |
| Inference | Sequential | Speculative Decoding |
| Caching | Session Memory | Semantic Cache (Redis/GPTCache) |

### 6. Context Bleed Fix

When clearing history fixes quality but hurts latency:

**Implement Query-Context Filtering:**
1. Before sending retrieved documents to LLM
2. Run quick similarity check: "Does this document mention keywords in current query?"
3. If history contains "CAP Theorem" but query is "NoSQL", discard CAP docs from prompt

### 7. The 64s Latency Problem

When complex queries take 60+ seconds:
- The retrieved context is too large
- Ollama prefill phase is the bottleneck
- Solution: LLMLingua to shrink context before it hits generate

### 8. Semantic Caching

If two users ask "How do I reset my password?":
- Use Semantic Cache (GPTCache or Redis)
- Store previous answers
- Use vector search to see if new question is "95% similar" to old one
- Return cached answer in <10ms without calling Ollama

## Priority Implementation Order

1. **LLMLingua** - Biggest latency impact
2. **Context Filter** - Prevents quality issues
3. **Semantic Cache** - Prevents redundant LLM calls
4. **ColBERTv2** - Improves retrieval accuracy
5. **Speculative Decoding** - Requires 2 models

## Key Insight

> "If you naively compress or filter data to save time, you risk throwing away the 'needle in the haystack'—that one specific sentence that answers the question."

**Solution:** Use Question-Aware Compression, not naive compression.
