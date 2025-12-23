# Agentic RAG - Project Structure

> **Production-grade scaffold** with proper separation of concerns, ready for Claude Code to implement.

---

## Complete File Structure

```
agentic-rag/
├── src/                              # Backend (Python)
│   ├── api/                          # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                   # App entry, middleware, routes
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── requests.py           # Pydantic request models
│   │   │   └── responses.py          # Pydantic response models
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py               # /chat endpoints with streaming
│   │   │   ├── ingest.py             # /ingest endpoints
│   │   │   └── collections.py        # /collections endpoints
│   │   └── middleware/               # (placeholder for auth)
│   │
│   ├── rag/                          # LangGraph RAG pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py               # Main RAGPipeline class
│   │   ├── state.py                  # RAGState TypedDict
│   │   ├── nodes.py                  # Individual graph nodes
│   │   └── prompts.py                # All LLM prompts
│   │
│   ├── vectorstore/                  # Vector store abstraction
│   │   ├── __init__.py
│   │   └── store.py                  # Qdrant + ChromaDB support
│   │
│   ├── ingest/                       # Document ingestion (placeholder)
│   ├── evaluation/                   # RAGAS metrics (placeholder)
│   ├── memory/                       # Conversation memory (placeholder)
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py               # Pydantic Settings with env vars
│
├── frontend/                         # React + TypeScript
│   ├── src/
│   │   ├── components/               # UI components (placeholder dirs)
│   │   │   ├── chat/
│   │   │   ├── upload/
│   │   │   ├── collections/
│   │   │   ├── ui/
│   │   │   └── layout/
│   │   │
│   │   ├── constants/                # ✅ CENTRALIZED CONSTANTS
│   │   │   ├── index.ts              # Re-exports all
│   │   │   ├── design.ts             # Colors, spacing, typography
│   │   │   ├── api.ts                # Endpoints, config
│   │   │   └── app.ts                # App-wide constants
│   │   │
│   │   ├── types/
│   │   │   └── index.ts              # All TypeScript interfaces
│   │   │
│   │   ├── lib/
│   │   │   ├── index.ts
│   │   │   ├── api.ts                # API client with error handling
│   │   │   └── sse.ts                # Server-Sent Events for streaming
│   │   │
│   │   ├── hooks/
│   │   │   ├── index.ts
│   │   │   ├── useChat.ts            # Chat with streaming
│   │   │   ├── useCollections.ts     # TanStack Query for collections
│   │   │   └── useFileUpload.ts      # File upload with progress
│   │   │
│   │   ├── stores/
│   │   │   ├── index.ts
│   │   │   ├── chatStore.ts          # Zustand chat state
│   │   │   └── uiStore.ts            # Zustand UI state
│   │   │
│   │   └── styles/
│   │       └── globals.css           # Tailwind + custom styles
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── tests/                            # Test directories (placeholder)
│   ├── api/
│   ├── rag/
│   └── e2e/
│
├── docs/                             # Documentation (placeholder)
│
├── docker-compose.yml                # Full stack: API, Qdrant, Redis, Ollama
├── Dockerfile                        # Backend container
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
└── .gitignore
```

---

## Key Design Decisions

### Backend

| Component | Choice | Why |
|-----------|--------|-----|
| Framework | FastAPI | Async, auto-docs, Pydantic |
| RAG Pipeline | LangGraph | State machine, conditional routing |
| Vector Store | Qdrant (primary) | Production-ready, metadata filtering |
| Fallback | ChromaDB | Local development, simpler |
| Streaming | SSE | Browser-native, simpler than WebSocket |
| Config | Pydantic Settings | Type-safe, env var support |

### Frontend

| Component | Choice | Why |
|-----------|--------|-----|
| Framework | React 18 + Vite | Fast, modern, great DX |
| Styling | Tailwind + CSS vars | Utility-first, themeable |
| Server State | TanStack Query | Caching, mutations, refetching |
| Client State | Zustand | Simple, performant |
| Types | TypeScript | Type safety, IDE support |

---

## Separation of Concerns (Frontend)

### Constants (NO hardcoding anywhere else)

```typescript
// ✅ CORRECT: Import from constants
import { colors, spacing, API_ENDPOINTS } from '@/constants';

// ❌ WRONG: Hardcoded values
const primaryColor = '#3b82f6';  // Never do this
```

### State Management Rules

| State Type | Where | Tool |
|------------|-------|------|
| Server data (collections, history) | `hooks/useCollections.ts` | TanStack Query |
| Client UI (sidebar, modals) | `stores/uiStore.ts` | Zustand |
| Chat messages | `stores/chatStore.ts` | Zustand |
| Form state | Component-local | useState |

### Component Rules

1. **Single Responsibility** - One component, one job
2. **Props Down, Events Up** - Data flows down, actions flow up
3. **No inline styles** - Use Tailwind classes or CSS vars
4. **Loading/Error/Empty states** - Every async component needs all 3

---

## What's Implemented vs Placeholder

### ✅ Fully Implemented

| File | What's Done |
|------|-------------|
| `src/config/settings.py` | Complete Pydantic settings |
| `src/api/models/*` | All request/response schemas |
| `src/api/routes/*` | Route structure with placeholder logic |
| `src/api/main.py` | FastAPI app with middleware |
| `src/rag/pipeline.py` | LangGraph workflow structure |
| `src/rag/nodes.py` | All node functions (need LLM integration) |
| `src/rag/prompts.py` | All prompts |
| `src/rag/state.py` | RAGState definition |
| `src/vectorstore/store.py` | Qdrant + Chroma abstraction |
| `frontend/src/constants/*` | All design tokens, API config |
| `frontend/src/types/*` | All TypeScript interfaces |
| `frontend/src/lib/*` | API client, SSE streaming |
| `frontend/src/hooks/*` | useChat, useCollections, useFileUpload |
| `frontend/src/stores/*` | Zustand stores |
| `frontend/src/styles/globals.css` | Tailwind config + custom styles |

### 🔨 Needs Implementation

| Directory | What's Needed |
|-----------|---------------|
| `src/ingest/` | Document loaders, chunking |
| `src/memory/` | Conversation memory (Redis/SQLite) |
| `src/evaluation/` | RAGAS integration |
| `frontend/src/components/*` | Actual UI components |

---

## For Claude Code

### Step 1: Wire Up the Backend

1. Connect RAG pipeline to actual LLM calls
2. Implement document ingestion (`src/ingest/`)
3. Add conversation memory (`src/memory/`)
4. Test with `python -m uvicorn src.api.main:app --reload`

### Step 2: Build the Frontend

1. Create components following the structure
2. Use existing hooks (`useChat`, `useCollections`)
3. Follow constants for all styling
4. Test with `npm run dev`

### Step 3: Integration

1. Test streaming chat
2. Test file upload → ingestion → query
3. Add RAGAS evaluation

---

## Running Locally

```bash
# Backend
cd agentic-rag
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python -m uvicorn src.api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Full Stack (Docker)
docker-compose up
```

---

*This scaffold follows engineering best practices from the knowledge base. Claude Code should read `engineering_thinking_framework.md` before implementing.*
