"""
RAG Pipeline - V5 with Intent Classification + Context-Aware Handlers

Flow:
classify_intent → [needs_rag?]
    → NO: handle_non_rag_intent → END (greeting, gratitude, followup, simplify, deepen)
    → YES: route_query → [SUMMARIZE?] → retrieve_sequential → grade → generate
                       → [SIMPLE?] → retrieve (skip rewrite)
                       → [COMPLEX?] → rewrite_query → retrieve

Changes from V4:
- Added classify_intent as new entry point
- Added handle_non_rag_intent for non-RAG intents
- Context-aware handlers: followup, simplify, deepen use conversation memory
- Intent router: 3-layer hybrid (hard rules → semantic → LLM)
"""
from typing import AsyncGenerator
import logging

from langgraph.graph import StateGraph, END

from rag.state import RAGState, create_initial_state
from rag.nodes import RAGNodes, needs_rag, should_rewrite, has_relevant_docs, should_retry
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
            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0
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
        """Stream a query through the RAG pipeline."""
        collection = collection_name or settings.collection_name
        
        logger.info(f"Starting RAG stream: '{question[:50]}...' in collection '{collection}'")
        
        initial_state = create_initial_state(
            question=question,
            session_id=session_id,
            collection_name=collection,
            max_iterations=settings.max_retries
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        logger.info(f"RAG stream complete. Steps: {final_state['processing_steps']}")
        
        # Stream words
        words = final_state["answer"].split()
        for word in words:
            yield {"type": "token", "content": word + " "}
        
        # Send sources
        yield {"type": "sources", "sources": final_state["sources"]}
        
        # Send done
        yield {
            "type": "done",
            "is_grounded": final_state["is_grounded"],
            "iterations": final_state["iteration"],
            "query_complexity": final_state.get("query_complexity"),
            "is_summarization": final_state.get("is_summarization", False),
        }
