"""RabbitMQ queue service for async document processing."""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TaskType(str, Enum):
    """Types of tasks that can be queued."""

    DOCUMENT_INGEST = "document_ingest"
    DOCUMENT_DELETE = "document_delete"
    COLLECTION_REINDEX = "collection_reindex"
    EMBEDDING_UPDATE = "embedding_update"


class TaskStatus(str, Enum):
    """Status of a queued task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Represents a queued task."""

    task_id: str
    task_type: TaskType
    payload: dict
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create task from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            payload=data["payload"],
            status=TaskStatus(data["status"]),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            error=data.get("error"),
        )


class QueueService:
    """Service for managing message queues with RabbitMQ."""

    def __init__(self):
        """Initialize queue service."""
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self._connection = await aio_pika.connect_robust(
                settings.rabbitmq_connection_url,
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)

            # Declare queue
            self._queue = await self._channel.declare_queue(
                settings.rabbitmq_queue,
                durable=True,
            )

            self._connected = True
            logger.info("Connected to RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Close RabbitMQ connection."""
        if self._connection:
            await self._connection.close()
            self._connected = False
            logger.info("Disconnected from RabbitMQ")

    async def publish(self, task: Task) -> bool:
        """
        Publish a task to the queue.

        Args:
            task: Task to publish

        Returns:
            True if published successfully
        """
        if not self._connected or not self._channel:
            logger.error("Not connected to RabbitMQ")
            return False

        try:
            message = Message(
                body=json.dumps(task.to_dict()).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await self._channel.default_exchange.publish(
                message,
                routing_key=settings.rabbitmq_queue,
            )

            logger.info(
                f"Published task {task.task_id}",
                extra={"task_type": task.task_type.value},
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish task: {e}")
            return False

    async def consume(
        self,
        callback: Callable[[Task], Any],
    ) -> None:
        """
        Start consuming messages from the queue.

        Args:
            callback: Async function to handle each task
        """
        if not self._connected or not self._queue:
            raise RuntimeError("Not connected to RabbitMQ")

        async def process_message(message: AbstractIncomingMessage) -> None:
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    task = Task.from_dict(data)

                    logger.info(
                        f"Processing task {task.task_id}",
                        extra={"task_type": task.task_type.value},
                    )

                    await callback(task)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Message will be requeued due to exception

        await self._queue.consume(process_message)
        logger.info("Started consuming messages")

    async def publish_document_ingest(
        self,
        doc_id: str,
        filename: str,
        collection: str,
        storage_path: str,
    ) -> str:
        """
        Publish a document ingestion task.

        Args:
            doc_id: Document ID
            filename: Original filename
            collection: Target collection
            storage_path: Path in MinIO

        Returns:
            Task ID
        """
        from uuid import uuid4

        task = Task(
            task_id=str(uuid4()),
            task_type=TaskType.DOCUMENT_INGEST,
            payload={
                "doc_id": doc_id,
                "filename": filename,
                "collection": collection,
                "storage_path": storage_path,
            },
        )

        await self.publish(task)
        return task.task_id

    async def publish_collection_reindex(
        self,
        collection: str,
        batch_size: int = 100,
    ) -> str:
        """
        Publish a collection reindex task.

        Args:
            collection: Collection to reindex
            batch_size: Batch size for reindexing

        Returns:
            Task ID
        """
        from uuid import uuid4

        task = Task(
            task_id=str(uuid4()),
            task_type=TaskType.COLLECTION_REINDEX,
            payload={
                "collection": collection,
                "batch_size": batch_size,
            },
        )

        await self.publish(task)
        return task.task_id

    async def get_queue_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Queue statistics
        """
        if not self._queue:
            return {"error": "Not connected"}

        return {
            "name": self._queue.name,
            "message_count": self._queue.declaration_result.message_count,
            "consumer_count": self._queue.declaration_result.consumer_count,
        }

    @property
    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ."""
        return self._connected
