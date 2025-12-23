"""
Full 8-Query Benchmark - Phase 1 Optimization Test
Tests the same pipeline the UI uses with proper isolation.

Key isolation measures:
1. Unique session_id per test run (no memory bleed)
2. Uses existing knowledge_base collection (has system-design-primer.txt)
3. Each query gets unique session to prevent followup confusion
"""
import asyncio
import time
import sys
sys.path.insert(0, '.')

# Test queries matching the original benchmark
TEST_QUERIES = [
    # RAG queries (simple)
    {"query": "What is the CAP theorem?", "type": "simple_rag", "expect_rag": True},
    {"query": "What is load balancing?", "type": "simple_rag", "expect_rag": True},
    {"query": "What is consistent hashing?", "type": "simple_rag", "expect_rag": True},
    {"query": "What is a CDN?", "type": "simple_rag", "expect_rag": True},
    # RAG queries (complex)
    {"query": "Compare SQL and NoSQL databases", "type": "complex_rag", "expect_rag": True},
    {"query": "How does database sharding work and what are the tradeoffs?", "type": "complex_rag", "expect_rag": True},
    # Non-RAG queries
    {"query": "hi", "type": "greeting", "expect_rag": False},
    {"query": "thanks", "type": "gratitude", "expect_rag": False},
]

async def run_benchmark():
    from rag.pipeline import RAGPipeline

    # Generate unique run ID for complete isolation
    run_id = int(time.time())

    print("=" * 70)
    print(f"FULL BENCHMARK - Phase 1 Optimizations")
    print(f"Run ID: {run_id} (ensures no cache contamination)")
    print("=" * 70)
    print()

    pipeline = RAGPipeline()

    results = []
    total_rag_time = 0
    rag_count = 0

    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        query_type = test["type"]
        expect_rag = test["expect_rag"]

        # ISOLATION: Unique session per query
        session_id = f"bench_{run_id}_{i}"

        print(f"[{i}/8] {query_type.upper()}: {query[:50]}...")

        start = time.time()
        try:
            result = await pipeline.aquery(
                question=query,
                session_id=session_id,
                collection_name="knowledge_base"  # Use existing collection
            )
            elapsed = time.time() - start

            # Extract key metrics
            complexity = result.get("query_complexity", "N/A")
            intent = result.get("detected_intent", "N/A")
            sources_count = len(result.get("sources", []))
            is_grounded = result.get("is_grounded", False)
            steps = result.get("processing_steps", [])
            answer = result.get("answer", "")[:150]

            # Check if RAG was used
            used_rag = "retrieve" in str(steps) or "generate" in str(steps)

            # Quality check: did we get a real answer?
            has_answer = len(answer) > 20

            results.append({
                "query": query,
                "type": query_type,
                "latency": elapsed,
                "complexity": complexity,
                "intent": intent,
                "sources": sources_count,
                "grounded": is_grounded,
                "used_rag": used_rag,
                "has_answer": has_answer,
                "steps": steps,
            })

            # Track RAG latencies separately
            if expect_rag:
                total_rag_time += elapsed
                rag_count += 1

            # Status indicator
            status = "PASS" if has_answer else "FAIL"
            if expect_rag and not used_rag:
                status = "WARN"

            print(f"       Latency: {elapsed:.2f}s | Complexity: {complexity} | Sources: {sources_count} | {status}")

        except Exception as e:
            elapsed = time.time() - start
            print(f"       ERROR: {str(e)[:100]}")
            results.append({
                "query": query,
                "type": query_type,
                "latency": elapsed,
                "error": str(e),
            })

    # Summary
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    # Calculate metrics
    passed = sum(1 for r in results if r.get("has_answer", False) or not TEST_QUERIES[results.index(r)]["expect_rag"])
    avg_rag_latency = total_rag_time / rag_count if rag_count > 0 else 0

    simple_rag_times = [r["latency"] for r in results if r.get("complexity") == "simple" and "error" not in r]
    complex_rag_times = [r["latency"] for r in results if r.get("complexity") == "complex" and "error" not in r]

    print(f"Tests Passed: {passed}/8")
    print(f"Avg RAG Latency: {avg_rag_latency:.2f}s")

    if simple_rag_times:
        print(f"Avg Simple Query: {sum(simple_rag_times)/len(simple_rag_times):.2f}s (K=2 docs)")
    if complex_rag_times:
        print(f"Avg Complex Query: {sum(complex_rag_times)/len(complex_rag_times):.2f}s (K=5 docs)")

    print()
    print("Detailed Results:")
    print("-" * 70)
    print(f"{'Query':<40} {'Type':<12} {'Latency':>8} {'Sources':>7}")
    print("-" * 70)

    for r in results:
        query_short = r["query"][:38] + ".." if len(r["query"]) > 40 else r["query"]
        latency = f"{r['latency']:.2f}s" if "error" not in r else "ERROR"
        sources = str(r.get("sources", "-"))
        print(f"{query_short:<40} {r['type']:<12} {latency:>8} {sources:>7}")

    print("-" * 70)
    print()

    # Optimization verification
    print("OPTIMIZATION CHECKS:")
    for r in results:
        if r.get("complexity") == "simple":
            steps = r.get("steps", [])
            if "hallucination_skip_simple_highconf" in str(steps):
                print(f"  [OK] Hallucination skip triggered for: {r['query'][:40]}")
            if r.get("sources", 0) == 2:
                print(f"  [OK] Adaptive K=2 for simple query: {r['query'][:40]}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
