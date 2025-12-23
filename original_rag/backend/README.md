# Agentic RAG System

> **Self-correcting Retrieval Augmented Generation with RAGAS evaluation**

A production-ready RAG implementation featuring:
- 🧠 **LangGraph** agentic workflow with self-correction
- 🔍 **Qdrant** vector database (or ChromaDB fallback)
- ✅ **RAGAS-style** evaluation metrics
- 🔄 **Self-RAG** pattern: query rewriting, relevance grading, hallucination checking

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Question                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
         ┌───────────────┐
         │    Router     │ → Vector DB or Web Search?
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │ Query Rewrite │ → Optimize for retrieval
         └───────┬───────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Retrieve Documents                        │
│                    (Qdrant / Chroma)                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
         ┌───────────────┐
         │ Grade Docs    │ → Filter irrelevant
         └───────┬───────┘
                 │
        ┌────────┴────────┐
        │ Relevant?       │
        └────────┬────────┘
           Yes   │   No
                 │    └─────→ Web Search (fallback)
                 ▼
         ┌───────────────┐
         │   Generate    │
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │ Hallucination │ → Is answer grounded?
         │    Check      │
         └───────┬───────┘
                 │
        ┌────────┴────────┐
        │ Grounded?       │
        └────────┬────────┘
           Yes   │   No (max 2 tries)
                 │    └─────→ Regenerate
                 ▼
         ┌───────────────┐
         │   RAGAS Eval  │ (optional)
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │ Final Answer  │
         └───────────────┘
```

## Quick Start

### 1. Environment Setup

```bash
# Clone
cd agentic-rag

# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API key
export OPENAI_API_KEY=sk-...
```

### 2. Run Demo (No Docker)

```bash
cd src
export PYTHONPATH=$PWD

# Run demo with sample documents
python main.py demo
```

### 3. Run with Qdrant (Docker)

```bash
# Start Qdrant + App
docker compose up -d

# Access:
# - API: http://localhost:8001/docs
# - Qdrant Dashboard: http://localhost:6333/dashboard
```

## API Usage

### Query RAG

```bash
# Agentic RAG (self-correcting)
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is retrieval augmented generation?",
    "use_agentic": true,
    "evaluate": true
  }'
```

### Response

```json
{
  "query_id": "abc123",
  "question": "What is retrieval augmented generation?",
  "answer": "RAG is a technique that enhances LLMs by...",
  "sources": [
    {"content": "RAG combines retrieval with...", "metadata": {...}}
  ],
  "pipeline_used": "agentic",
  "iterations": 1,
  "was_grounded": true,
  "evaluation": {
    "faithfulness": 0.95,
    "answer_relevancy": 0.88,
    "context_precision": 0.92,
    "context_recall": 0.85,
    "overall_score": 0.90
  }
}
```

### Ingest Documents

```bash
# Ingest texts
curl -X POST http://localhost:8001/ingest/texts \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["Document 1 content...", "Document 2 content..."],
    "source": "api"
  }'

# Ingest file (PDF, MD, TXT)
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf"
```

### Evaluate Responses

```bash
curl -X POST http://localhost:8001/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "questions": ["What is X?"],
    "answers": ["X is..."],
    "contexts": [["Context about X..."]]
  }'
```

## Project Structure

```
agentic-rag/
├── src/
│   ├── rag/
│   │   ├── pipeline.py      # LangGraph agentic RAG
│   │   └── vector_store.py  # Qdrant/Chroma abstraction
│   ├── evaluation/
│   │   └── ragas_eval.py    # RAGAS-style metrics
│   └── main.py              # FastAPI application
├── tests/
├── docker-compose.yml       # Qdrant + App
├── Dockerfile
├── requirements.txt
└── README.md
```

## RAGAS Evaluation Metrics

| Metric | Description | What it measures |
|--------|-------------|------------------|
| **Faithfulness** | Is answer grounded in context? | Reduces hallucinations |
| **Answer Relevancy** | Does answer address question? | Response quality |
| **Context Precision** | Are retrieved docs relevant? | Retrieval quality |
| **Context Recall** | Did we get all needed info? | Retrieval completeness |

### Interpretation Guide

| Score | Quality |
|-------|---------|
| > 0.85 | Excellent |
| 0.70-0.85 | Good |
| 0.50-0.70 | Needs improvement |
| < 0.50 | Poor |

## Agentic RAG Features

### 1. Query Rewriting
Optimizes user questions for better retrieval:
- Expands abbreviations
- Adds technical terms
- Makes context explicit

### 2. Relevance Grading
Filters retrieved documents:
- Scores each document (0-1)
- Removes irrelevant content
- Falls back to web search if no good docs

### 3. Hallucination Checking
Ensures answer is grounded:
- Extracts claims from answer
- Verifies each against context
- Regenerates if not grounded (max 2 tries)

### 4. Self-Correction Loop
Automatic improvement:
- Detects low-quality responses
- Tries alternative strategies
- Returns best result

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Vector Store (choose one)
VECTOR_PROVIDER=qdrant  # or "chroma"
QDRANT_URL=http://localhost:6333
COLLECTION_NAME=knowledge_base

# Optional
MODEL_NAME=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

## Comparison: Agentic vs Simple RAG

| Feature | Simple RAG | Agentic RAG |
|---------|------------|-------------|
| Query processing | Direct | Rewritten |
| Document filtering | None | Relevance grading |
| Hallucination check | None | Yes |
| Self-correction | None | Up to 2 retries |
| Web fallback | None | Yes |
| Typical accuracy | 70-80% | 85-95% |

## Extending

### Add Custom Retrieval Strategy

```python
# In src/rag/pipeline.py

def hybrid_retrieve(self, state: RAGState) -> dict:
    """Combine vector + keyword search"""
    # Implement BM25 + vector hybrid
    pass

# Add to graph
workflow.add_node("hybrid_retrieve", rag.hybrid_retrieve)
```

### Add Custom Evaluation Metric

```python
# In src/evaluation/ragas_eval.py

def evaluate_safety(self, answer: str) -> float:
    """Check for harmful content"""
    pass
```

## Key Technologies

| Category | Technology |
|----------|------------|
| **Orchestration** | LangGraph |
| **Vector DB** | Qdrant (primary), ChromaDB (fallback) |
| **LLM** | OpenAI GPT-4o-mini |
| **Embeddings** | text-embedding-3-small |
| **Evaluation** | RAGAS-style metrics |
| **API** | FastAPI |

## License

MIT
