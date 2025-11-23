"""RabbitMQ consumer for document processing tasks."""

import asyncio
import json
import logging
import os
from typing import Optional

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.ingestor import DocumentIngestor
from app.storage import MinIOStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueueConsumer:
    """Consumer for processing document ingestion tasks from RabbitMQ."""

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

        # Services
        self.ingestor = DocumentIngestor()
        self.storage = MinIOStorage()

    async def connect(self) -> None:
        """Connect to RabbitMQ."""
        logger.info(f"Connecting to RabbitMQ: {self.rabbitmq_url}")
        self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=5)

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
                task_type = data.get("task_type")
                payload = data.get("payload", {})
                task_id = data.get("task_id", "unknown")

                logger.info(f"Processing task {task_id}: {task_type}")

                if task_type == "document_ingest":
                    await self._handle_document_ingest(payload)
                elif task_type == "document_delete":
                    await self._handle_document_delete(payload)
                else:
                    logger.warning(f"Unknown task type: {task_type}")

                logger.info(f"Completed task {task_id}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                raise

    async def _handle_document_ingest(self, payload: dict) -> None:
        """Handle document ingestion task."""
        doc_id = payload.get("doc_id")
        filename = payload.get("filename")
        collection = payload.get("collection", "default")
        storage_path = payload.get("storage_path")

        logger.info(f"Ingesting document: {filename} -> {collection}")

        # Download from MinIO
        content = await self.storage.download(storage_path)
        if content is None:
            raise ValueError(f"Failed to download file: {storage_path}")

        # Process document
        result = await self.ingestor.ingest(
            content=content,
            filename=filename,
            collection=collection,
            metadata={"source_path": storage_path},
        )

        if result.status != "success":
            raise ValueError(f"Ingestion failed: {result.error}")

        logger.info(f"Created {result.chunks_created} chunks for {filename}")

    async def _handle_document_delete(self, payload: dict) -> None:
        """Handle document deletion task."""
        doc_id = payload.get("doc_id")
        collection = payload.get("collection")

        logger.info(f"Deleting document {doc_id} from {collection}")
        # Deletion logic would go here

    async def start(self) -> None:
        """Start consuming messages."""
        if self._queue is None:
            await self.connect()

        logger.info("Starting message consumer...")
        await self._queue.consume(self.process_message)

        # Keep running
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")

    async def run(self) -> None:
        """Run the consumer."""
        try:
            await self.connect()
            await self.start()
        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    consumer = QueueConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
