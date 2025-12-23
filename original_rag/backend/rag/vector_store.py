"""
Vector Store Setup - Qdrant (primary) or ChromaDB (fallback)
Supports: Local, Docker, or Qdrant Cloud
"""
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

@dataclass
class VectorStoreConfig:
    """Configuration for vector store"""
    provider: str = "qdrant"  # "qdrant" or "chroma"
    collection_name: str = "documents"
    embedding_model: str = "text-embedding-3-small"
    
    # Qdrant settings
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    
    # Chroma settings (fallback)
    chroma_persist_dir: str = "./chroma_db"

class VectorStoreManager:
    """Unified interface for vector store operations"""
    
    def __init__(self, config: VectorStoreConfig = None):
        self.config = config or VectorStoreConfig()
        self.embeddings = OpenAIEmbeddings(model=self.config.embedding_model)
        self.store = None
        
    def initialize(self) -> None:
        """Initialize vector store based on config"""
        if self.config.provider == "qdrant":
            self.store = self._init_qdrant()
        else:
            self.store = self._init_chroma()
    
    def _init_qdrant(self):
        """Initialize Qdrant vector store"""
        try:
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            # Connect to Qdrant
            if self.config.qdrant_api_key:
                client = QdrantClient(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key
                )
            else:
                client = QdrantClient(url=self.config.qdrant_url)
            
            # Create collection if not exists
            collections = [c.name for c in client.get_collections().collections]
            
            if self.config.collection_name not in collections:
                client.create_collection(
                    collection_name=self.config.collection_name,
                    vectors_config=VectorParams(
                        size=1536,  # text-embedding-3-small dimension
                        distance=Distance.COSINE
                    )
                )
                print(f"✓ Created Qdrant collection: {self.config.collection_name}")
            
            store = QdrantVectorStore(
                client=client,
                collection_name=self.config.collection_name,
                embedding=self.embeddings
            )
            
            print(f"✓ Connected to Qdrant: {self.config.qdrant_url}")
            return store
            
        except Exception as e:
            print(f"⚠ Qdrant failed ({e}), falling back to ChromaDB")
            return self._init_chroma()
    
    def _init_chroma(self):
        """Initialize ChromaDB vector store (fallback)"""
        from langchain_chroma import Chroma
        
        store = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.config.chroma_persist_dir
        )
        
        print(f"✓ ChromaDB initialized: {self.config.chroma_persist_dir}")
        return store
    
    def add_documents(self, documents: List[Document], batch_size: int = 100) -> int:
        """Add documents to vector store in batches"""
        if not self.store:
            self.initialize()
        
        total_added = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            self.store.add_documents(batch)
            total_added += len(batch)
            print(f"  Added {total_added}/{len(documents)} documents")
        
        return total_added
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        batch_size: int = 100
    ) -> int:
        """Add texts directly to vector store"""
        if not self.store:
            self.initialize()
        
        documents = [
            Document(
                page_content=text,
                metadata=metadatas[i] if metadatas else {}
            )
            for i, text in enumerate(texts)
        ]
        
        return self.add_documents(documents, batch_size)
    
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None
    ) -> List[Document]:
        """Search for similar documents"""
        if not self.store:
            self.initialize()
        
        return self.store.similarity_search(query, k=k, filter=filter)
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4
    ) -> List[Tuple[Document, float]]:
        """Search with relevance scores"""
        if not self.store:
            self.initialize()
        
        return self.store.similarity_search_with_score(query, k=k)
    
    def delete_collection(self) -> None:
        """Delete the collection"""
        if self.config.provider == "qdrant":
            from qdrant_client import QdrantClient
            client = QdrantClient(url=self.config.qdrant_url)
            client.delete_collection(self.config.collection_name)
        else:
            import shutil
            if os.path.exists(self.config.chroma_persist_dir):
                shutil.rmtree(self.config.chroma_persist_dir)
        
        print(f"✓ Deleted collection: {self.config.collection_name}")
    
    def get_stats(self) -> dict:
        """Get collection statistics"""
        if self.config.provider == "qdrant":
            from qdrant_client import QdrantClient
            client = QdrantClient(url=self.config.qdrant_url)
            info = client.get_collection(self.config.collection_name)
            return {
                "provider": "qdrant",
                "collection": self.config.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count
            }
        else:
            # ChromaDB stats
            return {
                "provider": "chroma",
                "collection": self.config.collection_name,
                "count": len(self.store.get()["ids"]) if self.store else 0
            }


# Document loaders and chunking
class DocumentProcessor:
    """Process and chunk documents for ingestion"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_and_chunk(self, file_path: str) -> List[Document]:
        """Load file and split into chunks"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # Determine file type and load
        if file_path.endswith(".pdf"):
            docs = self._load_pdf(file_path)
        elif file_path.endswith(".md"):
            docs = self._load_markdown(file_path)
        elif file_path.endswith(".txt"):
            docs = self._load_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        # Chunk
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = splitter.split_documents(docs)
        
        # Add chunk metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        
        return chunks
    
    def _load_pdf(self, path: str) -> List[Document]:
        """Load PDF file"""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(path)
            return loader.load()
        except ImportError:
            print("Install pypdf: pip install pypdf")
            return []
    
    def _load_markdown(self, path: str) -> List[Document]:
        """Load Markdown file"""
        from langchain_community.document_loaders import TextLoader
        loader = TextLoader(path)
        return loader.load()
    
    def _load_text(self, path: str) -> List[Document]:
        """Load plain text file"""
        from langchain_community.document_loaders import TextLoader
        loader = TextLoader(path)
        return loader.load()
    
    def chunk_texts(self, texts: List[str], source: str = "manual") -> List[Document]:
        """Chunk raw texts into documents"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        documents = []
        for i, text in enumerate(texts):
            chunks = splitter.split_text(text)
            for j, chunk in enumerate(chunks):
                documents.append(Document(
                    page_content=chunk,
                    metadata={
                        "source": source,
                        "text_index": i,
                        "chunk_index": j
                    }
                ))
        
        return documents
