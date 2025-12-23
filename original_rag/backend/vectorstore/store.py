"""
Vector Store Abstraction - V3 with FastEmbed
Supports ChromaDB with FastEmbed embeddings (ONNX-based, no PyTorch for embeddings).

Changes from V2:
- Removed TF-based lexical search (moved to HybridRetriever with proper BM25)
- Added FastEmbed support (BAAI/bge-small-en-v1.5)
- Simplified embedding factory
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import uuid

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# EMBEDDING IMPLEMENTATIONS
# =============================================================================

class FastEmbedEmbeddings(Embeddings):
    """
    LangChain-compatible embeddings using FastEmbed.
    
    FastEmbed uses ONNX runtime - no PyTorch dependency required.
    CPU-optimized with true batch processing for fast ingestion.
    
    Recommended models:
    - BAAI/bge-small-en-v1.5: Best quality/speed balance (MTEB 62)
    - all-MiniLM-L6-v2: Fastest (MTEB 56)
    """

    def __init__(
        self, 
        model_name: str = "BAAI/bge-small-en-v1.5",
        batch_size: int = 256,
    ):
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError(
                "fastembed is required. Install with: pip install fastembed"
            )
        
        logger.info(f"Loading FastEmbed model: {model_name}")
        self.model = TextEmbedding(model_name=model_name)
        self.model_name = model_name
        self.batch_size = batch_size
        logger.info(f"FastEmbed model loaded: {model_name}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents with batch processing."""
        if not texts:
            return []
        
        # FastEmbed returns a generator, convert to list
        embeddings = list(self.model.embed(texts, batch_size=self.batch_size))
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist()


class OllamaEmbeddings(Embeddings):
    """
    LangChain-compatible embeddings using Ollama.
    
    Note: Slower than FastEmbed due to HTTP overhead per request.
    Only use if you need a specific Ollama model.
    """

    def __init__(
        self, 
        model_name: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ):
        try:
            from langchain_community.embeddings import OllamaEmbeddings as LCOllamaEmbeddings
        except ImportError:
            raise ImportError(
                "langchain-community is required. Install with: pip install langchain-community"
            )
        
        logger.info(f"Initializing Ollama embeddings: {model_name}")
        self._embeddings = LCOllamaEmbeddings(
            model=model_name,
            base_url=base_url,
        )
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents (slow - HTTP call per text)."""
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self._embeddings.embed_query(text)


class OpenAIEmbeddings(Embeddings):
    """
    LangChain-compatible embeddings using OpenAI API.
    """

    def __init__(
        self, 
        model_name: str = "text-embedding-3-small",
        api_key: str = "",
    ):
        try:
            from langchain_openai import OpenAIEmbeddings as LCOpenAIEmbeddings
        except ImportError:
            raise ImportError(
                "langchain-openai is required. Install with: pip install langchain-openai"
            )
        
        logger.info(f"Initializing OpenAI embeddings: {model_name}")
        self._embeddings = LCOpenAIEmbeddings(
            model=model_name,
            api_key=api_key or settings.openai_api_key,
        )
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents."""
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self._embeddings.embed_query(text)


