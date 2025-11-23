#!/usr/bin/env python3
"""
Initialize MinIO object storage with default buckets for RAGaaS.

This script creates the necessary buckets for document storage.
Run this after deploying MinIO for the first time.

Usage:
    python init-minio.py --endpoint localhost:9000 --access-key minio --secret-key minio123
"""

import argparse
import sys

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    print("Error: minio not installed. Run: pip install minio")
    sys.exit(1)


# Default bucket configurations
DEFAULT_BUCKETS = [
    {
        "name": "ragaas-documents",
        "description": "Raw uploaded documents (PDF, DOCX, etc.)",
    },
    {
        "name": "ragaas-chunks",
        "description": "Processed document chunks (JSON)",
    },
    {
        "name": "ragaas-embeddings",
        "description": "Cached embeddings (optional)",
    },
]


def create_bucket(client: Minio, name: str, description: str = "") -> bool:
    """Create a bucket if it doesn't exist."""
    try:
        if client.bucket_exists(name):
            print(f"  Bucket '{name}' already exists, skipping...")
            return True

        client.make_bucket(name)
        print(f"✓ Created bucket '{name}' - {description}")
        return True

    except S3Error as e:
        print(f"✗ Failed to create bucket '{name}': {e}")
        return False


def init_storage(
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool = False,
) -> bool:
    """Initialize MinIO with default buckets."""
    print(f"\n{'='*60}")
    print("RAGaaS MinIO Storage Initialization")
    print(f"{'='*60}")
    print(f"MinIO Endpoint: {endpoint}")
    print(f"Secure: {secure}")
    print()

    # Create client
    try:
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        # Test connection
        client.list_buckets()
        print("✓ Connected to MinIO")
    except Exception as e:
        print(f"✗ Failed to connect to MinIO: {e}")
        return False

    # Create buckets
    print("\nCreating buckets...")
    success = True
    for config in DEFAULT_BUCKETS:
        if not create_bucket(
            client=client,
            name=config["name"],
            description=config.get("description", ""),
        ):
            success = False

    # Print summary
    print(f"\n{'='*60}")
    if success:
        print("✓ Storage initialization completed successfully")

        # List all buckets
        print("\nCurrent buckets:")
        for bucket in client.list_buckets():
            print(f"  - {bucket.name} (created: {bucket.creation_date})")
    else:
        print("✗ Storage initialization completed with errors")
    print(f"{'='*60}\n")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Initialize MinIO storage for RAGaaS"
    )
    parser.add_argument(
        "--endpoint",
        default="localhost:9000",
        help="MinIO endpoint (default: localhost:9000)",
    )
    parser.add_argument(
        "--access-key",
        default="minio",
        help="MinIO access key (default: minio)",
    )
    parser.add_argument(
        "--secret-key",
        default="minio123",
        help="MinIO secret key (default: minio123)",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        help="Use HTTPS (default: False)",
    )

    args = parser.parse_args()

    success = init_storage(
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        secure=args.secure,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
