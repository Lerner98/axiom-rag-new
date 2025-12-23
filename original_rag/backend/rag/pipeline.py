"""
RAG Pipeline - V6 with TRUE STREAMING

Flow:
classify_intent → [needs_rag?]
    → NO: handle_non_rag_intent → END (greeting, gratitude, followup, simplify, deepen)
    → YES: route_query → [SUMMARIZE?] → retrieve_sequential → grade → generate
                       → [SIMPLE?] → retrieve (skip rewrite)
                       → [COMPLEX?] → rewrite_query → retrieve

V6 STREAMING ARCHITECTURE:
- Phase events emitted in real-time: searching → found_sources → generating → done
- Sources emitted BEFORE generation starts (user sees what docs were found)
- TRUE LLM streaming: tokens yielded as they're generated
- Seamless UX with progressive feedback

Changes from V5:
- TRUE STREAMING: Tokens are yielded as LLM generates them
- Phase events: searching → found_sources → generating → done
- Sources are emitted BEFORE generation (not after)
- Real-time feedback for seamless UX

Changes from V4:
- Added classify_intent as new entry point
- Added handle_non_rag_intent for non-RAG intents
- Context-aware handlers: followup, simplify, deepen use conversation memory
- Intent router: 3-layer hybrid (hard rules → semantic → LLM)
"""
from typing import AsyncGenerator, Optional, List, Dict, Any
import logging
import asyncio

from langgraph.graph import StateGraph, END

