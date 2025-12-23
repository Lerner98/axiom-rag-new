"""
RAG Pipeline Prompts
All prompts used in the RAG pipeline.
"""

# === Query Processing ===

QUERY_REWRITE_PROMPT = """You are a query optimizer for a RAG system.

Your task is to rewrite the user's question to be more effective for semantic search.

Guidelines:
- Expand abbreviations
- Add relevant technical terms
- Make implicit context explicit
- Keep the core intent
- Output ONLY the rewritten query, nothing else

Original question: {question}

Chat history (for context):
{chat_history}

Rewritten query:"""


QUERY_CLASSIFICATION_PROMPT = """Classify the following question into one of these categories:
- factual: Asking for specific facts, definitions, or data
- analytical: Asking for analysis, comparison, or explanation
- conversational: Follow-up question or clarification

Question: {question}

Output ONLY one word: factual, analytical, or conversational"""


# === Retrieval Grading ===

RELEVANCE_GRADING_PROMPT = """You are a relevance grader for a RAG system.

Evaluate if the following document is relevant to the question.
A document is relevant if it contains information that could help answer the question, even partially.

Question: {question}

Document:
{document}

Is this document relevant? Answer with ONLY 'yes' or 'no':"""


# === Generation ===

# NOTE: Prompt order optimized for Ollama KV cache hits
# Static content (system + rules) at TOP -> cached across queries
# Dynamic content (context, history, question) at BOTTOM -> varies per query
GENERATION_PROMPT = """Answer the user's question using the provided context.

RULES:
1. Answer directly based on what's in the context - don't be overly cautious
2. If the context contains relevant information, USE IT to answer
3. Only say you don't know if the context truly has nothing relevant
4. Write naturally - never mention "context", "documents", "sources", or use citations like [Source 1]
5. Match answer length to question complexity

CONTEXT:
{context}

CHAT HISTORY:
{chat_history}

QUESTION: {question}

Answer:"""


# NOTE: Retry prompt also optimized for KV cache
GENERATION_WITH_RETRY_PROMPT = """Your previous answer may have included unsupported information. Try again, sticking strictly to the context.

RULES:
1. ONLY use information explicitly stated in the context
2. If something isn't clearly stated, don't include it
3. Never use citations like [Source 1] - the UI shows sources separately
4. Write naturally without mentioning "context" or "documents"

CONTEXT:
{context}

QUESTION: {question}

Answer:"""


# === Hallucination Checking ===

HALLUCINATION_CHECK_PROMPT = """You are a fact-checker for a RAG system.

Your task is to verify if the answer is grounded in the provided sources.
An answer is grounded if every claim can be traced back to the sources.

Sources:
{sources}

Answer to verify:
{answer}

For each claim in the answer, determine if it's supported by the sources.

Output your analysis in this exact format:
GROUNDED: yes/no
SCORE: 0.0-1.0 (what percentage of claims are supported)
ISSUES: List any unsupported claims, or "None" if fully grounded

Analysis:"""


CLAIM_EXTRACTION_PROMPT = """Extract all factual claims from the following answer.
Output each claim on a new line.
Only extract verifiable factual claims, not opinions or hedged statements.

Answer: {answer}

Claims:"""


# === Conversation Memory ===

SUMMARIZE_HISTORY_PROMPT = """Summarize the following conversation history in 2-3 sentences.
Focus on the main topics discussed and any important context.

Conversation:
{history}

Summary:"""


# === Source Formatting ===

SOURCE_TEMPLATE = """--- {filename} ---
{content}
"""

def format_sources_for_prompt(documents: list[dict]) -> str:
    """Format retrieved documents for inclusion in prompts."""
    formatted = []
    for doc in documents:
        content = doc.get("content", "")[:1000]
        # Try to truncate at sentence boundary
        if len(content) == 1000:
            last_period = content.rfind('.')
            if last_period > 700:
                content = content[:last_period + 1]

        formatted.append(SOURCE_TEMPLATE.format(
            filename=doc.get("metadata", {}).get("filename", "Unknown"),
            content=content
        ))
    return "\n".join(formatted)
