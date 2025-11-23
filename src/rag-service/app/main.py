"""Main FastAPI application for RAG Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import routes
from app.core.config import settings
from app.services.cache_service import CacheService
from app.services.document_processor import DocumentProcessor
from app.services.llm_service import LLMService
from app.services.vector_store import VectorStoreService
from app.utils.logger import get_logger, setup_logging
from app.utils.metrics import app_info

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize services
    routes.vector_store = VectorStoreService()
    routes.llm_service = LLMService()
    routes.doc_processor = DocumentProcessor()
    routes.cache_service = CacheService()

    # Connect to external services
    try:
        await routes.cache_service.connect()
        logger.info("Cache service connected")
    except Exception as e:
        logger.warning(f"Cache service connection failed: {e}")

    # Set app info metrics
    app_info.info({
        "version": settings.app_version,
        "environment": "production" if not settings.debug else "development",
    })

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")
    if routes.cache_service:
        await routes.cache_service.disconnect()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="RAG (Retrieval-Augmented Generation) Service API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Include API routes
    app.include_router(routes.router, prefix="/api/v1", tags=["RAG"])

    # Root health check
    @app.get("/")
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
        }

    @app.get("/health")
    async def health():
        return await routes.health_check()

    @app.get("/ready")
    async def ready():
        return await routes.readiness_check()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