from rag.state import RAGState, create_initial_state
from rag.nodes import RAGNodes, needs_rag, should_rewrite, has_relevant_docs, should_retry
from rag.prompts import (
    GENERATION_PROMPT,
    GENERATION_WITH_RETRY_PROMPT,
    HALLUCINATION_CHECK_PROMPT,
    format_sources_for_prompt,
)
from config.settings import settings
from memory import memory_store

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Adaptive RAG pipeline with Router Agent, HybridRetriever, and Summarization.
    
    Features:
    - Router classifies query complexity AND detects summarization intent
    - SUMMARIZE queries bypass vector search, get full document in order
    - Simple queries skip rewrite (saves 1 LLM call)
    - Complex/conversational queries go through full rewrite
    - HybridRetriever: Vector + BM25 + RRF fusion
    - Parent expansion: Small chunks for search, large context for LLM
    - Cross-encoder reranking: 50 candidates → 5 final (skipped for summaries)
    """
    
    def __init__(self, llm=None, vectorstore=None, memory=None):
        self.llm = llm or self._create_llm()
        self.vectorstore = vectorstore or self._create_vectorstore()
        self.memory = memory or memory_store
        
        # Initialize HybridRetriever with vectorstore
        self._init_hybrid_retriever()

        self.nodes = RAGNodes(self.llm, self.vectorstore, self.memory)
        self.graph = self._build_graph()
    
    def _create_llm(self):
        """Create LLM based on settings."""
        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0
            )
        elif settings.llm_provider == "ollama":
            from langchain_community.chat_models import ChatOllama
            # Performance-tuned Ollama configuration
            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0,
                # KV cache settings for faster prefill
                num_ctx=settings.ollama_num_ctx,
                # Additional model parameters passed to Ollama
                # Note: kv_cache_type and flash_attention are set via OLLAMA_* env vars
                # at the Ollama server level, not per-request
            )
        elif settings.llm_provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key,
                temperature=0
            )
        else:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
    
    def _create_vectorstore(self):
        """Create vector store based on settings."""
        from vectorstore import VectorStore
        return VectorStore()
    
    def _init_hybrid_retriever(self):
        """Initialize HybridRetriever singleton."""
        try:
            from rag.retriever import get_hybrid_retriever
            # Initialize with our vectorstore
            get_hybrid_retriever(self.vectorstore)
            logger.info("HybridRetriever initialized in pipeline")
        except Exception as e:
            logger.warning(f"Could not initialize HybridRetriever: {e}")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with V5 Intent Classification.

        Flow:
        1. classify_intent: Detect intent (greeting, followup, simplify, question, etc.)
        2. [needs_rag?] → NO: handle_non_rag_intent → END
        3. [needs_rag?] → YES: route_query → (existing RAG flow)
        4. route_query: Classify query (SUMMARIZE, SIMPLE, COMPLEX, CONVERSATIONAL)
        5. [SUMMARIZE] → retrieve_sequential (all chunks, ordered)
        6. [SIMPLE] → retrieve | [COMPLEX] → rewrite_query → retrieve
        7. grade_documents
        8. [has_relevant_docs] → generate or rewrite_query
        9. check_hallucination
        10. [should_retry] → generate or save_to_memory
        """
        workflow = StateGraph(RAGState)

        # Add V5 intent classification nodes
        workflow.add_node("classify_intent", self.nodes.classify_intent)
        workflow.add_node("handle_non_rag_intent", self.nodes.handle_non_rag_intent)

        # Add existing RAG nodes
        workflow.add_node("route_query", self.nodes.route_query)
        workflow.add_node("rewrite_query", self.nodes.rewrite_query)
        workflow.add_node("retrieve", self.nodes.retrieve)
        workflow.add_node("retrieve_sequential", self.nodes.retrieve_sequential)
        workflow.add_node("grade_documents", self.nodes.grade_documents)
        workflow.add_node("generate", self.nodes.generate)
        workflow.add_node("check_hallucination", self.nodes.check_hallucination)
        workflow.add_node("save_to_memory", self.nodes.save_to_memory)
        workflow.add_node("handle_garbage_query", self.nodes.handle_garbage_query)

        # V5: Entry point is now classify_intent
        workflow.set_entry_point("classify_intent")

        # V5: After intent classification, decide if RAG is needed
        workflow.add_conditional_edges(
            "classify_intent",
            needs_rag,
            {
                "rag": "route_query",           # Continue to RAG pipeline
                "no_rag": "handle_non_rag_intent",  # Skip RAG, handle directly
            }
        )

        # Non-RAG intent handler goes straight to END
        workflow.add_edge("handle_non_rag_intent", END)

        # Router decides: garbage, summarize, skip rewrite, or do rewrite
        workflow.add_conditional_edges(
            "route_query",
            should_rewrite,
            {
                "rewrite": "rewrite_query",
                "retrieve": "retrieve",
                "summarize": "retrieve_sequential",
                "garbage": "handle_garbage_query",
            }
        )

        # Garbage goes straight to END (no retrieval, no hallucination check)
        workflow.add_edge("handle_garbage_query", END)
        
        # After rewrite, go to retrieve
        workflow.add_edge("rewrite_query", "retrieve")
        
        # After retrieve, go to grade
        workflow.add_edge("retrieve", "grade_documents")
        
        # After retrieve_sequential, go to grade (NEW)
        workflow.add_edge("retrieve_sequential", "grade_documents")
        
        # After grade, check if we have relevant docs
        workflow.add_conditional_edges(
            "grade_documents",
            has_relevant_docs,
            {
                "generate": "generate",
                "rewrite": "rewrite_query",
            }
        )
        
        # After generate, check hallucination
        workflow.add_edge("generate", "check_hallucination")
        
        # After hallucination check, retry or finish
        workflow.add_conditional_edges(
            "check_hallucination",
            should_retry,
            {
                "retry": "generate",
                "finish": "save_to_memory",
            }
        )
        
        # After save, end
        workflow.add_edge("save_to_memory", END)
        
        return workflow.compile()
    
    async def aquery(
        self,
        question: str,
        session_id: str = "default",
        collection_name: str | None = None
    ) -> dict:
        """Run a query through the RAG pipeline."""
        collection = collection_name or settings.collection_name
        
        logger.info(f"Starting RAG query: '{question[:50]}...' in collection '{collection}'")
        
        initial_state = create_initial_state(
            question=question,
            session_id=session_id,
            collection_name=collection,
            max_iterations=settings.max_retries
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        logger.info(f"RAG query complete. Steps: {final_state['processing_steps']}")
        
        return {
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "is_grounded": final_state["is_grounded"],
            "groundedness_score": final_state["groundedness_score"],
            "iterations": final_state["iteration"],
            "query_complexity": final_state.get("query_complexity"),
            "is_summarization": final_state.get("is_summarization", False),
            "processing_steps": final_state["processing_steps"],
            "detected_intent": final_state.get("detected_intent"),
            "intent_confidence": final_state.get("intent_confidence"),
        }
    
    async def astream(
        self,
        question: str,
        session_id: str = "default",
        collection_name: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        TRUE STREAMING: Stream a query through the RAG pipeline with real-time events.

        Event sequence:
        1. {"type": "phase", "phase": "searching"} - Intent classification + retrieval starting
        2. {"type": "sources", "sources": [...]} - Sources found (BEFORE generation)
        3. {"type": "phase", "phase": "generating"} - LLM generation starting
        4. {"type": "token", "content": "..."} - Each token as generated
        5. {"type": "done", ...} - Stream complete with metadata
        """
        collection = collection_name or settings.collection_name

        logger.info(f"Starting TRUE STREAMING: '{question[:50]}...' in collection '{collection}'")

        # Phase 1: Signal searching
        yield {"type": "phase", "phase": "searching"}

        initial_state = create_initial_state(
            question=question,
            session_id=session_id,
            collection_name=collection,
            max_iterations=settings.max_retries
        )

        # Run pipeline up to generation (classify → route → retrieve → grade)
        # We need to intercept BEFORE generate to emit sources and stream tokens

        try:
            # Step 1: Intent classification
            state = dict(initial_state)
            intent_result = await self.nodes.classify_intent(state)
            state.update(intent_result)

            intent = state.get("detected_intent", "question")

            # Check if we need RAG at all
            if needs_rag(state) == "no_rag":
                # Handle non-RAG intent (greeting, etc.)
                logger.info(f"Non-RAG intent: {intent}")
                result = await self.nodes.handle_non_rag_intent(state)
                state.update(result)

                # Emit sources (empty for non-RAG)
                yield {"type": "sources", "sources": []}
                yield {"type": "phase", "phase": "generating"}

                # Stream the pre-built answer
                answer = state.get("answer", "")
                for word in answer.split():
                    yield {"type": "token", "content": word + " "}
                    await asyncio.sleep(0.01)  # Small delay for visual effect

                yield {
                    "type": "done",
                    "is_grounded": True,
                    "iterations": 0,
                    "query_complexity": None,
                    "detected_intent": intent,
                }
                return

            # Step 2: Route query (fast heuristic)
            route_result = await self.nodes.route_query(state)
            state.update(route_result)

            # Step 3: Retrieval
            if state.get("query_complexity") == "garbage":
                # Handle garbage query
                result = await self.nodes.handle_garbage_query(state)
                state.update(result)
                yield {"type": "sources", "sources": []}
                yield {"type": "phase", "phase": "generating"}
                for word in state.get("answer", "").split():
                    yield {"type": "token", "content": word + " "}
                yield {"type": "done", "is_grounded": True, "iterations": 0}
                return

            # Run appropriate retrieval
            if state.get("is_summarization"):
                retrieve_result = await self.nodes.retrieve_sequential(state)
            else:
                if not state.get("skip_rewrite"):
                    rewrite_result = await self.nodes.rewrite_query(state)
                    state.update(rewrite_result)
                retrieve_result = await self.nodes.retrieve(state)

            state.update(retrieve_result)

            # Step 4: Grade documents
            grade_result = await self.nodes.grade_documents(state)
            state.update(grade_result)

            # EMIT SOURCES - User sees what was found BEFORE generation
            sources = state.get("sources", [])
            yield {"type": "sources", "sources": sources}
            logger.info(f"Emitted {len(sources)} sources to frontend")

            # Phase 3: Generation with TRUE streaming
            yield {"type": "phase", "phase": "generating"}

            # Build context for generation
            context = self._build_context(state.get("relevant_documents", []))
            chat_history = await self._get_chat_history(session_id)

            # Build prompt
            prompt = GENERATION_PROMPT.format(
                context=context,
                question=question,
                chat_history=chat_history or "No previous conversation",
            )

            # TRUE LLM STREAMING - yield tokens as they're generated
            full_answer = ""
            async for chunk in self.llm.astream(prompt):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if token:
                    full_answer += token
                    yield {"type": "token", "content": token}

            state["answer"] = full_answer
            logger.info(f"Streamed {len(full_answer)} chars of answer")

            # Step 5: Hallucination check (non-blocking, doesn't affect stream)
            hallucination_result = await self.nodes.check_hallucination(state)
            state.update(hallucination_result)

            # Step 6: Save to memory
            await self.nodes.save_to_memory(state)

            # Done event with metadata
            yield {
                "type": "done",
                "is_grounded": state.get("is_grounded", True),
                "iterations": state.get("iteration", 0),
                "query_complexity": state.get("query_complexity"),
                "is_summarization": state.get("is_summarization", False),
                "detected_intent": state.get("detected_intent"),
            }

            logger.info(f"TRUE STREAMING complete. Grounded: {state.get('is_grounded')}")

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    def _build_context(self, relevant_documents: List[Dict]) -> str:
        """Build context string from relevant documents."""
        if not relevant_documents:
            return "No relevant documents found in the knowledge base."

        context_parts = []
        for i, doc in enumerate(relevant_documents, 1):
            source = doc.get("metadata", {}).get("source", "unknown")
            page = doc.get("metadata", {}).get("page", "")
            page_str = f" (page {page})" if page else ""
            content = doc.get("content", "")
            context_parts.append(f"[Source {i}: {source}{page_str}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

    async def _get_chat_history(self, session_id: str) -> str:
        """Get formatted chat history."""
        if not self.memory:
            return ""
        try:
            history = await self.memory.get_history(session_id, limit=5)
            return "\n".join([f"{m['role']}: {m['content']}" for m in history])
        except Exception as e:
            logger.warning(f"Could not get chat history: {e}")
            return ""
