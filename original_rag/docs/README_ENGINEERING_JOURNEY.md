# Production-Grade RAG Pipeline: Quality & Performance Optimization

A high-performance Retrieval-Augmented Generation (RAG) system built with **FastAPI**, **LangGraph**, and **Ollama**. This project documents a rigorous engineering journey from a baseline prototype to an optimized pipeline achieving **94% answer quality** and **100% test reliability**.

## Performance at a Glance

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| **Accuracy** | ≥80% | **94%** | PASS |
| **Reliability** | 8/8 tests | **8/8 (100%)** | PASS |
| **Min Quality** | ≥70% | **85%** | PASS |

### Query Type Performance
| Query Type | Quality | Latency |
|------------|---------|---------|
| Simple Factual | 100% | 12.3s |
| How-To | 100% | 13.0s |
| Comparison | 100% | 50.0s |
| Conversational | 100% | 28.6s |
| Short Query | 90% | 42.4s |
| Complex Multi-part | 90% | 50.6s |
| Vague Query | 85% | 40.2s |
| Out-of-Domain | 85% | 10.7s |

## System Architecture

The pipeline uses a modular, agentic workflow managed by **LangGraph** to ensure precise control over each stage of the RAG lifecycle.

### 1. Intent Classification (3-Layer Hybrid)
- **Layer 0:** Regex-based hard rules for instant responses (0ms)
- **Layer 1:** Semantic matching with FastEmbed for intent categorization (~20ms)
- **Layer 2:** LLM fallback only for high-ambiguity cases

### 2. Intelligent Retrieval & Filtering
- **Hybrid Search:** Combines Vector search (dense) and BM25 (sparse) with RRF Fusion
- **Context Filter:** Custom-built similarity gate that removes irrelevant documents before generation, saving tokens and preventing hallucinations

### 3. Generation & Validation
- **LLM:** DeepSeek-R1-Distill-Qwen-14B (running locally via Ollama)
- **Hallucination Check:** Hybrid deterministic + LLM validator ensures every answer is grounded in retrieved sources

### Latency Breakdown
```
Total: ~31 seconds average
├── Intent Classification: ~100ms
├── Route Query: ~10ms (was 2-5s with LLM)
├── Retrieval: ~500ms
├── Context Filter: ~200ms
├── Reranking: ~300ms
├── LLM Generation: ~25-45s ← 95% of latency
└── Hallucination Check: ~100-2000ms
```

## The Optimization Journey

This project was defined by iterative, data-backed improvements documented in this directory.

### Key Engineering Wins

#### 1. The "Context Bleed" Fix
Resolved a critical bug where chat history from previous queries contaminated new answers. The solution involved implementing strict session isolation and per-query document filtering.

**See:** [DEBUGGING_CONTEXT_BLEED.md](DEBUGGING_CONTEXT_BLEED.md)

#### 2. Fast-Path Routing
Replaced a 5-second LLM classification step with a heuristic pattern-matcher, reducing TTI (Time to Interactive) for simple queries.

#### 3. Testing Infrastructure
Developed a custom `test-quality.js` suite that automatically validates the pipeline across 8 distinct query categories (Factual, Comparison, Out-of-Domain, etc.).

### Comparison: Before vs After
| Metric | agentic-rag (before) | original_rag (after) | Change |
|--------|---------------------|---------------------|--------|
| Tests Passed | 5/8 (62.5%) | **8/8 (100%)** | +37.5% |
| Quality | 67% | **94%** | +27% |
| Latency | 29s | 31s | Similar |

**Decision:** Chose `original_rag` for superior quality with maintained latency.

## Documentation Index

### Core Documentation
| File | Description |
|------|-------------|
| [README.md](README.md) | This file - overview and index |
| [OPTIMIZATION_JOURNEY.md](OPTIMIZATION_JOURNEY.md) | Full optimization process (Phases 1-6) |
| [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md) | Current pipeline flow and components |

### Debugging & Analysis
| File | Description |
|------|-------------|
| [DEBUGGING_CONTEXT_BLEED.md](DEBUGGING_CONTEXT_BLEED.md) | How we found and fixed the "swapped answers" bug |
| [FRONTEND_ANALYSIS.md](FRONTEND_ANALYSIS.md) | Frontend performance audit |
| [GEMINI_RECOMMENDATIONS.md](GEMINI_RECOMMENDATIONS.md) | Advanced optimization ideas |

### Results & Benchmarks
| File | Description |
|------|-------------|
| [FINAL_BENCHMARK_RESULTS.md](FINAL_BENCHMARK_RESULTS.md) | Complete E2E benchmark data |
| [RAG_COMPARISON_RESULTS.md](RAG_COMPARISON_RESULTS.md) | original_rag vs agentic-rag comparison |
| [OPTIMIZATION_RESULTS.md](OPTIMIZATION_RESULTS.md) | Early optimization results |

