"""
E2E Benchmark - Full Pipeline Test with Fresh Document Ingestion
Simulates exactly what a user does in the UI.

Isolation measures:
1. Fresh timestamped collection (no old cached data)
2. Unique session_id per query (no memory bleed)
3. Ingests real PDF before testing
4. Cleans up collection after test
"""
import asyncio
import time
import sys
import os
sys.path.insert(0, '.')

# Test document path
TEST_DOC_PATH = r"c:\Users\guyle\Desktop\Toon\original_rag\RAG_Scale_Tests\doc_a_large.pdf"

# 8 Test queries - mix of simple and complex
TEST_QUERIES = [
    # Simple RAG queries (should use K=2, skip hallucination)
    {"query": "What is the CAP theorem?", "type": "simple"},
    {"query": "What is load balancing?", "type": "simple"},
    {"query": "What is a CDN?", "type": "simple"},
    {"query": "What is consistent hashing?", "type": "simple"},
    # Complex RAG queries (should use K=5, full hallucination check)
    {"query": "Compare SQL and NoSQL databases and their tradeoffs", "type": "complex"},
    {"query": "How does database sharding work and what are the challenges?", "type": "complex"},
    # Non-RAG queries (instant)
    {"query": "hi", "type": "greeting"},
    {"query": "thanks", "type": "gratitude"},
]


async def ingest_document(collection_name: str, file_path: str) -> int:
    """Ingest a document into the collection. Returns chunk count."""
    from ingest.service import ingestion_service
    import uuid

    print(f"Ingesting: {os.path.basename(file_path)}")
    print(f"Collection: {collection_name}")

    doc_id = str(uuid.uuid4())
    job = ingestion_service.create_job(collection_name, document_count=1)

    await ingestion_service._process_file(
        job,
        file_path,
        doc_id=doc_id,
        original_filename=os.path.basename(file_path)
    )

    if job.status.value == "completed":
        print(f"Ingested {job.chunks_created} chunks successfully")
        return job.chunks_created
    else:
        print(f"Ingestion failed: {job.errors}")
        return 0


async def cleanup_collection(collection_name: str):
    """Delete the test collection."""
    from vectorstore.store import VectorStore
    vs = VectorStore()
    try:
        await vs.delete_collection(collection_name)
        print(f"Cleaned up collection: {collection_name}")
    except Exception as e:
        print(f"Cleanup warning: {e}")


async def run_benchmark():
    from rag.pipeline import RAGPipeline

    # Generate unique collection name (complete isolation)
    run_id = int(time.time())
    collection_name = f"benchmark_{run_id}"

    print("=" * 70)
    print("E2E BENCHMARK - Phase 1 Optimizations")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Collection: {collection_name} (fresh, no cache)")
    print(f"Test Doc: {os.path.basename(TEST_DOC_PATH)}")
    print("=" * 70)
    print()

    # Step 1: Ingest document
    print("[STEP 1] Ingesting test document...")
    ingest_start = time.time()
    chunk_count = await ingest_document(collection_name, TEST_DOC_PATH)
    ingest_time = time.time() - ingest_start
    print(f"Ingestion time: {ingest_time:.2f}s")
    print()

    if chunk_count == 0:
        print("ERROR: Document ingestion failed. Aborting.")
        return

    # Step 2: Run queries
    print("[STEP 2] Running 8 test queries...")
    print("-" * 70)

    pipeline = RAGPipeline()
    results = []

    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        query_type = test["type"]

        # Unique session per query (no memory contamination)
        session_id = f"bench_{run_id}_q{i}"

        print(f"[{i}/8] {query[:50]}...")

        start = time.time()
        try:
            result = await pipeline.aquery(
                question=query,
                session_id=session_id,
                collection_name=collection_name
            )
            elapsed = time.time() - start

            complexity = result.get("query_complexity", "N/A")
            sources = len(result.get("sources", []))
            grounded = result.get("is_grounded", False)
            steps = result.get("processing_steps", [])
            answer = result.get("answer", "")

            # Quality: has real answer?
            has_answer = len(answer) > 30 and "error" not in answer.lower()

            results.append({
                "query": query,
                "type": query_type,
                "latency": elapsed,
                "complexity": complexity,
                "sources": sources,
                "grounded": grounded,
                "has_answer": has_answer,
                "steps": steps,
                "answer_preview": answer[:100]
            })

            status = "PASS" if has_answer or query_type in ["greeting", "gratitude"] else "FAIL"
            print(f"      {elapsed:.2f}s | {complexity} | {sources} sources | {status}")

        except Exception as e:
            elapsed = time.time() - start
            print(f"      ERROR: {str(e)[:80]}")
            results.append({
                "query": query,
                "type": query_type,
                "latency": elapsed,
                "error": str(e)
            })

    # Step 3: Results Summary
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    # Calculate metrics
    rag_results = [r for r in results if r["type"] in ["simple", "complex"] and "error" not in r]
    simple_results = [r for r in rag_results if r.get("complexity") == "simple"]
    complex_results = [r for r in rag_results if r.get("complexity") == "complex"]

    passed = sum(1 for r in results if r.get("has_answer", False) or r["type"] in ["greeting", "gratitude"])
    quality_pct = (passed / len(results)) * 100

    print(f"Tests Passed: {passed}/8 ({quality_pct:.0f}%)")
    print()

    if rag_results:
        avg_rag = sum(r["latency"] for r in rag_results) / len(rag_results)
        print(f"Avg RAG Latency: {avg_rag:.2f}s")

    if simple_results:
        avg_simple = sum(r["latency"] for r in simple_results) / len(simple_results)
        print(f"Avg Simple Query: {avg_simple:.2f}s (Adaptive K=2)")

    if complex_results:
        avg_complex = sum(r["latency"] for r in complex_results) / len(complex_results)
        print(f"Avg Complex Query: {avg_complex:.2f}s (K=5)")

    print()
    print("Detailed Results:")
    print("-" * 70)
    print(f"{'#':<3} {'Query':<35} {'Type':<8} {'Time':>7} {'Src':>4} {'Status':<6}")
    print("-" * 70)

    for i, r in enumerate(results, 1):
        q = r["query"][:33] + ".." if len(r["query"]) > 35 else r["query"]
        t = r["type"][:8]
        latency = f"{r['latency']:.1f}s" if "error" not in r else "ERR"
        src = str(r.get("sources", "-"))
        status = "PASS" if r.get("has_answer") or r["type"] in ["greeting", "gratitude"] else "FAIL"
        if "error" in r:
            status = "ERROR"
        print(f"{i:<3} {q:<35} {t:<8} {latency:>7} {src:>4} {status:<6}")

    print("-" * 70)

    # Optimization verification
    print()
    print("OPTIMIZATION CHECKS:")
    for r in results:
        if r.get("complexity") == "simple" and "error" not in r:
            if "hallucination_skip_simple_highconf" in str(r.get("steps", [])):
                print(f"  [OK] Hallucination bypassed: {r['query'][:40]}")
            if r.get("sources") == 2:
                print(f"  [OK] Adaptive K=2 applied: {r['query'][:40]}")

    # Step 4: Cleanup
    print()
    print("[STEP 3] Cleaning up test collection...")
    await cleanup_collection(collection_name)

    print()
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
