import os
import asyncio
from typing import List, Dict, Optional, Callable, Any, Union
import logging

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
except Exception:  # pragma: no cover - imported in real runtime
    QdrantClient = None
    models = None
    UnexpectedResponse = Exception

try:
    import openai
except Exception:  # pragma: no cover
    openai = None

logger = logging.getLogger(__name__)

# Constants for vector dimensions and distance
VECTOR_DIM = 1536  # OpenAI ada-002 dimension
DEFAULT_DISTANCE = "Cosine"  # Cosine similarity is standard for embeddings


class VectorStoreService:
    """Simple Vector Store service with pluggable embedder and Qdrant client.

    Design decisions:
    - Methods are async to match FastAPI usage; blocking calls are delegated to
      asyncio.to_thread to avoid blocking the event loop.
    - For testability, you can inject `qdrant_client` and `embedder`.
      `embedder(texts: List[str]) -> List[List[float]]` must return embeddings.
    - By default it will try to create a QdrantClient from env vars:
      QDRANT_HOST, QDRANT_API_KEY.
    - Uses OpenAI ada-002 embeddings by default (1536 dim) if OPENAI_API_KEY
      present. Can inject any embedder that returns float vectors.
    - Creates collections automatically if they don't exist, with proper
      vector size and distance metric (cosine by default).
    """

    def __init__(
        self,
        qdrant_client: Optional[Any] = None,
        embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ):
        self.qdrant_client = qdrant_client
        self.embedder = embedder

        if self.qdrant_client is None:
            host = os.getenv("QDRANT_HOST")
            api_key = os.getenv("QDRANT_API_KEY")
            if QdrantClient is None:
                raise RuntimeError("qdrant-client is not installed")
            # If host not provided, QdrantClient will try local default
            if host:
                self.qdrant_client = QdrantClient(url=host, api_key=api_key)
            else:
                self.qdrant_client = QdrantClient()

        if self.embedder is None:
            if openai is not None and os.getenv("OPENAI_API_KEY"):
                openai.api_key = os.getenv("OPENAI_API_KEY")
                model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

                def _openai_embed(texts: List[str]) -> List[List[float]]:
                    resp = openai.Embedding.create(model=model, input=texts)
                    return [d["embedding"] for d in resp["data"]]

                self.embedder = _openai_embed
            else:
                # Fallback embedder (very small deterministic vector) to allow
                # local runs without external deps. Replace in prod.
                def _fallback_embed(texts: List[str]) -> List[List[float]]:
                    vectors = []
                    for t in texts:
                        # simple hash-based vector of fixed small dim
                        h = abs(hash(t))
                        vectors.append([(h >> (i * 8)) % 256 / 255.0 for i in range(8)])
                    return vectors

                self.embedder = _fallback_embed

    async def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        # allow embedder to be sync; run in threadpool
        if asyncio.iscoroutinefunction(self.embedder):
            return await self.embedder(texts)
        return await asyncio.to_thread(self.embedder, texts)

    async def _ensure_collection_exists(
        self, collection: str, vector_size: Optional[int] = None
    ) -> None:
        """Create collection if it doesn't exist, with proper vector config."""
        try:
            collections = await self.list_collections()
            if collection not in collections:
                if vector_size is None:
                    vector_size = VECTOR_DIM

                if models and hasattr(models, "Distance"):
                    distance = getattr(models.Distance, DEFAULT_DISTANCE)
                else:
                    distance = DEFAULT_DISTANCE

                # Build vector params based on available models
                if models and hasattr(models, "VectorParams"):
                    vector_params = models.VectorParams(
                        size=vector_size,
                        distance=distance
                    )
                else:
                    vector_params = {
                        "size": vector_size,
                        "distance": distance
                    }

                await asyncio.to_thread(
                    self.qdrant_client.recreate_collection,
                    collection_name=collection,
                    vectors_config=vector_params
                )
                logger.info(
                    f"Created collection {collection} "
                    f"(dim={vector_size}, distance={distance})"
                )

        except Exception as e:
            logger.error(f"Error ensuring collection exists: {str(e)}")
            raise

    async def store_documents(
        self,
        documents: List[Dict],
        collection: str = "default",
        batch_size: int = 100
    ) -> None:
        """Store documents in Qdrant.

        documents: list of dicts with at least 'id' and 'text' keys. Additional
                 keys will be stored as payload.
        collection: name of collection to store in
        batch_size: number of documents to process at once
        """
        if not documents:
            return

        # Process in batches to avoid memory issues
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            # Get embeddings for batch
            texts = [d.get("text", "") for d in batch]
            try:
                vectors = await self._embed_texts(texts)
            except Exception as e:
                logger.error(f"Error getting embeddings: {str(e)}")
                raise

            # Ensure collection exists with right dimensions
            await self._ensure_collection_exists(
                collection,
                vector_size=len(vectors[0]) if vectors else None
            )

            # Prepare points
            points = []
            for doc, vec in zip(batch, vectors):
                pid = doc.get("id")
                payload = {k: v for k, v in doc.items() if k != "text"}
                
                # Create point using models if available
                if models and hasattr(models, "PointStruct"):
                    point = models.PointStruct(
                        id=pid,
                        vector=vec,
                        payload=payload
                    )
                else:
                    point = {
                        "id": pid,
                        "vector": vec,
                        "payload": payload
                    }
                points.append(point)

            try:
                # Upsert points
                await asyncio.to_thread(
                    self.qdrant_client.upsert,
                    collection_name=collection,
                    points=points
                )
                logger.info(
                    f"Stored {len(points)} documents in collection {collection}"
                )
            except UnexpectedResponse as e:
                logger.error(f"Qdrant error storing documents: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error storing documents: {str(e)}")
                raise

    async def similarity_search(self, query: str, collection: str = "default", k: int = 5) -> List[Dict]:
        """Return top-k documents as payloads from Qdrant similar to query.
        
        Uses cosine similarity by default (configured when collection is created).
        """
        q_vec = (await self._embed_texts([query]))[0]

        # qdrant search
        try:
            res = await asyncio.to_thread(
                self.qdrant_client.search,
                collection_name=collection,
                query_vector=q_vec,
                limit=k
            )
        except UnexpectedResponse as e:
            if "does not exist" in str(e):
                logger.warning(f"Collection {collection} does not exist")
                return []
            logger.error(f"Qdrant error in similarity search: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            raise

        # Normalize results: expect list of objects with payload attribute or dicts
        out = []
        for item in res:
            if hasattr(item, "payload"):
                out.append(item.payload)
            elif isinstance(item, dict) and "payload" in item:
                out.append(item["payload"])
            else:
                out.append({})
        return out

    async def list_collections(self) -> List[str]:
        """List all available collections in Qdrant."""
        try:
            res = await asyncio.to_thread(self.qdrant_client.get_collections)
        except Exception as e:
            logger.error(f"Error listing collections: {str(e)}")
            raise

        # Handle different response formats
        if hasattr(self.qdrant_client, "get_collections"):
            # qdrant-client returns object with collections attribute
            if hasattr(res, "collections"):
                return [c.name for c in res.collections]
            # Try dict format
            elif isinstance(res, dict) and "collections" in res:
                return [c.get("name") for c in res["collections"]]
            # Fall back to list format
            elif isinstance(res, list):
                return [c.get("name") for c in res]
        return []
