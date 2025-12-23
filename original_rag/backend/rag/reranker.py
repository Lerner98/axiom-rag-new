"""
Cross-Encoder Reranker Module
Provides fast, accurate relevance scoring using cross-encoder models.

This replaces slow LLM-based document grading with a dedicated reranking model
that is 10-50x faster and often more accurate.

SUPPORTED BACKENDS:
1. sentence-transformers (local)
2. Ollama (local, if model supports it)
3. Cohere Rerank API (cloud)
"""
from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
import logging
import asyncio

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Base class for reranker implementations."""
    
    @abstractmethod
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Score query-document pairs for relevance.
        
        Args:
            pairs: List of (query, document) tuples
            
        Returns:
            List of relevance scores (0-1)
        """
        pass
    
    @abstractmethod
    async def rerank(
        self, 
        query: str, 
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: The search query
            documents: List of document texts
            top_k: Return only top_k results (None = all)
            
        Returns:
            List of (original_index, score) tuples, sorted by score descending
        """
        pass


class CrossEncoderReranker(BaseReranker):
    """
    Cross-encoder reranker using sentence-transformers.
    
    Recommended models:
    - 'cross-encoder/ms-marco-MiniLM-L-6-v2' (fast, good quality)
    - 'cross-encoder/ms-marco-MiniLM-L-12-v2' (better quality)
    - 'BAAI/bge-reranker-base' (multilingual)
    - 'BAAI/bge-reranker-large' (best quality)
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize the cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        self.model_name = model_name
        self._model = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of the model."""
        if self._initialized:
            return
            
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading cross-encoder model: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            self._initialized = True
            logger.info("Cross-encoder model loaded successfully")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for CrossEncoderReranker. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            raise
    
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Score query-document pairs for relevance.
        
        Args:
            pairs: List of (query, document) tuples
            
        Returns:
            List of relevance scores (0-1, normalized)
        """
        self._ensure_initialized()
        
        # Run in executor to not block async loop
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self._model.predict(pairs)
        )

        # Normalize scores to 0-1 range
        # ms-marco models output logits (-10 to +10 typically)
        # Using min-max normalization to spread scores across 0-1 range
        # This gives more meaningful relevance percentages for display
        import numpy as np
        scores_arr = np.array(scores)

        if len(scores_arr) > 1:
            # Min-max normalization across the batch
            min_score = scores_arr.min()
            max_score = scores_arr.max()
            if max_score > min_score:
                normalized = (scores_arr - min_score) / (max_score - min_score)
            else:
                normalized = np.ones_like(scores_arr) * 0.5
        else:
            # Single document - use sigmoid for absolute scoring
            normalized = 1 / (1 + np.exp(-scores_arr))

        return normalized.tolist()
    
    async def rerank(
        self, 
        query: str, 
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: The search query
            documents: List of document texts
            top_k: Return only top_k results (None = all)
            
        Returns:
            List of (original_index, score) tuples, sorted by score descending
        """
        if not documents:
            return []
        
        # Create pairs
        pairs = [(query, doc) for doc in documents]
        
        # Get scores
        scores = await self.predict(pairs)
        
        # Create indexed scores and sort
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k if specified
        if top_k is not None:
            indexed_scores = indexed_scores[:top_k]
        
        return indexed_scores


class OllamaReranker(BaseReranker):
    """
    Reranker using Ollama with a model that supports scoring.
    
    Note: This is a workaround - most Ollama models don't have native
    reranking support. We use a prompt-based approach which is slower
    but works with any model.
    """
    
    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama reranker.
        
        Args:
            model_name: Ollama model name
            base_url: Ollama API base URL
        """
        self.model_name = model_name
        self.base_url = base_url
        self._client = None
    
    def _ensure_initialized(self):
        """Lazy initialization."""
        if self._client is not None:
            return
            
        try:
            from langchain_community.chat_models import ChatOllama
            self._client = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0
            )
        except ImportError:
            raise ImportError(
                "langchain-community is required for OllamaReranker. "
                "Install with: pip install langchain-community"
            )
    
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Score query-document pairs using Ollama.
        
        This is slower than a dedicated cross-encoder but works with any model.
        """
        self._ensure_initialized()
        
        scores = []
        for query, doc in pairs:
            prompt = f"""Rate the relevance of this document to the query on a scale of 0-10.
            
