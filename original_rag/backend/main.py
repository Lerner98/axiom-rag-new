"""
Agentic RAG - Main Entry Point
Run with: python main.py
"""
import uvicorn
from config.settings import settings

if __name__ == "__main__":
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"API docs: http://{settings.api_host}:{settings.api_port}/docs")

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