## Files Modified

### Backend (`original_rag/backend/rag/`)
| File | Change |
|------|--------|
| `nodes.py` | Fast route_query + context filter integration |
| `context_filter.py` | NEW - Prevents context bleed |
| `context_compressor.py` | NEW - LLMLingua (prepared, not integrated) |

### Test Infrastructure
| File | Change |
|------|--------|
| `test-quality.js` | Fixed session isolation, proper document uploads |

## Future Roadmap

### High Impact
1. **Context Compression:** Integrate `context_compressor.py` (LLMLingua) to reduce context tokens by ~70% and drop latency to <15s
2. **Prefix Caching:** Reorder prompt templates (System → Docs → Query) to maximize Ollama's KV cache hit rate
3. **Frontend Virtualization:** Implement `react-virtuoso` to handle 100+ message threads without DOM degradation

### Low Priority
- Code splitting for frontend modals
- React.memo for MessageBubble component
- Remove unused recharts dependency

## Getting Started

```bash
# Backend
cd original_rag/backend
pip install -r requirements.txt
python main.py

# Frontend
cd original_rag/frontend
npm install
npm run dev

# Run Quality Tests
node test-quality.js 8001 original_rag
```

## Tech Stack

- **Backend:** FastAPI, LangGraph, Python 3.11+
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui
- **LLM:** Ollama (DeepSeek-R1-Distill-Qwen-14B-Q4_K_M)
- **Vector Store:** ChromaDB with FastEmbed
- **Search:** Hybrid (Vector + BM25 with RRF Fusion)



gemini suggested readme:


# 🚀 Elite Agentic RAG Pipeline: Quality & Performance Optimization

A production-grade **Retrieval-Augmented Generation (RAG)** system built with **FastAPI**, **LangGraph**, and **Ollama**. This project documents a rigorous engineering journey from a baseline prototype to an optimized pipeline achieving **96% answer quality** and **100% test reliability**.

## 📊 Performance Benchmark (Final Phase)
After exhaustive E2E testing across 8 query types, the system delivered:
* **Quality:** **96% average** (exceeding the initial 80% target).
* **Pass Rate:** **8/8 query types** (100% success in groundedness and keyword recall).
* **Latency:** **~34s average** (Physically optimal for Llama 3.1 8B on 6GB VRAM).
* **Stability:** **100% state isolation**, fully resolving the "Context Bleed" bug.

## 🏗️ System Architecture: V5 "Guardian"
The pipeline utilizes a modular state machine to wrap fragile LLM generation with robust "Quality Gates."

### 1. Intent-Aware Orchestration
- **3-Layer Router:** Uses a hybrid approach (Rules -> Semantic -> LLM) to classify queries.
- **Intent Fallback:** A custom engineering fix that forces "question" intent if follow-up requests are detected without chat history, ensuring RAG reliability.

### 2. High-Precision Retrieval
- **Hybrid Search:** Combines Vector (FastEmbed) and BM25 with **RRF Fusion**.
- **Context Filter:** A custom similarity gate (threshold 0.3) that prunes irrelevant documents before generation to prevent context contamination.

### 3. Validated Generation
- **Hallucination Check:** A hybrid validator uses word/trigram overlap for instant grounding checks, only calling the LLM for ambiguous cases.

## 🧪 The "Science of RAG" Experiment
A key engineering milestone was the **LLMLingua Threshold Test**. We hypothesized that for context sizes under 1,000 tokens, the overhead of the compression model pass was degrading performance.

| Metric | With LLMLingua | **Without LLMLingua** | Delta |
| :--- | :--- | :--- | :--- |
| **Latency** | 45.5s | **34.1s** | **-25% Faster** |
| **Quality** | 89% | **96%** | **+7% Better** |
| **Pass Rate** | 7/8 | **8/8** | **Success** |

**Conclusion:** Compression logic is preserved but **disabled** for standard workloads. It is programmatically gated to only trigger when context exceeds 2,000 tokens.

## 🛠️ Performance Tuning (6GB VRAM Profile)
To maximize local hardware, the following environment variables are required:
- `OLLAMA_FLASH_ATTENTION=true`: Optimized memory access.
- `OLLAMA_KV_CACHE_TYPE=q8_0`: Quantized memory for long chat contexts.
- `MODEL_NAME=llama3.1:8b`: Fits entirely in GPU VRAM to avoid slow System RAM spill.

## 📁 Documentation
- `OPTIMIZATION_JOURNEY.md`: Step-by-step audit of every backend fix.
- `DEBUGGING_CONTEXT_BLEED.md`: Root cause analysis of state management failures.
- `FRONTEND_ANALYSIS.md`: Bundle and virtualization audit.
