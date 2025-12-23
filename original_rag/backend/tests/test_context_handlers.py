"""
Phase 3 Tests: Context-Aware Intent Handlers

Tests:
1. Followup with context - should expand previous answer
2. Followup without context - should ask for question first
3. Simplify with context - should simplify previous answer
4. Simplify without context - should ask for question first
5. Deepen with context - should add technical depth
6. Deepen without context - should ask for question first

Usage:
    cd backend
    python -m pytest tests/test_context_handlers.py -v
"""
import pytest
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class MockMemory:
    """Mock memory store for testing."""

    def __init__(self, history=None):
        self._history = history or []

    async def get_history(self, session_id: str, limit: int = 10):
        return self._history[-limit:] if self._history else []

    async def add_message(self, session_id: str, role: str, content: str, metadata=None):
        self._history.append({
            "role": role,
            "content": content,
            "metadata": metadata or {}
        })


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response="Mock LLM response"):
        self._response = response

    async def ainvoke(self, prompt):
        # Return a mock response object
        class Response:
            content = f"[Mocked] {self._response}"
        return Response()


@pytest.fixture
def memory_with_context():
    """Memory with a previous Q&A exchange."""
    return MockMemory(history=[
        {"role": "user", "content": "What is the CAP theorem?"},
        {"role": "assistant", "content": "The CAP theorem states that a distributed system can only guarantee two of three properties: Consistency, Availability, and Partition tolerance.", "metadata": {"sources": [{"source": "test.pdf"}]}},
    ])


@pytest.fixture
def memory_empty():
    """Memory with no history."""
    return MockMemory(history=[])


@pytest.fixture
def mock_llm():
    """Mock LLM instance."""
    return MockLLM(response="Extended explanation with more details.")


# =============================================================================
# TEST: FOLLOWUP
# =============================================================================

@pytest.mark.asyncio
async def test_followup_with_context(memory_with_context, mock_llm):
    """Followup with previous answer should expand on it."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="followup",
        query="Tell me more",
        session_id="test_session",
        memory=memory_with_context,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_followup"
    assert result.needs_rag == False
    assert "[Mocked]" in result.answer  # LLM was called
    print(f"\n✓ Followup with context: {result.answer[:80]}...")


@pytest.mark.asyncio
async def test_followup_without_context(memory_empty, mock_llm):
    """Followup without previous answer should indicate no context."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="followup",
        query="Tell me more",
        session_id="test_session",
        memory=memory_empty,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_followup"
    assert result.needs_rag == True  # Signals no context available
    print(f"\n✓ Followup without context: needs_rag={result.needs_rag}")


# =============================================================================
# TEST: SIMPLIFY
# =============================================================================

@pytest.mark.asyncio
async def test_simplify_with_context(memory_with_context, mock_llm):
    """Simplify with previous answer should simplify it."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="simplify",
        query="Can you explain that more simply?",
        session_id="test_session",
        memory=memory_with_context,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_simplify"
    assert result.needs_rag == False
    assert "[Mocked]" in result.answer
    print(f"\n✓ Simplify with context: {result.answer[:80]}...")


@pytest.mark.asyncio
async def test_simplify_without_context(memory_empty, mock_llm):
    """Simplify without previous answer should indicate no context."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="simplify",
        query="Make it simpler",
        session_id="test_session",
        memory=memory_empty,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_simplify"
    assert result.needs_rag == True
    print(f"\n✓ Simplify without context: needs_rag={result.needs_rag}")


# =============================================================================
# TEST: DEEPEN
# =============================================================================

@pytest.mark.asyncio
async def test_deepen_with_context(memory_with_context, mock_llm):
    """Deepen with previous answer should add technical depth."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="deepen",
        query="Go into more technical detail",
        session_id="test_session",
        memory=memory_with_context,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_deepen"
    assert result.needs_rag == False
    assert "[Mocked]" in result.answer
    print(f"\n✓ Deepen with context: {result.answer[:80]}...")


@pytest.mark.asyncio
async def test_deepen_without_context(memory_empty, mock_llm):
    """Deepen without previous answer should indicate no context."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="deepen",
        query="More depth please",
        session_id="test_session",
        memory=memory_empty,
        llm=mock_llm,
    )

    assert result is not None
    assert result.handler_used == "handle_deepen"
    assert result.needs_rag == True
    print(f"\n✓ Deepen without context: needs_rag={result.needs_rag}")


# =============================================================================
# TEST: SIMPLE HANDLERS STILL WORK
# =============================================================================

@pytest.mark.asyncio
async def test_greeting_no_context_needed():
    """Greeting should work without memory/llm."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="greeting",
        query="hello",
        session_id=None,
        memory=None,
        llm=None,
    )

    assert result is not None
    assert result.handler_used == "handle_greeting"
    assert result.needs_rag == False
    assert "Hello" in result.answer
    print(f"\n✓ Greeting (no context): {result.answer}")


@pytest.mark.asyncio
async def test_gratitude_no_context_needed():
    """Gratitude should work without memory/llm."""
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="gratitude",
        query="thanks!",
        session_id=None,
        memory=None,
        llm=None,
    )

    assert result is not None
    assert result.handler_used == "handle_gratitude"
    assert result.needs_rag == False
    print(f"\n✓ Gratitude (no context): {result.answer}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
