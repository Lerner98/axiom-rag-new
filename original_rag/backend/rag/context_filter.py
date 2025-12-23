"""
Context Filter - Prevents Context Bleed (ADR-016)

Filters retrieved documents to ensure only relevant content reaches the LLM.
This prevents the "context bleed" issue where previous query context
contaminates answers to new queries.

Usage:
    filter = ContextFilter()
    filtered_docs = filter.filter(documents, query, threshold=0.3)
"""
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy load embeddings
_embeddings = None


def _get_embeddings():
    """Lazy initialization of FastEmbed for similarity checking."""
    global _embeddings
    if _embeddings is None:
        try:
            from fastembed import TextEmbedding
            _embeddings = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("FastEmbed initialized for context filtering")
        except ImportError:
            logger.warning("FastEmbed not available for context filtering")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
    return _embeddings


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import math
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


@dataclass
class FilterResult:
    """Result of context filtering."""
    original_count: int
    filtered_count: int
    removed_count: int
    documents: List[Dict]
    removal_reasons: List[str]


class ContextFilter:
    """
    Filters documents based on relevance to the current query.

    Uses fast embedding similarity to detect documents that don't match
    the current query, preventing "context bleed" from chat history.
    """

    def __init__(
        self,
        relevance_threshold: float = 0.3,
        use_keyword_fallback: bool = True,
    ):
        """
        Args:
            relevance_threshold: Minimum similarity score (0-1) to keep document
            use_keyword_fallback: If embeddings fail, use keyword matching
        """
        self.relevance_threshold = relevance_threshold
        self.use_keyword_fallback = use_keyword_fallback

    def filter(
        self,
        documents: List[Dict],
        query: str,
        threshold: float = None,
    ) -> FilterResult:
        """
        Filter documents by relevance to the query.

        Args:
            documents: List of document dicts with 'content' key
            query: The user's current query
            threshold: Override default threshold

        Returns:
            FilterResult with filtered documents and stats
        """
        if not documents:
            return FilterResult(
                original_count=0,
                filtered_count=0,
                removed_count=0,
                documents=[],
                removal_reasons=[],
            )

        threshold = threshold or self.relevance_threshold
        embeddings = _get_embeddings()

        if embeddings:
            return self._filter_with_embeddings(documents, query, threshold)
        elif self.use_keyword_fallback:
            return self._filter_with_keywords(documents, query, threshold)
        else:
            # No filtering available, return all
            logger.warning("No filtering available, returning all documents")
            return FilterResult(
                original_count=len(documents),
                filtered_count=len(documents),
                removed_count=0,
                documents=documents,
                removal_reasons=[],
            )

    def _filter_with_embeddings(
        self,
        documents: List[Dict],
        query: str,
        threshold: float,
    ) -> FilterResult:
        """Filter using embedding similarity."""
        embeddings = _get_embeddings()

        # Embed the query
        query_embedding = list(embeddings.embed([query]))[0].tolist()

        filtered = []
        removed_reasons = []

        for i, doc in enumerate(documents):
            content = doc.get("content", "")

            # Get content embedding
            doc_embedding = list(embeddings.embed([content[:1000]]))[0].tolist()

            # Compute similarity
            similarity = _cosine_similarity(query_embedding, doc_embedding)

            if similarity >= threshold:
                # Keep document, add similarity score
                doc_copy = dict(doc)
                doc_copy["filter_similarity"] = similarity
                filtered.append(doc_copy)
            else:
                # Remove document
                source = doc.get("metadata", {}).get("source", "unknown")
                removed_reasons.append(
                    f"Doc '{source}' removed (similarity={similarity:.3f} < {threshold})"
                )
                logger.debug(f"Filtered out document: {source} (sim={similarity:.3f})")

        if removed_reasons:
            logger.info(
                f"Context filter: {len(documents)} -> {len(filtered)} docs "
                f"(removed {len(removed_reasons)} irrelevant)"
            )

        return FilterResult(
            original_count=len(documents),
            filtered_count=len(filtered),
            removed_count=len(removed_reasons),
            documents=filtered,
            removal_reasons=removed_reasons,
        )

    def _filter_with_keywords(
        self,
        documents: List[Dict],
        query: str,
        threshold: float,
    ) -> FilterResult:
        """Fallback: filter using keyword overlap."""
        import re

        # Extract significant words from query
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
            'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
            'and', 'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that',
            'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
        }

        query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower())) - stopwords

        if not query_words:
            # Can't filter without keywords
            return FilterResult(
                original_count=len(documents),
                filtered_count=len(documents),
                removed_count=0,
                documents=documents,
                removal_reasons=[],
            )

        filtered = []
        removed_reasons = []

        for doc in documents:
            content = doc.get("content", "").lower()
            doc_words = set(re.findall(r'\b[a-z]{3,}\b', content))

            # Calculate keyword overlap
            overlap = len(query_words & doc_words) / len(query_words) if query_words else 0

            if overlap >= threshold:
                doc_copy = dict(doc)
                doc_copy["filter_keyword_overlap"] = overlap
                filtered.append(doc_copy)
            else:
                source = doc.get("metadata", {}).get("source", "unknown")
                removed_reasons.append(
                    f"Doc '{source}' removed (keyword overlap={overlap:.3f} < {threshold})"
                )

        if removed_reasons:
            logger.info(
                f"Keyword filter: {len(documents)} -> {len(filtered)} docs "
                f"(removed {len(removed_reasons)} irrelevant)"
            )

        return FilterResult(
            original_count=len(documents),
            filtered_count=len(filtered),
            removed_count=len(removed_reasons),
            documents=filtered,
            removal_reasons=removed_reasons,
        )


# Global singleton
_filter = None


def get_context_filter() -> ContextFilter:
    """Get or create singleton context filter."""
    global _filter
    if _filter is None:
        _filter = ContextFilter()
    return _filter


def filter_context(documents: List[Dict], query: str) -> List[Dict]:
    """
    Simple function to filter documents by relevance.

    Returns only the filtered document list.
    """
    filter_obj = get_context_filter()
    result = filter_obj.filter(documents, query)
    return result.documents
