"""
Intent Handlers V2 - With Conversation Context

Handles non-RAG intents by generating appropriate responses.
V2 adds: followup, simplify, deepen (require conversation context)

These handlers are called when intent classification determines
the query doesn't need full RAG pipeline.

Usage:
    from rag.intent_handlers import dispatch_intent_handler

    result = await dispatch_intent_handler(
        intent="simplify",
        query="Can you make that simpler?",
        session_id="abc123",
        memory=memory_store,  # Required for context-aware handlers
        llm=llm_instance,     # Required for context-aware handlers
    )
"""
import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HandlerResult:
    """Result from an intent handler."""
    answer: str
    handler_used: str
    needs_rag: bool = False  # If True, fall back to RAG pipeline
    sources: list = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = []


# =============================================================================
# SIMPLE HANDLERS (No context needed)
# =============================================================================

def handle_greeting(query: str) -> HandlerResult:
    """
    Handle greeting intents.

    Examples: "hello", "hi there", "hey", "good morning"
    """
    logger.info(f"Handling greeting: {query}")

    return HandlerResult(
        answer="Hello! How can I help you with your documents today?",
        handler_used="handle_greeting",
    )


def handle_gratitude(query: str) -> HandlerResult:
    """
    Handle gratitude/thanks intents.

    Examples: "thanks", "thank you", "appreciate it"
    """
    logger.info(f"Handling gratitude: {query}")

    return HandlerResult(
        answer="You're welcome! Feel free to ask if you have more questions about your documents.",
        handler_used="handle_gratitude",
    )


def handle_garbage(query: str) -> HandlerResult:
    """
    Handle garbage/unintelligible input.

    Examples: "asdfghjkl", "123", "!!!", single characters
    """
    logger.info(f"Handling garbage input: {query}")

    return HandlerResult(
        answer="I didn't quite understand that. Could you rephrase your question about the documents?",
        handler_used="handle_garbage",
    )


def handle_off_topic(query: str) -> HandlerResult:
    """
    Handle off-topic queries (not related to documents).

    Examples: "What's the weather?", "Tell me a joke"
    """
    logger.info(f"Handling off-topic: {query}")

    return HandlerResult(
        answer="I'm designed to help you with questions about your uploaded documents. Is there something specific in your documents you'd like to know about?",
        handler_used="handle_off_topic",
    )


# =============================================================================
# CONTEXT-AWARE HANDLERS (Need conversation history)
# =============================================================================

async def handle_followup(
    query: str,
    session_id: str,
    memory: Any,
    llm: Any,
) -> HandlerResult:
    """
    Handle followup requests - user wants more information on the same topic.

    Examples: "Tell me more", "What else?", "Continue", "And?"

    Strategy:
    1. Get last assistant answer from memory
    2. Ask LLM to expand on it with more details
    3. If no context, fall back to RAG
    """
    logger.info(f"Handling followup: {query}")

    # Get conversation context
    context = await _get_conversation_context(session_id, memory)

    if not context["last_answer"]:
        logger.info("No previous answer found, falling back to RAG")
        return HandlerResult(
            answer="",
            handler_used="handle_followup",
            needs_rag=True,  # Fall back to RAG
        )

    # Build prompt for LLM
    prompt = f"""The user previously asked a question and received this answer:

PREVIOUS ANSWER:
{context["last_answer"]}

Now the user wants to know more. They said: "{query}"

Provide additional relevant information that expands on the previous answer.
Add new details, examples, or related concepts that weren't covered.
Keep the response focused and helpful.

If you don't have more information to add, say so honestly."""

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content.strip()

        return HandlerResult(
            answer=answer,
            handler_used="handle_followup",
            sources=context.get("last_sources", []),
        )
    except Exception as e:
        logger.error(f"LLM call failed in followup handler: {e}")
        return HandlerResult(
            answer="I'd like to tell you more, but I encountered an issue. Could you ask a specific question instead?",
            handler_used="handle_followup_error",
        )


async def handle_simplify(
    query: str,
    session_id: str,
    memory: Any,
    llm: Any,
) -> HandlerResult:
    """
    Handle simplification requests - user wants a simpler explanation.

    Examples: "Can you simplify that?", "Explain like I'm 5", "In simple terms?"

    Strategy:
    1. Get last assistant answer from memory
    2. Ask LLM to rewrite it in simpler language
    3. If no context, fall back to RAG
    """
    logger.info(f"Handling simplify: {query}")

    # Get conversation context
    context = await _get_conversation_context(session_id, memory)

    if not context["last_answer"]:
        logger.info("No previous answer found, falling back to RAG")
        return HandlerResult(
            answer="",
            handler_used="handle_simplify",
            needs_rag=True,
        )

    # Build prompt for LLM
    prompt = f"""The user received this explanation but wants it simplified:

ORIGINAL ANSWER:
{context["last_answer"]}

The user said: "{query}"

Rewrite this explanation in simpler terms:
- Use everyday language, avoid jargon
- Use short sentences
- Use analogies if helpful
- Keep the core meaning intact
- Aim for a 5th grade reading level

Simplified explanation:"""

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content.strip()

        return HandlerResult(
            answer=answer,
            handler_used="handle_simplify",
            sources=context.get("last_sources", []),
        )
    except Exception as e:
        logger.error(f"LLM call failed in simplify handler: {e}")
        return HandlerResult(
            answer="I'd like to simplify that, but I encountered an issue. Could you ask your question again?",
            handler_used="handle_simplify_error",
        )


