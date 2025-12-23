"""
RAG Pipeline Nodes - V4 with Intent Classification (ADR-011)

Changes from V3:
- Added classify_intent node as new entry point
- Intent router: greeting/gratitude/garbage skip RAG entirely
- Existing route_query only runs for question/command intents
- Added handle_non_rag_intent node for fast responses

Flow:
  classify_intent → [greeting/gratitude/garbage] → handle_non_rag_intent → END
                  → [question/command] → route_query → (existing flow)
"""
from typing import Literal, List, Tuple, Dict
import logging
import re

from langchain_core.documents import Document

from rag.state import RAGState, Document as StateDocument
from rag.prompts import (
    QUERY_REWRITE_PROMPT,
    GENERATION_PROMPT,
    GENERATION_WITH_RETRY_PROMPT,
    HALLUCINATION_CHECK_PROMPT,
    format_sources_for_prompt,
)
from rag.utils import extract_relevant_snippet
from config.settings import settings

logger = logging.getLogger(__name__)


# Router Agent Prompt (unchanged from V3)
ROUTER_PROMPT = """Classify this query's complexity. Be strict.

Query: {question}
Chat History: {chat_history}

Rules:
- SIMPLE: Single direct question, one topic, no comparison, no analysis
  ONLY these patterns: "What is X?", "Define X", "Who is X?", "When did X?"
- COMPLEX: ANY of these → COMPLEX:
  * Contains "compare", "contrast", "vs", "difference", "relationship"
  * References document parts: "section", "chapter", "appendix", "paragraph"
  * Multi-part: "and also", "as well as", multiple question marks
  * Requires analysis: "why", "how does X affect Y", "explain how"
- CONVERSATIONAL: References prior context without being explicit
  * Pronouns without antecedent: "it", "that", "those", "the one"
  * Follow-ups: "tell me more", "elaborate", "continue", "and?"

If uncertain, choose COMPLEX.

Answer with exactly one word: SIMPLE, COMPLEX, or CONVERSATIONAL"""


