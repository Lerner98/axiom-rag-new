"""
Quality Verification Benchmark
Shows FULL LLM outputs and lets us verify against source document.
"""
import asyncio
import time
import sys
sys.path.insert(0, '.')

TEST_DOC_PATH = r"c:\Users\guyle\Desktop\Toon\original_rag\test-docs\system-design-primer.txt"

# 6 RAG queries to verify quality
TEST_QUERIES = [
    "What is the CAP theorem?",
    "What is load balancing?",
    "What is a CDN?",
    "What is consistent hashing?",
    "Compare SQL and NoSQL databases",
    "How does database sharding work?",
]

async def run_quality_check():
    from rag.pipeline import RAGPipeline
    from ingest.service import ingestion_service
    import uuid
    import os

    run_id = int(time.time())
    collection_name = f"quality_check_{run_id}"

    print("=" * 80)
    print("QUALITY VERIFICATION - Full Output Review")
    print("=" * 80)
    print(f"Collection: {collection_name}")
    print()

    # Ingest document
    print("[INGESTING DOCUMENT...]")
    doc_id = str(uuid.uuid4())
    job = ingestion_service.create_job(collection_name, document_count=1)
    await ingestion_service._process_file(job, TEST_DOC_PATH, doc_id=doc_id, original_filename="system-design-primer.txt")
    print(f"Ingested {job.chunks_created} chunks")
    print()

    pipeline = RAGPipeline()
    results = []

    for i, query in enumerate(TEST_QUERIES, 1):
        session_id = f"quality_{run_id}_{i}"

        print("=" * 80)
        print(f"QUERY {i}/6: {query}")
        print("=" * 80)

        start = time.time()
        result = await pipeline.aquery(
            question=query,
            session_id=session_id,
            collection_name=collection_name
        )
        elapsed = time.time() - start

        answer = result.get("answer", "NO ANSWER")
        sources = result.get("sources", [])
        complexity = result.get("query_complexity", "N/A")

        print(f"Latency: {elapsed:.1f}s | Complexity: {complexity} | Sources: {len(sources)}")
        print("-" * 80)
        print("FULL ANSWER:")
        print(answer)
        print("-" * 80)

        if sources:
            print("SOURCE SNIPPETS USED:")
            for j, src in enumerate(sources[:2], 1):
                preview = src.get("content_preview", src.get("page_content", ""))[:300]
                print(f"  [{j}] {preview}...")
        print()

        results.append({
            "query": query,
            "latency": elapsed,
            "answer_length": len(answer),
            "sources": len(sources),
            "complexity": complexity
        })

    # Cleanup
    from vectorstore.store import VectorStore
    vs = VectorStore()
    await vs.delete_collection(collection_name)

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Query':<40} {'Latency':>8} {'Ans Len':>8} {'Sources':>8}")
    print("-" * 80)
    for r in results:
        q = r["query"][:38] + ".." if len(r["query"]) > 40 else r["query"]
        print(f"{q:<40} {r['latency']:>7.1f}s {r['answer_length']:>8} {r['sources']:>8}")

    avg_latency = sum(r["latency"] for r in results) / len(results)
    print("-" * 80)
    print(f"Average Latency: {avg_latency:.1f}s")

if __name__ == "__main__":
    asyncio.run(run_quality_check())
