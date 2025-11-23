#!/usr/bin/env python3
"""
Qdrant Vector Database Restore Script

Restores collections from a backup created by backup-vector-db.py.

Usage:
    python restore-vector-db.py --backup DIR [--url URL] [--collection NAME]

Environment:
    QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
"""

import os
import sys
import json
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


def load_manifest(backup_dir: Path) -> dict:
    """Load backup manifest."""
    manifest_file = backup_dir / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    with open(manifest_file) as f:
        return json.load(f)


def create_collection(qdrant_url: str, collection_name: str, config: dict):
    """Create a collection with the given configuration."""
    # Extract vector configuration
    params = config.get("config", {}).get("params", {})
    vectors = params.get("vectors", {})

    # Build creation payload
    payload = {
        "vectors": vectors,
    }

    # Add optional configurations
    if "hnsw_config" in config.get("config", {}):
        payload["hnsw_config"] = config["config"]["hnsw_config"]

    if "optimizer_config" in config.get("config", {}):
        payload["optimizers_config"] = config["config"]["optimizer_config"]

    response = requests.put(
        f"{qdrant_url}/collections/{collection_name}",
        json=payload,
        timeout=60
    )

    if response.status_code in [200, 201]:
        return True
    elif response.status_code == 409:
        print(f"    Collection already exists")
        return True
    else:
        print(f"    Error creating collection: {response.status_code} - {response.text}")
        return False


def restore_points(qdrant_url: str, collection_name: str, points_file: Path, batch_size: int = 100):
    """Restore points to a collection."""
    with open(points_file) as f:
        data = json.load(f)

    points = data.get("points", [])
    total = len(points)
    restored = 0

    for i in range(0, total, batch_size):
        batch = points[i:i + batch_size]

        # Format points for upsert
        upsert_points = []
        for p in batch:
            upsert_points.append({
                "id": p["id"],
                "vector": p.get("vector"),
                "payload": p.get("payload", {}),
            })

        response = requests.put(
            f"{qdrant_url}/collections/{collection_name}/points",
            json={"points": upsert_points},
            timeout=120
        )

        if response.status_code != 200:
            print(f"    Error at batch {i}: {response.status_code} - {response.text}")
            return restored

        restored += len(batch)
        print(f"    Restored {restored}/{total} points...", end="\r")

    print(f"    Restored {restored}/{total} points    ")
    return restored


def restore_collection(qdrant_url: str, backup_dir: Path, collection_info: dict) -> dict:
    """Restore a single collection."""
    name = collection_info["collection"]
    config_file = Path(collection_info["config_file"])
    points_file = Path(collection_info["points_file"])

    # Use relative paths from backup dir if absolute paths don't exist
    if not config_file.exists():
        config_file = backup_dir / f"{name}_config.json"
    if not points_file.exists():
        points_file = backup_dir / f"{name}_points.json"

    print(f"\nRestoring collection: {name}")

    # Load config
    with open(config_file) as f:
        config = json.load(f)

    # Create collection
    print(f"  Creating collection...")
    if not create_collection(qdrant_url, name, config):
        return {"collection": name, "status": "failed", "points": 0}

    # Restore points
    print(f"  Restoring points...")
    points_restored = restore_points(qdrant_url, name, points_file)

    return {
        "collection": name,
        "status": "success",
        "points": points_restored,
    }


def main():
    parser = argparse.ArgumentParser(description="Restore Qdrant vector database")
    parser.add_argument("--backup", "-b", required=True,
                        help="Backup directory to restore from")
    parser.add_argument("--url", default=os.getenv("QDRANT_URL", "http://localhost:6333"),
                        help="Qdrant server URL")
    parser.add_argument("--collection", "-c", default=None,
                        help="Specific collection to restore (default: all)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force restore even if collection exists")
    args = parser.parse_args()

    backup_dir = Path(args.backup)
    if not backup_dir.exists():
        print(f"Error: Backup directory not found: {backup_dir}")
        sys.exit(1)

    print("=== Qdrant Vector Database Restore ===")
    print(f"Backup: {backup_dir}")
    print(f"URL: {args.url}")
    print()

    try:
        # Load manifest
        manifest = load_manifest(backup_dir)
        print(f"Backup timestamp: {manifest.get('timestamp', 'unknown')}")

        collections = manifest.get("collections", [])
        if args.collection:
            collections = [c for c in collections if c["collection"] == args.collection]
            if not collections:
                print(f"Error: Collection '{args.collection}' not found in backup")
                sys.exit(1)

        print(f"Collections to restore: {len(collections)}")

        # Restore each collection
        results = []
        for col_info in collections:
            result = restore_collection(args.url, backup_dir, col_info)
            results.append(result)

        # Summary
        print("\n=== Restore Complete ===")
        for r in results:
            status = "OK" if r["status"] == "success" else "FAILED"
            print(f"  {r['collection']}: {status} ({r['points']} points)")

        total_points = sum(r["points"] for r in results)
        print(f"\nTotal points restored: {total_points}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Qdrant at {args.url}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
