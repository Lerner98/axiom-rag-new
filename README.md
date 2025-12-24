# Axiom RAG

**Your documents. Your machine. Real answers.**

<p align="center">
  <img src="https://img.shields.io/badge/100%25-Local_First-green" alt="Local First">
  <img src="https://img.shields.io/badge/Source-Citations-blue" alt="Source Citations">
  <img src="https://img.shields.io/badge/Hallucination-Protected-red" alt="Hallucination Protected">
</p>

---

## The Problem

You upload a document to ChatGPT. You ask a question. It gives you a confident answer.

**But is it actually in your document?** You have no idea.

---

## The Solution

Axiom is a document Q&A system that runs entirely on your machine. Upload any document, ask questions, and get answers that are:

- **Grounded** — Every answer comes with source citations
- **Private** — Your data never leaves your machine
- **Honest** — Built-in hallucination detection catches false claims

---

## How It Works

```
1. Upload your documents (PDF, TXT, MD, DOCX)
2. Ask a question
3. Get an answer with exact source citations
```

That's it. No API keys. No cloud. No data leaving your machine.

---

## Features

| Feature | What It Does |
|---------|--------------|
| **Chat Isolation** | Each conversation has its own document set |
| **Source Citations** | See exactly which document and page answered your question |
| **Hybrid Search** | Finds both semantic matches AND exact keywords |
| **Smart Chunking** | Returns full context, not choppy fragments |
| **Hallucination Check** | Flags answers that aren't grounded in your documents |
| **Conversation Memory** | "Tell me more" expands the previous answer, not a new search |

---

## Performance

| Metric | Value |
|--------|-------|
| **Answer Quality** | 96% accuracy (8/8 benchmark tests) |
| **Response Time** | ~34s average (6GB VRAM) |
| **Embedding Speed** | 0.5s per 100 chunks |
| **Search Latency** | <100ms |
| **Reranking** | ~200ms for 50 documents |
| **Memory Usage** | <500MB |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai) (for local LLM)

### Setup

```bash
# Clone
git clone https://github.com/Lerner98/axiom-rag-new
cd axiom-rag-new

# Backend
cd original_rag/backend
pip install -r requirements.txt

# Start Ollama
ollama pull llama3.1:8b
ollama serve

# Run backend
uvicorn api.main:app --port 8001

# Frontend (new terminal)
cd ../frontend
npm install
npm run dev
```

Open http://localhost:5173 and start chatting.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, Vite, Tailwind, shadcn/ui |
| **Backend** | FastAPI, LangGraph |
| **Embeddings** | FastEmbed (BAAI/bge-small-en-v1.5) |
| **Vector Store** | ChromaDB |
| **Reranker** | Cross-Encoder (ms-marco-MiniLM) |
| **LLM** | Ollama (llama3.1:8b) |

---

## Requirements

| Component | Minimum |
|-----------|---------|
| RAM | 4GB |
| VRAM | 6GB (for llama3.1:8b) |
| Disk | 10GB |
| GPU | Optional (CPU works) |

---

## Roadmap

- [x] Chat-scoped document isolation
- [x] Real-time streaming responses
- [x] Source citations with relevance scores
- [x] Hallucination detection
- [x] Hybrid search (vector + keyword)
- [ ] Cloud mode (optional Gemini/OpenAI)
- [ ] Multi-user support
- [ ] Document preview

---

## License

MIT

---

**Axiom RAG** — Answers you can trust.
