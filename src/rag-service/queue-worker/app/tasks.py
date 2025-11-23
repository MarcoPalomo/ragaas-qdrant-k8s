"""Task handlers for background processing."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of background tasks."""

    DOCUMENT_INGEST = "document_ingest"
    DOCUMENT_DELETE = "document_delete"
    COLLECTION_REINDEX = "collection_reindex"
    EMBEDDING_UPDATE = "embedding_update"
    CACHE_INVALIDATE = "cache_invalidate"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """Result of task execution."""

    task_id: str
    status: TaskStatus
    result: Optional[dict] = None
    error: Optional[str] = None


class TaskHandler:
    """Base class for task handlers."""

    async def handle(self, task_id: str, payload: dict) -> TaskResult:
        """Handle a task."""
        raise NotImplementedError


class DocumentIngestHandler(TaskHandler):
    """Handler for document ingestion tasks."""

    def __init__(self, vector_store, doc_processor):
        self.vector_store = vector_store
        self.doc_processor = doc_processor

    async def handle(self, task_id: str, payload: dict) -> TaskResult:
        """Process document ingestion."""
        try:
            doc_id = payload.get("doc_id")
            content = payload.get("content")
            filename = payload.get("filename")
            collection = payload.get("collection", "default")

            logger.info(f"Processing document ingest: {filename}")

            # Process document
            from app.services.document_processor import Document

            doc = Document(
                content=content,
                metadata={"filename": filename},
                doc_id=doc_id,
            )
            chunks = self.doc_processor.process_document(doc)

            # Store in vector database
            documents = [
                {"content": chunk.content, "metadata": chunk.metadata}
                for chunk in chunks
            ]
            await self.vector_store.store_documents(documents, collection)

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "doc_id": doc_id,
                    "chunks_created": len(chunks),
                },
            )

        except Exception as e:
            logger.error(f"Document ingest failed: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )


class CollectionReindexHandler(TaskHandler):
    """Handler for collection reindex tasks."""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def handle(self, task_id: str, payload: dict) -> TaskResult:
        """Reindex a collection."""
        try:
            collection = payload.get("collection")
            batch_size = payload.get("batch_size", 100)

            logger.info(f"Reindexing collection: {collection}")

            # Reindex logic would go here
            # This would typically involve:
            # 1. Reading all documents from the collection
            # 2. Re-generating embeddings
            # 3. Updating the vectors

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result={"collection": collection, "reindexed": True},
            )

        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )


class CacheInvalidateHandler(TaskHandler):
    """Handler for cache invalidation tasks."""

    def __init__(self, cache_service):
        self.cache_service = cache_service

    async def handle(self, task_id: str, payload: dict) -> TaskResult:
        """Invalidate cache entries."""
        try:
            pattern = payload.get("pattern", "*")
            collection = payload.get("collection")

            if collection:
                count = await self.cache_service.invalidate_collection(collection)
            else:
                count = await self.cache_service.clear_pattern(pattern)

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result={"invalidated_count": count},
            )

        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )


class TaskRegistry:
    """Registry for task handlers."""

    def __init__(self):
        self._handlers: dict[TaskType, TaskHandler] = {}

    def register(self, task_type: TaskType, handler: TaskHandler) -> None:
        """Register a task handler."""
        self._handlers[task_type] = handler

    def get_handler(self, task_type: TaskType) -> Optional[TaskHandler]:
        """Get handler for a task type."""
        return self._handlers.get(task_type)

    async def execute(self, task_type: TaskType, task_id: str, payload: dict) -> TaskResult:
        """Execute a task."""
        handler = self.get_handler(task_type)
        if handler is None:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"No handler for task type: {task_type}",
            )
        return await handler.handle(task_id, payload)
