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

Axiom gives you a **clean chat interface** for your documents with everything running locally. No terminal commands. No model configuration. Just upload and ask.

---

## What You Get

- **Complete privacy** — Nothing leaves your machine. Ever.
- **Simple interface** — Upload documents, start chatting. That's it.
- **Source citations** — See exactly where every answer comes from
- **Accurate answers** — 96% quality score on our benchmark tests

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

Open http://localhost:5173 — upload a document and start asking questions.

---

## Performance

| Metric | Value |
|--------|-------|
| **Answer Quality** | 96% accuracy |
| **Response Time** | ~34s (6GB VRAM) |
| **Search** | <100ms |
| **Memory** | <500MB |

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
| Frontend | React, TypeScript, Tailwind |
| Backend | FastAPI, LangGraph |
| LLM | Ollama (llama3.1:8b) |
| Vector Store | ChromaDB |
| Embeddings | FastEmbed |

---

## Roadmap

- [x] Private local chat with documents
- [x] Source citations
- [x] Real-time streaming
- [x] Chat-scoped document isolation
- [ ] Optional cloud mode (for users who want it)
- [ ] Multi-user support

---

**Axiom RAG** — Your documents. Your machine. Your privacy.