class RAGNodes:
    """Collection of nodes for the RAG pipeline."""
    
    def __init__(self, llm, vectorstore, memory=None):
        self.llm = llm
        self.vectorstore = vectorstore
        self.memory = memory
        self._reranker = None
        self._reranker_initialized = False
        self._hybrid_retriever = None
        self._hybrid_retriever_initialized = False
        self._intent_router = None
        self._intent_router_initialized = False
    
    def _get_reranker(self):
        """Lazy initialization of reranker. Returns None if unavailable."""
        if self._reranker_initialized:
            return self._reranker
        
        try:
            from rag.reranker import create_reranker
            self._reranker = create_reranker(
                backend="cross-encoder",
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            logger.info("Cross-encoder reranker initialized successfully")
        except ImportError as e:
            logger.warning(f"Reranker not available (missing dependency): {e}")
            logger.warning("Install with: pip install sentence-transformers")
            self._reranker = None
        except Exception as e:
            logger.warning(f"Reranker initialization failed: {e}")
            self._reranker = None
        
        self._reranker_initialized = True
        return self._reranker
    
    def _get_hybrid_retriever(self):
        """Lazy initialization of hybrid retriever."""
        if self._hybrid_retriever_initialized:
            return self._hybrid_retriever
        
        try:
            from rag.retriever import get_hybrid_retriever
            self._hybrid_retriever = get_hybrid_retriever(self.vectorstore)
            logger.info("HybridRetriever initialized successfully")
        except Exception as e:
            logger.warning(f"HybridRetriever initialization failed: {e}")
            self._hybrid_retriever = None
        
        self._hybrid_retriever_initialized = True
        return self._hybrid_retriever
    
    def _get_intent_router(self):
        """Lazy initialization of intent router."""
        if self._intent_router_initialized:
            return self._intent_router
        
        try:
            from rag.intent_router import IntentRouter
            self._intent_router = IntentRouter(llm=self.llm)
            logger.info("IntentRouter initialized successfully")
        except Exception as e:
            logger.warning(f"IntentRouter initialization failed: {e}")
            self._intent_router = None
        
        self._intent_router_initialized = True
        return self._intent_router
    
    # ========================================================================
    # INTENT CLASSIFICATION (NEW - V4)
    # ========================================================================
    
    async def classify_intent(self, state: RAGState) -> dict:
        """
        Classify user intent BEFORE routing to RAG.
        
        This is the NEW entry point for the pipeline (replaces route_query as entry).
        Determines if query needs RAG at all, or can be handled directly.
        
        Returns:
            detected_intent: The classified intent type
            intent_confidence: Confidence score (0.0-1.0)
        """
        logger.info(f"Classifying intent: {state['question'][:50]}...")
        
        intent_router = self._get_intent_router()
        
        if intent_router:
            intent, confidence = await intent_router.classify(state["question"])
        else:
            # Fallback: assume question if router unavailable
            logger.warning("IntentRouter unavailable, defaulting to 'question'")
            intent = "question"
            confidence = 0.5

        # FIX: Conversation-dependent intents (followup, simplify, deepen) need prior context.
        # If no chat history exists, these should fall back to "question" to trigger RAG.
        conversation_intents = {"followup", "simplify", "deepen"}
        if intent in conversation_intents:
            # Check if there's any conversation history for this session
            has_history = False
            if self.memory and state.get("session_id"):
                try:
                    history = await self.memory.get_history(state["session_id"], limit=1)
                    has_history = len(history) > 0
                except Exception as e:
                    logger.debug(f"Could not check history: {e}")

            if not has_history:
                logger.info(f"Intent '{intent}' has no conversation history - falling back to 'question'")
                intent = "question"
                confidence = 1.0  # High confidence since this is a deliberate override

        logger.info(f"Intent classified as: {intent} (confidence={confidence:.2f})")
        
        return {
            "detected_intent": intent,
            "intent_confidence": confidence,
            "processing_steps": ["classify_intent"],
        }
    
    async def handle_non_rag_intent(self, state: RAGState) -> dict:
        """
        Handle intents that don't require RAG (greeting, gratitude, garbage, etc.)
        
        This node produces a final answer and skips the entire RAG pipeline.
        
        V2: Now supports context-aware handlers (followup, simplify, deepen)
        that need conversation history from memory.
        """
        intent = state.get("detected_intent", "unknown")
        logger.info(f"Handling non-RAG intent: {intent}")
        
        try:
            from rag.intent_handlers import dispatch_intent_handler
            
            # Call dispatcher with full context for context-aware handlers
            result = await dispatch_intent_handler(
                intent=intent,
                query=state["question"],
                session_id=state.get("session_id"),
                memory=self.memory,
                llm=self.llm,
            )
            
            # Check if handler says we need context but don't have it
            if result.needs_rag:
                logger.info(f"Handler {result.handler_used} has no context")
                # Provide helpful message instead of RAG fallback
                return {
                    "answer": "I don't have a previous answer to work with. Could you ask a specific question about your documents first?",
                    "sources": [],
                    "is_grounded": True,
                    "groundedness_score": 1.0,
                    "processing_steps": [f"{result.handler_used}_no_context"],
                }
            
            # Handler produced a final answer
            return {
                "answer": result.answer,
                "sources": result.sources,
                "is_grounded": True,
                "groundedness_score": 1.0,
                "processing_steps": [result.handler_used],
            }
            
        except ImportError as e:
            logger.error(f"Intent handlers not available: {e}")
            return {
                "answer": "I encountered an error. Please try asking a question about your documents.",
                "sources": [],
                "is_grounded": True,
                "groundedness_score": 1.0,
                "processing_steps": ["handle_non_rag_error"],
            }
        except Exception as e:
            logger.error(f"Error in non-RAG intent handler: {e}")
            return {
                "answer": "Something went wrong. Could you try rephrasing your question?",
                "sources": [],
                "is_grounded": True,
                "groundedness_score": 1.0,
                "processing_steps": ["handle_non_rag_exception"],
            }
    
    # ========================================================================
    # ROUTER AGENT (existing, now runs AFTER intent classification)
    # ========================================================================
    
    async def route_query(self, state: RAGState) -> dict:
        """Router Agent - FAST heuristic-only classification (NO LLM)."""
        logger.info(f"Routing query: {state['question'][:50]}...")
        question = state["question"].lower()
        complex_patterns = ["compare", "contrast", "vs", "difference"]
        is_complex = any(p in question for p in complex_patterns) or question.count("?") > 1
        if is_complex:
            query_complexity = "complex"
            skip_rewrite = False
        else:
            query_complexity = "simple"
            skip_rewrite = True
        logger.info(f"Query classified as: {query_complexity} (FAST)")
        return {
            "query_complexity": query_complexity,
            "skip_rewrite": skip_rewrite,
            "processing_steps": ["route_query_fast"],
        }
    
    # ========================================================================
    # QUERY PROCESSING
    # ========================================================================
    
    async def rewrite_query(self, state: RAGState) -> dict:
        """Rewrite the query for better retrieval."""
        logger.info(f"Rewriting query (attempt {state.get('rewrite_count', 0) + 1})")
        
        chat_history = ""
        if self.memory:
            history = await self.memory.get_history(state["session_id"], limit=5)
            chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        
        prompt = QUERY_REWRITE_PROMPT.format(
            question=state["question"],
            chat_history=chat_history or "No previous conversation"
        )
        
        rewritten = await self.llm.ainvoke(prompt)
        rewritten_query = rewritten.content.strip()
        
        new_rewrite_count = state.get("rewrite_count", 0) + 1
        
        return {
            "rewritten_query": rewritten_query,
            "rewrite_count": new_rewrite_count,
            "processing_steps": ["query_rewrite"],
        }
    
    # ========================================================================
    # SEQUENTIAL RETRIEVAL (for summarization)
    # ========================================================================
    
    async def retrieve_sequential(self, state: RAGState) -> dict:
        """
        Bypass vector search - get ALL chunks in page order for summarization.
        
        This is used when user asks for document overview/summary.
        Vector search finds "needles in haystack" - this returns the whole haystack.
        """
        logger.info(f"Sequential retrieval for summarization: {state['collection_name']}")
        
        # Get all chunks (not similarity search)
        try:
            all_docs = await self.vectorstore.get_all_chunks(
                state["collection_name"],
                limit=500  # Reasonable limit for context window
            )
        except Exception as e:
            logger.error(f"Failed to get all chunks: {e}")
            all_docs = []
        
        if not all_docs:
            logger.warning("No documents found for summarization")
            return {
                "retrieved_documents": [],
                "collection_empty": True,
                "is_summarization": True,
                "processing_steps": ["retrieve_sequential_empty"],
            }
        
        # Sort by page order (CRITICAL for "top to bottom")
        def sort_key(doc):
            meta = doc.metadata
            page = meta.get('page', 0)
            if isinstance(page, str):
                try:
                    page = int(page)
                except:
                    page = 9999
            parent_idx = meta.get('parent_index', 0) or 0
            child_idx = meta.get('child_index', 0) or 0
            return (page, parent_idx, child_idx)
        
        all_docs.sort(key=sort_key)
        
        # Deduplicate by parent_id, use parent_context for coherence
        seen_parents = set()
        unique_docs = []
        
        for doc in all_docs:
            parent_id = doc.metadata.get('parent_id')
            
            if parent_id:
                if parent_id not in seen_parents:
                    seen_parents.add(parent_id)
                    # Use parent content (larger, more coherent)
                    parent_content = doc.metadata.get('parent_context', doc.page_content)
                    unique_docs.append({
                        "content": parent_content,
                        "metadata": doc.metadata,
                        "relevance_score": 100.0,  # All docs relevant for summary
                    })
            else:
                # No parent-child structure, include as-is
                unique_docs.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": 100.0,
                })
        
        logger.info(f"Sequential retrieval: {len(all_docs)} chunks -> {len(unique_docs)} unique parents (page-ordered)")
        
        return {
            "retrieved_documents": unique_docs,
            "collection_empty": False,
            "is_summarization": True,
            "processing_steps": ["retrieve_sequential"],
        }
    
    # ========================================================================
    # HYBRID RETRIEVAL WITH PARENT EXPANSION
    # ========================================================================
    
    async def retrieve(self, state: RAGState) -> dict:
        """
        Hybrid retrieval with parent expansion.
        
        Flow:
        1. HybridRetriever: Vector + BM25 + RRF fusion (k=50)
        2. Parent expansion: Replace child content with parent_context
        3. Deduplicate by parent_id
        4. Pass to reranker/grading
        """
        logger.info(f"Retrieving documents (HYBRID + PARENT EXPANSION) from: {state['collection_name']}")
        
        query = state.get("rewritten_query") or state["question"]
        initial_k = settings.retrieval_initial_k  # 50
        
        hybrid_retriever = self._get_hybrid_retriever()
        
        results = []
        collection_empty = False
        
        if hybrid_retriever:
            try:
                # Use hybrid search with parent expansion
                results = await hybrid_retriever.search_with_parent_expansion(
                    query=query,
                    collection_name=state["collection_name"],
                    initial_k=initial_k,
                    final_k=initial_k,  # Let reranker do final filtering
                )
                logger.info(f"Hybrid retrieval returned {len(results)} results")
            except Exception as e:
                logger.warning(f"Hybrid retrieval failed: {e}")
                results = []
        
        # Fallback to vector-only search if hybrid fails
        if not results:
            logger.info("Falling back to vector-only search")
            try:
                vector_results = await self.vectorstore.similarity_search_with_score(
                    query=query,
                    collection_name=state["collection_name"],
                    k=initial_k,
                )
                
                # Apply parent expansion manually
                results = self._expand_to_parents(vector_results)
                logger.info(f"Vector fallback returned {len(results)} results")
            except Exception as e:
                logger.error(f"Vector search also failed: {e}")
                results = []
        
        # Check if collection is empty
        if not results:
            try:
                collection_info = await self.vectorstore.get_collection_info(state["collection_name"])
                if collection_info is None or collection_info.get("count", 0) == 0:
                    collection_empty = True
                    logger.info(f"Collection '{state['collection_name']}' is empty")
            except Exception:
                pass
        
        # Convert to state format
        retrieved_documents = []
        for doc, score in results:
            retrieved_documents.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": float(score) * 100,  # Convert to percentage
            })
        
        logger.info(f"Retrieved {len(retrieved_documents)} documents for grading")
        
        return {
            "retrieved_documents": retrieved_documents,
            "collection_empty": collection_empty,
            "processing_steps": ["retrieve_hybrid"],
        }
    
    def _expand_to_parents(
        self, 
        results: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """
        Expand child chunks to parent context.
        
        Deduplicates by parent_id and replaces content with parent_context.
        """
        seen_parents: Dict[str, Tuple[Document, float]] = {}
        no_parent_docs: List[Tuple[Document, float]] = []
        
        for doc, score in results:
            parent_id = doc.metadata.get("parent_id")
            
            if parent_id:
                if parent_id not in seen_parents:
                    # Get parent context from metadata
                    parent_context = doc.metadata.get("parent_context", doc.page_content)
                    
                    # Create expanded document
                    expanded_doc = Document(
                        page_content=parent_context,
                        metadata={
                            **doc.metadata,
                            "retrieval_score": score,
                            "expanded_from_child": True,
                        }
                    )
                    seen_parents[parent_id] = (expanded_doc, score)
            else:
                # No parent - include as-is
                no_parent_docs.append((doc, score))
        
        # Combine and sort by score
        all_docs = list(seen_parents.values()) + no_parent_docs
        all_docs.sort(key=lambda x: x[1], reverse=True)
        
        return all_docs
    
    # ========================================================================
    # DOCUMENT GRADING WITH RERANKER
    # ========================================================================
    
    async def grade_documents(self, state: RAGState) -> dict:
        """
        Grade documents using context filter + cross-encoder reranker.

        Flow:
        1. Context filter: Remove docs irrelevant to current query (prevents context bleed)
        2. Reranker: Score and rank remaining docs
        3. Return top K to LLM (ADAPTIVE: K=2 for simple, K=5 for complex)
        """
        logger.info(f"Grading {len(state['retrieved_documents'])} documents")

        if not state["retrieved_documents"]:
            logger.info("No documents to grade")
            return {
                "relevant_documents": [],
                "sources": [],
                "processing_steps": ["grade_empty"],
            }

        query = state.get("rewritten_query") or state["question"]

        # ADAPTIVE K: Simple queries need fewer docs (faster prefill)
        # Simple: K=2 (~1200 tokens), Complex: K=5 (~3000 tokens)
        query_complexity = state.get("query_complexity", "complex")
        if query_complexity == "simple":
            final_k = 2
            logger.info("Adaptive K: Using K=2 for simple query (faster prefill)")
        else:
            final_k = settings.retrieval_final_k  # 5
            logger.info(f"Adaptive K: Using K={final_k} for {query_complexity} query")

        # Step 1: Context filter to prevent context bleed
        docs_to_grade = state["retrieved_documents"]
        try:
            from rag.context_filter import get_context_filter
            context_filter = get_context_filter()
            filter_result = context_filter.filter(docs_to_grade, query)

            if filter_result.removed_count > 0:
                logger.info(f"Context filter: {filter_result.original_count} -> {filter_result.filtered_count} docs")

            docs_to_grade = filter_result.documents
        except ImportError:
            logger.debug("Context filter not available")
        except Exception as e:
            logger.warning(f"Context filter failed: {e}")
        
        # Step 2: Reranker
        reranker = self._get_reranker()

        if reranker and docs_to_grade:
            try:
                # Prepare documents for reranking
                doc_texts = [d["content"] for d in docs_to_grade]
                
                # Rerank
                reranked = await reranker.rerank(
                    query=query,
                    documents=doc_texts,
                    top_k=final_k,
                )
                
                # Build relevant documents from reranked results
                relevant_documents = []
                sources_by_file = {}  # Dedupe by filename - show DOCUMENTS not chunks

                for orig_idx, score in reranked:
                    doc = docs_to_grade[orig_idx]

                    # Update relevance score with reranker score
                    doc_with_score = {
                        **doc,
                        "relevance_score": float(score) * 100,  # Convert to percentage
                    }
                    relevant_documents.append(doc_with_score)

                    # Group by document filename - keep highest scoring chunk's info
                    filename = doc["metadata"].get("source", "unknown")
                    score_pct = float(score) * 100

                    if filename not in sources_by_file or score_pct > sources_by_file[filename]["relevance_score"]:
                        sources_by_file[filename] = {
                            "source": filename,
                            "filename": filename,
                            "page": doc["metadata"].get("page"),
                            "chunk_id": doc["metadata"].get("chunk_id", ""),
                            "relevance_score": score_pct,
                            "content_preview": extract_relevant_snippet(query, doc["content"]),
                        }

                sources = list(sources_by_file.values())
                logger.info(f"Reranker: {len(relevant_documents)} chunks from {len(sources)} unique documents")

                return {
                    "relevant_documents": relevant_documents,
                    "sources": sources,
                    "processing_steps": ["grade_context_filter", "grade_reranker"],
                }

            except Exception as e:
                logger.warning(f"Reranker failed: {e}, falling back to score threshold")

        # Fallback: Filter by relevance threshold
        threshold = settings.relevance_threshold * 100  # Convert to percentage

        relevant_documents = []
        sources_by_file = {}  # Dedupe by filename - show DOCUMENTS not chunks

        # Sort by score and take top final_k
        sorted_docs = sorted(
            docs_to_grade,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )[:final_k]

        for doc in sorted_docs:
            score = doc.get("relevance_score", 0)

            # Include if above threshold OR if we have no relevant docs yet
            if score >= threshold or not relevant_documents:
                relevant_documents.append(doc)

                # Group by document filename - keep highest scoring chunk's info
                filename = doc["metadata"].get("source", "unknown")
                if filename not in sources_by_file or score > sources_by_file[filename]["relevance_score"]:
                    sources_by_file[filename] = {
                        "source": filename,
                        "filename": filename,
                        "page": doc["metadata"].get("page"),
                        "chunk_id": doc["metadata"].get("chunk_id", ""),
                        "relevance_score": score,
                        "content_preview": extract_relevant_snippet(query, doc["content"]),
                    }

        sources = list(sources_by_file.values())
        logger.info(f"Threshold: {len(relevant_documents)} chunks from {len(sources)} unique documents")

        return {
            "relevant_documents": relevant_documents,
            "sources": sources,
            "processing_steps": ["grade_context_filter", "grade_threshold"],
        }
    
    # ========================================================================
    # GENERATION
    # ========================================================================
    
    async def generate(self, state: RAGState) -> dict:
        """Generate answer from relevant documents."""
        logger.info(f"Generating answer (iteration {state['iteration']})")

        # Build context from relevant documents (LLMLingua DISABLED for benchmarking)
        # LLMLingua was adding ~14s overhead for small context sizes (~810 tokens)
        # Re-enable if context exceeds 2000+ tokens where compression benefits outweigh overhead
        if state.get("relevant_documents"):
            context_parts = []
            for i, doc in enumerate(state["relevant_documents"], 1):
                source = doc["metadata"].get("source", "unknown")
                page = doc["metadata"].get("page", "")
                page_str = f" (page {page})" if page else ""
                context_parts.append(f"[Source {i}: {source}{page_str}]\n{doc['content']}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant documents found in the knowledge base."

        # Get chat history
        chat_history = ""
        if self.memory:
            history = await self.memory.get_history(state["session_id"], limit=5)
            chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in history])

        # Choose prompt based on iteration
        # On retry, use stricter prompt (but don't mention "improving" to avoid LLM echoing that)
        if state["iteration"] > 0:
            prompt = GENERATION_WITH_RETRY_PROMPT.format(
                context=context,
                question=state["question"],
            )
        else:
            prompt = GENERATION_PROMPT.format(
                context=context,
                question=state["question"],
                chat_history=chat_history or "No previous conversation",
            )

        response = await self.llm.ainvoke(prompt)
        answer = response.content.strip()

        return {
            "answer": answer,
            "processing_steps": ["generate"],
        }
    
    # ========================================================================
    # HALLUCINATION CHECK (HYBRID: FAST + LLM)
    # ========================================================================
    
    def _fast_groundedness_check(self, answer: str, sources: list[dict]) -> float:
        """
        Fast deterministic groundedness check using word/trigram overlap.
        
        Returns score 0.0-1.0:
        - >= 0.8: High confidence grounded (skip LLM check)
        - 0.3-0.8: Ambiguous (need LLM check)
        - < 0.3: High confidence NOT grounded (skip LLM check)
        """
        if not sources:
            return 0.5
        
        # Combine all source content
        source_text = " ".join(s.get("content", s.get("page_content", "")) for s in sources).lower()
        
        if not source_text.strip():
            return 0.5
        
        answer_lower = answer.lower()
        
        # Stopwords to ignore
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
            'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
            'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
            'because', 'until', 'while', 'this', 'that', 'these', 'those', 'it',
            'its', 'i', 'me', 'my', 'myself', 'we', 'our', 'you', 'your', 'he',
            'him', 'his', 'she', 'her', 'they', 'them', 'their', 'what', 'which',
            'who', 'whom', 'according', 'based', 'provided', 'context', 'document',
            'source', 'information', 'answer', 'question'
        }
        
        # Extract content words from answer
        answer_words = set(re.findall(r'\b[a-z]{3,}\b', answer_lower)) - stopwords
        
        if not answer_words:
            return 0.5
        
        # Word overlap score
        matched_words = sum(1 for word in answer_words if word in source_text)
        word_overlap_score = matched_words / len(answer_words) if answer_words else 0
        
        # Trigram overlap score
        answer_trigrams = set()
        words = answer_lower.split()
        for i in range(len(words) - 2):
            trigram = " ".join(words[i:i+3])
            trigram_words = set(words[i:i+3])
            if len(trigram_words - stopwords) >= 2:
                answer_trigrams.add(trigram)
        
        matched_trigrams = sum(1 for tg in answer_trigrams if tg in source_text)
        trigram_score = matched_trigrams / len(answer_trigrams) if answer_trigrams else 0
        
        # Weighted combination
        final_score = (word_overlap_score * 0.6) + (trigram_score * 0.4)
        
        logger.info(f"Fast groundedness: word={word_overlap_score:.2f}, trigram={trigram_score:.2f}, final={final_score:.2f}")
        
        return final_score
    
    async def check_hallucination(self, state: RAGState) -> dict:
        """
        Hybrid hallucination check: fast deterministic first, LLM if ambiguous.

        OPTIMIZATION: For simple queries with high retrieval scores, skip entirely.
        This saves ~3-5s on simple factual queries where hallucination is unlikely.
        """
        logger.info("Checking for hallucinations (hybrid)")

        if not state.get("relevant_documents"):
            logger.info("Skipping hallucination check - no documents")
            return {
                "is_grounded": True,
                "groundedness_score": 1.0,
                "fast_groundedness_score": 1.0,
                "skip_llm_hallucination_check": True,
                "hallucination_details": None,
                "iteration": state["iteration"] + 1,
                "processing_steps": ["hallucination_skip"],
            }

        # OPTIMIZATION: Skip hallucination check for simple queries with high-confidence retrieval
        # Simple queries with top doc score >= 70% are unlikely to hallucinate
        query_complexity = state.get("query_complexity", "complex")
        if query_complexity == "simple":
            top_score = max(
                (d.get("relevance_score", 0) for d in state["relevant_documents"]),
                default=0
            )
            if top_score >= 70:  # 70% retrieval confidence
                logger.info(f"FAST PATH: Skipping hallucination check (simple + high retrieval score={top_score:.1f}%)")
                return {
                    "is_grounded": True,
                    "groundedness_score": top_score / 100,
                    "fast_groundedness_score": top_score / 100,
                    "skip_llm_hallucination_check": True,
                    "hallucination_details": None,
                    "iteration": state["iteration"] + 1,
                    "processing_steps": ["hallucination_skip_simple_highconf"],
                }

        sources_for_check = [
            {"content": d["content"], "metadata": d["metadata"]}
            for d in state["relevant_documents"]
        ]

        # Fast check first
        fast_score = self._fast_groundedness_check(state["answer"], sources_for_check)
        
        # High confidence grounded
        if fast_score >= 0.8:
            logger.info(f"Fast check PASSED (score={fast_score:.2f}), skipping LLM")
            return {
                "is_grounded": True,
                "groundedness_score": fast_score,
                "fast_groundedness_score": fast_score,
                "skip_llm_hallucination_check": True,
                "hallucination_details": None,
                "iteration": state["iteration"] + 1,
                "processing_steps": ["hallucination_fast_pass"],
            }
        
        # High confidence NOT grounded
        if fast_score < 0.3:
            logger.info(f"Fast check FAILED (score={fast_score:.2f}), skipping LLM")
            return {
                "is_grounded": False,
                "groundedness_score": fast_score,
                "fast_groundedness_score": fast_score,
                "skip_llm_hallucination_check": True,
                "hallucination_details": "Answer contains claims not found in sources",
                "iteration": state["iteration"] + 1,
                "processing_steps": ["hallucination_fast_fail"],
            }
        
        # Ambiguous - use LLM
        logger.info(f"Fast check AMBIGUOUS (score={fast_score:.2f}), calling LLM")
        
        sources_text = format_sources_for_prompt(sources_for_check)
        
        prompt = HALLUCINATION_CHECK_PROMPT.format(
            sources=sources_text,
            answer=state["answer"]
        )
        
        response = await self.llm.ainvoke(prompt)
        analysis = response.content.strip()
        
        is_grounded = "grounded: yes" in analysis.lower()
        
        # Try to parse score from response
        score = fast_score
        if "SCORE:" in analysis:
            try:
                score_line = [l for l in analysis.split("\n") if "SCORE:" in l][0]
                score = float(score_line.split(":")[1].strip())
            except:
                pass
        
        # Parse issues
        issues = None
        if "ISSUES:" in analysis:
            try:
                issues_line = analysis.split("ISSUES:")[1].strip()
                if issues_line.lower() != "none":
                    issues = issues_line
            except:
                pass
        
        return {
            "is_grounded": is_grounded,
            "groundedness_score": score,
            "fast_groundedness_score": fast_score,
            "skip_llm_hallucination_check": False,
            "hallucination_details": issues,
            "iteration": state["iteration"] + 1,
            "processing_steps": ["hallucination_llm_check"],
        }
    
    # ========================================================================
    # MEMORY
    # ========================================================================
    
    async def save_to_memory(self, state: RAGState) -> dict:
        """Save the Q&A to conversation memory."""
        if self.memory:
            await self.memory.add_message(
                session_id=state["session_id"],
                role="user",
                content=state["question"]
            )
            await self.memory.add_message(
                session_id=state["session_id"],
                role="assistant",
                content=state["answer"],
                metadata={"sources": state["sources"]}
            )
        
        return {"processing_steps": ["save_to_memory"]}

    async def handle_garbage_query(self, state: RAGState) -> dict:
        """
        Handle garbage/nonsense queries - skip RAG entirely.
        Returns a polite message asking for clarification.
        """
        logger.info(f"Handling garbage query: {state['question'][:50]}...")

        return {
            "answer": "I'm not sure I understand your question. Could you please rephrase it or ask something about the documents?",
            "sources": [],
            "is_grounded": True,
            "groundedness_score": 1.0,
            "processing_steps": ["handle_garbage_query"],
        }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def needs_rag(state: RAGState) -> Literal["rag", "no_rag"]:
    """
    NEW: Decide if query needs RAG based on intent classification.
    
    Routes:
    - question, command → "rag" (continue to route_query)
    - greeting, gratitude, garbage, off_topic, etc. → "no_rag" (skip to handler)
    """
    intent = state.get("detected_intent")
    
    # These intents need RAG
    rag_intents = {"question", "command"}
    
    if intent in rag_intents:
        logger.debug(f"Intent '{intent}' needs RAG")
        return "rag"
    
    # All other intents skip RAG
    logger.debug(f"Intent '{intent}' skips RAG")
    return "no_rag"


