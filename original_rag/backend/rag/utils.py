"""
RAG Utility Functions
Provides helper functions for document processing.
"""
import re
from typing import Optional


# Common English stopwords to ignore in query matching
STOPWORDS = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
    'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
    'you', 'your', 'yours', 'yourself', 'yourselves',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
    'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
    'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
    'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under',
    'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
    'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 's', 't', 'just', 'don', 'now',
})


def extract_query_terms(query: str) -> list[str]:
    """
    Extract meaningful terms from a query, removing stopwords.

    Args:
        query: The search query

    Returns:
        List of lowercase query terms (excluding stopwords)
    """
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\w+', query.lower())
    # Filter out stopwords and very short words
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def extract_relevant_snippet(
    query: str,
    content: str,
    max_length: int = 300,
    context_chars: int = 100
) -> str:
    """
    Extract the most relevant snippet from content based on query terms.

    This is a fast, pure-Python implementation that:
    1. Finds sentences containing query terms
    2. Scores sentences by term match count
    3. Returns the highest-scoring sentence
    4. Falls back to context around first match if no sentences found

    Performance: Sub-millisecond for typical document chunks (<10KB)

    Args:
        query: The search query
        content: Document content to extract snippet from
        max_length: Maximum length of returned snippet
        context_chars: Characters of context around matches (for fallback)

    Returns:
        Most relevant snippet from content
    """
    if not content or not query:
        return content[:max_length] if content else ""

    query_terms = extract_query_terms(query)

    if not query_terms:
        # No meaningful query terms, return start of content
        return _truncate(content, max_length)

    # Try sentence-based extraction first
    snippet = _find_best_sentence(content, query_terms, max_length)

    if snippet:
        return snippet

    # Fallback: Find context around first query term match
    snippet = _find_term_context(content, query_terms, max_length, context_chars)

    if snippet:
        return snippet

    # Ultimate fallback: return start of content
    return _truncate(content, max_length)


def _find_best_sentence(content: str, query_terms: list[str], max_length: int) -> Optional[str]:
    """Find the sentence with the most query term matches."""
    # Split into sentences (handles periods, exclamation, question marks, newlines)
    # Also handles bullet points and numbered lists
    sentences = re.split(r'[.!?\n]+|\s*[-•]\s*|\s*\d+[.)]\s*', content)

    best_sentence = ""
    best_score = 0

    content_lower = content.lower()

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:  # Skip very short fragments
            continue

        sentence_lower = sentence.lower()

        # Count query term matches
        score = sum(1 for term in query_terms if term in sentence_lower)

        # Bonus for exact phrase matches (consecutive terms)
        if len(query_terms) >= 2:
            for i in range(len(query_terms) - 1):
                phrase = f"{query_terms[i]} {query_terms[i+1]}"
                if phrase in sentence_lower:
                    score += 0.5  # Bonus for phrase match

        if score > best_score:
            best_score = score
            best_sentence = sentence

    if best_score > 0 and best_sentence:
        return _truncate(best_sentence, max_length)

    return None


def _find_term_context(
    content: str,
    query_terms: list[str],
    max_length: int,
    context_chars: int
) -> Optional[str]:
    """Find context around the first query term match."""
    content_lower = content.lower()

    # Find first matching term position
    first_match_pos = -1
    for term in query_terms:
        pos = content_lower.find(term)
        if pos != -1 and (first_match_pos == -1 or pos < first_match_pos):
            first_match_pos = pos

    if first_match_pos == -1:
        return None

    # Extract context around the match
    start = max(0, first_match_pos - context_chars)
    end = min(len(content), first_match_pos + context_chars + len(query_terms[0]))

    snippet = content[start:end].strip()

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return _truncate(snippet, max_length)


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    text = text.strip()
    if len(text) <= max_length:
        return text

    # Try to break at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')

    if last_space > max_length * 0.7:  # Don't cut too much
        truncated = truncated[:last_space]

    return truncated.rstrip() + "..."
