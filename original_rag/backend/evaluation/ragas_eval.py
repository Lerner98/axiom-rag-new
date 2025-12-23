"""
RAG Evaluation Module
Implements RAGAS-style metrics + DeepEval patterns
"""
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

@dataclass
class EvaluationResult:
    """Result of RAG evaluation"""
    question: str
    answer: str
    contexts: List[str]
    
    # RAGAS metrics
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    
    # Additional metrics
    coherence: float = 0.0
    conciseness: float = 0.0
    
    # Computed
    overall_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate overall score"""
        metrics = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.context_recall
        ]
        self.overall_score = sum(metrics) / len(metrics) if metrics else 0.0

class RAGEvaluator:
    """
    RAGAS-style evaluation for RAG systems
    
    Metrics:
    - Faithfulness: Is the answer grounded in the context?
    - Answer Relevancy: Does the answer address the question?
    - Context Precision: Are retrieved docs relevant?
    - Context Recall: Did we retrieve all needed info?
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
    
    def evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Check if answer is fully supported by context.
        
        Process:
        1. Extract claims from answer
        2. Verify each claim against context
        3. Return ratio of supported claims
        """
        # Step 1: Extract claims
        claims_prompt = f"""Extract factual claims from this answer as a numbered list.
Only include specific factual claims, not opinions or hedged statements.

Answer: {answer}

Claims (numbered list):"""
        
        claims_response = self.llm.invoke(claims_prompt)
        claims_text = claims_response.content
        
        # Parse claims
        claims = [
            line.strip().lstrip("0123456789.-) ")
            for line in claims_text.split("\n")
            if line.strip() and any(c.isalpha() for c in line)
        ]
        
        if not claims:
            return 1.0  # No claims to verify
        
        # Step 2: Verify each claim
        context_combined = "\n\n".join(contexts)
        supported = 0
        
        for claim in claims[:10]:  # Limit to 10 claims
            verify_prompt = f"""Is this claim supported by the context?
Answer "yes" or "no" only.

Claim: {claim}

Context: {context_combined[:3000]}

Supported:"""
            
            result = self.llm.invoke(verify_prompt)
            if "yes" in result.content.lower():
                supported += 1
        
        return supported / len(claims) if claims else 1.0
    
    def evaluate_answer_relevancy(
        self,
        question: str,
        answer: str
    ) -> float:
        """
        Check if answer addresses the question.
        
        Uses reverse-generation: Generate questions from answer,
        then compare similarity to original question.
        """
        prompt = f"""Rate how well this answer addresses the question.
Score from 0.0 to 1.0 where:
- 1.0 = Answer directly and completely addresses the question
- 0.7 = Answer mostly addresses the question with minor gaps
- 0.4 = Answer partially addresses the question
- 0.0 = Answer is irrelevant to the question

Question: {question}
Answer: {answer}

Return ONLY a decimal number between 0.0 and 1.0:"""
        
        result = self.llm.invoke(prompt)
        try:
            return float(result.content.strip())
        except:
            return 0.5
    
    def evaluate_context_precision(
        self,
        question: str,
        contexts: List[str]
    ) -> float:
        """
        Check if retrieved contexts are relevant.
        
        Measures ratio of relevant contexts to total retrieved.
        """
        if not contexts:
            return 0.0
        
        relevant_count = 0
        
        for ctx in contexts:
            prompt = f"""Is this context relevant to answering the question?
Answer "yes" or "no" only.

Question: {question}
Context: {ctx[:1500]}

Relevant:"""
            
            result = self.llm.invoke(prompt)
            if "yes" in result.content.lower():
                relevant_count += 1
        
        return relevant_count / len(contexts)
    
    def evaluate_context_recall(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> float:
        """
        Check if context contains all info needed to answer.
        
        If ground_truth provided, checks if context covers it.
        Otherwise, uses answer as proxy.
        """
        reference = ground_truth or answer
        context_combined = "\n\n".join(contexts)
        
        prompt = f"""Does the context contain all the information needed to produce this answer?

Answer being evaluated: {reference}

Available context: {context_combined[:3000]}

Score from 0.0 to 1.0:
- 1.0 = Context contains all necessary information
- 0.5 = Context contains some but not all information
- 0.0 = Context is missing critical information

Return ONLY a decimal number:"""
        
        result = self.llm.invoke(prompt)
        try:
            return float(result.content.strip())
        except:
            return 0.5
    
    def evaluate_coherence(self, answer: str) -> float:
        """Check answer readability and logical flow"""
        prompt = f"""Rate the coherence of this answer.
Score from 0.0 to 1.0:
- 1.0 = Well-organized, clear, logical flow
- 0.5 = Understandable but could be clearer
- 0.0 = Confusing, contradictory, or incoherent

Answer: {answer}

