"""
Text Chunker - V2 with Parent-Child Chunking

Parent-Child chunking decouples index chunks from generation chunks:
- CHILD chunks (400 chars): Small, precise vectors for embedding/retrieval
- PARENT chunks (2000 chars): Large, coherent context sent to LLM

Flow:
1. Split document into PARENT chunks (2000 chars)
2. Split each PARENT into CHILD chunks (400 chars)
3. Store parent_context in child metadata (Option A - atomic retrieval)
4. Embed and index CHILD chunks only
5. On retrieval: Search children, expand to parent_context

Benefits:
- +20-30% coherence improvement (research-backed)
- Small chunks = precise vector matching
- Large context = coherent LLM responses
- No separate parent store needed (metadata storage)
"""
import logging
from typing import List, Optional
from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings

logger = logging.getLogger(__name__)


class ParentChildChunker:
    """
    Parent-Child chunker for improved RAG quality.
    
    Embeds small chunks (children) for precise retrieval,
    but returns large chunks (parents) for coherent generation.
    
    Parent context is stored in child metadata for atomic retrieval.
    """
    
    def __init__(
        self,
        parent_chunk_size: int | None = None,
        parent_chunk_overlap: int | None = None,
        child_chunk_size: int | None = None,
        child_chunk_overlap: int | None = None,
    ):
        """
        Initialize the parent-child chunker.
        
        Args:
            parent_chunk_size: Size of parent chunks (default: 2000)
            parent_chunk_overlap: Overlap between parent chunks (default: 200)
            child_chunk_size: Size of child chunks (default: 400)
            child_chunk_overlap: Overlap between child chunks (default: 50)
        """
        self.parent_chunk_size = parent_chunk_size or settings.parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap or settings.parent_chunk_overlap
        self.child_chunk_size = child_chunk_size or settings.child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap or settings.child_chunk_overlap
        
        # Parent splitter - large chunks for context
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=self.parent_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        # Child splitter - small chunks for embedding
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.child_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        logger.info(
            f"ParentChildChunker initialized: "
            f"parent={self.parent_chunk_size}/{self.parent_chunk_overlap}, "
            f"child={self.child_chunk_size}/{self.child_chunk_overlap}"
        )
    
    def chunk(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into parent-child chunks.
        
        Returns CHILD chunks with parent_context in metadata.
        Only child chunks are embedded and indexed.
        
        Args:
            documents: List of documents to chunk
            
        Returns:
            List of child chunks with parent_context in metadata
        """
        if not documents:
            return []
        
        all_children: List[Document] = []
        total_parents = 0
        
        for doc in documents:
            # Step 1: Split into parent chunks
            parent_chunks = self.parent_splitter.split_documents([doc])
            total_parents += len(parent_chunks)
            
            # Step 2: For each parent, create child chunks
            for parent_idx, parent in enumerate(parent_chunks):
                parent_id = str(uuid4())
                parent_content = parent.page_content
                
                # Split parent into children
                # Create a temporary doc for the child splitter
                parent_as_doc = Document(
                    page_content=parent_content,
                    metadata=parent.metadata.copy()
                )
                child_chunks = self.child_splitter.split_documents([parent_as_doc])
                
                # Add parent info to each child's metadata
                for child_idx, child in enumerate(child_chunks):
                    child.metadata['chunk_id'] = str(uuid4())
                    child.metadata['parent_id'] = parent_id
                    child.metadata['parent_context'] = parent_content  # Option A: Store in metadata
                    child.metadata['parent_index'] = parent_idx
                    child.metadata['child_index'] = child_idx
                    child.metadata['total_children'] = len(child_chunks)
                    child.metadata['chunk_size'] = len(child.page_content)
                    child.metadata['parent_size'] = len(parent_content)
                    
                    all_children.append(child)
        
        logger.info(
            f"ParentChildChunker: {len(documents)} docs → "
            f"{total_parents} parents → {len(all_children)} children"
        )
        
        return all_children
    
    def chunk_text(self, text: str, metadata: dict | None = None) -> List[Document]:
        """
        Chunk raw text into parent-child documents.
        
        Args:
            text: Raw text to chunk
            metadata: Optional metadata to attach
            
        Returns:
            List of child chunks with parent_context in metadata
        """
        if not text.strip():
            return []
        
        doc = Document(page_content=text, metadata=metadata or {})
        return self.chunk([doc])


class SimpleChunker:
    """
    Simple chunker without parent-child relationships.
    
    Use this for backward compatibility or when parent-child
    chunking is not needed (e.g., already small documents).
    """
    
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        """
        Initialize simple chunker.
        
        Args:
            chunk_size: Size of chunks (default from settings)
            chunk_overlap: Overlap between chunks (default from settings)
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
    
    def chunk(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks with metadata."""
        if not documents:
            return []
        
        chunks = self.splitter.split_documents(documents)
        
        # Add chunk-specific metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_id'] = str(uuid4())
            chunk.metadata['chunk_index'] = i
            chunk.metadata['total_chunks'] = len(chunks)
            chunk.metadata['chunk_size'] = len(chunk.page_content)
        
        logger.info(f"SimpleChunker: {len(documents)} docs → {len(chunks)} chunks")
        return chunks
    
    def chunk_text(self, text: str, metadata: dict | None = None) -> List[Document]:
        """Chunk raw text into documents."""
        if not text.strip():
            return []
        
        doc = Document(page_content=text, metadata=metadata or {})
        return self.chunk([doc])


# Backward-compatible aliases
TextChunker = ParentChildChunker


def chunk_documents(
    documents: List[Document],
    use_parent_child: bool = True,
    **kwargs
) -> List[Document]:
    """
    Convenience function to chunk documents.
    
    Args:
        documents: Documents to chunk
        use_parent_child: Whether to use parent-child chunking (default: True)
        **kwargs: Additional arguments passed to chunker
        
    Returns:
        List of chunks
    """
    if use_parent_child:
        chunker = ParentChildChunker(**kwargs)
    else:
        chunker = SimpleChunker(**kwargs)
    
    return chunker.chunk(documents)
