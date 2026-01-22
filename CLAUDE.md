# CLAUDE.md - Axiom RAG Project Configuration

## Prime Directives

### Git Safety
- NEVER use `git diff --reset`, `git checkout .`, or destructive git commands without explicit approval
- NEVER include co-authored-by lines or Claude Code attribution in commits
- Understand code by reading it directly, not by trusting commit history blindly
- Always stage specific files, never use `git add -A` or `git add .`

### Code Quality
- Read existing code before modifying
- No over-engineering or speculative features
- Fix only what is requested
- Keep solutions minimal and focused

## Project Structure

```
Toon/
├── original_rag/           # Main application
│   ├── backend/            # FastAPI + RAG pipeline
│   ├── frontend/           # React + TypeScript
│   └── docs/               # Technical documentation
└── ARCHIVED/               # Deprecated files
```

## Quick Commands

```bash
# Start backend (port 8001)
cd original_rag/backend && python -m uvicorn api.main:app --port 8001

# Start frontend (port 8080)
cd original_rag/frontend && npm run dev

# Run benchmark
node test-quality.js 8001 original_rag

# Check Ollama models
ollama list
```

## Environment Setup

Required Ollama variables (restart Ollama after setting):

```
OLLAMA_FLASH_ATTENTION=true
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_CTX=4096
```

PowerShell startup script (`start-ollama.ps1`):

```powershell
$env:OLLAMA_FLASH_ATTENTION="true"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_NUM_CTX="4096"
Stop-Process -Name "ollama" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
ollama serve
```

## Documentation

- [original_rag/README.md](original_rag/README.md) - Developer reference
- [original_rag/docs/](original_rag/docs/) - Architecture and pipeline docs
- [original_rag/CLAUDE.md](original_rag/CLAUDE.md) - RAG-specific configuration