Return ONLY a decimal number:"""
        
        result = self.llm.invoke(prompt)
        try:
            return float(result.content.strip())
        except:
            return 0.5
    
    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """Run full evaluation suite"""
        return EvaluationResult(
            question=question,
            answer=answer,
            contexts=contexts,
            faithfulness=self.evaluate_faithfulness(answer, contexts),
            answer_relevancy=self.evaluate_answer_relevancy(question, answer),
            context_precision=self.evaluate_context_precision(question, contexts),
            context_recall=self.evaluate_context_recall(
                question, answer, contexts, ground_truth
            ),
            coherence=self.evaluate_coherence(answer)
        )
    
    def evaluate_batch(
        self,
        questions: List[str],
        answers: List[str],
        contexts_list: List[List[str]],
        ground_truths: Optional[List[str]] = None
    ) -> List[EvaluationResult]:
        """Evaluate multiple Q&A pairs"""
        results = []
        
        for i, (q, a, ctx) in enumerate(zip(questions, answers, contexts_list)):
            gt = ground_truths[i] if ground_truths else None
            result = self.evaluate(q, a, ctx, gt)
            results.append(result)
            
            print(f"Evaluated {i+1}/{len(questions)}: score={result.overall_score:.2f}")
        
        return results


class TestDatasetGenerator:
    """Generate test Q&A pairs from documents for evaluation"""
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0.7)
    
    def generate_qa_pairs(
        self,
        documents: List[Document],
        num_questions: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate question-answer pairs from documents"""
        qa_pairs = []
        
        for doc in documents[:10]:  # Limit documents
            prompt = f"""Based on this text, generate {num_questions} question-answer pairs.

Text: {doc.page_content[:2000]}

For each pair, provide:
1. A question that can be answered from the text
2. The correct answer based only on the text

Format as:
Q1: [question]
A1: [answer]
Q2: [question]
A2: [answer]
..."""
            
            result = self.llm.invoke(prompt)
            
            # Parse Q&A pairs
            lines = result.content.split("\n")
            current_q = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("Q") and ":" in line:
                    current_q = line.split(":", 1)[1].strip()
                elif line.startswith("A") and ":" in line and current_q:
                    answer = line.split(":", 1)[1].strip()
                    qa_pairs.append({
                        "question": current_q,
                        "ground_truth": answer,
                        "source_doc": doc.page_content[:500]
                    })
                    current_q = None
        
        return qa_pairs


def create_evaluation_report(results: List[EvaluationResult]) -> str:
    """Generate markdown evaluation report"""
    if not results:
        return "No results to report."
    
    # Calculate averages
    avg_faithfulness = sum(r.faithfulness for r in results) / len(results)
    avg_relevancy = sum(r.answer_relevancy for r in results) / len(results)
    avg_precision = sum(r.context_precision for r in results) / len(results)
    avg_recall = sum(r.context_recall for r in results) / len(results)
    avg_overall = sum(r.overall_score for r in results) / len(results)
    
    report = f"""# RAG Evaluation Report

## Summary

| Metric | Score |
|--------|-------|
| **Overall** | {avg_overall:.2%} |
| Faithfulness | {avg_faithfulness:.2%} |
| Answer Relevancy | {avg_relevancy:.2%} |
| Context Precision | {avg_precision:.2%} |
| Context Recall | {avg_recall:.2%} |

## Interpretation

- **Faithfulness** ({avg_faithfulness:.2%}): {"✅ Good" if avg_faithfulness > 0.8 else "⚠️ Needs improvement"} - Answers are {"well" if avg_faithfulness > 0.8 else "not fully"} grounded in retrieved context
- **Answer Relevancy** ({avg_relevancy:.2%}): {"✅ Good" if avg_relevancy > 0.8 else "⚠️ Needs improvement"} - Answers {"address" if avg_relevancy > 0.8 else "partially address"} the questions
- **Context Precision** ({avg_precision:.2%}): {"✅ Good" if avg_precision > 0.8 else "⚠️ Needs improvement"} - Retrieved documents are {"mostly" if avg_precision > 0.8 else "not all"} relevant
- **Context Recall** ({avg_recall:.2%}): {"✅ Good" if avg_recall > 0.8 else "⚠️ Needs improvement"} - Retrieved context {"contains" if avg_recall > 0.8 else "may be missing"} necessary information

## Detailed Results

"""
    
    for i, r in enumerate(results, 1):
        report += f"""### Question {i}

**Q:** {r.question}

**A:** {r.answer[:200]}...

| Metric | Score |
|--------|-------|
| Faithfulness | {r.faithfulness:.2%} |
| Answer Relevancy | {r.answer_relevancy:.2%} |
| Context Precision | {r.context_precision:.2%} |
| Context Recall | {r.context_recall:.2%} |
| **Overall** | {r.overall_score:.2%} |

---

"""
    
    return report
