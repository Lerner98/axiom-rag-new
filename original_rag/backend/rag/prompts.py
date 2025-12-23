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

GENERATION_PROMPT = """You are a helpful assistant answering questions based on provided context.

RULES:
1. Answer ONLY based on the provided context
2. If the context doesn't contain enough information, say "I don't have enough information about that in the knowledge base"
3. Cite your sources using [Source N] format where N corresponds to the source number
4. Be concise but complete
5. If multiple sources agree, mention that for credibility

Context:
{context}

Question: {question}

Chat history (for conversation continuity):
{chat_history}

Answer:"""


GENERATION_WITH_RETRY_PROMPT = """You are a helpful assistant answering questions based on provided context.

RULES:
1. Answer ONLY based on the provided context - do not add any information not present in the sources
2. If the context doesn't contain enough information, say "I don't have enough information about that in the knowledge base"
3. Cite your sources using [Source N] format where N corresponds to the source number
4. Every claim must be directly traceable to a specific source
5. Be precise and avoid generalizations not supported by the text

Context:
{context}

Question: {question}

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

SOURCE_TEMPLATE = """[Source {index}: {filename}]
{content}
"""

def format_sources_for_prompt(documents: list[dict]) -> str:
    """Format retrieved documents for inclusion in prompts."""
    formatted = []
    for i, doc in enumerate(documents, 1):
        formatted.append(SOURCE_TEMPLATE.format(
            index=i,
            filename=doc.get("metadata", {}).get("filename", "Unknown"),
            content=doc.get("content", "")[:1000]  # Truncate long content
        ))
    return "\n---\n".join(formatted)
