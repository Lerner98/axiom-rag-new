"""
RAG Pipeline State - V3 with Intent Classification + Context-Aware Handlers
"""
from typing import TypedDict, Literal, Optional, Annotated
from operator import add


class Document(TypedDict):
    """A retrieved document."""
    content: str
    metadata: dict
    relevance_score: float


class RAGState(TypedDict):
    """State that flows through the RAG pipeline."""
    # Input
    question: str
    session_id: str
    collection_name: str

    # V5 Intent Classification (NEW)
    detected_intent: Optional[str]  # greeting, question, followup, simplify, deepen, etc.
    intent_confidence: float  # 0.0 - 1.0

    # Router Agent
    query_complexity: Optional[Literal["simple", "complex", "conversational", "summarize", "garbage"]]
    skip_rewrite: bool
    is_summarization: bool  # For sequential retrieval path
    is_garbage_query: bool  # For rejecting single chars/meaningless input
    
    # Query Processing
    rewritten_query: Optional[str]
    query_type: Optional[Literal["factual", "analytical", "conversational"]]
    
    # Retrieval
    retrieved_documents: list[Document]
    relevant_documents: list[Document]
    collection_empty: bool
    
    # Generation
    answer: Optional[str]
    sources: list[dict]
    
    # Validation - Original
    is_grounded: bool
    groundedness_score: float
    hallucination_details: Optional[str]
    
    # Validation - Hybrid Hallucination Check (NEW)
    fast_groundedness_score: float  # Score from fast keyword check
    skip_llm_hallucination_check: bool  # Whether we skipped LLM check
    
    # Control Flow
    iteration: int
    max_iterations: int
    should_rewrite: bool
    rewrite_count: int
    
    # Metadata
    errors: Annotated[list[str], add]
    processing_steps: Annotated[list[str], add]


def create_initial_state(
    question: str,
    session_id: str,
    collection_name: str,
    max_iterations: int = 2
) -> RAGState:
    """Create initial state for a new query."""
    return RAGState(
        question=question,
        session_id=session_id,
        collection_name=collection_name,
        # V5 Intent Classification
        detected_intent=None,
        intent_confidence=0.0,
        # Router Agent
        query_complexity=None,
        skip_rewrite=False,
        is_summarization=False,
        is_garbage_query=False,
        # Query Processing
        rewritten_query=None,
        query_type=None,
        # Retrieval
        retrieved_documents=[],
        relevant_documents=[],
        collection_empty=False,
        # Generation
        answer=None,
        sources=[],
        # Validation
        is_grounded=False,
        groundedness_score=0.0,
        hallucination_details=None,
        fast_groundedness_score=0.0,
        skip_llm_hallucination_check=False,
        # Control Flow
        iteration=0,
        max_iterations=max_iterations,
        should_rewrite=False,
        rewrite_count=0,
        # Metadata
        errors=[],
        processing_steps=[],
    )
