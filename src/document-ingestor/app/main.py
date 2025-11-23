"""Main entry point for document ingestor service."""

import asyncio
import logging
import os
import signal
import sys

from app.queue_consumer import QueueConsumer

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handle graceful shutdown on signals."""

    def __init__(self):
        self.shutdown_event = asyncio.Event()

    def signal_handler(self, sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    logger.info("Starting Document Ingestor Service")

    # Setup graceful shutdown
    shutdown = GracefulShutdown()
    signal.signal(signal.SIGTERM, shutdown.signal_handler)
    signal.signal(signal.SIGINT, shutdown.signal_handler)

    # Create consumer
    consumer = QueueConsumer(
        rabbitmq_url=os.getenv("RABBITMQ_URL"),
        queue_name=os.getenv("QUEUE_NAME", "document_processing"),
    )

    try:
        # Connect to RabbitMQ
        await consumer.connect()
        logger.info("Connected to RabbitMQ")

        # Start consuming
        consume_task = asyncio.create_task(consumer.start())

        # Wait for shutdown signal
        await shutdown.shutdown_event.wait()
        logger.info("Shutdown signal received")

        # Cancel consumer
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

    finally:
        await consumer.disconnect()
        logger.info("Document Ingestor Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
