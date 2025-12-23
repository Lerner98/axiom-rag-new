"""
Intent Router - ADR-011 Hybrid Intent Classification

3-Layer Architecture:
  Layer 0: Hard rules (length, stopwords, no letters) → GARBAGE
  Layer 1: Semantic fast path (FastEmbed similarity) → Most intents
  Layer 2: LLM router fallback (complex cases) → Full classification

This replaces the basic garbage detection in route_query with a full
intent classification system that can route greetings, gratitude, etc.
to specialized handlers WITHOUT triggering RAG.

Usage:
    router = IntentRouter()
    intent, confidence = await router.classify("hi there")
    # → ("greeting", 0.95)

    intent, confidence = await router.classify("What is CAP theorem?")
    # → ("question", 0.88)
"""
import logging
import re
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# INTENT DEFINITIONS
# =============================================================================

INTENT_TYPES = [
    "question",        # Standard RAG query
    "greeting",        # "hi", "hello" → no RAG
    "gratitude",       # "thanks" → no RAG
    "followup",        # "more", "continue" → expand last answer
    "simplify",        # "explain simpler" → rephrase
    "deepen",          # "go deeper" → more technical
    "clarify_needed",  # Ambiguous → ask clarifying question
    "command",         # "summarize", "compare" → specialized handler
    "garbage",         # Invalid input → reject
    "off_topic",       # Unrelated to documents → redirect
]


# =============================================================================
# LAYER 0: HARD RULES (Deterministic, 0ms)
# =============================================================================

# Stopword-heavy queries that aren't real questions
STOPWORD_SET = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
    'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
    'and', 'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that',
    'these', 'those', 'it', 'its', 'what', 'which', 'who', 'whom', 'how',
    'when', 'where', 'why', 'i', 'me', 'my', 'you', 'your', 'he', 'she',
    'they', 'them', 'we', 'our', 'there', 'here',
}


def layer0_hard_rules(query: str) -> Optional[Tuple[str, float]]:
    """
    Layer 0: Deterministic rules that don't need embeddings or LLM.

    Returns:
        (intent, confidence) if rule matches, None otherwise
    """
    query = query.strip()
    query_lower = query.lower()

    # Rule 1: Empty or too short
    if len(query) <= 1:
        logger.debug(f"Layer 0: GARBAGE (too short: {len(query)} chars)")
        return ("garbage", 1.0)

    # Rule 2: No alphabetic characters
    if not any(c.isalpha() for c in query):
        logger.debug(f"Layer 0: GARBAGE (no letters)")
        return ("garbage", 1.0)

    # Rule 3: Pure punctuation/symbols with maybe some letters
    alpha_count = sum(1 for c in query if c.isalpha())
    if alpha_count < 2 and len(query) > 2:
        logger.debug(f"Layer 0: GARBAGE (only {alpha_count} letters)")
        return ("garbage", 1.0)

    # Rule 4: Stopword density check (ADR-010 recommendation)
    words = re.findall(r'\b[a-z]+\b', query_lower)
    if words:
        stopword_count = sum(1 for w in words if w in STOPWORD_SET)
        stopword_ratio = stopword_count / len(words)

        # If >90% stopwords and short, likely garbage like "the the the"
        if stopword_ratio > 0.9 and len(words) <= 5:
            logger.debug(f"Layer 0: GARBAGE (stopword ratio {stopword_ratio:.0%})")
            return ("garbage", 0.95)

    # Rule 5: Repetitive characters (keyboard spam)
    # e.g., "aaaaaaa", "asdfasdf"
    if len(query) >= 4:
        unique_chars = len(set(query_lower.replace(" ", "")))
        if unique_chars <= 2:
            logger.debug(f"Layer 0: GARBAGE (repetitive: {unique_chars} unique chars)")
            return ("garbage", 0.95)

    return None  # No hard rule matched, continue to Layer 1


# =============================================================================
# LAYER 1: SEMANTIC FAST PATH (FastEmbed similarity, <20ms)
# =============================================================================

