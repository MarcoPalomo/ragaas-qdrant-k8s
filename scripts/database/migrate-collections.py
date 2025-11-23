#!/usr/bin/env python3
"""
Qdrant Collection Migration Script

Migrates or updates Qdrant collection configurations.
Supports schema updates, optimizer tuning, and index creation.

Usage:
    python migrate-collections.py [--url URL] [--collection NAME] [--action ACTION]

Actions:
    check     - Check current collection configurations
    optimize  - Apply optimizer configurations
    index     - Create payload index (requires --field)

Environment:
    QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
"""

import os
import sys
import argparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


# Default optimizer configuration for production
DEFAULT_OPTIMIZER_CONFIG = {
    "default_segment_number": 5,
    "max_segment_size": 200000,
    "memmap_threshold": 50000,
    "indexing_threshold": 20000,
    "flush_interval_sec": 5,
    "max_optimization_threads": 2,
}


def get_collections(qdrant_url: str) -> list:
    """Get list of all collections."""
    response = requests.get(f"{qdrant_url}/collections", timeout=30)
    response.raise_for_status()
    return response.json()["result"]["collections"]


def get_collection_info(qdrant_url: str, collection_name: str) -> dict:
    """Get collection configuration and stats."""
    response = requests.get(f"{qdrant_url}/collections/{collection_name}", timeout=30)
    response.raise_for_status()
    return response.json()["result"]


def check_collections(qdrant_url: str, collection_name: str = None):
    """Check and display collection configurations."""
    collections = get_collections(qdrant_url)

    if collection_name:
        collections = [c for c in collections if c["name"] == collection_name]

    print(f"Found {len(collections)} collection(s)\n")

    for col in collections:
        name = col["name"]
        info = get_collection_info(qdrant_url, name)

        print(f"Collection: {name}")
        print(f"  Status: {info.get('status', 'unknown')}")
        print(f"  Points: {info.get('points_count', 0)}")
        print(f"  Segments: {info.get('segments_count', 0)}")

        config = info.get("config", {})
        params = config.get("params", {})

        # Vector configuration
        vectors = params.get("vectors", {})
        if isinstance(vectors, dict) and "size" in vectors:
            print(f"  Vector size: {vectors.get('size')}")
            print(f"  Distance: {vectors.get('distance')}")
        elif isinstance(vectors, dict):
            for vname, vconfig in vectors.items():
                print(f"  Vector '{vname}': size={vconfig.get('size')}, distance={vconfig.get('distance')}")

        # HNSW configuration
        hnsw = config.get("hnsw_config", {})
        print(f"  HNSW: m={hnsw.get('m')}, ef_construct={hnsw.get('ef_construct')}")

        # Optimizer configuration
        optimizer = config.get("optimizer_config", {})
        print(f"  Optimizer: segment_number={optimizer.get('default_segment_number')}")

        print()


def apply_optimizer_config(qdrant_url: str, collection_name: str = None, config: dict = None):
    """Apply optimizer configuration to collections."""
    if config is None:
        config = DEFAULT_OPTIMIZER_CONFIG

    collections = get_collections(qdrant_url)
    if collection_name:
        collections = [c for c in collections if c["name"] == collection_name]

    print(f"Applying optimizer config to {len(collections)} collection(s)\n")

    for col in collections:
        name = col["name"]
        print(f"Updating {name}...")

        response = requests.patch(
            f"{qdrant_url}/collections/{name}",
            json={"optimizer_config": config},
            timeout=30
        )

        if response.status_code == 200:
            print(f"  OK - Optimizer config updated")
        else:
            print(f"  Error: {response.status_code} - {response.text}")

    print("\nOptimizer configuration applied")


def create_payload_index(qdrant_url: str, collection_name: str, field_name: str, field_type: str = "keyword"):
    """Create a payload index for faster filtering."""
    print(f"Creating payload index on {collection_name}.{field_name} ({field_type})...")

    schema_types = {
        "keyword": {"type": "keyword"},
        "integer": {"type": "integer"},
        "float": {"type": "float"},
        "bool": {"type": "bool"},
        "datetime": {"type": "datetime"},
        "text": {"type": "text"},
    }

    if field_type not in schema_types:
        print(f"Error: Invalid field type '{field_type}'")
        print(f"Valid types: {', '.join(schema_types.keys())}")
        return

    response = requests.put(
        f"{qdrant_url}/collections/{collection_name}/index",
        json={
            "field_name": field_name,
            "field_schema": schema_types[field_type],
        },
        timeout=60
    )

    if response.status_code == 200:
        print(f"  OK - Index created")
    else:
        print(f"  Error: {response.status_code} - {response.text}")


def main():
    parser = argparse.ArgumentParser(description="Migrate Qdrant collections")
    parser.add_argument("--url", default=os.getenv("QDRANT_URL", "http://localhost:6333"),
                        help="Qdrant server URL")
    parser.add_argument("--collection", "-c", default=None,
                        help="Specific collection (default: all)")
    parser.add_argument("--action", "-a", default="check",
                        choices=["check", "optimize", "index"],
                        help="Action to perform")
    parser.add_argument("--field", default=None,
                        help="Field name for index creation")
    parser.add_argument("--field-type", default="keyword",
                        help="Field type for index (keyword, integer, float, bool, datetime, text)")
    args = parser.parse_args()

    print("=== Qdrant Collection Migration ===")
    print(f"URL: {args.url}")
    print(f"Action: {args.action}")
    print()

    try:
        if args.action == "check":
            check_collections(args.url, args.collection)

        elif args.action == "optimize":
            apply_optimizer_config(args.url, args.collection)

        elif args.action == "index":
            if not args.collection or not args.field:
                print("Error: --collection and --field required for index action")
                sys.exit(1)
            create_payload_index(args.url, args.collection, args.field, args.field_type)

    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Qdrant at {args.url}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()