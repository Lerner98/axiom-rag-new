"""Tests for Agentic RAG Pipeline"""
import pytest
import os
from unittest.mock import Mock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

class TestRAGState:
    """Test RAG state management"""
    
    def test_state_initialization(self):
        from rag.pipeline import RAGState
        
        state: RAGState = {
            "question": "test question",
            "query": "",
            "documents": [],
            "generation": "",
            "relevance_scores": [],
            "needs_web_search": False,
            "search_queries": [],
            "iteration": 0,
            "max_iterations": 2,
            "final_answer": "",
            "grounded": True,
            "feedback": ""
        }
        
        assert state["question"] == "test question"
        assert state["max_iterations"] == 2

class TestVectorStoreConfig:
    """Test vector store configuration"""
    
    def test_default_config(self):
        from rag.vector_store import VectorStoreConfig
        
        config = VectorStoreConfig()
        assert config.provider == "qdrant"
        assert config.collection_name == "documents"
    
    def test_custom_config(self):
        from rag.vector_store import VectorStoreConfig
        
        config = VectorStoreConfig(
            provider="chroma",
            collection_name="test_collection"
        )
        assert config.provider == "chroma"
        assert config.collection_name == "test_collection"

class TestDocumentProcessor:
    """Test document processing"""
    
    def test_chunk_texts(self):
        from rag.vector_store import DocumentProcessor
        
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        
        texts = ["This is a test document. " * 20]
        docs = processor.chunk_texts(texts, "test")
        
        assert len(docs) > 0
        assert docs[0].metadata["source"] == "test"
    
    def test_small_text_single_chunk(self):
        from rag.vector_store import DocumentProcessor
        
        processor = DocumentProcessor(chunk_size=1000, chunk_overlap=100)
        
        texts = ["Short text"]
        docs = processor.chunk_texts(texts, "test")
        
        assert len(docs) == 1
        assert docs[0].page_content == "Short text"

class TestEvaluationResult:
    """Test evaluation result dataclass"""
    
    def test_overall_score_calculation(self):
        from evaluation.ragas_eval import EvaluationResult
        
        result = EvaluationResult(
            question="test",
            answer="test answer",
            contexts=["context"],
            faithfulness=0.8,
            answer_relevancy=0.9,
            context_precision=0.7,
            context_recall=0.8
        )
        
        expected = (0.8 + 0.9 + 0.7 + 0.8) / 4
        assert abs(result.overall_score - expected) < 0.001

class TestEvaluationReport:
    """Test evaluation report generation"""
    
    def test_create_report(self):
        from evaluation.ragas_eval import EvaluationResult, create_evaluation_report
        
        results = [
            EvaluationResult(
                question="Q1",
                answer="A1",
                contexts=["C1"],
                faithfulness=0.9,
                answer_relevancy=0.85,
                context_precision=0.8,
                context_recall=0.75
            )
        ]
        
        report = create_evaluation_report(results)
        
        assert "# RAG Evaluation Report" in report
        assert "Summary" in report
        assert "0.9" in report or "90" in report

@pytest.mark.asyncio
class TestAPI:
    """Test FastAPI endpoints"""
    
    async def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        
        # Mock the vector store before importing main
        with patch('rag.vector_store.VectorStoreManager') as MockVS:
            mock_instance = MagicMock()
            mock_instance.get_stats.return_value = {"count": 0}
            mock_instance.store = MagicMock()
            MockVS.return_value = mock_instance
            
            from main import app
            client = TestClient(app)
            response = client.get("/health")
            
            assert response.status_code == 200

# Integration test
@pytest.mark.skipif(
    os.getenv("OPENAI_API_KEY", "").startswith("test"),
    reason="Requires real API key"
)
class TestIntegration:
    """Integration tests with real components"""
    
    def test_simple_rag_query(self):
        from rag.pipeline import SimpleRAG
        from rag.vector_store import VectorStoreManager, VectorStoreConfig
        
        # Use ChromaDB for testing
        config = VectorStoreConfig(provider="chroma", chroma_persist_dir="./test_chroma")
        vs = VectorStoreManager(config)
        vs.initialize()
        
        # Add test document
        vs.add_texts(["RAG stands for Retrieval Augmented Generation."])
        
        # Query
        rag = SimpleRAG(vs.store)
        answer = rag.query("What does RAG stand for?")
        
        assert "retrieval" in answer.lower() or "generation" in answer.lower()
        
        # Cleanup
        vs.delete_collection()
