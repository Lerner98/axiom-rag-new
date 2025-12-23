Browser Testing Workflow for V5 Intent System
Prerequisites Checklist
bash# 1. Backend running
cd backend
uvicorn api.main:app --port 8001 --reload

# 2. Frontend running
cd frontend
npm run dev

# 3. Ollama running (for LLM)
ollama serve
# Verify: ollama list (should show llama3 or your model)

# 4. Have a collection with documents
# Upload a PDF via the UI first, or use existing chat with docs

Test Plan
Test 1: Basic Question (RAG Flow)
Action:

Open http://localhost:5173
Create new chat or use existing one with documents
Type: What is CAP theorem?

Expected:

Answer comes from documents (with source citations)
Console/logs show: classify_intent → route_query → retrieve → generate
Intent should be question

Verify in browser DevTools (Network tab):

POST to /chat/{chat_id}/stream or /chat/{chat_id}/query
Response includes detected_intent: "question"


Test 2: Greeting (No RAG)
Action:

Same chat, type: hi or hello

Expected:

Instant response like "Hello! How can I help you with your documents today?"
NO document retrieval happens
Response is fast (<1 second)

Verify:

detected_intent: "greeting"
processing_steps should NOT include retrieve or generate
Should include handle_non_rag_intent


Test 3: Followup (Memory-Based)
Action:

First ask: What is CAP theorem? (wait for answer)
Then ask: tell me more

Expected:

Response expands on the previous CAP theorem answer
Does NOT do new RAG retrieval
Uses memory/context from previous answer

Verify:

detected_intent: "followup"
processing_steps includes handle_non_rag_intent
Answer references/expands previous content


Test 4: Simplify (Memory-Based)
Action:

After getting an answer, type: can you simplify that?

Expected:

Response is a simpler version of the previous answer
No new document retrieval
Language is more accessible

Verify:

detected_intent: "simplify"
Answer is genuinely simpler than original


Test 5: Deepen (Memory-Based)
Action:

After getting an answer, type: go deeper into this

Expected:

Response adds technical depth to previous answer
No new document retrieval
More detailed/technical explanation

Verify:

detected_intent: "deepen"


Test 6: Gratitude (No RAG)
Action:

Type: thanks or thank you

Expected:

Polite acknowledgment like "You're welcome!"
Instant response
No RAG triggered

Verify:

detected_intent: "gratitude"


Test 7: Garbage (Rejected)
Action:

Type: asdfasdf or !!!??? or just a

Expected:

Polite rejection: "I'm not sure I understand. Could you rephrase?"
No RAG triggered
Fast response

Verify:

detected_intent: "garbage"


How to See Intent in Browser
Option A: Check Network Response

Open DevTools → Network tab
Send a message
Click the request to /stream or /query
Look at Response JSON for:

json   {
     "detected_intent": "followup",
     "intent_confidence": 0.95,
     "processing_steps": ["classify_intent", "handle_non_rag_intent"]
   }
```

### Option B: Check Backend Logs

Watch the terminal where uvicorn is running:
```
INFO: Layer 1: FOLLOWUP (confidence=0.999)
INFO: Query classified as: followup, skip_rewrite: True
```

### Option C: Add UI Display (Optional)

If you want to see intent in the UI, the frontend would need to display `detected_intent` from the response. Check if `ChatMessage` component shows metadata.

---

## Quick Test Script (All in One Chat)
```
1. "What is CAP theorem?"           → question, full RAG
2. "tell me more"                   → followup, memory expansion
3. "simplify that"                  → simplify, simpler version
4. "go deeper"                      → deepen, more technical
5. "thanks"                         → gratitude, acknowledgment
6. "hi"                             → greeting, hello response
7. "asdfgh"                         → garbage, rejection
8. "What is load balancing?"        → question, new RAG query

Success Criteria
TestIntentRAG UsedResponse TimeQuestionquestionYes5-30sGreetinggreetingNo<1sFollowupfollowupNo2-5s (LLM only)SimplifysimplifyNo2-5s (LLM only)DeependeepenNo2-5s (LLM only)GratitudegratitudeNo<1sGarbagegarbageNo<1s

Troubleshooting
If intent always shows question:

