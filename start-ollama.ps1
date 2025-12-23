# Optimized Ollama Startup for RAG Pipeline
# Run this before starting the backend to ensure performance settings are active

$env:OLLAMA_FLASH_ATTENTION="true"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_NUM_CTX="4096"

Write-Host "Stopping existing Ollama processes..." -ForegroundColor Yellow
Stop-Process -Name "ollama" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "Starting Ollama with optimized settings:" -ForegroundColor Cyan
Write-Host "  FLASH_ATTENTION = true"
Write-Host "  KV_CACHE_TYPE   = q8_0"
Write-Host "  NUM_CTX         = 4096"

ollama serve
