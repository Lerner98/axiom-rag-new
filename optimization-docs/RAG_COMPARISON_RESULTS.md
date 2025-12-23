# RAG Implementation Comparison Results

**Date:** 2025-12-23
**Test Document:** system-design-primer.txt (22 chunks)

## Executive Summary

**original_rag is the superior implementation.** The agentic-rag branch, which was used for TOON compression experiments, performs significantly worse across all metrics.

**Decision: Continue optimization work on original_rag.**

## Test Results

### original_rag (Port 8001)
| Metric | Value |
|--------|-------|
| Tests Passed | 8/8 (100%) |
| Avg Quality | 94% |
| Avg Latency | 13,952ms |

### agentic-rag (Port 8000)
| Metric | Value |
|--------|-------|
| Tests Passed | 5/8 (62.5%) |
| Avg Quality | 67% |
| Avg Latency | 28,958ms |

## By Query Type

| Query Type | original_rag Quality | original_rag Latency | agentic-rag Quality | agentic-rag Latency |
|------------|---------------------|---------------------|--------------------|--------------------|
| simple_factual | 100% | 7,232ms | 100% | 31,958ms |
| how_to | 90% | 12,565ms | **15%** | 11,311ms |
| comparison | 100% | 15,835ms | **15%** | 17,585ms |
| conversational | 100% | 10,304ms | **48%** | 90,086ms |
| short | 90% | 7,830ms | 90% | 9,355ms |
| complex | 100% | 16,521ms | 100% | 26,008ms |
| vague | 85% | 23,851ms | 85% | 23,999ms |
| out_of_domain | 85% | 17,481ms | 85% | 21,362ms |

## Critical Failures in agentic-rag

1. **how_to (15% quality)**: Said "I don't have enough information" when document clearly contains caching info
2. **comparison (15% quality)**: Answered about CACHING when asked about SQL vs NoSQL - severe retrieval bug
3. **conversational (48% quality, 90s latency!)**: Timeout and poor context handling

## Root Cause Analysis

The agentic-rag branch introduced:
- Intent routing with TOON compression (deprecated, no value)
- Complex 3-layer classification adding latency
- Memory/context bugs causing wrong document retrieval
- Extra processing overhead without quality benefit

## Recommendation

1. **Archive agentic-rag** - Keep for reference but do not develop further
2. **Optimize original_rag** - This is the working baseline
3. **Apply targeted improvements** to original_rag:
   - Intent-based fast-path routing (without TOON)
   - Latency optimizations
   - Frontend improvements

## Next Steps

Focus all optimization efforts on `original_rag/`:
- Backend: Reduce 14s average latency
- Frontend: Performance improvements
- E2E: Comprehensive benchmarking
