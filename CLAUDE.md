# CLAUDE.md - RAG Pipeline Configuration

## Current Baseline (6GB VRAM)
| Metric | Value | Status |
|--------|-------|--------|
| Model | llama3.1:8b (4.9GB) | Active |
| Quality | 96% avg | PASS |
| Pass Rate | 8/8 tests | PASS |
| Latency | ~34s avg | NEEDS WORK |

## Critical Rules

1. **LLMLingua Compression**: DISABLED for context < 2000 tokens
   - Overhead (14s) exceeds prefill savings at small context sizes
   - Code preserved in `context_compressor.py` for future large-context use

2. **Session Isolation**: ALWAYS use unique `session_id` per query
   - Prevents memory/context bleed between queries
   - Test script generates: `session-{timestamp}-{random}`

3. **Intent Fallback**: If no chat history exists, force `FOLLOWUP` → `QUESTION`
   - Prevents standalone queries from skipping RAG
   - Fixed in `nodes.py:classify_intent()`

4. **Model Selection**: NEVER use reasoning models (DeepSeek-R1, etc.)
   - `<think>` tags cause 200-350s latency per query
   - Use standard completion models only

## Environment Setup

Required OS-level variables (restart Ollama after setting):
```
OLLAMA_FLASH_ATTENTION=true
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_CTX=4096
```

### PowerShell Startup Script
Save as `start-ollama.ps1` in project root:
```powershell
$env:OLLAMA_FLASH_ATTENTION="true"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_NUM_CTX="4096"
Stop-Process -Name "ollama" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
ollama serve
```

## Commands

```bash
# Run benchmark
node test-quality.js 8001 original_rag

# Start backend
cd original_rag/backend && python -m uvicorn api.main:app --port 8001

# Check Ollama models
ollama list
```

## Latency Optimization Roadmap

Current 34s latency breakdown:
- Pipeline (intent, retrieval, rerank): ~2s (6%)
- LLM Prefill (context processing): ~25s (73%)
- LLM Generation (tokens out): ~7s (21%)

### Planned Optimizations (Not Yet Implemented)

1. **Semantic Caching** - <100ms for repeat/similar queries
   - Embed query, check similarity to cached Q&A pairs
   - Bypass LLM entirely for >0.95 similarity matches

2. **Adaptive Context Size** - Reduce prefill for simple queries
   - Simple queries: 2-3 docs instead of 5
   - Complex queries: keep 5 docs

3. **Query-Adaptive Model Routing** - Faster model for simple queries
   - Simple/short: use smaller model (if available)
   - Complex: use llama3.1:8b

## File Reference

| File | Purpose |
|------|---------|
| `nodes.py` | RAG pipeline nodes, intent fallback fix |
| `context_compressor.py` | LLMLingua (disabled, preserved for future) |
| `context_filter.py` | Prevents context bleed |
| `intent_router.py` | 3-layer hybrid intent classification |
| `test-quality.js` | Benchmark script with session isolation |