# Intent exemplars - canonical examples for each intent
# These will be embedded once at startup and compared to incoming queries
INTENT_EXEMPLARS: Dict[str, List[str]] = {
    "greeting": [
        "hi",
        "hello",
        "hey",
        "hey there",
        "hi there",
        "hello there",
        "good morning",
        "good afternoon",
        "good evening",
        "howdy",
        "greetings",
        "yo",
        "sup",
        "what's up",
    ],
    "gratitude": [
        "thanks",
        "thank you",
        "thanks a lot",
        "thank you so much",
        "thanks for your help",
        "appreciate it",
        "much appreciated",
        "thx",
        "ty",
        "cheers",
        "great thanks",
        "perfect thank you",
        "awesome thanks",
    ],
    "followup": [
        "more",
        "tell me more",
        "more details",
        "continue",
        "go on",
        "elaborate",
        "elaborate on that",
        "can you expand on that",
        "what else",
        "and then",
        "keep going",
        "more please",
    ],
    "simplify": [
        "explain simpler",
        "simpler please",
        "in simpler terms",
        "explain like i'm five",
        "eli5",
        "dumb it down",
        "too complicated",
        "i don't understand",
        "can you simplify",
        "make it simpler",
        "easier explanation",
    ],
    "deepen": [
        "go deeper",
        "more technical",
        "more detail",
        "in depth",
        "technically speaking",
        "dive deeper",
        "elaborate technically",
        "more specifics",
        "get into the weeds",
    ],
    "command": [
        "summarize this",
        "summarize the document",
        "give me a summary",
        "compare these",
        "list all",
        "list the topics",
        "what are the main points",
        "overview",
        "table of contents",
    ],
}

# Confidence threshold for semantic matching
SEMANTIC_CONFIDENCE_THRESHOLD = 0.85