def create_embeddings() -> Embeddings:
    """
    Factory function to create embeddings based on settings.
    
    Returns:
        Configured Embeddings instance
    """
    provider = settings.embedding_provider
    
    if provider == "fastembed":
        return FastEmbedEmbeddings(
            model_name=settings.fastembed_model,
            batch_size=settings.fastembed_batch_size,
        )
    elif provider == "ollama":
        return OllamaEmbeddings(
            model_name=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url,
        )
    elif provider == "openai":
        return OpenAIEmbeddings(
            model_name=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


# =============================================================================
# DOCUMENT METADATA
# =============================================================================

@dataclass
class DocumentMetadata:
    """Metadata about a document in the vector store."""
    doc_id: str
    name: str
    file_type: str
    size: int
    chunk_count: int
    uploaded_at: str


# =============================================================================
# VECTOR STORE IMPLEMENTATION
# =============================================================================

class ChromaVectorStore:
    """
    ChromaDB vector store implementation.
    
    Features:
    - Lazy initialization of collections
    - Batch embedding with pre-computed vectors
    - Per-collection isolation
    - Document management (list, delete by metadata)
    """
    
    def __init__(self):
        self.embeddings = create_embeddings()
        self._stores: Dict[str, Any] = {}
    
    def _get_store(self, collection_name: str):
        """Get or create a LangChain Chroma store for a collection."""
        if collection_name not in self._stores:
            from langchain_chroma import Chroma
            
            self._stores[collection_name] = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(settings.chroma_path),
            )
            logger.info(f"Initialized ChromaDB collection: {collection_name}")
        
        return self._stores[collection_name]
    
    async def add_documents(
        self,
        documents: List[Document],
        collection_name: str | None = None
    ) -> List[str]:
        """
        Add documents to ChromaDB with batch embedding.
        
        Pre-computes embeddings in batch for efficiency, then adds to ChromaDB.
        """
        import chromadb
        
        collection = collection_name or settings.collection_name
        
        if not documents:
            return []
        
        # Get or create ChromaDB collection directly for batch operations
        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        
        try:
            chroma_collection = client.get_collection(name=collection)
        except Exception:
            chroma_collection = client.create_collection(name=collection)
            logger.info(f"Created new ChromaDB collection: {collection}")
        
        # Extract texts
        texts = [doc.page_content for doc in documents]
        
        # Batch embed all documents at once
        logger.info(f"Batch embedding {len(texts)} documents...")
        embeddings = self.embeddings.embed_documents(texts)
        logger.info(f"Batch embedding complete")
        
        # Prepare data for batch insert
        ids = [str(uuid.uuid4()) for _ in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # Add all at once with pre-computed embeddings
        chroma_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        # Invalidate cached store to pick up new documents
        if collection in self._stores:
            del self._stores[collection]
        
        return ids
    
    async def similarity_search(
        self,
        query: str,
        collection_name: str | None = None,
        k: int = 5
    ) -> List[Document]:
        """Search ChromaDB for similar documents."""
        collection = collection_name or settings.collection_name
        store = self._get_store(collection)
        
        return store.similarity_search(query, k=k)
    
    async def similarity_search_with_score(
        self,
        query: str,
        collection_name: str | None = None,
        k: int = 5
    ) -> List[tuple[Document, float]]:
        """Search ChromaDB with scores."""
        collection = collection_name or settings.collection_name
        store = self._get_store(collection)
        
        return store.similarity_search_with_score(query, k=k)
    
    async def delete_collection(self, collection_name: str) -> None:
        """Delete a ChromaDB collection."""
        import chromadb
        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        try:
            client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Could not delete collection {collection_name}: {e}")
        
        if collection_name in self._stores:
            del self._stores[collection_name]
    
    async def list_collections(self) -> List[str]:
        """List all ChromaDB collections."""
        import chromadb
        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        return [c.name for c in client.list_collections()]
    
    async def delete_by_metadata(
        self,
        collection_name: str,
        metadata_filter: Dict[str, Any]
    ) -> int:
        """Delete documents matching metadata filter. Returns count deleted."""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(name=collection_name)
            
            results = collection.get(where=metadata_filter, include=[])
            count = len(results['ids']) if results['ids'] else 0
            
            if count > 0:
                collection.delete(where=metadata_filter)
                # Invalidate cached store
                if collection_name in self._stores:
                    del self._stores[collection_name]
            
            return count
        except Exception as e:
            logger.error(f"Error deleting by metadata in ChromaDB: {e}")
            return 0
    
    async def list_documents(
        self,
        collection_name: str
    ) -> List[DocumentMetadata]:
        """List unique documents in collection (grouped by doc_id)."""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(name=collection_name)
            
            results = collection.get(include=['metadatas'])
            
            docs_by_id: Dict[str, Dict] = {}
            metadatas = results.get('metadatas', []) or []
            
            for metadata in metadatas:
                if not metadata:
                    continue
                doc_id = metadata.get('doc_id')
                if doc_id and doc_id not in docs_by_id:
                    docs_by_id[doc_id] = {
                        'doc_id': doc_id,
                        'name': metadata.get('source', 'unknown'),
                        'file_type': metadata.get('file_type', 'unknown'),
                        'size': metadata.get('file_size', 0),
                        'chunk_count': 0,
                        'uploaded_at': metadata.get('ingested_at', '')
                    }
                if doc_id:
                    docs_by_id[doc_id]['chunk_count'] += 1
            
            return [
                DocumentMetadata(**doc_data)
                for doc_data in docs_by_id.values()
            ]
        except Exception as e:
            logger.error(f"Error listing documents in ChromaDB: {e}")
            return []
    
    async def get_chunks_by_doc_id(
        self,
        collection_name: str,
        doc_id: str,
        limit: int = 100
    ) -> List[Document]:
        """Get all chunks for a specific document."""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(name=collection_name)
            
            results = collection.get(
                where={"doc_id": doc_id},
                include=['documents', 'metadatas'],
                limit=limit
            )
            
            documents = []
            docs = results.get('documents', []) or []
            metadatas = results.get('metadatas', []) or []
            
            for i, content in enumerate(docs):
                metadata = metadatas[i] if i < len(metadatas) else {}
                documents.append(Document(page_content=content, metadata=metadata or {}))
            
            return documents
        except Exception as e:
            logger.error(f"Error getting chunks by doc_id in ChromaDB: {e}")
            return []
    
    async def get_all_chunks(
        self,
        collection_name: str,
        limit: int = 10000
    ) -> List[Document]:
        """Get all chunks in a collection (for BM25 index building)."""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(name=collection_name)
            
            results = collection.get(
                include=['documents', 'metadatas'],
                limit=limit
            )
            
            documents = []
            docs = results.get('documents', []) or []
            metadatas = results.get('metadatas', []) or []
            
            for i, content in enumerate(docs):
                metadata = metadatas[i] if i < len(metadatas) else {}
                documents.append(Document(page_content=content, metadata=metadata or {}))
            
            return documents
        except Exception as e:
            logger.error(f"Error getting all chunks in ChromaDB: {e}")
            return []
    
    async def get_collection_info(
        self,
        collection_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get collection info. Returns None if doesn't exist, {"count": int} if exists."""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(name=collection_name)
            return {"count": collection.count()}
        except Exception as e:
            logger.debug(f"Collection '{collection_name}' not found or error: {e}")
            return None


def VectorStore() -> ChromaVectorStore:
    """
    Factory function to create the vector store.
    
    Currently only ChromaDB is supported (Qdrant removed for simplicity).
    """
    logger.info("Using ChromaDB vector store with FastEmbed")
    return ChromaVectorStore()
