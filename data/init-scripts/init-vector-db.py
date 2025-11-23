#!/usr/bin/env python3
"""
Initialize Qdrant vector database with default collections for RAGaaS.

This script creates the necessary collections and indexes for the RAG service.
Run this after deploying Qdrant for the first time.

Usage:
    python init-vector-db.py --url http://localhost:6333
"""

import argparse
import sys
import time
from typing import Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
except ImportError:
    print("Error: qdrant-client not installed. Run: pip install qdrant-client")
    sys.exit(1)


# Default collection configurations
DEFAULT_COLLECTIONS = [
    {
        "name": "default",
        "description": "Default collection for document embeddings",
        "vector_size": 1536,  # OpenAI text-embedding-3-small dimension
        "distance": models.Distance.COSINE,
    },
    {
        "name": "documents",
        "description": "Collection for ingested document chunks",
        "vector_size": 1536,
        "distance": models.Distance.COSINE,
    },
]


def wait_for_qdrant(client: QdrantClient, max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for Qdrant to become available."""
    for attempt in range(max_retries):
        try:
            # Try to get collections list
            client.get_collections()
            print(" Qdrant is ready")
            return True
        except Exception as e:
            print(f"  Waiting for Qdrant... (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)

    print(" Qdrant did not become available")
    return False


def create_collection(
    client: QdrantClient,
    name: str,
    vector_size: int,
    distance: models.Distance,
    description: str = "",
) -> bool:
    """Create a collection if it doesn't exist."""
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        existing_names = [c.name for c in collections]

        if name in existing_names:
            print(f"  Collection '{name}' already exists, skipping...")
            return True

        # Create collection with optimized settings
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=distance,
                on_disk=True,  # Store vectors on disk for large collections
            ),
            # Optimized indexing settings
            hnsw_config=models.HnswConfigDiff(
                m=16,  # Number of edges per node
                ef_construct=100,  # Size of the dynamic candidate list
                full_scan_threshold=10000,  # Use full scan for small collections
            ),
            # Write-ahead log for durability
            wal_config=models.WalConfigDiff(
                wal_capacity_mb=32,
                wal_segments_ahead=0,
            ),
            # Payload indexing for filtering
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=20000,
                memmap_threshold=50000,
            ),
        )

        # Create payload indexes for common filter fields
        client.create_payload_index(
            collection_name=name,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=name,
            field_name="document_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=name,
            field_name="chunk_index",
            field_schema=models.PayloadSchemaType.INTEGER,
        )
        client.create_payload_index(
            collection_name=name,
            field_name="created_at",
            field_schema=models.PayloadSchemaType.DATETIME,
        )

        print(f" Created collection '{name}' (vectors: {vector_size}, distance: {distance})")
        return True

    except Exception as e:
        print(f" Failed to create collection '{name}': {e}")
        return False


def init_database(url: str, api_key: Optional[str] = None) -> bool:
    """Initialize the vector database with default collections."""
    print(f"\n{'='*60}")
    print("RAGaaS Vector Database Initialization")
    print(f"{'='*60}")
    print(f"Qdrant URL: {url}")
    print()

    # Create client
    try:
        client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=30,
        )
    except Exception as e:
        print(f" Failed to create Qdrant client: {e}")
        return False

    # Wait for Qdrant to be ready
    print("Checking Qdrant availability...")
    if not wait_for_qdrant(client):
        return False

    # Create collections
    print("\nCreating collections...")
    success = True
    for config in DEFAULT_COLLECTIONS:
        if not create_collection(
            client=client,
            name=config["name"],
            vector_size=config["vector_size"],
            distance=config["distance"],
            description=config.get("description", ""),
        ):
            success = False

    # Print summary
    print(f"\n{'='*60}")
    if success:
        print(" Database initialization completed successfully")

        # List all collections
        print("\nCurrent collections:")
        collections = client.get_collections().collections
        for col in collections:
            info = client.get_collection(col.name)
            print(f"  - {col.name}: {info.points_count} points, {info.vectors_count} vectors")
    else:
        print(" Database initialization completed with errors")
    print(f"{'='*60}\n")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Qdrant vector database for RAGaaS"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:6333",
        help="Qdrant server URL (default: http://localhost:6333)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Qdrant API key (optional)",
    )

    args = parser.parse_args()

    success = init_database(url=args.url, api_key=args.api_key)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
