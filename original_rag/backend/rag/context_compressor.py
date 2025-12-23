"""
Context Compressor - LLMLingua Integration (ADR-015)

Compresses retrieved context before sending to LLM to reduce prefill latency.
Can compress 4000 tokens down to 800-1200 while retaining 95%+ information.

Usage:
    compressor = ContextCompressor()
    compressed = compressor.compress(documents, query)
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy load to avoid import overhead
_compressor = None


@dataclass
class CompressionResult:
    """Result of context compression."""
    original_text: str
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float

    @property
    def saved_tokens(self) -> int:
        return self.original_tokens - self.compressed_tokens


class ContextCompressor:
    """
    Compresses retrieved context using LLMLingua-2.

    Uses a small language model to identify and remove redundant/filler tokens
    while preserving the semantic meaning needed for the LLM to generate answers.
    """

    def __init__(
        self,
        target_ratio: float = 0.3,  # Keep 30% of tokens
        model_name: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        use_llmlingua2: bool = True,
    ):
        self.target_ratio = target_ratio
        self.model_name = model_name
        self.use_llmlingua2 = use_llmlingua2
        self._compressor = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of LLMLingua."""
        if self._initialized:
            return

        try:
            if self.use_llmlingua2:
                from llmlingua import PromptCompressor

                logger.info(f"Initializing LLMLingua-2 with {self.model_name}...")
                self._compressor = PromptCompressor(
                    model_name=self.model_name,
                    use_llmlingua2=True,
                    device_map="cpu",  # Use CPU for compatibility
                )
                logger.info("LLMLingua-2 initialized successfully")
            else:
                logger.warning("LLMLingua not configured, compression disabled")

        except ImportError as e:
            logger.warning(f"LLMLingua not available: {e}")
            logger.warning("Install with: pip install llmlingua")
        except Exception as e:
            logger.error(f"Failed to initialize LLMLingua: {e}")

        self._initialized = True

    def compress(
        self,
        documents: List[Dict],
        query: str,
        target_ratio: Optional[float] = None,
    ) -> CompressionResult:
        """
        Compress retrieved documents for LLM context.

        Args:
            documents: List of document dicts with 'content' key
            query: The user's query (used for query-aware compression)
            target_ratio: Override default compression ratio

        Returns:
            CompressionResult with original and compressed text
        """
        self._initialize()

        # Build context from documents
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.get("metadata", {}).get("source", "unknown")
            content = doc.get("content", "")
            context_parts.append(f"[Source {i}: {source}]\n{content}")

        original_text = "\n\n---\n\n".join(context_parts)
        original_tokens = len(original_text.split())  # Rough estimate

        if not self._compressor:
            # No compression available, return as-is
            logger.debug("Compression unavailable, returning original context")
            return CompressionResult(
                original_text=original_text,
                compressed_text=original_text,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
            )

        try:
            ratio = target_ratio or self.target_ratio

            # Use LLMLingua-2 compression
            result = self._compressor.compress_prompt(
                context=[original_text],
                instruction="",
                question=query,
                target_token=int(original_tokens * ratio),
                condition_compare=True,
                condition_in_question="after",
                reorder_context="sort",
                dynamic_context_compression_ratio=0.3,
            )

            compressed_text = result["compressed_prompt"]
            compressed_tokens = len(compressed_text.split())
            compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

            logger.info(
                f"Compressed context: {original_tokens} -> {compressed_tokens} tokens "
                f"({compression_ratio:.1%} of original, saved {original_tokens - compressed_tokens})"
            )

            return CompressionResult(
                original_text=original_text,
                compressed_text=compressed_text,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio,
            )

        except Exception as e:
            logger.error(f"Compression failed: {e}, returning original")
            return CompressionResult(
                original_text=original_text,
                compressed_text=original_text,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
            )

    def estimate_savings(self, documents: List[Dict]) -> Dict:
        """
        Estimate token savings without actually compressing.

        Returns:
            Dict with estimated original tokens, target tokens, and time savings
        """
        context_parts = [doc.get("content", "") for doc in documents]
        original_text = " ".join(context_parts)
        original_tokens = len(original_text.split())

        target_tokens = int(original_tokens * self.target_ratio)
        saved_tokens = original_tokens - target_tokens

        # Rough estimate: ~50 tokens/second for Ollama prefill on CPU
        estimated_time_saved_ms = (saved_tokens / 50) * 1000

        return {
            "original_tokens": original_tokens,
            "target_tokens": target_tokens,
            "saved_tokens": saved_tokens,
            "estimated_time_saved_ms": estimated_time_saved_ms,
        }


# Global singleton
def get_context_compressor() -> ContextCompressor:
    """Get or create the singleton context compressor."""
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


# Simple function interface
def compress_context(documents: List[Dict], query: str) -> str:
    """
    Simple function to compress documents for LLM context.

    Returns the compressed text string.
    """
    compressor = get_context_compressor()
    result = compressor.compress(documents, query)
    return result.compressed_text
