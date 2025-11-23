"""Tests for service modules."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDocumentProcessor:
    """Tests for DocumentProcessor service."""

    def test_process_document_creates_chunks(self):
        """Test document processing creates chunks."""
        from app.services.document_processor import Document, DocumentProcessor

        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        doc = Document(
            content="This is a test document. " * 20,
            metadata={"source": "test"},
        )

        chunks = processor.process_document(doc)

        assert len(chunks) > 0
        assert all(len(c.content) <= 100 + 50 for c in chunks)  # Allow some overflow

    def test_process_document_preserves_metadata(self):
        """Test that metadata is preserved in chunks."""
        from app.services.document_processor import Document, DocumentProcessor

        processor = DocumentProcessor()
        doc = Document(
            content="Test content",
            metadata={"source": "test", "author": "tester"},
        )

        chunks = processor.process_document(doc)

        assert len(chunks) > 0
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["author"] == "tester"

    def test_extract_metadata(self):
        """Test metadata extraction from content."""
        from app.services.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        metadata = processor.extract_metadata(
            "test.txt",
            "Line one\nLine two\nLine three"
        )

        assert metadata["filename"] == "test.txt"
        assert metadata["file_extension"] == "txt"
        assert metadata["line_count"] == 3

    def test_clean_text(self):
        """Test text cleaning."""
        from app.services.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        cleaned = processor._clean_text("  Multiple   spaces  \n\n  here  ")

        assert "  " not in cleaned  # No double spaces


class TestLLMService:
    """Tests for LLMService."""

    @pytest.mark.asyncio
    async def test_generate_response_with_context(self):
        """Test response generation with context."""
        from app.services.llm_service import LLMService

        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test answer"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = LLMService(client=mock_client)
        answer, confidence = await service.generate_response(
            query="What is this?",
            context=["Context 1", "Context 2"],
        )

        assert answer == "Test answer"
        assert 0 <= confidence <= 1
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_without_context(self):
        """Test response generation without context."""
        from app.services.llm_service import LLMService

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I don't have enough context"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = LLMService(client=mock_client)
        answer, confidence = await service.generate_response(
            query="What is this?",
            context=[],
        )

        # Lower confidence without context
        assert confidence < 0.5

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        from app.services.llm_service import LLMService

        service = LLMService(client=MagicMock())

        # With context
        conf = service._calculate_confidence(["ctx1", "ctx2"], "Here is the answer")
        assert conf > 0.5

        # Without context
        conf = service._calculate_confidence([], "No context available")
        assert conf <= 0.5

        # With uncertainty phrase
        conf = service._calculate_confidence(
            ["ctx1"],
            "I'm not sure but maybe..."
        )
        assert conf < 0.7


class TestCacheService:
    """Tests for CacheService."""

    @pytest.mark.asyncio
    async def test_generate_query_key(self):
        """Test query key generation."""
        from app.services.cache_service import CacheService

        key1 = CacheService.generate_query_key("query1", "collection1", 5)
        key2 = CacheService.generate_query_key("query1", "collection1", 5)
        key3 = CacheService.generate_query_key("query2", "collection1", 5)

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different query = different key
        assert key1.startswith("query:")

    @pytest.mark.asyncio
    async def test_generate_embedding_key(self):
        """Test embedding key generation."""
        from app.services.cache_service import CacheService

        key = CacheService.generate_embedding_key("test text")

        assert key.startswith("embedding:")

    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test cache get/set operations."""
        from app.services.cache_service import CacheService

        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_redis.ping = AsyncMock()

        service = CacheService(redis_client=mock_redis)
        service._connected = True

        # Test get (cache miss)
        result = await service.get("test_key")
        assert result is None

        # Test set
        success = await service.set("test_key", {"data": "value"})
        assert success


class TestQueueService:
    """Tests for QueueService."""

    @pytest.mark.asyncio
    async def test_task_creation(self):
        """Test task creation."""
        from app.services.queue_service import Task, TaskStatus, TaskType

        task = Task(
            task_id="test-123",
            task_type=TaskType.DOCUMENT_INGEST,
            payload={"doc_id": "doc-1"},
        )

        assert task.status == TaskStatus.PENDING
        assert task.created_at != ""

    def test_task_serialization(self):
        """Test task to/from dict."""
        from app.services.queue_service import Task, TaskStatus, TaskType

        task = Task(
            task_id="test-123",
            task_type=TaskType.DOCUMENT_INGEST,
            payload={"doc_id": "doc-1"},
        )

        task_dict = task.to_dict()
        restored = Task.from_dict(task_dict)

        assert restored.task_id == task.task_id
        assert restored.task_type == task.task_type
        assert restored.payload == task.payload