async def handle_deepen(
    query: str,
    session_id: str,
    memory: Any,
    llm: Any,
) -> HandlerResult:
    """
    Handle deepening requests - user wants more technical/detailed explanation.

    Examples: "Go deeper", "More technical details", "Explain in depth"

    Strategy:
    1. Get last assistant answer from memory
    2. Ask LLM to provide more technical depth
    3. If no context, fall back to RAG
    """
    logger.info(f"Handling deepen: {query}")

    # Get conversation context
    context = await _get_conversation_context(session_id, memory)

    if not context["last_answer"]:
        logger.info("No previous answer found, falling back to RAG")
        return HandlerResult(
            answer="",
            handler_used="handle_deepen",
            needs_rag=True,
        )

    # Build prompt for LLM
    prompt = f"""The user received this explanation but wants more depth:

ORIGINAL ANSWER:
{context["last_answer"]}

The user said: "{query}"

Provide a more detailed, technical explanation:
- Add technical details and specifics
- Explain underlying mechanisms or principles
- Include relevant terminology with definitions
- Discuss edge cases or nuances if applicable
- Maintain accuracy while adding depth

Detailed explanation:"""

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content.strip()

        return HandlerResult(
            answer=answer,
            handler_used="handle_deepen",
            sources=context.get("last_sources", []),
        )
    except Exception as e:
        logger.error(f"LLM call failed in deepen handler: {e}")
        return HandlerResult(
            answer="I'd like to go deeper on that, but I encountered an issue. Could you ask a more specific question?",
            handler_used="handle_deepen_error",
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _get_conversation_context(
    session_id: str,
    memory: Any,
) -> dict:
    """
    Extract relevant conversation context from memory.

    Returns:
        dict with:
        - last_question: The user's previous question
        - last_answer: The assistant's previous answer
        - last_sources: Sources used in previous answer (if any)
    """
    context = {
        "last_question": None,
        "last_answer": None,
        "last_sources": [],
    }

    if memory is None:
        logger.warning("No memory store provided")
        return context

    try:
        # Get recent history (last 4 messages = 2 exchanges)
        history = await memory.get_history(session_id, limit=4)

        if not history:
            logger.info(f"No history found for session {session_id}")
            return context

        # Find the last assistant message
        for msg in reversed(history):
            if msg.get("role") == "assistant" and context["last_answer"] is None:
                context["last_answer"] = msg.get("content", "")
                # Extract sources from metadata if present
                metadata = msg.get("metadata", {})
                if metadata and "sources" in metadata:
                    context["last_sources"] = metadata["sources"]
            elif msg.get("role") == "user" and context["last_question"] is None:
                context["last_question"] = msg.get("content", "")

            # Stop once we have both
            if context["last_answer"] and context["last_question"]:
                break

        logger.info(f"Retrieved context: question={bool(context['last_question'])}, answer={bool(context['last_answer'])}")
        return context

    except Exception as e:
        logger.error(f"Failed to get conversation context: {e}")
        return context


# =============================================================================
# DISPATCHER
# =============================================================================

async def dispatch_intent_handler(
    intent: str,
    query: str,
    session_id: str = None,
    memory: Any = None,
    llm: Any = None,
) -> HandlerResult:
    """
    Dispatch to the appropriate handler based on intent.

    Args:
        intent: The classified intent (greeting, gratitude, followup, etc.)
        query: The user's original query
        session_id: Session ID for context retrieval
        memory: Memory store instance (required for context-aware handlers)
        llm: LLM instance (required for context-aware handlers)

    Returns:
        HandlerResult with answer and metadata
    """
    logger.info(f"Dispatching handler for intent: {intent}")

    # Simple handlers (no context needed)
    simple_handlers = {
        "greeting": handle_greeting,
        "gratitude": handle_gratitude,
        "garbage": handle_garbage,
        "off_topic": handle_off_topic,
    }

    if intent in simple_handlers:
        return simple_handlers[intent](query)

    # Context-aware handlers (need memory and LLM)
    context_handlers = {
        "followup": handle_followup,
        "simplify": handle_simplify,
        "deepen": handle_deepen,
    }

    if intent in context_handlers:
        if memory is None or llm is None:
            logger.warning(f"Context handler {intent} called without memory/llm, falling back to RAG")
            return HandlerResult(
                answer="",
                handler_used=f"handle_{intent}_no_context",
                needs_rag=True,
            )

        return await context_handlers[intent](
            query=query,
            session_id=session_id,
            memory=memory,
            llm=llm,
        )

    # Unknown intent - fall back to RAG
    logger.warning(f"Unknown intent: {intent}, falling back to RAG")
    return HandlerResult(
        answer="",
        handler_used="unknown_intent",
        needs_rag=True,
    )
