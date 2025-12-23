"""
End-to-End Test: Context-Aware Handlers
Run from backend directory: python test_e2e_context.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from rag.pipeline import RAGPipeline

async def test_context_flow():
    print("=" * 60)
    print("E2E TEST: Context-Aware Handlers")
    print("=" * 60)

    pipeline = RAGPipeline()
    session_id = "test_context_e2e"

    # Pick a collection that has documents
    # Adjust this to match an existing collection in your system
    collection = "chat_test"  # CHANGE IF NEEDED

    # Step 1: Ask a real question
    print("\n[STEP 1] Asking initial question...")
    result1 = await pipeline.aquery(
        question="What is CAP theorem?",
        session_id=session_id,
        collection_name=collection
    )
    print(f"Intent: {result1.get('detected_intent', 'N/A')}")
    print(f"Steps: {result1.get('processing_steps', [])}")
    print(f"Answer: {result1['answer'][:200]}...")

    # Verify it went through RAG
    steps1 = result1.get('processing_steps', [])
    used_rag = any('retrieve' in s or 'generate' in s for s in steps1)
    print(f"[OK] Used RAG: {used_rag}")

    # Step 2: Say "tell me more" (followup)
    print("\n[STEP 2] Testing followup: 'tell me more'...")
    result2 = await pipeline.aquery(
        question="tell me more",
        session_id=session_id,
        collection_name=collection
    )
    print(f"Intent: {result2.get('detected_intent', 'N/A')}")
    print(f"Steps: {result2.get('processing_steps', [])}")
    print(f"Answer: {result2['answer'][:200]}...")

    # Verify it detected followup and used memory (not RAG)
    intent2 = result2.get('detected_intent', '')
    steps2 = result2.get('processing_steps', [])
    is_followup = intent2 == 'followup' or 'handle_non_rag' in str(steps2)
    print(f"[OK] Detected as followup/context handler: {is_followup}")

    # Step 3: Say "simplify that" (simplify)
    print("\n[STEP 3] Testing simplify: 'can you simplify that?'...")
    result3 = await pipeline.aquery(
        question="can you simplify that?",
        session_id=session_id,
        collection_name=collection
    )
    print(f"Intent: {result3.get('detected_intent', 'N/A')}")
    print(f"Steps: {result3.get('processing_steps', [])}")
    print(f"Answer: {result3['answer'][:200]}...")

    # Verify it detected simplify
    intent3 = result3.get('detected_intent', '')
    steps3 = result3.get('processing_steps', [])
    is_simplify = intent3 == 'simplify' or 'handle_non_rag' in str(steps3)
    print(f"[OK] Detected as simplify/context handler: {is_simplify}")

    # Step 4: Say "go deeper" (deepen)
    print("\n[STEP 4] Testing deepen: 'go deeper into this'...")
    result4 = await pipeline.aquery(
        question="go deeper into this",
        session_id=session_id,
        collection_name=collection
    )
    print(f"Intent: {result4.get('detected_intent', 'N/A')}")
    print(f"Steps: {result4.get('processing_steps', [])}")
    print(f"Answer: {result4['answer'][:200]}...")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Step 1 (question):  RAG used = {used_rag}")
    print(f"Step 2 (followup):  Intent = {result2.get('detected_intent', 'N/A')}")
    print(f"Step 3 (simplify):  Intent = {result3.get('detected_intent', 'N/A')}")
    print(f"Step 4 (deepen):    Intent = {result4.get('detected_intent', 'N/A')}")

    # Pass/Fail
    all_pass = (
        used_rag and
        result2.get('detected_intent') == 'followup' and
        result3.get('detected_intent') == 'simplify' and
        result4.get('detected_intent') == 'deepen'
    )

    print("\n" + ("[PASS] ALL TESTS PASSED" if all_pass else "[FAIL] SOME TESTS FAILED"))
    return all_pass

if __name__ == "__main__":
    result = asyncio.run(test_context_flow())
    sys.exit(0 if result else 1)
