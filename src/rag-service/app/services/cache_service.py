"""Redis cache service for caching query results and embeddings."""

import hashlib
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """Service for caching with Redis."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client (for testing)
        """
        self._client = redis_client
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_connection_url,
                encoding="utf-8",
                decode_responses=True,
            )
        try:
            await self._client.ping()
            self._connected = True
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self._connected:
            return None

        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        try:
            ttl = ttl or settings.redis_cache_ttl
            await self._client.setex(
                key,
                ttl,
                json.dumps(value),
            )
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if not self._connected:
            return False

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "query:*")

        Returns:
            Number of keys deleted
        """
        if not self._connected:
            return 0

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._client.delete(*keys)

            return len(keys)
        except Exception as e:
            logger.warning(f"Cache clear pattern error: {e}")
            return 0

    @staticmethod
    def generate_query_key(
        query: str,
        collection: str,
        top_k: int,
    ) -> str:
        """
        Generate cache key for a query.

        Args:
            query: Query text
            collection: Collection name
            top_k: Number of results

        Returns:
            Cache key
        """
        content = f"{query}:{collection}:{top_k}"
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"query:{collection}:{hash_value}"

    @staticmethod
    def generate_embedding_key(text: str) -> str:
        """
        Generate cache key for an embedding.

        Args:
            text: Text to embed

        Returns:
            Cache key
        """
        hash_value = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"embedding:{hash_value}"

    async def get_cached_query(
        self,
        query: str,
        collection: str,
        top_k: int,
    ) -> Optional[dict]:
        """
        Get cached query result.

        Args:
            query: Query text
            collection: Collection name
            top_k: Number of results

        Returns:
            Cached result or None
        """
        key = self.generate_query_key(query, collection, top_k)
        return await self.get(key)

    async def cache_query(
        self,
        query: str,
        collection: str,
        top_k: int,
        result: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache a query result.

        Args:
            query: Query text
            collection: Collection name
            top_k: Number of results
            result: Result to cache
            ttl: Time to live

        Returns:
            True if cached successfully
        """
        key = self.generate_query_key(query, collection, top_k)
        return await self.set(key, result, ttl)

    async def invalidate_collection(self, collection: str) -> int:
        """
        Invalidate all cached queries for a collection.

        Args:
            collection: Collection name

        Returns:
            Number of keys invalidated
        """
        return await self.clear_pattern(f"query:{collection}:*")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected
