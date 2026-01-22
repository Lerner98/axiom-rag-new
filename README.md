# Axiom RAG

A local-first document Q&A system with source citations and hallucination detection.

## Overview

Axiom RAG enables question-answering over private documents without sending data to external services. All processing happens locally using Ollama for LLM inference and ChromaDB for vector storage.

### Core Capabilities

- **Document Ingestion**: PDF, TXT, MD, DOCX support with parent-child chunking
- **Hybrid Search**: Vector similarity (FastEmbed) combined with BM25 keyword matching
- **Cross-Encoder Reranking**: Neural reranking for improved relevance
- **Source Citations**: Every answer includes document and page references
- **Hallucination Detection**: Hybrid verification (deterministic + LLM) ensures answers are grounded
- **Session Isolation**: Each chat maintains separate document context
- **Real-time Streaming**: Token-by-token response delivery

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Ollama with `llama3.1:8b` model

### Installation

```bash
git clone https://github.com/Lerner98/axiom-rag-new
cd axiom-rag-new/original_rag

# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --port 8001

# Frontend (separate terminal)
cd ../frontend
npm install
npm run dev

# Ollama (if not running)
ollama pull llama3.1:8b
ollama serve
```

Access the application at `http://localhost:8080`.

## Architecture

| Component | Technology |
|-----------|------------|
| Frontend | React, TypeScript, Vite, Tailwind, shadcn/ui |
| Backend | FastAPI, LangGraph |
| LLM | Ollama (llama3.1:8b) |
| Embeddings | FastEmbed (BAAI/bge-small-en-v1.5) |
| Vector Store | ChromaDB |
| Reranker | Cross-Encoder (ms-marco-MiniLM-L-6-v2) |
| Keyword Search | BM25 (rank-bm25) |

## System Requirements

| Resource | Minimum |
|----------|---------|
| RAM | 4GB |
| VRAM | 6GB |
| Python | 3.11+ |
| Node.js | 18+ |

## Project Structure

```
original_rag/
├── backend/          # FastAPI application
│   ├── api/          # HTTP endpoints
│   ├── rag/          # Pipeline, nodes, retrieval
│   ├── ingest/       # Document processing
│   ├── vectorstore/  # ChromaDB integration
│   └── memory/       # Session storage
├── frontend/         # React application
└── docs/             # Technical documentation
```

## Documentation

Technical documentation is available in `original_rag/docs/`:

- `PROJECT_ARCHITECTURE.md` - System design and component overview
- `RAG_Pipeline_Architecture.md` - Detailed pipeline documentation
- `ENGINEERING_JOURNEY.md` - Optimization history and decisions
- `BENCHMARK_RESULTS.md` - Performance measurements
- `adrs/` - Architecture Decision Records

## License

MIT
