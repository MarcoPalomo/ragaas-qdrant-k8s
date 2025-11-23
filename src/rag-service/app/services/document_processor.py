"""Document processing service for chunking and preparing documents."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Document:
    """Represents a document with content and metadata."""

    content: str
    metadata: dict = field(default_factory=dict)
    doc_id: Optional[str] = None

    def __post_init__(self):
        if not self.doc_id:
            self.doc_id = str(uuid4())


@dataclass
class Chunk:
    """Represents a document chunk."""

    content: str
    metadata: dict
    chunk_id: str
    doc_id: str
    chunk_index: int


class DocumentProcessor:
    """Service for processing and chunking documents."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        """
        Initialize document processor.

        Args:
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def process_document(self, document: Document) -> list[Chunk]:
        """
        Process a document into chunks.

        Args:
            document: Document to process

        Returns:
            List of document chunks
        """
        # Clean content
        cleaned_content = self._clean_text(document.content)

        # Split into chunks
        chunks = self._split_into_chunks(cleaned_content)

        # Create chunk objects
        result = []
        for i, chunk_content in enumerate(chunks):
            chunk = Chunk(
                content=chunk_content,
                metadata={
                    **document.metadata,
                    "doc_id": document.doc_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "processed_at": datetime.utcnow().isoformat(),
                },
                chunk_id=self._generate_chunk_id(document.doc_id, i),
                doc_id=document.doc_id,
                chunk_index=i,
            )
            result.append(chunk)

        logger.info(
            f"Processed document into {len(result)} chunks",
            extra={
                "doc_id": document.doc_id,
                "original_length": len(document.content),
                "num_chunks": len(result),
            },
        )

        return result

    def process_documents(self, documents: list[Document]) -> list[Chunk]:
        """
        Process multiple documents into chunks.

        Args:
            documents: List of documents to process

        Returns:
            List of all document chunks
        """
        all_chunks = []
        for doc in documents:
            chunks = self.process_document(doc)
            all_chunks.extend(chunks)

        logger.info(
            f"Processed {len(documents)} documents into {len(all_chunks)} chunks"
        )
        return all_chunks

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text content

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove null characters
        text = text.replace("\x00", "")

        # Normalize unicode
        text = text.strip()

        return text

    def _split_into_chunks(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            # Find end of chunk
            end = start + self.chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                sentence_end = self._find_sentence_boundary(text, start, end)
                if sentence_end > start:
                    end = sentence_end

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.chunk_overlap
            if start <= chunks[-1] if chunks else 0:
                start = end

        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """
        Find a sentence boundary near the end position.

        Args:
            text: Full text
            start: Start position
            end: Target end position

        Returns:
            Best sentence boundary position
        """
        # Look for sentence endings (.!?) within the last 20% of the chunk
        search_start = start + int((end - start) * 0.8)
        search_text = text[search_start:end]

        # Find last sentence ending
        for pattern in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            last_pos = search_text.rfind(pattern)
            if last_pos != -1:
                return search_start + last_pos + len(pattern)

        # Fall back to paragraph break
        last_para = search_text.rfind("\n\n")
        if last_para != -1:
            return search_start + last_para + 2

        return end

    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """
        Generate a unique chunk ID.

        Args:
            doc_id: Parent document ID
            chunk_index: Index of chunk within document

        Returns:
            Unique chunk ID
        """
        content = f"{doc_id}:{chunk_index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def extract_metadata(self, filename: str, content: str) -> dict:
        """
        Extract metadata from document.

        Args:
            filename: Original filename
            content: Document content

        Returns:
            Extracted metadata
        """
        return {
            "filename": filename,
            "file_extension": filename.split(".")[-1].lower() if "." in filename else "",
            "char_count": len(content),
            "word_count": len(content.split()),
            "line_count": content.count("\n") + 1,
        }
