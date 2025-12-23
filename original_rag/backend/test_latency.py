"""Quick latency test for Phase 1 optimizations."""
import asyncio
import time
import sys
sys.path.insert(0, '.')

async def test_simple_query():
    from rag.pipeline import RAGPipeline

    pipeline = RAGPipeline()

    query = 'What is the CAP theorem?'
    print(f'Testing: {query}')
    print('='*50)

    start = time.time()
    result = await pipeline.aquery(
        question=query,
        session_id=f'latency_test_{int(time.time())}',
        collection_name='knowledge_base'
    )
    elapsed = time.time() - start

    print(f'Query complexity: {result.get("query_complexity")}')
    print(f'Processing steps: {result.get("processing_steps")}')
    print(f'Sources count: {len(result.get("sources", []))}')
    print(f'Is grounded: {result.get("is_grounded")}')
    print(f'Latency: {elapsed:.2f}s')
    print('='*50)
    answer = result.get("answer", "")
    print(f'Answer preview: {answer[:300]}...')

if __name__ == "__main__":
    asyncio.run(test_simple_query())
