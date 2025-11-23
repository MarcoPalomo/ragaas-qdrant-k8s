"""API routes for the RAG service."""

import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.models import (
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceDocument,
)
from app.core.config import settings
from app.core.security import verify_api_key
from app.services.cache_service import CacheService
from app.services.document_processor import Document, DocumentProcessor
from app.services.llm_service import LLMService
from app.services.queue_service import QueueService
from app.services.vector_store import VectorStoreService
from app.utils.logger import get_logger
from app.utils.metrics import record_query, record_vector_search, update_health

logger = get_logger(__name__)

router = APIRouter()

# Service instances (initialized in lifespan)
vector_store: Optional[VectorStoreService] = None
llm_service: Optional[LLMService] = None
doc_processor: Optional[DocumentProcessor] = None
cache_service: Optional[CacheService] = None
queue_service: Optional[QueueService] = None


def get_vector_store() -> VectorStoreService:
    """Get vector store service."""
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    return vector_store


def get_llm_service() -> LLMService:
    """Get LLM service."""
    if llm_service is None:
        raise HTTPException(status_code=503, detail="LLM service not initialized")
    return llm_service


def get_doc_processor() -> DocumentProcessor:
    """Get document processor."""
    if doc_processor is None:
        raise HTTPException(status_code=503, detail="Document processor not initialized")
    return doc_processor


def get_cache_service() -> CacheService:
    """Get cache service."""
    if cache_service is None:
        raise HTTPException(status_code=503, detail="Cache service not initialized")
    return cache_service


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    _api_key: str = Depends(verify_api_key),
    vs: VectorStoreService = Depends(get_vector_store),
    llm: LLMService = Depends(get_llm_service),
    cache: CacheService = Depends(get_cache_service),
) -> QueryResponse:
    """
    Query the RAG system.

    Performs similarity search on the vector store and generates
    a response using the LLM with retrieved context.
    """
    start_time = time.time()

    try:
        # Check cache first
        cached = await cache.get_cached_query(
            request.question, request.collection, request.top_k
        )
        if cached:
            logger.info("Cache hit for query")
            return QueryResponse(**cached)

        # Similarity search
        search_start = time.time()
        results = await vs.similarity_search(
            query=request.question,
            collection=request.collection,
            k=request.top_k,
        )
        search_duration = time.time() - search_start
        record_vector_search(request.collection, True, search_duration)

        # Prepare context and sources
        context = [r["content"] for r in results]
        sources = [
            SourceDocument(
                content=r["content"][:500],  # Truncate for response
                metadata=r.get("metadata", {}),
                score=r.get("score", 0.0),
            )
            for r in results
        ]

        # Generate response
        answer, confidence = await llm.generate_response(
            query=request.question,
            context=context,
            temperature=request.temperature,
        )

        response = QueryResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
        )

        # Cache result
        await cache.cache_query(
            request.question,
            request.collection,
            request.top_k,
            response.model_dump(),
        )

        duration = time.time() - start_time
        record_query(request.collection, True, duration, confidence)

        return response

    except Exception as e:
        duration = time.time() - start_time
        record_query(request.collection, False, duration, 0.0)
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_documents_stream(
    request: QueryRequest,
    _api_key: str = Depends(verify_api_key),
    vs: VectorStoreService = Depends(get_vector_store),
    llm: LLMService = Depends(get_llm_service),
):
    """
    Query the RAG system with streaming response.

    Returns a streaming response that sends chunks as they are generated.
    """
    try:
        # Similarity search
        results = await vs.similarity_search(
            query=request.question,
            collection=request.collection,
            k=request.top_k,
        )

        context = [r["content"] for r in results]

        async def generate():
            async for chunk in llm.generate_streaming_response(
                query=request.question,
                context=context,
                temperature=request.temperature,
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Streaming query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    collection: str = Query(default="default"),
    async_processing: bool = Query(default=False),
    _api_key: str = Depends(verify_api_key),
    vs: VectorStoreService = Depends(get_vector_store),
    processor: DocumentProcessor = Depends(get_doc_processor),
    cache: CacheService = Depends(get_cache_service),
) -> IngestResponse:
    """
    Ingest documents into a collection.

    Processes uploaded files, chunks them, generates embeddings,
    and stores them in the vector database.
    """
    try:
        total_chunks = 0

        for file in files:
            # Read file content
            content = await file.read()
            text_content = content.decode("utf-8", errors="ignore")

            # Create document
            metadata = processor.extract_metadata(file.filename or "unknown", text_content)
            doc = Document(content=text_content, metadata=metadata)

            # Process into chunks
            chunks = processor.process_document(doc)
            total_chunks += len(chunks)

            # Store in vector database
            documents = [
                {"content": chunk.content, "metadata": chunk.metadata}
                for chunk in chunks
            ]
            await vs.store_documents(documents, collection)

        # Invalidate cache for this collection
        await cache.invalidate_collection(collection)

        return IngestResponse(
            message=f"Successfully processed {len(files)} file(s)",
            collection=collection,
            documents_processed=len(files),
            chunks_created=total_chunks,
        )

    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections(
    _api_key: str = Depends(verify_api_key),
    vs: VectorStoreService = Depends(get_vector_store),
) -> CollectionsResponse:
    """List all available collections."""
    try:
        collections = await vs.list_collections()
        collection_infos = [
            CollectionInfo(
                name=c.get("name", "unknown"),
                vectors_count=c.get("vectors_count", 0),
                status=c.get("status", "unknown"),
            )
            for c in collections
        ]
        return CollectionsResponse(collections=collection_infos)

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}")
async def delete_collection(
    collection_name: str,
    _api_key: str = Depends(verify_api_key),
    vs: VectorStoreService = Depends(get_vector_store),
    cache: CacheService = Depends(get_cache_service),
):
    """Delete a collection."""
    try:
        await vs.delete_collection(collection_name)
        await cache.invalidate_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted"}

    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    components = {
        "api": True,
        "vector_store": vector_store is not None,
        "llm": llm_service is not None,
        "cache": cache_service is not None and cache_service.is_connected,
    }

    # Update metrics
    for component, healthy in components.items():
        update_health(component, healthy)

    all_healthy = all(components.values())
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=settings.app_version,
        components=components,
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Not ready")
    return {"status": "ready"}