def should_rewrite(state: RAGState) -> Literal["rewrite", "retrieve"]:
    """Router decision - should we rewrite the query or go direct to retrieve?"""
    if state.get("skip_rewrite", False):
        logger.debug("Skipping rewrite (simple query)")
        return "retrieve"
    logger.debug("Query needs rewrite")
    return "rewrite"


def has_relevant_docs(state: RAGState) -> Literal["generate", "rewrite"]:
    """Decide whether to generate or rewrite query."""
    rewrite_count = state.get("rewrite_count", 0)
    max_iterations = state.get("max_iterations", 2)
    
    logger.debug(f"has_relevant_docs: rewrite_count={rewrite_count}, max={max_iterations}, "
                 f"collection_empty={state.get('collection_empty', False)}, "
                 f"relevant_docs={len(state.get('relevant_documents', []))}")
    
    if rewrite_count >= max_iterations:
        logger.warning(f"Max rewrite attempts ({rewrite_count}) reached, forcing generate")
        return "generate"
    
    if state.get("collection_empty", False):
        logger.info("Collection is empty - going to generate")
        return "generate"
    
    if state.get("relevant_documents"):
        return "generate"
    
    logger.info(f"No relevant docs, rewriting (attempt {rewrite_count + 1}/{max_iterations})")
    return "rewrite"


def should_retry(state: RAGState) -> Literal["retry", "finish"]:
    """Decide whether to retry generation or finish."""
    if state["is_grounded"]:
        return "finish"
    
    if state["iteration"] >= state["max_iterations"]:
        return "finish"
    
    return "retry"

