#!/bin/bash
set -e

# Wait for dependencies
echo "Waiting for Qdrant..."
while ! nc -z ${QDRANT_HOST:-qdrant} ${QDRANT_PORT:-6333}; do
    sleep 1
done
echo "Qdrant is ready"

echo "Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
    sleep 1
done
echo "Redis is ready"

# Run migrations or setup if needed
# python -m app.scripts.setup

# Start the application
exec "$@"
