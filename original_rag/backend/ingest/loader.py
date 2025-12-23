"""
Document Loaders
Handles loading documents from various file formats.
"""
import logging
from pathlib import Path
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Unified document loader supporting multiple file types."""

    SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx'}

    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        """Check if file type is supported."""
        path = Path(file_path)
        return path.suffix.lower() in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def load(cls, file_path: str | Path) -> List[Document]:
        """Load document from file path."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not cls.is_supported(path):
            raise ValueError(f"Unsupported file type: {suffix}")

        logger.info(f"Loading document: {path.name}")

        if suffix == '.pdf':
            return cls._load_pdf(path)
        elif suffix == '.txt':
            return cls._load_text(path)
        elif suffix == '.md':
            return cls._load_markdown(path)
        elif suffix == '.docx':
            return cls._load_docx(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    @staticmethod
    def _load_pdf(path: Path) -> List[Document]:
        """Load PDF file."""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(str(path))
            docs = loader.load()
            # Add source metadata
            for doc in docs:
                doc.metadata['source'] = path.name
                doc.metadata['file_type'] = 'pdf'
                # Fix page numbering: PyPDFLoader is 0-indexed, convert to 1-indexed
                if 'page' in doc.metadata:
                    doc.metadata['page'] = doc.metadata['page'] + 1
            return docs
        except ImportError:
            logger.error("pypdf not installed. Run: pip install pypdf")
            raise
        except Exception as e:
            logger.error(f"Error loading PDF {path}: {e}")
            raise

    @staticmethod
    def _load_text(path: Path) -> List[Document]:
        """Load plain text file."""
        try:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(str(path), encoding='utf-8')
            docs = loader.load()
            for doc in docs:
                doc.metadata['source'] = path.name
                doc.metadata['file_type'] = 'txt'
            return docs
        except Exception as e:
            logger.error(f"Error loading text file {path}: {e}")
            raise

    @staticmethod
    def _load_markdown(path: Path) -> List[Document]:
        """Load Markdown file."""
        try:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(str(path), encoding='utf-8')
            docs = loader.load()
            for doc in docs:
                doc.metadata['source'] = path.name
                doc.metadata['file_type'] = 'md'
            return docs
        except Exception as e:
            logger.error(f"Error loading markdown file {path}: {e}")
            raise

    @staticmethod
    def _load_docx(path: Path) -> List[Document]:
        """Load DOCX file."""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            loader = Docx2txtLoader(str(path))
            docs = loader.load()
            for doc in docs:
                doc.metadata['source'] = path.name
                doc.metadata['file_type'] = 'docx'
            return docs
        except ImportError:
            logger.error("docx2txt not installed. Run: pip install docx2txt")
            raise
        except Exception as e:
            logger.error(f"Error loading DOCX {path}: {e}")
            raise


def load_document(file_path: str | Path) -> List[Document]:
    """Convenience function to load a document."""
    return DocumentLoader.load(file_path)
