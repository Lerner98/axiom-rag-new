# RAG VERIFICATION CHECKLIST (V3: Adaptive Architecture)

> **MANDATORY**: This checklist must be completed before claiming "Done" on any feature.
> **EVIDENCE**: You must provide `curl` output, log snippets, or screenshots for every check.

---

## 1. Core Infrastructure (Stability)
| # | Test | Expected Result | Evidence Required |
|---|------|-----------------|-------------------|
| 1.1 | Backend Startup | Server starts on port 8001 without error | Log snippet |
| 1.2 | Frontend Startup | Vite server runs on port 5173/8080 | Console output |
| 1.3 | FastEmbed Model Load | `BAAI/bge-small-en-v1.5` loads successfully | Log: "FastEmbed model loaded" |
| 1.4 | Reranker Model Load | Cross-Encoder loads successfully | Log: "Cross-encoder model loaded" |

## 2. Ingestion Pipeline (V3: Parent-Child + BM25)
| # | Test | Expected Result | Evidence Required |
|---|------|-----------------|-------------------|
| 2.1 | Upload PDF | Upload completes in < 5s (100+ chunks) | Response time log |
| 2.2 | Chunking Strategy | Logs show "Created X parents, Y children" | Log snippet |
| 2.3 | BM25 Indexing | Log shows "Built BM25 index for chat_X" | Log snippet |
| 2.4 | Vector Storage | ChromaDB contains child chunks | `count` from API |

## 3. Retrieval & Routing (V3: Adaptive)
| # | Query Type | Expected Behavior | Evidence Required |
|---|------------|-------------------|-------------------|
| 3.1 | **Simple Query** | Router logs: `skip_rewrite: True` | Log: "Query classified as: simple" |
| 3.2 | **Complex Query** | Router logs: `skip_rewrite: False` | Log: "Query classified as: complex" |
| 3.3 | **Keyword Search** | Finds exact match ID (e.g., "Error 504") | Answer contains exact term |
| 3.4 | **Hybrid Fusion** | Logs show "RRF fusion returned X results" | Log snippet |
| 3.5 | **Parent Expansion** | Context sent to LLM is >1000 chars (Parent) | Log: "Context length" |

## 4. Generation & Quality (V3: Reranker)
| # | Test | Expected Result | Evidence Required |
|---|------|-----------------|-------------------|
| 4.1 | **Relevance** | Top result has high reranker score (>0.7) | Log: "Reranker returned..." |
| 4.2 | **Citations** | Answer contains `[Source X]` citations | Final Answer Text |
| 4.3 | **Hallucination** | Fast check passes (>=0.8) OR LLM check passes | Log: "Fast check PASSED" or "grounded: yes" |
| 4.4 | **Empty State** | Query with 0 docs returns helpful message | Response text (No recursion error) |

## 5. Security & Isolation (ADR-006)
| # | Test | Expected Result | Evidence Required |
|---|------|-----------------|-------------------|
| 5.1 | Chat Isolation | Chat A cannot see Chat B's documents | `list_documents` output |
| 5.2 | Cloud Mode | Toggle is present; Default is "Local" | UI Screenshot/State dump |

---

## Verification Report Template

**Date:** [DD-MM-YYYY]
**Agent:** @auditor

**Summary:**
[Pass/Fail] - [Brief description of system state]

**Failed Tests:**
- [Test ID]: [Error message or unexpected behavior]

**Corrective Actions:**
- [Action taken to fix failure]

**Signature:** [Agent Name]