Query: {query}

Document: {doc[:500]}

Respond with ONLY a number from 0-10."""
            
            try:
                response = await self._client.ainvoke(prompt)
                score_text = response.content.strip()
                # Extract number from response
                import re
                numbers = re.findall(r'\d+(?:\.\d+)?', score_text)
                if numbers:
                    score = float(numbers[0]) / 10.0  # Normalize to 0-1
                    scores.append(min(max(score, 0), 1))  # Clamp to 0-1
                else:
                    scores.append(0.5)  # Default score if parsing fails
            except Exception as e:
                logger.warning(f"Ollama reranker failed for pair: {e}")
                scores.append(0.5)
        
        return scores
    
    async def rerank(
        self, 
        query: str, 
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []
        
        pairs = [(query, doc) for doc in documents]
        scores = await self.predict(pairs)
        
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        if top_k is not None:
            indexed_scores = indexed_scores[:top_k]
        
        return indexed_scores


class CohereReranker(BaseReranker):
    """
    Reranker using Cohere's Rerank API.
    
    Pros:
    - Very high quality
    - No local compute needed
    
    Cons:
    - Requires API key
    - Has usage costs
    - Adds network latency
    """
    
    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        """
        Initialize Cohere reranker.
        
        Args:
            api_key: Cohere API key
            model: Rerank model name
        """
        self.api_key = api_key
        self.model = model
        self._client = None
    
    def _ensure_initialized(self):
        """Lazy initialization."""
        if self._client is not None:
            return
            
        try:
            import cohere
            self._client = cohere.Client(self.api_key)
        except ImportError:
            raise ImportError(
                "cohere is required for CohereReranker. "
                "Install with: pip install cohere"
            )
    
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Score query-document pairs using Cohere Rerank.
        
        Note: Cohere API expects a single query with multiple docs,
        so we batch by query.
        """
        self._ensure_initialized()
        
        if not pairs:
            return []
        
        # Cohere expects single query, multiple docs
        # For simplicity, we assume all pairs have the same query
        query = pairs[0][0]
        documents = [doc for _, doc in pairs]
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                return_documents=False
            )
        )
        
        # Map scores back to original order
        scores = [0.0] * len(pairs)
        for result in response.results:
            scores[result.index] = result.relevance_score
        
        return scores
    
    async def rerank(
        self, 
        query: str, 
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """Rerank documents using Cohere API."""
        self._ensure_initialized()
        
        if not documents:
            return []
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=False
            )
        )
        
        return [(r.index, r.relevance_score) for r in response.results]


def create_reranker(
    backend: str = "cross-encoder",
    model_name: Optional[str] = None,
    **kwargs
) -> BaseReranker:
    """
    Factory function to create a reranker.
    
    Args:
        backend: One of "cross-encoder", "ollama", "cohere"
        model_name: Model name (backend-specific)
        **kwargs: Additional backend-specific arguments
    
    Returns:
        Configured reranker instance
    """
    if backend == "cross-encoder":
        return CrossEncoderReranker(
            model_name=model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
    elif backend == "ollama":
        return OllamaReranker(
            model_name=model_name or "llama3.1:8b",
            base_url=kwargs.get("base_url", "http://localhost:11434")
        )
    elif backend == "cohere":
        if "api_key" not in kwargs:
            raise ValueError("Cohere reranker requires api_key")
        return CohereReranker(
            api_key=kwargs["api_key"],
            model=model_name or "rerank-english-v3.0"
        )
    else:
        raise ValueError(f"Unknown reranker backend: {backend}")