@dataclass
class SemanticRouter:
    """
    Semantic intent router using FastEmbed similarity.

    Embeds intent exemplars once, then compares incoming queries
    to find the closest matching intent.
    """
    embeddings: any = None  # FastEmbed model
    exemplar_embeddings: Dict[str, List[List[float]]] = None
    initialized: bool = False

    def initialize(self):
        """Lazy initialization of embeddings and exemplar vectors."""
        if self.initialized:
            return

        try:
            from fastembed import TextEmbedding

            logger.info("Initializing SemanticRouter with FastEmbed...")
            self.embeddings = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

            # Pre-embed all exemplars
            self.exemplar_embeddings = {}
            for intent, examples in INTENT_EXEMPLARS.items():
                embeddings = list(self.embeddings.embed(examples))
                self.exemplar_embeddings[intent] = [e.tolist() for e in embeddings]
                logger.debug(f"Embedded {len(examples)} exemplars for intent: {intent}")

            self.initialized = True
            logger.info(f"SemanticRouter initialized with {len(INTENT_EXEMPLARS)} intents")

        except ImportError:
            logger.warning("FastEmbed not available, semantic routing disabled")
            self.initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize SemanticRouter: {e}")
            self.initialized = False

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def classify(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Classify query intent using semantic similarity.

        Returns:
            (intent, confidence) if confidence > threshold, None otherwise
        """
        if not self.initialized:
            self.initialize()

        if not self.initialized:
            return None  # Fall through to Layer 2

        # Embed the query
        query_embedding = list(self.embeddings.embed([query]))[0].tolist()

        # Find best matching intent
        best_intent = None
        best_score = 0.0

        for intent, exemplar_vecs in self.exemplar_embeddings.items():
            # Find max similarity to any exemplar for this intent
            max_sim = max(
                self._cosine_similarity(query_embedding, exemplar_vec)
                for exemplar_vec in exemplar_vecs
            )

            if max_sim > best_score:
                best_score = max_sim
                best_intent = intent

        logger.debug(f"Layer 1: Best match '{best_intent}' with confidence {best_score:.3f}")

        if best_score >= SEMANTIC_CONFIDENCE_THRESHOLD:
            logger.info(f"Layer 1: {best_intent.upper()} (confidence={best_score:.3f})")
            return (best_intent, best_score)

        return None  # Confidence too low, fall through to Layer 2


# Global semantic router instance (lazy initialized)
_semantic_router: Optional[SemanticRouter] = None


def get_semantic_router() -> SemanticRouter:
    """Get or create the singleton semantic router."""
    global _semantic_router
    if _semantic_router is None:
        _semantic_router = SemanticRouter()
    return _semantic_router


def layer1_semantic(query: str) -> Optional[Tuple[str, float]]:
    """
    Layer 1: Semantic similarity matching against intent exemplars.

    Returns:
        (intent, confidence) if high confidence match, None otherwise
    """
    router = get_semantic_router()
    return router.classify(query)


# =============================================================================
# LAYER 2: LLM FALLBACK (for complex/ambiguous cases)
# =============================================================================

# LLM prompt for intent classification
INTENT_CLASSIFICATION_PROMPT = """Classify this user message into ONE intent category.

Message: {query}

Categories:
- QUESTION: Asking about document content (who, what, when, where, why, how)
- GREETING: Social greeting (hi, hello, hey)
- GRATITUDE: Expressing thanks (thanks, thank you)
- FOLLOWUP: Wants more on previous topic (more, continue, elaborate)
- SIMPLIFY: Wants simpler explanation (simpler, eli5, dumb it down)
- DEEPEN: Wants more technical detail (deeper, more technical)
- COMMAND: Direct instruction (summarize, compare, list)
- GARBAGE: Meaningless input (random chars, keyboard spam)
- OFF_TOPIC: Unrelated to documents (weather, jokes, personal questions)

If the message looks like a genuine question about document content, classify as QUESTION.
If uncertain between QUESTION and something else, choose QUESTION.

Respond with ONLY the category name in caps (e.g., QUESTION):"""


async def layer2_llm(query: str, llm) -> Tuple[str, float]:
    """
    Layer 2: LLM-based intent classification for ambiguous cases.

    This is the fallback when Layer 0 and Layer 1 don't produce
    a high-confidence result.

    Args:
        query: The user's query
        llm: LangChain LLM instance

    Returns:
        (intent, confidence) - confidence is 0.7 for LLM classifications
    """
    prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)

    try:
        response = await llm.ainvoke(prompt)
        classification = response.content.strip().upper()

        # Map LLM response to intent type
        intent_map = {
            "QUESTION": "question",
            "GREETING": "greeting",
            "GRATITUDE": "gratitude",
            "FOLLOWUP": "followup",
            "SIMPLIFY": "simplify",
            "DEEPEN": "deepen",
            "COMMAND": "command",
            "GARBAGE": "garbage",
            "OFF_TOPIC": "off_topic",
            "CLARIFY_NEEDED": "clarify_needed",
        }

        # Find matching intent
        for key, value in intent_map.items():
            if key in classification:
                logger.info(f"Layer 2 (LLM): {value.upper()} (confidence=0.70)")
                return (value, 0.70)

        # Default to question if LLM response unclear
        logger.warning(f"Layer 2: LLM returned unclear '{classification}', defaulting to QUESTION")
        return ("question", 0.50)

    except Exception as e:
        logger.error(f"Layer 2: LLM classification failed: {e}")
        return ("question", 0.30)


# =============================================================================
# MAIN ROUTER CLASS
# =============================================================================

class IntentRouter:
    """
    3-Layer Hybrid Intent Router (ADR-011)

    Classifies user queries into intents to determine routing:
    - Greetings/gratitude → Respond directly (no RAG)
    - Questions → Full RAG pipeline
    - Follow-ups → Expand previous answer (Phase 2)
    - Commands → Specialized handlers
    - Garbage → Friendly rejection

    Usage:
        router = IntentRouter(llm)
        intent, confidence = await router.classify("What is CAP theorem?")
    """

    def __init__(self, llm=None):
        """
        Initialize the intent router.

        Args:
            llm: LangChain LLM instance for Layer 2 fallback.
                 If None, Layer 2 will return "question" as default.
        """
        self.llm = llm

    async def classify(self, query: str) -> Tuple[str, float]:
        """
        Classify a query into an intent category.

        Uses 3-layer approach:
        1. Hard rules (instant)
        2. Semantic similarity (fast, <20ms)
        3. LLM fallback (slow, only if needed)

        Args:
            query: The user's input query

        Returns:
            Tuple of (intent_type, confidence_score)
            - intent_type: One of INTENT_TYPES
            - confidence_score: 0.0-1.0
        """
        # Layer 0: Hard rules
        result = layer0_hard_rules(query)
        if result:
            return result

        # Layer 1: Semantic fast path
        result = layer1_semantic(query)
        if result:
            return result

        # Layer 2: LLM fallback
        if self.llm:
            return await layer2_llm(query, self.llm)

        # No LLM available, default to question
        logger.info("No LLM for Layer 2, defaulting to QUESTION")
        return ("question", 0.50)

    def classify_sync(self, query: str) -> Tuple[str, float]:
        """
        Synchronous classification (Layer 0 + Layer 1 only).

        Use this when you don't want to wait for LLM.
        Returns ("question", 0.50) if no confident match.
        """
        # Layer 0: Hard rules
        result = layer0_hard_rules(query)
        if result:
            return result

        # Layer 1: Semantic fast path
        result = layer1_semantic(query)
        if result:
            return result

        # No confident match
        return ("question", 0.50)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def is_rag_intent(intent: str) -> bool:
    """Check if this intent requires RAG pipeline."""
    return intent in ("question", "command")


def is_conversation_intent(intent: str) -> bool:
    """Check if this intent requires conversation context (Phase 2)."""
    return intent in ("followup", "simplify", "deepen", "clarify_needed")


def is_no_rag_intent(intent: str) -> bool:
    """Check if this intent should skip RAG entirely."""
    return intent in ("greeting", "gratitude", "garbage", "off_topic")
