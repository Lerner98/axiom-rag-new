# Debugging the Context Bleed Bug

**Date:** 2025-12-23
**Bug Type:** State Management / Test Infrastructure
**Resolution Time:** ~2 hours
**Severity:** Critical (caused 100% wrong answers)

## The Problem

### Symptoms
When running sequential queries, the RAG system returned "swapped answers":
- Query 1: "What is CAP theorem?" → Got caching information (WRONG)
- Query 2: "What is caching?" → Got CAP theorem information (WRONG)

### Initial Hypothesis
We thought the `context_filter.py` logic was broken - documents from previous queries were contaminating current query results.

## Investigation Process

### Step 1: Created Context Filter
First, we created `context_filter.py` to filter documents by relevance:

```python
class ContextFilter:
    def filter(self, documents, query, threshold=0.3):
        # Uses FastEmbed similarity to filter irrelevant documents
        similarity = cosine_similarity(query_embedding, doc_embedding)
        if similarity < threshold:
            remove_document()
```

**Result:** Still got swapped answers.

### Step 2: Integrated into grade_documents
Added the filter to the `grade_documents` node in `nodes.py`:

```python
async def grade_documents(self, state: RAGState) -> dict:
    # Step 1: Context filter to prevent context bleed
    docs_to_grade = state["retrieved_documents"]
    try:
        from rag.context_filter import get_context_filter
        context_filter = get_context_filter()
        filter_result = context_filter.filter(docs_to_grade, query)
        docs_to_grade = filter_result.documents
    except Exception as e:
        logger.warning(f"Context filter failed: {e}")

    # Step 2: Reranker...
```

**Result:** Still got swapped answers.

### Step 3: Consulted Gemini
Gemini identified the real issue wasn't the filter logic, but **state management**:

> "The 'swapped answer' bug you're seeing is a massive red flag. It confirms that while the logic in context_filter.py might be sound, the State Management or Concurrency in the pipeline is broken."

Possible causes:
1. **Reducer Problem** - Using `append` instead of `replace` for document state
2. **Key Shadowing** - New key created but old key still used
3. **Shared Instance** - Global variables holding state between requests

### Step 4: Checked LangGraph State
Examined `state.py`:

```python
class RAGState(TypedDict):
    # These DON'T have reducers - they OVERWRITE correctly
    retrieved_documents: list[Document]
    relevant_documents: list[Document]

    # These APPEND with 'add' reducer
    errors: Annotated[list[str], add]
    processing_steps: Annotated[list[str], add]
```

**Finding:** Document lists overwrite correctly. Not a reducer issue.

### Step 5: Checked Server Logs
```
Collection 'chat_test-chat-001' is empty
```

**KEY FINDING:** The test collection had NO DOCUMENTS!

### Step 6: Analyzed Test Script
Original test script:
```javascript
const CHAT_ID = 'test-chat-001';  // Fixed ID for all tests

// All queries use same chat_id AND same session
const { responseText } = await testQuery(port, test.query);
```

**Problems Found:**
1. Fixed `CHAT_ID` - same collection for every test run
2. No document upload - collection was empty
3. Same session - memory accumulated between queries

## Root Cause

The bug was NOT in the RAG pipeline. It was in the **test infrastructure**:

1. **Empty Collection** - Documents were never uploaded to `chat_test-chat-001`
2. **Shared Memory** - Same session_id meant chat history accumulated
3. **LLM Hallucination** - With no documents, LLM used chat history to generate answers

When Query 1 asked about CAP theorem, the LLM generated an answer from memory.
When Query 2 asked about caching, the LLM saw "CAP theorem" in chat history and got confused.

## The Fix

Updated `test-quality.js` with proper isolation:

```javascript
// Single chat ID for document collection
const CHAT_ID = `quality-test-${Date.now()}`;

// Generate unique session ID for memory isolation
function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// Upload documents FIRST
async function uploadTestDocument(port, chatId) {
  // POST to /chat/{chatId}/documents
}

// Each query uses unique session
for (const test of TEST_QUERIES) {
  const sessionId = generateSessionId();
  await testQuery(port, test.query, chatId, sessionId);
}
```

### Key Changes:
1. **Upload documents first** - Documents exist in collection before queries
2. **Unique session per query** - Fresh memory for each test
3. **Same chat_id for all queries** - All queries access same documents

## Verification

After the fix:
```
============================================================
Testing: original_rag (port 8001)
Chat ID: quality-test-1766484608611
============================================================

[simple_factual] "What is the CAP theorem?..."
  Session: session-1766484612096-l46c8lksa
  PASS | Quality: 100% | Keywords: 3/3

[how_to] "How does caching work?..."
  Session: session-1766484624906-ka9fspnp2
  PASS | Quality: 100% | Keywords: 4/4

...

Summary: 8/8 passed | 94% quality
```

## Lessons Learned

### 1. Test Infrastructure Matters
The bug wasn't in the code - it was in how we tested. Always verify:
- Documents are actually uploaded
- Collections aren't empty
- Sessions are properly isolated

### 2. "Swapped Answers" = State Issue
When answers seem to come from the wrong query, look for:
- Shared state between requests
- Memory/history accumulation
- Empty retrieval results forcing LLM to guess

### 3. Gemini's Debugging Approach
Gemini correctly identified this as a state management issue before we found it:
> "This isn't just because of the filter; it's likely a testing environment issue."

### 4. Chat-Scoped Collections
The architecture uses `chat_{chat_id}` as collection names:
- Each chat has its own document collection
- Session ID controls memory/history
- Both must be managed correctly for proper isolation

## Architecture Diagram

```
Test Script
    │
    ├── CHAT_ID: quality-test-{timestamp}
    │   └── Collection: chat_quality-test-{timestamp}
    │       └── Documents: system-design-primer.txt (22 chunks)
    │
    └── For each query:
        └── SESSION_ID: session-{timestamp}-{random}
            └── Memory: Fresh for each query (no accumulation)
```

## Files Changed

| File | Change |
|------|--------|
| `test-quality.js` | Added document upload, unique sessions |
| `nodes.py` | Context filter integration (bonus, not the fix) |
| `context_filter.py` | Created (bonus, not the fix) |

## Conclusion

The "context bleed" bug was a classic case of **debugging the wrong layer**. We spent time optimizing the filter logic when the real issue was that:

1. The test collection was empty
2. The LLM was generating answers from chat history
3. Chat history accumulated because we reused session IDs

**The fix was in test infrastructure, not pipeline logic.**
