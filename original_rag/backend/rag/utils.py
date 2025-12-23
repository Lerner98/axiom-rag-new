"""
RAG Utility Functions - Elite Snippet Extraction

Provides query-aware snippet extraction that finds the most relevant
part of a document to show in source previews.

Strategy (in priority order):
1. Key-Value patterns (Education:, Skills:, etc.) - structured docs
2. Header/Section matching (## Education, Education\n----)
3. Parent context search (higher semantic value)
4. 3-sentence window around best match
5. Fallback to first N chars
"""
import re
from typing import Optional, List, Tuple


# Common English stopwords to ignore in query matching
STOPWORDS = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
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
    'too', 'very', 's', 't', 'just', 'don', 'now', 'tell', 'me', 'about',
})

# Common key-value labels in structured documents (resumes, specs, etc.)
KV_LABELS = [
    'education', 'degree', 'qualification', 'certifications', 'certificate',
    'experience', 'work experience', 'employment', 'work history',
    'skills', 'technical skills', 'technologies', 'tools',
    'languages', 'language', 'programming languages',
    'projects', 'portfolio', 'achievements',
    'summary', 'objective', 'profile', 'about',
    'contact', 'email', 'phone', 'address', 'location',
    'name', 'title', 'role', 'position',
]

# Semantic aliases - query terms that should search for different labels
# e.g., "degree" query should look for "Education" section
LABEL_ALIASES = {
    'degree': ['education', 'qualification', 'certifications'],
    'studied': ['education'],
    'graduated': ['education'],
    'university': ['education'],
    'college': ['education'],
    'school': ['education'],
    'worked': ['experience', 'work experience', 'employment'],
    'job': ['experience', 'work experience'],
    'employed': ['experience', 'employment'],
    'programming': ['skills', 'technical skills', 'languages'],
    'tech': ['skills', 'technical skills', 'technologies'],
    'know': ['skills', 'languages'],
    'contact': ['contact', 'email', 'phone', 'address'],
    'reach': ['contact', 'email', 'phone'],
}


