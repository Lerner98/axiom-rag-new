"""
Hybrid Retriever - Vector + BM25Okapi with RRF Fusion

This module provides production-grade hybrid search that combines:
1. Vector search (semantic similarity via embeddings)
2. BM25Okapi search (keyword/lexical matching)
3. Reciprocal Rank Fusion (RRF) to merge results

Why Hybrid Search?
- Vector search excels at semantic similarity ("car" matches "automobile")
- BM25 excels at exact matches ("Error 504", dates, IDs, acronyms)
- RRF combines both without needing to tune weights

Architecture:
    Query
      │
      ├──► Vector Search (k=20) ──┐
      │                           ├──► RRF Fusion ──► Top 50 ──► Reranker ──► Top 5
      └──► BM25 Search (k=20) ────┘

References:
- BM25Okapi: https://en.wikipedia.org/wiki/Okapi_BM25
- RRF Paper: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
"""
import logging
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class BM25Index:
    """
    BM25 index for a single collection.
    
    Stores the BM25Okapi instance and the original documents
    so we can return Document objects from search results.
    """
    bm25: BM25Okapi
    documents: List[Document]
    doc_count: int = field(init=False)
    
    def __post_init__(self):
        self.doc_count = len(self.documents)


class HybridRetriever:
    """
    Combines vector search (semantic) with BM25 (keyword) using RRF fusion.
    
    This fixes the blind spots of pure vector search:
    - Exact terms, IDs, dates, acronyms
    - Rare words not well-represented in embeddings
    - Technical jargon and domain-specific terms
    
    Usage:
        retriever = HybridRetriever(vector_store)
        
        # Build BM25 index when documents are ingested
        retriever.build_bm25_index("chat_123", documents)
        
        # Search combines vector + BM25
        results = await retriever.search("What is CAP theorem?", "chat_123", k=50)
    """
    
    def __init__(
        self,
        vector_store,
        vector_k: int = 20,
        bm25_k: int = 20,
        rrf_k: int = 60,
    ):
        """
        Initialize the hybrid retriever.
        
        Args:
            vector_store: The vector store instance for semantic search
            vector_k: Number of results to retrieve from vector search
            bm25_k: Number of results to retrieve from BM25 search
            rrf_k: RRF constant (default 60 is standard, higher = more smoothing)
        """
        self.vector_store = vector_store
        self.vector_k = vector_k
        self.bm25_k = bm25_k
        self.rrf_k = rrf_k
        
        # BM25 indices per collection
        self._indices: Dict[str, BM25Index] = {}
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25.
        
        Simple whitespace tokenization with lowercasing.
        For production, consider:
        - Stemming/lemmatization
        - Stop word removal
        - N-grams for phrases
        
        But for RAG, simple tokenization often works well enough
        since we're matching against technical content.
        """
        if not text:
            return []
        return text.lower().split()
    
    def build_bm25_index(
        self,
        collection_name: str,
        documents: List[Document],
    ) -> None:
        """
        Build or rebuild BM25 index for a collection.
        
        Call this when:
        - Documents are first ingested
        - Documents are added to existing collection
        - Documents are deleted (rebuild from remaining)
        
        Args:
            collection_name: Name of the collection
            documents: List of Document objects to index
        """
        if not documents:
            logger.warning(f"No documents to index for {collection_name}")
            return
        
        # Tokenize all documents
        corpus = [self._tokenize(doc.page_content) for doc in documents]
        
        # Build BM25 index
        bm25 = BM25Okapi(corpus)
        
        # Store index with documents
        self._indices[collection_name] = BM25Index(
            bm25=bm25,
            documents=documents,
        )
        
        logger.info(f"Built BM25 index for '{collection_name}': {len(documents)} documents")
    
    def add_to_bm25_index(
        self,
        collection_name: str,
        documents: List[Document],
    ) -> None:
        """
        Add documents to existing BM25 index.
        
        Note: BM25Okapi doesn't support incremental updates,
        so we rebuild the entire index. For large collections,
        consider using a more sophisticated implementation.
        
        Args:
            collection_name: Name of the collection
            documents: New documents to add
        """
        if collection_name in self._indices:
            # Get existing documents and add new ones
            existing_docs = self._indices[collection_name].documents
            all_docs = existing_docs + documents
            self.build_bm25_index(collection_name, all_docs)
        else:
            # No existing index, just build new one
            self.build_bm25_index(collection_name, documents)
    
    def remove_from_bm25_index(
        self,
        collection_name: str,
        doc_ids: List[str],
    ) -> None:
        """
        Remove documents from BM25 index by doc_id.
        
        Args:
            collection_name: Name of the collection
            doc_ids: List of doc_id values to remove
        """
        if collection_name not in self._indices:
            return
        
        # Filter out documents with matching doc_ids
        remaining_docs = [
            doc for doc in self._indices[collection_name].documents
            if doc.metadata.get("doc_id") not in doc_ids
        ]
        
        if remaining_docs:
            self.build_bm25_index(collection_name, remaining_docs)
        else:
            # No documents left, remove index
            del self._indices[collection_name]
            logger.info(f"Removed BM25 index for '{collection_name}' (no documents remaining)")
    
    def clear_bm25_index(self, collection_name: str) -> None:
        """
        Clear BM25 index for a collection.
        
        Call this when a collection is deleted.
        """
        if collection_name in self._indices:
            del self._indices[collection_name]
            logger.info(f"Cleared BM25 index for '{collection_name}'")
    
    def has_bm25_index(self, collection_name: str) -> bool:
        """Check if BM25 index exists for collection."""
        return collection_name in self._indices
    
    def get_bm25_doc_count(self, collection_name: str) -> int:
        """Get number of documents in BM25 index."""
        if collection_name in self._indices:
            return self._indices[collection_name].doc_count
        return 0
    
    def _bm25_search(
        self,
        query: str,
        collection_name: str,
        k: int,
    ) -> List[Tuple[Document, float]]:
        """
        Search using BM25.
        
        Args:
            query: Search query
            collection_name: Collection to search
            k: Number of results to return
            
        Returns:
            List of (Document, score) tuples sorted by score descending
        """
        if collection_name not in self._indices:
            logger.debug(f"No BM25 index for '{collection_name}', returning empty results")
            return []
        
        index = self._indices[collection_name]
        
        # Tokenize query
        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []
        
        # Get BM25 scores for all documents
        scores = index.bm25.get_scores(tokenized_query)
        
        # Pair documents with scores
        scored_docs = list(zip(index.documents, scores))
        
        # Sort by score descending
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k
        return scored_docs[:k]
    
    def _rrf_fusion(
        self,
        vector_results: List[Tuple[Document, float]],
        bm25_results: List[Tuple[Document, float]],
        k: int,
    ) -> List[Tuple[Document, float]]:
        """
        Reciprocal Rank Fusion to combine results from multiple retrievers.
        
        RRF score = sum(1 / (rrf_k + rank_i)) for each result list
        
        Benefits of RRF:
        - No need to normalize scores across different retrievers
        - No weights to tune
        - Robust to outliers
        
        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            k: Number of results to return
            
        Returns:
            Fused results sorted by RRF score
        """
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}
        
        # Score vector results
        for rank, (doc, _score) in enumerate(vector_results):
            # Use chunk_id if available, otherwise hash content
            doc_id = doc.metadata.get("chunk_id") or str(hash(doc.page_content[:200]))
            rrf_score = 1.0 / (self.rrf_k + rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score
            doc_map[doc_id] = doc
        
        # Score BM25 results
        for rank, (doc, _score) in enumerate(bm25_results):
            doc_id = doc.metadata.get("chunk_id") or str(hash(doc.page_content[:200]))
            rrf_score = 1.0 / (self.rrf_k + rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score
            doc_map[doc_id] = doc
        
        # Sort by RRF score descending
        sorted_items = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return top k with documents
        results = []
        for doc_id, score in sorted_items[:k]:
            if doc_id in doc_map:
                results.append((doc_map[doc_id], score))
        
        return results
    
    async def search(
        self,
        query: str,
        collection_name: str,
        k: int = 50,
    ) -> List[Tuple[Document, float]]:
        """
        Hybrid search combining vector and BM25 with RRF fusion.
        
        Args:
            query: Search query
            collection_name: Collection to search
            k: Number of results to return (after fusion)
            
        Returns:
            List of (Document, score) tuples sorted by RRF score
        """
        logger.info(f"Hybrid search: '{query[:50]}...' in '{collection_name}'")
        
        # Vector search
        try:
            vector_results = await self.vector_store.similarity_search_with_score(
                query=query,
                collection_name=collection_name,
                k=self.vector_k,
            )
            logger.debug(f"Vector search returned {len(vector_results)} results")
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            vector_results = []
        
        # BM25 search
        bm25_results = self._bm25_search(
            query=query,
            collection_name=collection_name,
            k=self.bm25_k,
        )
        logger.debug(f"BM25 search returned {len(bm25_results)} results")
        
        # Handle edge cases
        if not vector_results and not bm25_results:
            logger.info("No results from either search method")
            return []
        
        if not vector_results:
            logger.info("Only BM25 results available")
            return bm25_results[:k]
        
        if not bm25_results:
            logger.info("Only vector results available (no BM25 index)")
            return vector_results[:k]
        
        # RRF Fusion
        fused_results = self._rrf_fusion(vector_results, bm25_results, k)
        logger.info(f"RRF fusion returned {len(fused_results)} results")
        
        return fused_results
    
    async def search_with_parent_expansion(
        self,
        query: str,
        collection_name: str,
        initial_k: int = 50,
        final_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Hybrid search with parent chunk expansion.
        
        Flow:
        1. Search child chunks (small, precise vectors)
        2. Deduplicate by parent_id
        3. Replace child content with parent_content from metadata
        4. Return expanded documents
        
        Args:
            query: Search query
            collection_name: Collection to search
            initial_k: Number of results from hybrid search
            final_k: Number of unique parents to return
            
        Returns:
            List of (Document, score) tuples with parent content
        """
        # Get hybrid search results
        results = await self.search(query, collection_name, k=initial_k)
        
        if not results:
            return []
        
        # Deduplicate by parent_id, keeping highest scoring child per parent
        seen_parents: Dict[str, Tuple[Document, float]] = {}
        no_parent_docs: List[Tuple[Document, float]] = []
        
        for doc, score in results:
            parent_id = doc.metadata.get("parent_id")
            
            if parent_id:
                if parent_id not in seen_parents:
                    # Get parent context from metadata
                    parent_context = doc.metadata.get("parent_context", doc.page_content)
                    
                    # Create new document with parent context
                    expanded_doc = Document(
                        page_content=parent_context,
                        metadata={
                            **doc.metadata,
                            "retrieval_score": score,
                            "expanded_from_child": True,
                        }
                    )
                    seen_parents[parent_id] = (expanded_doc, score)
            else:
                # No parent_id - this is either old data or simple chunking
                # Include it but don't deduplicate
                no_parent_docs.append((doc, score))
        
        # Combine parent docs and non-parent docs
        all_docs = list(seen_parents.values()) + no_parent_docs
        
        # Sort by score and return top final_k
        all_docs.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(
            f"Parent expansion: {len(results)} results → "
            f"{len(seen_parents)} unique parents + {len(no_parent_docs)} non-parent docs"
        )
        
        return all_docs[:final_k]


# Singleton instance (initialized lazily in pipeline)
_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever(vector_store=None) -> HybridRetriever:
    """
    Get or create the singleton HybridRetriever instance.
    
    Args:
        vector_store: Vector store instance (required on first call)
        
    Returns:
        HybridRetriever instance
    """
    global _hybrid_retriever
    
    if _hybrid_retriever is None:
        if vector_store is None:
            raise ValueError("vector_store required for first initialization")
        _hybrid_retriever = HybridRetriever(vector_store)
        logger.info("HybridRetriever initialized")
    
    return _hybrid_retriever


def reset_hybrid_retriever() -> None:
    """Reset the singleton (for testing)."""
    global _hybrid_retriever
    _hybrid_retriever = None
