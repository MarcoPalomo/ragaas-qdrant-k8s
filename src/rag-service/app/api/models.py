"""Pydantic models for API requests and responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for RAG queries."""

    question: str = Field(..., description="User's question", min_length=1)
    collection: str = Field(default="default", description="Collection to query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="LLM temperature"
    )


class SourceDocument(BaseModel):
    """Source document with content and metadata."""

    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")


class QueryResponse(BaseModel):
    """Response model for RAG queries."""

    answer: str = Field(..., description="Generated answer")
    sources: list[SourceDocument] = Field(default_factory=list, description="Source documents")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class IngestRequest(BaseModel):
    """Request model for document ingestion."""

    collection: str = Field(default="default", description="Target collection")
    chunk_size: Optional[int] = Field(None, ge=100, le=10000, description="Chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000, description="Chunk overlap")


class IngestResponse(BaseModel):
    """Response model for document ingestion."""

    message: str = Field(..., description="Status message")
    collection: str = Field(..., description="Target collection")
    documents_processed: int = Field(..., ge=0, description="Number of documents processed")
    chunks_created: int = Field(default=0, ge=0, description="Number of chunks created")
    task_id: Optional[str] = Field(None, description="Async task ID if queued")


class CollectionInfo(BaseModel):
    """Information about a collection."""

    name: str = Field(..., description="Collection name")
    vectors_count: int = Field(..., ge=0, description="Number of vectors")
    status: str = Field(..., description="Collection status")


class CollectionsResponse(BaseModel):
    """Response model for listing collections."""

    collections: list[CollectionInfo] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Service version")
    components: dict[str, bool] = Field(default_factory=dict, description="Component health")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")


class TaskStatusResponse(BaseModel):
    """Task status response."""

    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress percentage")
    result: Optional[dict] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
