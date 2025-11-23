"""Document ingestion service."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.file_parsers import ParsedDocument, parser_factory


@dataclass
class Chunk:
    """Document chunk with content and metadata."""

    content: str
    metadata: dict
    chunk_id: str
    doc_id: str
    chunk_index: int


@dataclass
class IngestResult:
    """Result of document ingestion."""

    doc_id: str
    filename: str
    chunks_created: int
    status: str
    error: Optional[str] = None


class DocumentIngestor:
    """Service for ingesting documents into the vector store."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def ingest(
        self,
        content: bytes,
        filename: str,
        collection: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> IngestResult:
        """
        Ingest a document into the system.

        Args:
            content: Raw file content
            filename: Original filename
            collection: Target collection
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            IngestResult with processing status
        """
        doc_id = str(uuid4())
        try:
            # Parse document
            parsed = await parser_factory.parse(content, filename, content_type)

            # Create chunks
            chunks = self._create_chunks(parsed, doc_id, metadata or {})

            # Return result (actual storage happens via vector store)
            return IngestResult(
                doc_id=doc_id,
                filename=filename,
                chunks_created=len(chunks),
                status="success",
            )

        except Exception as e:
            return IngestResult(
                doc_id=doc_id,
                filename=filename,
                chunks_created=0,
                status="failed",
                error=str(e),
            )

    def _create_chunks(
        self,
        parsed: ParsedDocument,
        doc_id: str,
        extra_metadata: dict,
    ) -> list[Chunk]:
        """Split parsed document into chunks."""
        text = parsed.content
        if not text:
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                boundary = self._find_boundary(text, start, end)
                if boundary > start:
                    end = boundary

            chunk_content = text[start:end].strip()
            if chunk_content:
                chunk = Chunk(
                    content=chunk_content,
                    metadata={
                        **parsed.metadata,
                        **extra_metadata,
                        "filename": parsed.filename,
                        "file_type": parsed.file_type,
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                        "ingested_at": datetime.utcnow().isoformat(),
                    },
                    chunk_id=self._generate_chunk_id(doc_id, chunk_index),
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                )
                chunks.append(chunk)
                chunk_index += 1

            start = end - self.chunk_overlap
            if start <= (chunks[-1].chunk_index if chunks else 0):
                start = end

        return chunks

    def _find_boundary(self, text: str, start: int, end: int) -> int:
        """Find a good boundary for splitting text."""
        search_start = start + int((end - start) * 0.8)
        search_text = text[search_start:end]

        # Look for sentence endings
        for pattern in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            pos = search_text.rfind(pattern)
            if pos != -1:
                return search_start + pos + len(pattern)

        # Fall back to paragraph break
        pos = search_text.rfind("\n\n")
        if pos != -1:
            return search_start + pos + 2

        return end

    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        content = f"{doc_id}:{chunk_index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_chunks_as_dicts(self, chunks: list[Chunk]) -> list[dict]:
        """Convert chunks to dictionaries for vector storage."""
        return [
            {"content": chunk.content, "metadata": chunk.metadata}
            for chunk in chunks
        ]