def extract_query_terms(query: str) -> List[str]:
    """Extract meaningful terms from query, removing stopwords."""
    words = re.findall(r'\w+', query.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def extract_query_phrases(query: str) -> List[str]:
    """Extract potential multi-word phrases from query."""
    query_lower = query.lower()
    phrases = []

    # Look for 2-3 word combinations that aren't just stopwords
    words = query_lower.split()
    for i in range(len(words)):
        for length in [3, 2]:  # Try longer phrases first
            if i + length <= len(words):
                phrase = ' '.join(words[i:i+length])
                # Only keep if at least one non-stopword
                phrase_words = phrase.split()
                if any(w not in STOPWORDS for w in phrase_words):
                    phrases.append(phrase)

    return phrases


def _get_labels_to_search(query_terms: List[str]) -> List[str]:
    """
    Get all labels to search for, including semantic aliases.
    e.g., "degree" -> also search for "education", "qualification"
    """
    labels_to_search = set()

    for term in query_terms:
        # Add the term itself if it's a known label
        if term in KV_LABELS:
            labels_to_search.add(term)
        # Add aliased labels
        if term in LABEL_ALIASES:
            labels_to_search.update(LABEL_ALIASES[term])

    return list(labels_to_search)


def find_key_value_match(query: str, content: str, max_length: int = 350) -> Optional[str]:
    """
    Find key-value pattern matches like "Education: Practical Software Engineer..."

    This is the "Golden Snippet" for structured documents.
    """
    query_lower = query.lower()
    query_terms = extract_query_terms(query)

    # Get labels to search including semantic aliases
    # e.g., "degree" query will also search for "education" section
    labels_to_search = _get_labels_to_search(query_terms)

    # Build regex pattern for key-value detection
    # Matches: "Label:" or "Label :" or "Label\n" followed by content
    for label in KV_LABELS:
        # Check if query is asking about this label
        # Match if: label in query, label in expanded search set, or term overlap
        if (label in query_lower or
            label in labels_to_search or
            any(term in label or label in term for term in query_terms)):
            # Pattern: Label followed by colon or newline, then content
            pattern = rf'(?i)(?:^|\n)[\s]*({label}[s]?)[\s]*[:\-\|]?\s*([^\n]+(?:\n(?![A-Z][a-z]+[\s]*[:\-\|])[^\n]+)*)'
            match = re.search(pattern, content)
            if match:
                result = match.group(0).strip()
                # Include a bit more context if short
                if len(result) < 100:
                    # Try to get the next line too
                    end_pos = match.end()
                    next_lines = content[end_pos:end_pos+150].split('\n')
                    if next_lines and next_lines[0].strip():
                        result += '\n' + next_lines[0].strip()
                return _truncate(result, max_length)

    return None


def find_header_section(query: str, content: str, max_length: int = 350) -> Optional[str]:
    """
    Find content under a matching header/section title.

    Handles markdown headers (##), underlined headers, and ALL CAPS headers.
    """
    query_terms = extract_query_terms(query)
    if not query_terms:
        return None

    # Pattern for headers: ## Header, Header\n====, Header\n----, ALL CAPS HEADER
    header_patterns = [
        r'(?:^|\n)(#{1,3})\s*([^\n]+)',  # Markdown headers
        r'(?:^|\n)([^\n]+)\n[=\-]{3,}',   # Underlined headers
        r'(?:^|\n)([A-Z][A-Z\s]{2,}[A-Z])(?:\n|$)',  # ALL CAPS headers
    ]

    for pattern in header_patterns:
        for match in re.finditer(pattern, content):
            header_text = match.group(2) if match.lastindex >= 2 else match.group(1)
            header_lower = header_text.lower().strip()

            # Check if header matches any query term
            if any(term in header_lower for term in query_terms):
                # Extract content after header until next header or max_length
                start_pos = match.end()

                # Find next header
                next_header = re.search(r'\n(?:#{1,3}\s|[A-Z][A-Z\s]{2,}[A-Z]\n|[^\n]+\n[=\-]{3,})', content[start_pos:])
                if next_header:
                    section_content = content[start_pos:start_pos + next_header.start()]
                else:
                    section_content = content[start_pos:start_pos + max_length]

                result = f"{header_text.strip()}\n{section_content.strip()}"
                return _truncate(result, max_length)

    return None


def find_in_parent_context(query: str, parent_context: str, max_length: int = 350) -> Optional[str]:
    """
    Search parent context for relevant content.
    Parent context often has better semantic summary.
    """
    if not parent_context:
        return None

    # Try key-value match in parent first
    kv_match = find_key_value_match(query, parent_context, max_length)
    if kv_match:
        return kv_match

    # Try header section in parent
    header_match = find_header_section(query, parent_context, max_length)
    if header_match:
        return header_match

    # Try phrase/term match with paragraph extraction
    query_phrases = extract_query_phrases(query)
    query_terms = extract_query_terms(query)

    parent_lower = parent_context.lower()

    # Check for phrase matches first
    for phrase in query_phrases:
        if phrase in parent_lower:
            return extract_paragraph_around_match(parent_context, phrase, max_length)

    # Check for term matches
    for term in query_terms:
        if term in parent_lower:
            return extract_paragraph_around_match(parent_context, term, max_length)

    return None


def extract_paragraph_around_match(content: str, search_term: str, max_length: int = 350) -> str:
    """Extract the paragraph containing the search term."""
    content_lower = content.lower()
    pos = content_lower.find(search_term.lower())

    if pos == -1:
        return content[:max_length]

    # Find paragraph boundaries (double newline or single newline with indent change)
    para_start = content.rfind('\n\n', 0, pos)
    para_start = para_start + 2 if para_start != -1 else 0

    para_end = content.find('\n\n', pos)
    para_end = para_end if para_end != -1 else len(content)

    paragraph = content[para_start:para_end].strip()
    return _truncate(paragraph, max_length)


def find_best_sentence_window(query: str, content: str, max_length: int = 350) -> Optional[str]:
    """
    Find the best matching sentence with surrounding context.
    Returns: sentence before + matching sentence + sentence after
    """
    query_terms = extract_query_terms(query)
    query_phrases = extract_query_phrases(query)

    if not query_terms:
        return None

    # Split into sentences
    sentences = split_into_sentences(content)
    if not sentences:
        return None

    # Prioritize terms: longer terms and terms that appear less frequently are more specific
    # This prevents "guy" from dominating over "degree"
    content_lower = content.lower()
    term_frequency = {term: content_lower.count(term) for term in query_terms}

    # Score each sentence
    best_idx = -1
    best_score = 0

    for i, sentence in enumerate(sentences):
        sentence_lower = sentence.lower()
        score = 0

        # Phrase matches worth more
        for phrase in query_phrases:
            if phrase in sentence_lower:
                score += 5

        # Term matches - weight by specificity (rarer terms = higher score)
        for term in query_terms:
            if term in sentence_lower:
                freq = term_frequency.get(term, 1)
                # Rarer terms get higher scores: 1 occurrence = 4 points, 5+ = 1 point
                specificity_bonus = max(1, 5 - freq)
                # Longer terms are more specific
                length_bonus = min(len(term) / 4, 2)
                score += specificity_bonus + length_bonus

        if score > best_score:
            best_score = score
            best_idx = i

    if best_score == 0:
        return None

    # Build 3-sentence window: before + match + after
    window_sentences = []

    if best_idx > 0:
        window_sentences.append(sentences[best_idx - 1])

    window_sentences.append(sentences[best_idx])

    if best_idx < len(sentences) - 1:
        window_sentences.append(sentences[best_idx + 1])

    result = ' '.join(window_sentences)
    return _truncate(result, max_length)


def split_into_sentences(content: str) -> List[str]:
    """Split content into sentences, handling various delimiters."""
    # Split on sentence endings, but not on abbreviations
    # This is a simplified version - could be improved with NLP

    # Replace common abbreviations to avoid false splits
    temp = content
    abbreviations = ['Mr.', 'Mrs.', 'Dr.', 'Prof.', 'Sr.', 'Jr.', 'vs.', 'etc.', 'e.g.', 'i.e.']
    for abbr in abbreviations:
        temp = temp.replace(abbr, abbr.replace('.', '<DOT>'))

    # Split on sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', temp)

    # Restore abbreviations and clean up
    sentences = [s.replace('<DOT>', '.').strip() for s in sentences if s.strip()]

    # Filter out very short fragments
    sentences = [s for s in sentences if len(s) > 15]

    return sentences


def extract_relevant_snippet(
    query: str,
    content: str,
    parent_context: Optional[str] = None,
    max_length: int = 350
) -> str:
    """
    Extract the most relevant snippet from document content.

    Priority order:
    1. Key-value patterns (Education:, Skills:, etc.)
    2. Header/section matches
    3. Parent context matches (higher semantic value)
    4. Best sentence with 3-sentence window
    5. Fallback to truncated content

    Args:
        query: User's search query
        content: Document chunk content
        parent_context: Parent chunk content (if available)
        max_length: Maximum snippet length

    Returns:
        Most relevant snippet from the document
    """
    if not content or not query:
        return _truncate(content or "", max_length)

    # Step 1: Key-value pattern match (Golden Snippet for structured docs)
    kv_match = find_key_value_match(query, content, max_length)
    if kv_match:
        return kv_match

    # Step 2: Header/section match
    header_match = find_header_section(query, content, max_length)
    if header_match:
        return header_match

    # Step 3: Search parent context (often better summary)
    if parent_context:
        parent_match = find_in_parent_context(query, parent_context, max_length)
        if parent_match:
            return parent_match

    # Step 4: Best sentence with context window
    sentence_match = find_best_sentence_window(query, content, max_length)
    if sentence_match:
        return sentence_match

    # Step 5: Fallback - just truncate content
    return _truncate(content, max_length)


def _truncate(text: str, max_length: int) -> str:
    """Truncate text at sentence boundary if possible."""
    text = text.strip()
    if len(text) <= max_length:
        return text

    # Try to break at sentence boundary
    truncated = text[:max_length]

    # Look for last sentence ending
    for ending in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        last_end = truncated.rfind(ending)
        if last_end > max_length * 0.6:
            return truncated[:last_end + 1].strip()

    # Fall back to word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        return truncated[:last_space].strip() + "..."

    return truncated.strip() + "..."
