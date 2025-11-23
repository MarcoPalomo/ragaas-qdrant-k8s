"""Background worker for processing queued tasks."""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Optional

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.tasks import (
    CacheInvalidateHandler,
    CollectionReindexHandler,
    DocumentIngestHandler,
    TaskRegistry,
    TaskStatus,
    TaskType,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Worker:
    """Background worker for processing tasks from RabbitMQ."""

    def __init__(
        self,
        rabbitmq_url: Optional[str] = None,
        queue_name: str = "document_processing",
    ):
        self.rabbitmq_url = rabbitmq_url or os.getenv(
            "RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672"
        )
        self.queue_name = queue_name
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._shutdown = asyncio.Event()

        # Initialize task registry
        self.registry = TaskRegistry()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup task handlers."""
        # Import services
        # In production, these would be properly initialized
        from unittest.mock import MagicMock

        # Create mock services for now
        vector_store = MagicMock()
        doc_processor = MagicMock()
        cache_service = MagicMock()

        # Register handlers
        self.registry.register(
            TaskType.DOCUMENT_INGEST,
            DocumentIngestHandler(vector_store, doc_processor),
        )
        self.registry.register(
            TaskType.COLLECTION_REINDEX,
            CollectionReindexHandler(vector_store),
        )
        self.registry.register(
            TaskType.CACHE_INVALIDATE,
            CacheInvalidateHandler(cache_service),
        )

    async def connect(self) -> None:
        """Connect to RabbitMQ."""
        logger.info(f"Connecting to RabbitMQ: {self.rabbitmq_url}")
        self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
        )
        logger.info(f"Connected to queue: {self.queue_name}")

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        if self._connection:
            await self._connection.close()
            logger.info("Disconnected from RabbitMQ")

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """Process a single message from the queue."""
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                task_id = data.get("task_id", "unknown")
                task_type_str = data.get("task_type")
                payload = data.get("payload", {})

                logger.info(f"Processing task {task_id}: {task_type_str}")

                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    logger.error(f"Unknown task type: {task_type_str}")
                    return

                # Execute task
                result = await self.registry.execute(task_type, task_id, payload)

                if result.status == TaskStatus.COMPLETED:
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    logger.error(f"Task {task_id} failed: {result.error}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                raise

    async def run(self) -> None:
        """Run the worker."""
        await self.connect()

        logger.info("Starting worker...")
        await self._queue.consume(self.process_message)

        # Wait for shutdown signal
        await self._shutdown.wait()

    def shutdown(self) -> None:
        """Signal the worker to shut down."""
        logger.info("Shutdown requested")
        self._shutdown.set()


async def main():
    """Main entry point."""
    logger.info("Starting Queue Worker")

    worker = Worker(
        rabbitmq_url=os.getenv("RABBITMQ_URL"),
        queue_name=os.getenv("QUEUE_NAME", "document_processing"),
    )

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.shutdown)

    try:
        await worker.run()
    finally:
        await worker.disconnect()
        logger.info("Queue Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
