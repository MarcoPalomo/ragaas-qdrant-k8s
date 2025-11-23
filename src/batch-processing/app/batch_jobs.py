"""Batch jobs for RAG service, including collection reindexing.

This module provides batch processing capabilities for the RAG service:
- Reindex documents in Qdrant collections (e.g., after changing embedding model)
- Support for partial reindexing (specific collections)
- Batched processing to handle large collections
- Progress tracking and error handling
"""

import os
import sys
import logging
import asyncio
import argparse
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
except ImportError:
    print("Error: qdrant-client not installed. Run: pip install qdrant-client")
    sys.exit(1)

try:
    import openai
except ImportError:
    print("Warning: openai not installed. Using fallback embedder.")
    openai = None

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Default settings (can be overridden via env vars or CLI args)
DEFAULT_BATCH_SIZE = 100
DEFAULT_VECTOR_SIZE = 1536  # OpenAI ada-002
DEFAULT_DISTANCE = "Cosine"


class ReindexingJob:
    """Handles reindexing of Qdrant collections."""

    def __init__(
        self,
        qdrant_host: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
    ):
        """Initialize reindexing job.
        
        Args:
            qdrant_host: Qdrant server URL (fallback: QDRANT_HOST env var)
            qdrant_api_key: Qdrant API key (fallback: QDRANT_API_KEY env var)
            batch_size: Number of vectors to process at once
            dry_run: If True, only show what would be done
        """
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Setup Qdrant client
        host = qdrant_host or os.getenv("QDRANT_HOST")
        api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY")

        if host:
            self.client = QdrantClient(url=host, api_key=api_key)
            logger.info(f"Connected to Qdrant at {host}")
        else:
            self.client = QdrantClient()
            logger.info("Using local Qdrant instance")

        # Setup embedder
        if openai is not None and os.getenv("OPENAI_API_KEY"):
            openai.api_key = os.getenv("OPENAI_API_KEY")
            self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            self.embedder = self._openai_embed
            logger.info(f"Using OpenAI embeddings ({self.model})")
        else:
            self.embedder = self._fallback_embed
            logger.warning("Using fallback hash-based embedder - not for production!")

    async def _openai_embed(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using OpenAI API."""
        response = await asyncio.to_thread(
            openai.Embedding.create, model=self.model, input=texts
        )
        return [d["embedding"] for d in response["data"]]

    def _fallback_embed(self, texts: List[str]) -> List[List[float]]:
        """Fallback embedder using hash (for testing only)."""
        vectors = []
        for t in texts:
            h = abs(hash(t))
            vectors.append([(h >> (i * 8)) % 256 / 255.0 for i in range(8)])
        return vectors

    async def list_collections(self) -> List[str]:
        """Get all collection names from Qdrant."""
        try:
            res = await asyncio.to_thread(self.client.get_collections)
            if hasattr(res, "collections"):
                return [c.name for c in res.collections]
            return []
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            raise

    async def get_collection_points(
        self, collection: str
    ) -> AsyncGenerator[Dict, None]:
        """Stream all points from a collection."""
        offset = 0
        while True:
            try:
                scroll_res = await asyncio.to_thread(
                    self.client.scroll,
                    collection_name=collection,
                    offset=offset,
                    limit=self.batch_size,
                    with_payload=True,
                    with_vectors=False,  # we'll recompute vectors
                )
                
                points = scroll_res[0]  # (points, next_offset)
                if not points:
                    break

                for point in points:
                    # Extract payload and ID
                    if hasattr(point, "payload"):
                        payload = point.payload
                        pid = point.id
                    else:
                        payload = point.get("payload", {})
                        pid = point.get("id")

                    yield {"id": pid, "payload": payload}

                offset += len(points)
                
            except Exception as e:
                logger.error(f"Error scrolling collection {collection}: {e}")
                raise

    async def reindex_collection(self, collection: str) -> None:
        """Reindex all documents in a collection with new embeddings."""
        try:
            logger.info(f"Starting reindexing of collection: {collection}")
            start_time = datetime.now()
            
            # Create temp collection for reindexing
            temp_name = f"{collection}_reindex_{int(start_time.timestamp())}"
            
            if not self.dry_run:
                vector_params = models.VectorParams(
                    size=DEFAULT_VECTOR_SIZE,
                    distance=getattr(models.Distance, DEFAULT_DISTANCE)
                )
                await asyncio.to_thread(
                    self.client.recreate_collection,
                    collection_name=temp_name,
                    vectors_config=vector_params
                )
            
            # Process all points in batches
            batch = []
            total_processed = 0
            
            async for point in self.get_collection_points(collection):
                # Get text from payload (adjust field name if needed)
                text = point["payload"].get("text", "")
                if not text:
                    logger.warning(f"No text found in point {point['id']}")
                    continue
                
                batch.append({"id": point["id"], "text": text, **point["payload"]})
                
                if len(batch) >= self.batch_size:
                    if not self.dry_run:
                        # Get embeddings and store
                        texts = [d["text"] for d in batch]
                        vectors = await self._openai_embed(texts)
                        
                        points = []
                        for doc, vec in zip(batch, vectors):
                            points.append(
                                models.PointStruct(
                                    id=doc["id"],
                                    vector=vec,
                                    payload={k: v for k, v in doc.items() if k != "text"}
                                )
                            )
                        
                        await asyncio.to_thread(
                            self.client.upsert,
                            collection_name=temp_name,
                            points=points
                        )
                    
                    total_processed += len(batch)
                    logger.info(
                        f"Processed {total_processed} documents "
                        f"({'dry run' if self.dry_run else 'actual'})"
                    )
                    batch = []
            
            # Process remaining batch
            if batch and not self.dry_run:
                texts = [d["text"] for d in batch]
                vectors = await self._openai_embed(texts)
                points = [
                    models.PointStruct(
                        id=doc["id"],
                        vector=vec,
                        payload={k: v for k, v in doc.items() if k != "text"}
                    )
                    for doc, vec in zip(batch, vectors)
                ]
                await asyncio.to_thread(
                    self.client.upsert,
                    collection_name=temp_name,
                    points=points
                )
                total_processed += len(batch)
            
            duration = datetime.now() - start_time
            logger.info(
                f"Reindexing complete: {total_processed} documents in {duration} "
                f"({'dry run' if self.dry_run else 'actual'})"
            )
            
            if not self.dry_run:
                # Rename collections to swap old and new
                old_name = f"{collection}_old_{int(start_time.timestamp())}"
                await asyncio.to_thread(
                    self.client.rename_collection,
                    collection_name=collection,
                    new_collection_name=old_name
                )
                await asyncio.to_thread(
                    self.client.rename_collection,
                    collection_name=temp_name,
                    new_collection_name=collection
                )
                # Optionally: delete old collection
                # await asyncio.to_thread(self.client.delete_collection, old_name)
            
        except Exception as e:
            logger.error(f"Error reindexing collection {collection}: {e}")
            raise


async def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Reindex Qdrant collections with new embeddings"
    )
    parser.add_argument(
        "--collections",
        nargs="*",
        help="Collections to reindex (default: all collections)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size for processing (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--qdrant-host",
        help="Qdrant server URL (default: from QDRANT_HOST env var)"
    )
    parser.add_argument(
        "--qdrant-api-key",
        help="Qdrant API key (default: from QDRANT_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    job = ReindexingJob(
        qdrant_host=args.qdrant_host,
        qdrant_api_key=args.qdrant_api_key,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    
    try:
        collections = args.collections
        if not collections:
            collections = await job.list_collections()
            
        if not collections:
            logger.warning("No collections found to reindex")
            return
            
        logger.info(
            f"Will reindex collections: {collections} "
            f"({'dry run' if args.dry_run else 'actual'})"
        )
        
        for collection in collections:
            await job.reindex_collection(collection)
            
    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
