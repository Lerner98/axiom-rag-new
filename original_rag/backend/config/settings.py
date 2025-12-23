"""
Agentic RAG - Configuration
Centralized settings with environment variable support.
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # === Application ===
    app_name: str = "Axiom RAG"
    app_version: str = "2.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # === API ===
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8001, env="API_PORT")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS"
    )
    
    # === LLM Provider ===
    llm_provider: Literal["openai", "ollama", "gemini"] = Field(
        default="ollama", env="LLM_PROVIDER"
    )
    
    # OpenAI
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", env="OLLAMA_MODEL")

    # Ollama Performance Tuning
    # KV cache quantization: "f16" (default), "q8_0" (faster, less memory), "q4_0" (fastest)
    ollama_kv_cache_type: str = Field(default="q8_0", env="OLLAMA_KV_CACHE_TYPE")
    # Number of context tokens to keep in cache
    ollama_num_ctx: int = Field(default=4096, env="OLLAMA_NUM_CTX")
    # Enable flash attention for better memory efficiency
    ollama_flash_attention: bool = Field(default=True, env="OLLAMA_FLASH_ATTENTION")
    
    # Gemini
    google_api_key: str = Field(default="", env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")
    
    # === Embeddings ===
    # FastEmbed is the default - ONNX-based, no PyTorch dependency, CPU-optimized
    # Options: fastembed, openai, ollama
    # NOTE: Different providers have different embedding dimensions:
    #   - fastembed (BAAI/bge-small-en-v1.5): 384 dimensions
    #   - fastembed (all-MiniLM-L6-v2): 384 dimensions
    #   - openai (text-embedding-3-small): 1536 dimensions
    #   - ollama (nomic-embed-text): 768 dimensions
    # Switching providers requires re-uploading documents to rebuild embeddings.
    embedding_provider: Literal["fastembed", "openai", "ollama"] = Field(
        default="fastembed", env="EMBEDDING_PROVIDER"
    )
    
    # FastEmbed settings (recommended - no external service, CPU-optimized)
    fastembed_model: str = Field(
        default="BAAI/bge-small-en-v1.5", env="FASTEMBED_MODEL"
    )
    fastembed_batch_size: int = Field(
        default=256, env="FASTEMBED_BATCH_SIZE"
    )
    
    # OpenAI embedding settings
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL"
    )
    
    # Ollama embedding settings (slower, requires Ollama service)
    ollama_embedding_model: str = Field(
        default="nomic-embed-text", env="OLLAMA_EMBEDDING_MODEL"
    )
    
    # === Vector Store ===
    vector_provider: Literal["chroma"] = Field(
        default="chroma", env="VECTOR_PROVIDER"
    )
    chroma_path: Path = Field(default=Path("./data/chroma"), env="CHROMA_PATH")
    collection_name: str = Field(default="knowledge_base", env="COLLECTION_NAME")
    
    # === Memory ===
    memory_backend: Literal["sqlite", "redis"] = Field(
        default="sqlite", env="MEMORY_BACKEND"
    )
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    memory_db_path: Path = Field(default=Path("./data/memory.db"), env="MEMORY_DB_PATH")
    
    # === Chunking (Parent-Child) ===
    # Parent chunks: Large, coherent context sent to LLM
    parent_chunk_size: int = Field(default=2000, env="PARENT_CHUNK_SIZE")
    parent_chunk_overlap: int = Field(default=200, env="PARENT_CHUNK_OVERLAP")
    
    # Child chunks: Small, precise vectors for embedding
    child_chunk_size: int = Field(default=400, env="CHILD_CHUNK_SIZE")
    child_chunk_overlap: int = Field(default=50, env="CHILD_CHUNK_OVERLAP")
    
    # Legacy settings (kept for backward compatibility, use parent/child instead)
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    
    # === Retrieval ===
    # Initial retrieval: Cast a wide net
    retrieval_initial_k: int = Field(default=50, env="RETRIEVAL_INITIAL_K")
    
    # Vector search K (per source in hybrid)
    retrieval_vector_k: int = Field(default=20, env="RETRIEVAL_VECTOR_K")
    
    # BM25 search K (per source in hybrid)
    retrieval_bm25_k: int = Field(default=20, env="RETRIEVAL_BM25_K")
    
    # Final K: After reranking, send this many to LLM
    retrieval_final_k: int = Field(default=5, env="RETRIEVAL_FINAL_K")
    
    # Reranker top N (legacy, use retrieval_final_k)
    rerank_top_n: int = Field(default=5, env="RERANK_TOP_N")
    
    # Legacy top_k (kept for backward compatibility)
    top_k: int = Field(default=5, env="TOP_K")
    
    # Relevance threshold for filtering
    relevance_threshold: float = Field(default=0.3, env="RELEVANCE_THRESHOLD")
    
    # === Self-Correction ===
    max_retries: int = Field(default=2, env="MAX_RETRIES")
    hallucination_threshold: float = Field(default=0.8, env="HALLUCINATION_THRESHOLD")
    
    # === Paths ===
    data_dir: Path = Field(default=Path("./data"), env="DATA_DIR")
    uploads_dir: Path = Field(default=Path("./data/uploads"), env="UPLOADS_DIR")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        if self.vector_provider == "chroma":
            self.chroma_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
