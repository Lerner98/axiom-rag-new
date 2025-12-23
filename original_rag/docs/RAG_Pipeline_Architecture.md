# Axiom RAG Pipeline Architecture

**Version:** V3 (Hybrid Search + Parent-Child Chunking) + V5 Intent Classification
**Last Updated:** 13-12-2025

This document provides a comprehensive explanation of how the Axiom RAG system processes user queries, from initial input through final response generation.

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Entry Points](#2-entry-points)
3. [Intent Classification (3-Layer Hybrid Router)](#3-intent-classification-3-layer-hybrid-router)
4. [Intent Types and Handlers](#4-intent-types-and-handlers)
5. [Full RAG Pipeline for Questions](#5-full-rag-pipeline-for-questions)
6. [Hybrid Retrieval System](#6-hybrid-retrieval-system)
7. [Parent-Child Chunking](#7-parent-child-chunking)
8. [Cross-Encoder Reranking](#8-cross-encoder-reranking)
9. [Hallucination Detection](#9-hallucination-detection)
10. [State Management](#10-state-management)
11. [Conversation Memory](#11-conversation-memory)
12. [Document Ingestion](#12-document-ingestion)
13. [Configuration Reference](#13-configuration-reference)
14. [Response Formats](#14-response-formats)
15. [File Reference](#15-file-reference)

---

## 1. High-Level Overview

The Axiom RAG system is designed as a **document assistant** that intelligently routes user queries through different processing paths based on intent. Not every query needs the full RAG pipeline - greetings, thank-yous, and follow-up requests are handled efficiently without retrieval.

```
                                    User Query
                                         │
                                         ▼
                            ┌─────────────────────────┐
                            │   Intent Classification │
                            │   (3-Layer Hybrid)      │
                            └─────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
            ┌───────────┐        ┌───────────┐        ┌───────────┐
            │  No-RAG   │        │  Context  │        │  Full RAG │
            │  Handler  │        │  Handler  │        │  Pipeline │
            └───────────┘        └───────────┘        └───────────┘
                 │                    │                    │
                 │                    │                    ▼
                 │                    │         ┌─────────────────────┐
                 │                    │         │   Hybrid Retrieval  │
                 │                    │         │  (Vector + BM25)    │
                 │                    │         └─────────────────────┘
                 │                    │                    │
                 │                    │                    ▼
                 │                    │         ┌─────────────────────┐
                 │                    │         │  Cross-Encoder      │
                 │                    │         │  Reranking          │
                 │                    │         └─────────────────────┘
                 │                    │                    │
                 │                    │                    ▼
                 │                    │         ┌─────────────────────┐
                 │                    │         │  LLM Generation     │
                 │                    │         └─────────────────────┘
                 │                    │                    │
                 │                    │                    ▼
                 │                    │         ┌─────────────────────┐
                 │                    │         │  Hallucination      │
                 │                    │         │  Detection          │
                 │                    │         └─────────────────────┘
                 │                    │                    │
                 └────────────────────┴────────────────────┘
                                         │
                                         ▼
                                    Response
```

---

## 2. Entry Points

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/` | POST | Non-streaming chat (complete response) |
| `/chat/stream` | POST | Streaming chat (legacy, requires collection_name) |
| `/chat/{chat_id}/stream` | POST | Chat-scoped streaming (ADR-007) |
| `/chat/history/{session_id}` | GET | Retrieve conversation history |
| `/chat/history/{session_id}` | DELETE | Clear conversation history |
| `/chat/{chat_id}/documents` | POST | Upload documents to chat |
| `/chat/{chat_id}/documents` | GET | List documents in chat |
| `/chat/{chat_id}/documents/{doc_id}` | DELETE | Remove document from chat |

### Request Flow

```
HTTP Request
    │
    ▼
FastAPI Route Handler (chat.py)
    │
    ├─► Validate ChatRequest
    │   - message: str (required)
    │   - session_id: str (optional, defaults to UUID)
    │   - collection_name: str (optional, derived from chat_id)
    │
    ├─► For streaming: generate_stream() → SSE EventSourceResponse
    │
    └─► For non-streaming: pipeline.aquery() → ChatResponse
```

### Streaming Protocol

The streaming endpoint uses Server-Sent Events (SSE):

```
Event: token
Data: {"type": "token", "content": "word"}

Event: sources
Data: {"type": "sources", "sources": [...]}

Event: done
Data: {
    "type": "done",
    "is_grounded": true,
    "iterations": 1,
    "query_complexity": "simple",
    "is_summarization": false
}
```

---

## 3. Intent Classification (3-Layer Hybrid Router)

The intent router determines what kind of query the user is making before deciding whether to run the full RAG pipeline.

### Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 0: Hard Rules                       │
│                  (Deterministic, <1ms)                       │
├─────────────────────────────────────────────────────────────┤
│  ✗ Empty or too short (≤1 char)         → GARBAGE          │
│  ✗ No alphabetic characters             → GARBAGE          │
│  ✗ Repetitive chars (>90% same char)    → GARBAGE          │
│  ✗ Stopword density >90% (≤5 words)     → GARBAGE          │
│  ✓ Passes all checks                    → Continue         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 1: Semantic Router                     │
│               (FastEmbed similarity, <20ms)                  │
├─────────────────────────────────────────────────────────────┤
│  1. Embed query with BAAI/bge-small-en-v1.5                 │
│  2. Compare to pre-embedded intent exemplars                │
│  3. Find best cosine similarity match                       │
│                                                             │
│  Score ≥ 0.85  → Return (intent, confidence)               │
│  Score < 0.85  → Continue to Layer 2                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                   LAYER 2: LLM Fallback                      │
│                 (For ambiguous cases, ~2s)                   │
├─────────────────────────────────────────────────────────────┤
│  1. Use LLM with intent classification prompt               │
│  2. Analyze query in context                                │
│  3. Return (intent, confidence=0.70)                        │
└─────────────────────────────────────────────────────────────┘
```

### Intent Exemplars

Each intent has pre-embedded canonical examples for fast similarity matching:

| Intent | Example Phrases |
|--------|----------------|
| **greeting** | "hi", "hello", "hey", "good morning", "sup", "howdy" |
| **gratitude** | "thanks", "thank you", "appreciate it", "thx", "ty", "cheers" |
| **followup** | "more", "tell me more", "continue", "elaborate", "what else" |
| **simplify** | "explain simpler", "eli5", "dumb it down", "too complicated" |
| **deepen** | "go deeper", "more technical", "in depth", "dive deeper" |
| **command** | "summarize", "compare", "list all", "give me an overview" |

---

## 4. Intent Types and Handlers

### Intent Categories

| Intent | Description | Needs RAG? | Handler |
|--------|-------------|------------|---------|
| `question` | Standard document query | YES | Full RAG Pipeline |
| `command` | Specialized operations (summarize, compare) | YES | Full RAG Pipeline |
| `greeting` | User says hello | NO | Simple response |
| `gratitude` | User says thanks | NO | Simple response |
| `garbage` | Invalid/meaningless input | NO | Friendly rejection |
| `off_topic` | Unrelated to documents | NO | Redirect message |
| `followup` | Wants more on previous topic | MAYBE | Context handler |
| `simplify` | Wants simpler explanation | MAYBE | Context handler |
| `deepen` | Wants more technical detail | MAYBE | Context handler |
| `clarify_needed` | Ambiguous query | NO | Ask for clarification |

### Simple Handlers (No Context Needed)

**Greeting Handler:**
```
Input:  "hi" / "hello" / "hey"
Output: "Hello! How can I help you with your documents today?"
```

**Gratitude Handler:**
```
Input:  "thanks" / "thank you"
Output: "You're welcome! Feel free to ask if you have more questions about your documents."
```

**Garbage Handler:**
```
Input:  "asdfghjkl" / "!!!" / "a"
Output: "I didn't quite understand that. Could you rephrase your question about the documents?"
```

**Off-Topic Handler:**
```
Input:  "What's the weather?" / "Tell me a joke"
Output: "I'm designed to help with questions about your uploaded documents.
        What would you like to know about them?"
```

### Context-Aware Handlers (Need Memory + LLM)

These handlers retrieve the last conversation exchange and transform the previous answer:

**Followup Handler:**
```
Strategy:
1. Get last Q&A from memory
2. If no context → fall back to RAG
3. Ask LLM to expand with more details
4. Preserve original sources
```

**Simplify Handler:**
```
Strategy:
1. Get last Q&A from memory
2. If no context → fall back to RAG
3. Ask LLM to rewrite at 5th-grade level
4. Preserve original sources
```

**Deepen Handler:**
```
Strategy:
1. Get last Q&A from memory
2. If no context → fall back to RAG
3. Ask LLM to add technical depth
4. Preserve original sources
```

---

## 5. Full RAG Pipeline for Questions

When a query is classified as `question` or `command`, it goes through the full retrieval-augmented generation pipeline.

### Pipeline Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         RAG PIPELINE FLOW                            │
└──────────────────────────────────────────────────────────────────────┘

User Query + Intent Classification
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. ROUTE QUERY (Query Router Agent)                                │
├─────────────────────────────────────────────────────────────────────┤
│  Analyze query complexity:                                          │
│  • SIMPLE: Direct factual question → Skip rewrite                  │
│  • COMPLEX: Multi-part or analytical → Rewrite query               │
│  • CONVERSATIONAL: Depends on history → Rewrite with context       │
│  • SUMMARIZE: User wants summary → Sequential retrieval            │
└─────────────────────────────────────────────────────────────────────┘
    │
    ├─── SIMPLE ────────────────────────────────────────┐
    │                                                   │
    ├─── SUMMARIZE ─────────────────────────────┐       │
    │                                           │       │
    └─── COMPLEX/CONVERSATIONAL                 │       │
         │                                      │       │
         ▼                                      │       │
┌─────────────────────────────────────┐         │       │
│  2. REWRITE QUERY                   │         │       │
├─────────────────────────────────────┤         │       │
│  • Get chat history (last 5 msgs)   │         │       │
│  • Use QUERY_REWRITE_PROMPT         │         │       │
│  • LLM optimizes for search         │         │       │
│  • Output: rewritten_query          │         │       │
└─────────────────────────────────────┘         │       │
         │                                      │       │
         ▼                                      ▼       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. RETRIEVE (Hybrid Search + Parent Expansion)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  For QUESTIONS:                      For SUMMARIZE:                 │
│  ┌─────────────────────────┐        ┌─────────────────────────┐    │
│  │ Vector Search (k=20)    │        │ Get ALL chunks          │    │
│  │ + BM25 Search (k=20)    │        │ Sort by page order      │    │
│  │ + RRF Fusion            │        │ Dedupe by parent_id     │    │
│  │ = 50 results            │        │ Use parent_context      │    │
│  └─────────────────────────┘        └─────────────────────────┘    │
│           │                                    │                    │
│           ▼                                    │                    │
│  ┌─────────────────────────┐                   │                    │
│  │ Parent Expansion        │                   │                    │
│  │ • Dedupe by parent_id   │                   │                    │
│  │ • Replace with parent   │                   │                    │
│  │   context               │                   │                    │
│  └─────────────────────────┘                   │                    │
│           │                                    │                    │
│           └────────────────────────────────────┘                    │
│                            │                                        │
│  Output: retrieved_documents (50 for questions, all for summary)    │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. GRADE DOCUMENTS (Cross-Encoder Reranking)                       │
├─────────────────────────────────────────────────────────────────────┤
│  • Model: cross-encoder/ms-marco-MiniLM-L-6-v2                     │
│  • Score all (query, doc) pairs                                    │
│  • Normalize scores via sigmoid (0-1)                              │
│  • Select top 5 documents                                          │
│  • Output: relevant_documents                                       │
│                                                                     │
│  Fallback: If reranker unavailable, use threshold (>0.3)           │
└─────────────────────────────────────────────────────────────────────┘
    │
    ├─── Has relevant docs? ───┐
    │                          │
    │ NO                       │ YES
    │ (retry or empty)         │
    │                          ▼
    │         ┌─────────────────────────────────────────────────────┐
    │         │  5. GENERATE (LLM Response)                         │
    │         ├─────────────────────────────────────────────────────┤
    │         │  Build context from relevant_documents:             │
    │         │                                                     │
    │         │  "[Source 1: document.pdf (page 5)]                 │
    │         │   {content}                                         │
    │         │   ---                                               │
    │         │   [Source 2: document.pdf (page 12)]                │
    │         │   {content}"                                        │
    │         │                                                     │
    │         │  • Get chat history (last 5 messages)               │
    │         │  • Use GENERATION_PROMPT                            │
    │         │  • LLM generates answer with [Source N] citations   │
    │         │  • Output: answer                                    │
    │         └─────────────────────────────────────────────────────┘
    │                          │
    │                          ▼
    │         ┌─────────────────────────────────────────────────────┐
    │         │  6. CHECK HALLUCINATION (Hybrid Detection)          │
    │         ├─────────────────────────────────────────────────────┤
    │         │                                                     │
    │         │  Fast Deterministic Check:                          │
    │         │  ┌─────────────────────────────────────────────┐    │
    │         │  │ • Extract content words (skip stopwords)    │    │
    │         │  │ • Calculate word overlap with sources       │    │
    │         │  │ • Calculate trigram overlap                 │    │
    │         │  │ • Score = (word * 0.6) + (trigram * 0.4)   │    │
    │         │  │                                             │    │
    │         │  │ ≥ 0.8 → GROUNDED (skip LLM) ✓              │    │
    │         │  │ < 0.3 → NOT GROUNDED (skip LLM) ✗          │    │
    │         │  │ 0.3-0.8 → Call LLM for verification        │    │
    │         │  └─────────────────────────────────────────────┘    │
    │         │                                                     │
    │         │  LLM Verification (if ambiguous):                   │
    │         │  • Use HALLUCINATION_CHECK_PROMPT                   │
    │         │  • Parse: GROUNDED: YES/NO, SCORE: [0-1]           │
    │         │  • Set is_grounded, groundedness_score              │
    │         └─────────────────────────────────────────────────────┘
    │                          │
    │                          ├─── Grounded? ───┐
    │                          │                 │
    │                          │ NO              │ YES
    │                          │ (and retries    │
    │                          │  remaining)     │
    │                          │                 │
    │                          ▼                 │
    │         ┌─────────────────────┐            │
    │         │ Retry Generation    │            │
    │         │ (with feedback)     │            │
    │         └─────────────────────┘            │
    │                   │                        │
    └───────────────────┴────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. SAVE TO MEMORY                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  • Save user message                                                │
│  • Save assistant message with metadata (sources)                   │
│  • END                                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Hybrid Retrieval System

The hybrid retrieval system combines semantic (vector) search with keyword (BM25) search to overcome the limitations of either approach alone.

### Why Hybrid Search?

| Approach | Strengths | Weaknesses |
|----------|-----------|------------|
| **Vector Search** | Semantic similarity, synonyms, concepts | Misses exact terms, IDs, dates, acronyms |
| **BM25 Search** | Exact matches, keywords, rare terms | No semantic understanding |
| **Hybrid (Both)** | Best of both worlds | Slightly more computation |

### Architecture

```
                            Query: "What is CAP theorem?"
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
        ┌─────────────────────┐               ┌─────────────────────┐
        │   Vector Search     │               │    BM25 Search      │
        │   (ChromaDB)        │               │    (rank_bm25)      │
        ├─────────────────────┤               ├─────────────────────┤
        │ • Embed query       │               │ • Tokenize query    │
        │ • Cosine similarity │               │ • Term frequency    │
        │ • k=20 results      │               │ • k=20 results      │
        └─────────────────────┘               └─────────────────────┘
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────┐
                          │   RRF Fusion            │
                          │   (Reciprocal Rank)     │
                          ├─────────────────────────┤
                          │ Score = Σ 1/(k + rank)  │
                          │ k = 60 (standard)       │
                          │ No weight tuning needed │
                          │ Output: 50 results      │
                          └─────────────────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────┐
                          │   Parent Expansion      │
                          ├─────────────────────────┤
                          │ • Deduplicate by        │
                          │   parent_id             │
                          │ • Replace child content │
                          │   with parent_context   │
                          │ • Preserve scores       │
                          └─────────────────────────┘
```

### RRF Fusion Formula

Reciprocal Rank Fusion combines multiple ranked lists without requiring weight tuning:

```
RRF_score(doc) = Σ 1 / (k + rank_i)

Where:
- k = 60 (smoothing constant)
- rank_i = position in each result list
```

Example:
- Document appears at rank 3 in vector search and rank 5 in BM25
- RRF_score = 1/(60+3) + 1/(60+5) = 0.0159 + 0.0154 = 0.0313

### BM25 Persistence (V3.1)

BM25 indices now survive backend restarts:

```
Upload Document
    │
    ▼
Build BM25 Index
    │
    ▼
Auto-save to: ./data/bm25_indices/{collection_name}.pkl
    │
    ▼
[Backend Restart]
    │
    ▼
First Search Query
    │
    ▼
Lazy Load from disk (self-healing)
```

---

## 7. Parent-Child Chunking

Parent-child chunking decouples **retrieval precision** from **context coherence**.

### The Problem with Fixed Chunking

| Chunk Size | Retrieval | Context |
|------------|-----------|---------|
| Small (400 chars) | Precise vectors | Fragmented, loses context |
| Large (2000 chars) | Imprecise vectors | Coherent answers |

### The Solution: Two-Level Chunking

```
                        Original Document
                               │
                               ▼
            ┌─────────────────────────────────────┐
            │         PARENT SPLITTER             │
            │  • Size: 2000 chars                 │
            │  • Overlap: 200 chars               │
            │  • Separators: \n\n, \n, ". ", " "  │
            └─────────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
     ┌──────────┐       ┌──────────┐       ┌──────────┐
     │ Parent 1 │       │ Parent 2 │       │ Parent 3 │
     │ 2000 ch  │       │ 2000 ch  │       │ 2000 ch  │
     └──────────┘       └──────────┘       └──────────┘
            │                  │                  │
            ▼                  ▼                  ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
     │ CHILD SPLIT  │   │ CHILD SPLIT  │   │ CHILD SPLIT  │
     │ Size: 400 ch │   │ Size: 400 ch │   │ Size: 400 ch │
     │ Overlap: 50  │   │ Overlap: 50  │   │ Overlap: 50  │
     └──────────────┘   └──────────────┘   └──────────────┘
            │                  │                  │
     ┌──────┼──────┐    ┌──────┼──────┐    ┌──────┼──────┐
     ▼      ▼      ▼    ▼      ▼      ▼    ▼      ▼      ▼
   [C1]   [C2]   [C3]  [C4]   [C5]   [C6] [C7]   [C8]   [C9]

   Each child stores:
   - chunk_id: unique ID
   - parent_id: reference to parent
   - parent_context: FULL parent text (key!)
   - content: child text (for embedding)
```

### How It Works in Retrieval

```
Search Query
    │
    ▼
Vector + BM25 search against CHILD chunks (precise)
    │
    ▼
Results: [C2, C7, C4, C1, C8, ...]
    │
    ▼
Parent Expansion:
    - C2 → Parent 1
    - C7 → Parent 3
    - C4 → Parent 2
    - C1 → Parent 1 (duplicate, skip)
    - C8 → Parent 3 (duplicate, skip)
    │
    ▼
Unique Parents with parent_context: [Parent 1, Parent 3, Parent 2]
    │
    ▼
LLM receives coherent 2000-char contexts
```

---

## 8. Cross-Encoder Reranking

The cross-encoder is a more accurate but slower model that re-scores the top candidates.

### Why Two-Stage Retrieval?

```
Stage 1: Fast Retrieval (Bi-Encoder)
├─ Speed: Very fast (embedding comparison)
├─ Accuracy: Good
├─ Results: 50 candidates
└─ Used for: Initial recall

Stage 2: Precise Reranking (Cross-Encoder)
├─ Speed: Slower (full pair encoding)
├─ Accuracy: Excellent
├─ Results: 5 final documents
└─ Used for: Final precision
```

### Cross-Encoder Architecture

```
                    Query + Document
                          │
                          ▼
               ┌────────────────────┐
               │   [CLS] Query      │
               │   [SEP] Document   │
               │   [SEP]            │
               └────────────────────┘
                          │
                          ▼
               ┌────────────────────┐
               │   Transformer      │
               │   (BERT-based)     │
               └────────────────────┘
                          │
                          ▼
               ┌────────────────────┐
               │   Relevance Score  │
               │   (0.0 - 1.0)      │
               └────────────────────┘
```

### Model Details

- **Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Alternatives:** ms-marco-MiniLM-L-12-v2, BAAI/bge-reranker-base
- **Normalization:** Sigmoid function to map scores to 0-1
- **Top-K:** Default 5 (configurable via `retrieval_final_k`)

---

## 9. Hallucination Detection

The system uses a hybrid approach to detect when the LLM generates claims not supported by the source documents.

### Two-Layer Detection

```
                        Generated Answer
                               │
                               ▼
            ┌─────────────────────────────────────┐
            │     LAYER 1: Fast Deterministic     │
            │            (~0ms)                   │
            ├─────────────────────────────────────┤
            │ 1. Extract content words from       │
            │    answer (skip stopwords)          │
            │ 2. Extract trigrams with 2+         │
            │    content words                    │
            │ 3. Calculate word overlap:          │
            │    matched_words / total_words      │
            │ 4. Calculate trigram overlap:       │
            │    matched_trigrams / total         │
            │ 5. Score = (word * 0.6) +          │
            │           (trigram * 0.4)           │
            └─────────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
      Score ≥ 0.8       0.3 ≤ Score < 0.8   Score < 0.3
            │                  │                  │
            ▼                  ▼                  ▼
      GROUNDED ✓          AMBIGUOUS         NOT GROUNDED ✗
      (skip LLM)              │              (skip LLM)
                              │
                              ▼
            ┌─────────────────────────────────────┐
            │      LAYER 2: LLM Verification      │
            │            (~2-5s)                  │
            ├─────────────────────────────────────┤
            │ • Send answer + sources to LLM      │
            │ • Parse response:                   │
            │   - GROUNDED: YES/NO                │
            │   - SCORE: [0-1]                    │
            │   - ISSUES: [specific claims]       │
            │ • Set is_grounded                   │
            └─────────────────────────────────────┘
```

### Retry Logic

If hallucination is detected and retries remain:

1. Generate uses `GENERATION_WITH_RETRY_PROMPT`
2. Includes feedback: "Previous answer contained unsupported claims"
3. LLM tries again with stricter grounding
4. Maximum 2 iterations (configurable)

---

## 10. State Management

The pipeline uses a TypedDict to pass state between LangGraph nodes.

### RAGState Fields

```python
class RAGState(TypedDict):
    # ═══════════════════════════════════════════════════════════════
    # INPUT
    # ═══════════════════════════════════════════════════════════════
    question: str                    # Original user query
    session_id: str                  # Conversation session ID
    collection_name: str             # Vector store collection (chat_{id})

    # ═══════════════════════════════════════════════════════════════
    # V5 INTENT CLASSIFICATION
    # ═══════════════════════════════════════════════════════════════
    detected_intent: Optional[str]   # greeting, question, followup, etc.
    intent_confidence: float         # 0.0 - 1.0

    # ═══════════════════════════════════════════════════════════════
    # ROUTER AGENT
    # ═══════════════════════════════════════════════════════════════
    query_complexity: Optional[str]  # simple, complex, conversational, summarize, garbage
    skip_rewrite: bool               # True for simple queries
    is_summarization: bool           # True for summary requests
    is_garbage_query: bool           # True for invalid input

    # ═══════════════════════════════════════════════════════════════
    # QUERY PROCESSING
    # ═══════════════════════════════════════════════════════════════
    rewritten_query: Optional[str]   # Optimized search query
    query_type: Optional[str]        # factual, analytical, conversational

    # ═══════════════════════════════════════════════════════════════
    # RETRIEVAL
    # ═══════════════════════════════════════════════════════════════
    retrieved_documents: list        # 50 docs from hybrid search
    relevant_documents: list         # 5 docs after reranking
    collection_empty: bool           # True if no documents in collection

    # ═══════════════════════════════════════════════════════════════
    # GENERATION
    # ═══════════════════════════════════════════════════════════════
    answer: Optional[str]            # LLM-generated response
    sources: list[dict]              # Source metadata for citations

    # ═══════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════
    is_grounded: bool                # Answer supported by sources?
    groundedness_score: float        # 0.0 - 1.0
    hallucination_details: str       # Specific issues found
    fast_groundedness_score: float   # From deterministic check
    skip_llm_hallucination_check: bool  # True if fast check decisive

    # ═══════════════════════════════════════════════════════════════
    # CONTROL FLOW
    # ═══════════════════════════════════════════════════════════════
    iteration: int                   # Current retry iteration
    max_iterations: int              # Max retries allowed (default: 2)
    should_rewrite: bool             # Should query be rewritten?
    rewrite_count: int               # Number of rewrites performed

    # ═══════════════════════════════════════════════════════════════
    # METADATA (Accumulative via LangGraph)
    # ═══════════════════════════════════════════════════════════════
    errors: Annotated[list[str], add]           # Error messages
    processing_steps: Annotated[list[str], add] # Audit trail
```

---

## 11. Conversation Memory

The memory system stores conversation history for context-aware responses.

### Storage

- **Backend:** SQLite (configurable)
- **Database:** `./data/memory.db`
- **Table:** `messages(id, session_id, role, content, metadata, timestamp)`

### Message Structure

```python
{
    "role": "user" | "assistant",
    "content": str,
    "timestamp": "2024-01-15T10:30:00Z",
    "metadata": {
        "sources": [...]  # For assistant messages
    }
}
```

### Usage Throughout Pipeline

| Component | Messages Retrieved | Purpose |
|-----------|-------------------|---------|
| Router Agent | Last 3 | Context awareness |
| Query Rewriting | Last 5 | Conversational context |
| Generation | Last 5 | Coherent responses |
| Context Handlers | Last 4 | Find last_answer |

---

## 12. Document Ingestion

### Flow

```
File Upload (POST /chat/{chat_id}/documents)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. COLLECTION SETUP                                                │
├─────────────────────────────────────────────────────────────────────┤
│  collection_name = f"chat_{chat_id}"                               │
│  (ADR-007: Chat-scoped document isolation)                         │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. DOCUMENT LOADING                                                │
├─────────────────────────────────────────────────────────────────────┤
│  DocumentLoader.load(file_path)                                    │
│  • Detect file type: .pdf, .txt, .md, .docx                        │
│  • Use appropriate loader                                          │
│  • Extract text with metadata (source, page)                       │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. PARENT-CHILD CHUNKING                                          │
├─────────────────────────────────────────────────────────────────────┤
│  ParentChildChunker.chunk(documents)                               │
│  • Parent: 2000 chars, 200 overlap                                 │
│  • Child: 400 chars, 50 overlap                                    │
│  • Each child stores parent_context in metadata                    │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. EMBEDDING                                                       │
├─────────────────────────────────────────────────────────────────────┤
│  FastEmbed (BAAI/bge-small-en-v1.5)                                │
│  • ONNX-based, CPU-optimized                                       │
│  • Batch size: 256                                                 │
│  • Dimension: 384                                                  │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. VECTOR STORAGE                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  ChromaDB.add(chunks, embeddings, metadata)                        │
│  • Persisted to: ./data/chroma/                                    │
│  • Collection: chat_{chat_id}                                      │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. BM25 INDEX                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  HybridRetriever.build_bm25_index(collection, chunks)              │
│  • Tokenize all chunks                                             │
│  • Build BM25Okapi index                                           │
│  • Persist to: ./data/bm25_indices/{collection}.pkl                │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
Response: { uploaded: [{id, name, chunk_count}], failed: [] }
```

---

## 13. Configuration Reference

### Key Settings (backend/config/settings.py)

| Category | Setting | Default | Description |
|----------|---------|---------|-------------|
| **Embeddings** | embedding_provider | fastembed | Vector embedding source |
| | fastembed_model | BAAI/bge-small-en-v1.5 | Embedding model (384 dims) |
| | fastembed_batch_size | 256 | Batch size for embedding |
| **Chunking** | parent_chunk_size | 2000 | Parent chunk characters |
| | parent_chunk_overlap | 200 | Parent overlap characters |
| | child_chunk_size | 400 | Child chunk characters |
| | child_chunk_overlap | 50 | Child overlap characters |
| **Retrieval** | retrieval_initial_k | 50 | Results from hybrid search |
| | retrieval_vector_k | 20 | Vector search component |
| | retrieval_bm25_k | 20 | BM25 search component |
| | retrieval_final_k | 5 | Results after reranking |
| | relevance_threshold | 0.3 | Minimum relevance score |
| **Quality** | max_retries | 2 | Hallucination retry attempts |
| | hallucination_threshold | 0.8 | Grounded score threshold |
| **LLM** | llm_provider | ollama | Provider: openai, ollama, gemini |
| | ollama_model | llama3 | Default Ollama model |
| | ollama_base_url | http://localhost:11434 | Ollama service URL |
| **Storage** | vector_provider | chroma | Vector database |
| | chroma_path | ./data/chroma | ChromaDB persistence |
| | memory_backend | sqlite | Conversation storage |
| | memory_db_path | ./data/memory.db | SQLite database path |

---

## 14. Response Formats

### Non-Streaming Response

```json
{
    "message_id": "uuid-string",
    "answer": "Based on the documents, [Source 1] explains that...",
    "sources": [
        {
            "filename": "document.pdf",
            "chunk_id": "uuid-string",
            "relevance_score": 0.89,
            "content_preview": "First 200 characters of chunk...",
            "page": 5
        }
    ],
    "session_id": "session-uuid",
    "was_grounded": true,
    "confidence": 0.92,
    "processing_time_ms": 3450
}
```

### Streaming Events

```
event: token
data: {"type": "token", "content": "Based"}

event: token
data: {"type": "token", "content": "on"}

event: token
data: {"type": "token", "content": "the"}

...

event: sources
data: {"type": "sources", "sources": [...]}

event: done
data: {
    "type": "done",
    "is_grounded": true,
    "iterations": 1,
    "query_complexity": "simple",
    "is_summarization": false
}
```

---

## 15. File Reference

| File | Purpose | Key Components |
|------|---------|----------------|
| `backend/rag/pipeline.py` | LangGraph orchestration | RAGPipeline, graph building |
| `backend/rag/nodes.py` | Node implementations | RAGNodes, all processing functions |
| `backend/rag/state.py` | State definitions | RAGState TypedDict |
| `backend/rag/intent_router.py` | Intent classification | IntentRouter, 3-layer system |
| `backend/rag/intent_handlers.py` | Non-RAG handlers | All intent handler functions |
| `backend/rag/retriever.py` | Hybrid search | HybridRetriever, BM25, RRF |
| `backend/rag/reranker.py` | Cross-encoder | CrossEncoderReranker |
| `backend/rag/prompts.py` | LLM prompts | All prompt templates |
| `backend/ingest/chunker.py` | Text splitting | ParentChildChunker |
| `backend/ingest/service.py` | Ingestion service | IngestionService |
| `backend/memory/store.py` | Conversation history | SQLiteMemoryStore |
| `backend/vectorstore/store.py` | Vector database | ChromaDB wrapper |
| `backend/api/routes/chat.py` | API endpoints | FastAPI routes |
| `backend/config/settings.py` | Configuration | Settings dataclass |

---

## Summary

The Axiom RAG system implements a sophisticated document assistant with:

1. **Smart Intent Routing** - Not every query needs RAG
2. **Hybrid Retrieval** - Vector + BM25 for comprehensive search
3. **Parent-Child Chunking** - Precise retrieval with coherent context
4. **Cross-Encoder Reranking** - High-precision final selection
5. **Hybrid Hallucination Detection** - Fast deterministic + LLM fallback
6. **Conversation Memory** - Context-aware responses

The architecture prioritizes **quality over speed** while using deterministic shortcuts where possible to minimize latency and LLM costs.
