# Axiom RAG - Backend & Frontend

This directory contains the complete Axiom RAG application.

## Directory Structure

```
original_rag/
├── backend/           # Python FastAPI application
├── frontend/          # React TypeScript application
├── docs/              # Technical documentation
├── RAG_Scale_Tests/   # Test documents for scale testing
├── Toonify/           # Utility scripts
└── archive/           # Historical files
```

## Running the Application

### Backend (Port 8001)

```bash
cd backend
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend (Port 8080)

```bash
cd frontend
npm install
npm run dev
```

### Ollama (Port 11434)

```bash
ollama pull llama3.1:8b
ollama serve
```

The frontend will be available at `http://localhost:8080`.

## Backend Architecture

### Core Modules

| Module | Purpose |
|--------|---------|
| `api/` | FastAPI routes, request/response handling |
| `rag/` | Pipeline orchestration, nodes, intent routing |
| `ingest/` | Document parsing, chunking, embedding |
| `vectorstore/` | ChromaDB operations, hybrid search |
| `memory/` | SQLite/Redis session storage |
| `config/` | Application settings |

### RAG Pipeline Flow

```
Query → Intent Classification → [Non-RAG Handler | RAG Path]
                                        ↓
                              Query Routing (simple/complex)
                                        ↓
                              Hybrid Retrieval (Vector + BM25)
                                        ↓
                              Parent Expansion
                                        ↓
                              Context Filter
                                        ↓
                              Cross-Encoder Reranking
                                        ↓
                              LLM Generation
                                        ↓
                              Hallucination Check
                                        ↓
                              Response + Citations
```

### Key Implementation Details

**Intent Router**: 3-layer classification (hard rules → semantic similarity → LLM fallback) that routes greetings and follow-ups without invoking the full RAG pipeline.

**Hybrid Search**: Combines FastEmbed vector search with BM25 keyword matching using Reciprocal Rank Fusion (RRF). Handles both semantic queries and exact term matching.

**Parent-Child Chunking**: Small chunks (400 chars) for precise retrieval, expanded to parent context (2000 chars) before LLM generation.

**Hallucination Detection**: Fast deterministic check (word/trigram overlap) with LLM fallback for ambiguous cases.

## Frontend Architecture

React application with TypeScript, Vite, Tailwind CSS, and shadcn/ui components.

### Key Features

- Chat interface with streaming responses
- Document upload with drag-and-drop
- Source citation display with relevance scores
- Session management (create, rename, delete chats)
- Responsive sidebar with chat history

## Configuration

Backend configuration via environment variables or `config/settings.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | ollama | LLM backend (ollama) |
| `OLLAMA_MODEL` | llama3.1:8b | Model for generation |
| `EMBEDDING_PROVIDER` | fastembed | Embedding backend |
| `VECTOR_PROVIDER` | chroma | Vector store |
| `MEMORY_BACKEND` | sqlite | Session storage |

## Docker Deployment

```bash
cd backend
docker-compose up -d
```

See `docs/DOCKER_DEPLOYMENT.md` for detailed instructions.

## Documentation

| Document | Description |
|----------|-------------|
| `docs/PROJECT_ARCHITECTURE.md` | System design overview |
| `docs/RAG_Pipeline_Architecture.md` | Detailed pipeline documentation |
| `docs/ENGINEERING_JOURNEY.md` | Optimization decisions and history |
| `docs/BENCHMARK_RESULTS.md` | Performance measurements |
| `docs/adrs/` | Architecture Decision Records |
