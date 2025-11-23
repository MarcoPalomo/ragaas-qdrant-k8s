#!/usr/bin/env python3
"""
Qdrant Vector Database Backup Script

Exports all collections from Qdrant to JSON files with full vector data.
Supports pagination for large collections.

Usage:
    python backup-vector-db.py [--url URL] [--output DIR] [--collection NAME]

Environment:
    QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


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


def export_collection(qdrant_url: str, collection_name: str, output_dir: Path, batch_size: int = 100) -> dict:
    """Export all points from a collection with pagination."""
    info = get_collection_info(qdrant_url, collection_name)
    total_points = info.get("points_count", 0)

    print(f"  Collection: {collection_name}")
    print(f"  Points: {total_points}")
    print(f"  Vector size: {info.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'N/A')}")

    # Save collection config
    config_file = output_dir / f"{collection_name}_config.json"
    with open(config_file, "w") as f:
        json.dump(info, f, indent=2)

    # Export points with pagination using scroll
    points = []
    offset = None
    exported = 0

    while True:
        payload = {
            "limit": batch_size,
            "with_payload": True,
            "with_vector": True,
        }
        if offset:
            payload["offset"] = offset

        response = requests.post(
            f"{qdrant_url}/collections/{collection_name}/points/scroll",
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()["result"]

        batch_points = result.get("points", [])
        if not batch_points:
            break

        points.extend(batch_points)
        exported += len(batch_points)
        offset = result.get("next_page_offset")

        print(f"  Exported {exported}/{total_points} points...", end="\r")

        if not offset:
            break

    print(f"  Exported {exported}/{total_points} points    ")

    # Save points
    points_file = output_dir / f"{collection_name}_points.json"
    with open(points_file, "w") as f:
        json.dump({"points": points}, f)

    return {
        "collection": collection_name,
        "points_count": exported,
        "config_file": str(config_file),
        "points_file": str(points_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Backup Qdrant vector database")
    parser.add_argument("--url", default=os.getenv("QDRANT_URL", "http://localhost:6333"),
                        help="Qdrant server URL")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: data/backups/TIMESTAMP)")
    parser.add_argument("--collection", "-c", default=None,
                        help="Specific collection to backup (default: all)")
    args = parser.parse_args()

    # Setup output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(__file__).parent.parent.parent / "data" / "backups" / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Qdrant Vector Database Backup ===")
    print(f"URL: {args.url}")
    print(f"Output: {output_dir}")
    print()

    try:
        # Get collections
        collections = get_collections(args.url)
        if args.collection:
            collections = [c for c in collections if c["name"] == args.collection]
            if not collections:
                print(f"Error: Collection '{args.collection}' not found")
                sys.exit(1)

        print(f"Found {len(collections)} collection(s)")
        print()

        # Export each collection
        results = []
        for col in collections:
            result = export_collection(args.url, col["name"], output_dir)
            results.append(result)
            print()

        # Save manifest
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "qdrant_url": args.url,
            "collections": results,
        }
        manifest_file = output_dir / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        print("=== Backup Complete ===")
        print(f"Location: {output_dir}")
        print(f"Collections: {len(results)}")
        total_points = sum(r["points_count"] for r in results)
        print(f"Total points: {total_points}")

    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Qdrant at {args.url}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
