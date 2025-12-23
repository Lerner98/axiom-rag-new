# Post-Mortem Report: PM-002

## LangGraph State Field Silent Drop Bug

**Date:** 2025-12-13
**Severity:** High
**Component:** Backend RAG Pipeline
**Root Cause:** Missing TypedDict field causing silent state merge failure
**Resolution Time:** ~45 minutes (from identification to fix)

---

## 1. Executive Summary

A new summarization feature was added to the RAG pipeline that routed "summarize the document" queries to a sequential retrieval path instead of the standard hybrid search. The feature appeared to work (logs showed correct classification) but silently failed at runtime, always falling back to the wrong code path.

**Root Cause:** The new `is_summarization` field was returned by `route_query()` but was never defined in the `RAGState` TypedDict. LangGraph silently dropped the field during state merging, causing the routing decision to fail.

---

## Key Takeaways

**The Core Issue:** LangGraph silently drops fields from node returns that aren't defined in the TypedDict. No error, no warning.

**Why It's Dangerous:**
- The feature *appeared* to work (logs showed correct classification)
- The failure happened silently at the state merge step
- Both code paths generate answers, making it hard to notice the wrong path was taken

**Feature Addition Checklist (New Rule):**
```
□ Identify all NEW state fields
□ Add fields to TypedDict definition
□ Add fields to create_initial_state()
□ Update any Literal types that need new values
□ Test state.get("new_field") returns expected value
```

**Debugging Strategy:** When a conditional edge routes incorrectly, check if the fields it reads actually exist in the TypedDict.

---

## 2. Timeline

| Time | Event |
|------|-------|
| T+0 | Opus added summarization feature: new `route_query()` logic, `retrieve_sequential` node, `should_rewrite()` router with "summarize" branch |
| T+1 | Feature deployed, appeared to work based on initial log: `Query classified as: SUMMARIZE` |
| T+2 | User reported issue: summarization queries not working correctly |
| T+3 | Logs examined - found `Skipping rewrite (simple query)` immediately after `SUMMARIZE` classification |
| T+4 | Opus hypothesized: file not deployed, bytecode cache, or state merge issue |
| T+5 | Verified file was deployed (896 lines, correct content) |
| T+6 | Examined `RAGState` TypedDict - **found missing `is_summarization` field** |
| T+7 | Added field to TypedDict + initial state, restarted backend |
| T+8 | Feature working correctly: `Routing to summarization path` |

---

## 3. Technical Deep Dive

### 3.1 The Feature Implementation

Opus added a three-part change:

**Part 1: Route Query Detection (nodes.py)**
```python
async def route_query(self, state: RAGState) -> dict:
    # Regex detection for summarization queries
    if is_summarize:
        logger.info("Query classified as: SUMMARIZE (regex match - fast path)")
        return {
            "query_complexity": "summarize",
            "skip_rewrite": True,
            "is_summarization": True,  # <-- NEW FIELD
            "processing_steps": ["route_query"],
        }
```

**Part 2: Router Decision (nodes.py)**
```python
def should_rewrite(state: RAGState) -> Literal["rewrite", "retrieve", "summarize"]:
    if state.get("is_summarization", False):  # <-- CHECK NEW FIELD
        logger.debug("Routing to summarization path")
        return "summarize"
    if state.get("skip_rewrite", False):
        logger.debug("Skipping rewrite (simple query)")
        return "retrieve"
    return "rewrite"
```

**Part 3: Pipeline Wiring (pipeline.py)**
```python
workflow.add_conditional_edges(
    "route_query",
    should_rewrite,
    {
        "rewrite": "rewrite_query",
        "retrieve": "retrieve",
        "summarize": "retrieve_sequential",  # <-- NEW BRANCH
    }
)
```

### 3.2 The Bug

The `RAGState` TypedDict was **NOT updated**:

```python
# BEFORE (buggy)
class RAGState(TypedDict):
    question: str
    session_id: str
    collection_name: str
    query_complexity: Optional[Literal["simple", "complex", "conversational"]]  # Missing "summarize"
    skip_rewrite: bool
    # is_summarization: bool  <-- MISSING!
    ...
```

### 3.3 Why LangGraph Silently Drops Unknown Fields

LangGraph uses TypedDict for state management. When a node returns a dictionary, LangGraph merges it with the current state. However, **fields not defined in the TypedDict are silently ignored**.

This is Python's TypedDict behavior - it's a structural type hint, not a runtime validator. LangGraph could add runtime validation but doesn't by default for performance reasons.

**The Merge Sequence:**

```
1. route_query() returns:
   {
     "query_complexity": "summarize",
     "skip_rewrite": True,
     "is_summarization": True,    # <-- RETURNED
     "processing_steps": ["route_query"]
   }

2. LangGraph merges with RAGState:
   - "query_complexity" ✓ defined in TypedDict, merged
   - "skip_rewrite" ✓ defined in TypedDict, merged
   - "is_summarization" ✗ NOT defined, SILENTLY DROPPED
   - "processing_steps" ✓ defined in TypedDict, merged

3. should_rewrite() receives state:
   - state.get("is_summarization", False) → False (field doesn't exist!)
   - state.get("skip_rewrite", False) → True
   - Returns "retrieve" instead of "summarize"
```

### 3.4 Why The Bug Was Hard to Detect

1. **No Error Messages:** LangGraph doesn't warn about unknown fields
2. **Partial Success:** The query WAS classified correctly (logs showed "SUMMARIZE")
3. **Close Behavior:** Both paths eventually generate an answer, just with different retrieval
4. **Log Ordering:** The critical logs were:
   ```
   Query classified as: SUMMARIZE (regex match - fast path)  ← Looks correct!
   Skipping rewrite (simple query)  ← Wait, why this message?
   ```
   The second log message was the tell - it shouldn't appear after SUMMARIZE.

