# Axiom RAG

**Chat with your documents. 100% private. Zero setup headaches.**

<p align="center">
  <img src="https://img.shields.io/badge/100%25-Private-green" alt="Private">
  <img src="https://img.shields.io/badge/No-Cloud-blue" alt="No Cloud">
  <img src="https://img.shields.io/badge/No-API_Keys-orange" alt="No API Keys">
</p>

---

## Why Axiom?

**Your documents stay on your machine. Period.**

Other options either:
- **Send your data to the cloud** (ChatGPT, Claude, Gemini)
- **Require technical setup** (LM Studio, Ollama CLI, LocalAI)

Axiom gives you a **clean chat interface** for your documents with everything running locally. No terminal commands after setup. No model configuration. Just upload and ask.

---

## What You Get

- **Complete privacy** — Nothing leaves your machine. Ever.
- **Simple interface** — Upload documents, start chatting. That's it.
- **Source citations** — See exactly where every answer comes from
- **Hallucination detection** — Answers are verified against your documents

---

## Quick Start

```bash
# Clone
git clone https://github.com/Lerner98/axiom-rag-new
cd axiom-rag-new

# Backend
cd original_rag/backend
pip install -r requirements.txt
uvicorn api.main:app --port 8001

# Frontend (new terminal)
cd original_rag/frontend
npm install
npm run dev

# Start Ollama (if not running)
ollama pull llama3.1:8b
ollama serve
```

Open http://localhost:8080 — upload a document and start asking questions.

---

## What's Under the Hood

| Feature | Implementation |
|---------|----------------|
| **Hybrid Search** | Vector (FastEmbed) + BM25 keyword search |
| **Smart Chunking** | Small chunks for search, large context for answers |
| **Cross-Encoder Reranking** | AI scores and picks the most relevant results |
| **Hallucination Check** | Verifies answers are grounded in your documents |
| **3-Layer Intent Router** | Knows greetings from questions, handles follow-ups |
| **Session Isolation** | Each chat stays separate, no context bleed |
| **BM25 Persistence** | Keyword search survives server restarts |
| **Real-time Streaming** | See answers as they're generated |

---

## Requirements

| Component | Minimum |
|-----------|---------|
| RAM | 4GB |
| VRAM | 6GB |
| Python | 3.11+ |
| Node.js | 18+ |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React, TypeScript, Vite, Tailwind, shadcn/ui |
| Backend | FastAPI, LangGraph |
| LLM | Ollama (llama3.1:8b) |
| Vector Store | ChromaDB |
| Embeddings | FastEmbed (BAAI/bge-small-en-v1.5) |
| Reranker | Cross-Encoder (ms-marco-MiniLM) |

---

## Documentation

See [original_rag/docs/](original_rag/docs/) for detailed technical documentation:
- `ENGINEERING_JOURNEY.md` — Full optimization story
- `RAG_Pipeline_Architecture.md` — System architecture
- `BENCHMARK_RESULTS.md` — Performance data

---

**Axiom RAG** — Your documents. Your machine. Your privacy.