Check intent_router.py exists in backend/rag/
Check SEMANTIC_CONFIDENCE_THRESHOLD (default 0.85)
Check FastEmbed is loading (look for "SemanticRouter initialized" in logs)

If followup/simplify/deepen don't work:

Verify memory is saving previous answers
Check intent_handlers.py exists
Look for errors in backend logs

If no detected_intent in response:

Check pipeline.py returns it in aquery()
Check state.py has the field defined








--------------------------------------------------------


RAG Value Proposition Test Plan
What I Need From You
1. Test Documents
Document A: Large Document (300+ pages)

Any technical PDF, 300-500 pages
Examples: textbook, manual, specification document
Why: Test precision on large docs, prove we don't "lose" info on page 347

Document B: Medium Document (50-100 pages)

Different topic than Document A
Why: Test multi-document search, prove we can find info across docs

Document C: Small Document (10-20 pages)

Different topic than A and B
Why: Verify cross-document retrieval works with varied sizes

Ideal scenario:
Document A: "system-design-textbook.pdf" (300+ pages) - covers databases, networking, etc.
Document B: "kubernetes-guide.pdf" (50-100 pages) - covers containers, deployments
Document C: "python-basics.pdf" (10-20 pages) - covers syntax, functions
Or any 3 documents you have where:

Topics are distinct enough to verify correct retrieval
You know what's in them (to verify answers are correct)


2. Test Environment Confirmation
Before Claude Code runs tests, confirm:
bash# Backend running?
curl http://localhost:8001/health

# Ollama running?
ollama list

# ChromaDB directory exists?
ls backend/data/chroma
```

---

### 3. What Claude Code Will Test

**Test 1: Multi-Document Search**
```
1. Create new chat
2. Upload Document A
3. Upload Document B  
4. Upload Document C
5. Ask question that's ONLY in Document B
6. Verify answer comes from Document B (not A or C)
7. Ask question that's ONLY in Document A
8. Verify answer comes from Document A
```

**Pass criteria:** Correctly identifies which document contains the answer

---

**Test 2: Large Document Precision**
```
1. Create new chat
2. Upload 300+ page document
3. Ask about content from page 10
4. Ask about content from page 150
5. Ask about content from page 290
6. Verify all answers are accurate with correct page citations
```

**Pass criteria:** Retrieves correct content regardless of page location

---

**Test 3: Repeated Query Speed**
```
1. Upload document, run query, note total time (includes indexing)
2. Restart backend server
3. Run same query again, note time
4. Run 5 more queries, note times
```

**Pass criteria:** 
- Query 2+ should be faster than Query 1 (no re-embedding)
- BM25 rebuild time should be documented (current gap)

---

**Test 4: Index Persistence**
```
1. Upload document
2. Stop backend
3. Delete BM25 in-memory (automatic on restart)
4. Start backend
5. Query - does it still work?
6. Check if hybrid search falls back to vector-only
```

**Pass criteria:** System works after restart (even if degraded)

---

## What You Need To Provide

| Item | Description | Required |
|------|-------------|----------|
| Document A | 300+ page PDF | ✅ Yes |
| Document B | 50-100 page PDF, different topic | ✅ Yes |
| Document C | 10-20 page PDF, different topic | ✅ Yes |
| Sample questions | 2-3 questions per document where you KNOW the answer | ✅ Yes |
| Page references | "Question X answer is on page Y" for large doc test | ✅ Yes |

---

## Example Test Questions Format
```
Document A (300+ page system design book):
- Q1: "What is the CAP theorem?" → Expected: Page 45-47
- Q2: "How does consistent hashing work?" → Expected: Page 156
- Q3: "What are the tradeoffs of SQL vs NoSQL?" → Expected: Page 289

Document B (Kubernetes guide):
- Q1: "What is a Pod?" → Expected: Page 12
- Q2: "How do deployments work?" → Expected: Page 34

Document C (Python basics):
- Q1: "What is a list comprehension?" → Expected: Page 8

Once You Have These
Tell me:

"I have the 3 documents ready"
Document names and topics
2-3 test questions per document with expected page numbers
Confirm backend + ollama running

Then I'll prepare the exact test script for Claude Code to execute.