---

## 4. The Fix

**Three changes to `state.py`:**

```python
# 1. Add "summarize" to query_complexity Literal
query_complexity: Optional[Literal["simple", "complex", "conversational", "summarize"]]

# 2. Add is_summarization field to TypedDict
is_summarization: bool  # For sequential retrieval path

# 3. Initialize in create_initial_state()
is_summarization=False,
```

**Total: 3 lines of code.**

---

## 5. Verification

After the fix, logs showed correct behavior:

```
Query classified as: SUMMARIZE (regex match - fast path)
Routing to summarization path                              ← CORRECT!
Sequential retrieval for summarization: knowledge_base     ← CORRECT!
Sequential retrieval: 242 chunks -> 58 unique parents (page-ordered)
Skipping reranking for summarization (preserving page order)
Built summarization context: 43 pages, 72767 chars
```

---

## 6. Lessons Learned

### 6.1 LangGraph State Contract

**Rule:** Every field returned by a node MUST be defined in the state TypedDict.

LangGraph will not warn you if you return fields that don't exist in the TypedDict. They will be silently dropped. This is a **silent contract violation**.

### 6.2 Feature Addition Checklist

When adding new features to LangGraph pipelines:

```
□ Identify all NEW state fields the feature needs
□ Add fields to TypedDict definition
□ Add fields to create_initial_state() with sensible defaults
□ Update any Literal types that need new values
□ Test that state.get("new_field") returns expected value AFTER the node runs
```

### 6.3 Debugging LangGraph State Issues

When a conditional edge routes incorrectly:

1. **Check the router function's state access:** What fields does it check?
2. **Verify those fields exist in TypedDict:** Look at the class definition
3. **Add debug logging in the router:** Print the actual state values
4. **Check if node returns match TypedDict:** Every returned key must be defined

### 6.4 Why This Pattern is Dangerous

```python
# DANGEROUS PATTERN - No compile-time or runtime error!
def my_node(state: RAGState) -> dict:
    return {
        "existing_field": "value",
        "typo_feild": True,  # Silently dropped!
    }
```

This pattern fails silently because:
- Python doesn't validate dict keys against TypedDict at runtime
- LangGraph doesn't enforce the schema on node returns
- No error, warning, or exception is raised

### 6.5 Defensive Coding for LangGraph

**Option 1: Return typed state updates**
```python
from typing import TypedDict

class RouteQueryUpdate(TypedDict):
    query_complexity: str
    skip_rewrite: bool
    is_summarization: bool

def route_query(state: RAGState) -> RouteQueryUpdate:
    # Type checker will catch missing fields
    return RouteQueryUpdate(
        query_complexity="summarize",
        skip_rewrite=True,
        is_summarization=True
    )
```

**Option 2: Runtime validation helper**
```python
def validate_state_update(update: dict, state_class: type) -> dict:
    """Warn about fields not in state TypedDict."""
    valid_fields = set(state_class.__annotations__.keys())
    unknown = set(update.keys()) - valid_fields
    if unknown:
        logger.warning(f"State update contains unknown fields: {unknown}")
    return update
```

---

## 7. Similar Bugs to Watch For

### 7.1 Typos in State Field Names
```python
# Node returns
return {"is_summerization": True}  # Typo!

# Router checks
if state.get("is_summarization"):  # Never true
```

### 7.2 Forgetting to Update Initial State
```python
# TypedDict has field
class RAGState(TypedDict):
    new_field: bool

# But initial state doesn't set it
def create_initial_state():
    return RAGState(
        # new_field missing - will be None/undefined
    )
```

### 7.3 Literal Type Drift
```python
# TypedDict says
query_complexity: Literal["simple", "complex"]

# Node returns
return {"query_complexity": "summarize"}  # Invalid value, no warning!
```

---

## 8. Recommendations

### 8.1 Immediate Actions
- [x] Fix applied to `state.py`
- [x] Feature verified working

### 8.2 Process Improvements
- [ ] Add state field checklist to feature PR template
- [ ] Consider adding runtime state validation in DEBUG mode
- [ ] Document LangGraph state contract in CLAUDE.md

### 8.3 Code Improvements
- [ ] Add type hints to all node return values
- [ ] Create state update helper classes for complex nodes
- [ ] Add integration test that verifies state fields after each node

---

## 9. References

- **Files Changed:**
  - `backend/rag/state.py` (3 lines added)

- **Related Files:**
  - `backend/rag/nodes.py` - Contains route_query() and should_rewrite()
  - `backend/rag/pipeline.py` - Contains workflow wiring

- **LangGraph Documentation:**
  - State management: https://langchain-ai.github.io/langgraph/concepts/state/

---

## 10. Appendix: Full State Definition After Fix

```python
class RAGState(TypedDict):
    """State that flows through the RAG pipeline."""
    # Input
    question: str
    session_id: str
    collection_name: str

    # Router Agent
    query_complexity: Optional[Literal["simple", "complex", "conversational", "summarize"]]
    skip_rewrite: bool
    is_summarization: bool  # <-- ADDED

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

    # Validation
    is_grounded: bool
    groundedness_score: float
    hallucination_details: Optional[str]
    fast_groundedness_score: float
    skip_llm_hallucination_check: bool

    # Control Flow
    iteration: int
    max_iterations: int
    should_rewrite: bool
    rewrite_count: int

    # Metadata
    errors: Annotated[list[str], add]
    processing_steps: Annotated[list[str], add]
```
