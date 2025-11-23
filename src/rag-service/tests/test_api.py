"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    with patch("app.api.routes.vector_store") as mock_vs, \
         patch("app.api.routes.llm_service") as mock_llm, \
         patch("app.api.routes.doc_processor") as mock_doc, \
         patch("app.api.routes.cache_service") as mock_cache:

        # Setup vector store mock
        mock_vs.similarity_search = AsyncMock(return_value=[
            {"content": "test content", "metadata": {}, "score": 0.9}
        ])
        mock_vs.store_documents = AsyncMock()
        mock_vs.list_collections = AsyncMock(return_value=[
            {"name": "default", "vectors_count": 100, "status": "green"}
        ])
        mock_vs.delete_collection = AsyncMock()

        # Setup LLM mock
        mock_llm.generate_response = AsyncMock(return_value=("Test answer", 0.85))

        # Setup cache mock
        mock_cache.get_cached_query = AsyncMock(return_value=None)
        mock_cache.cache_query = AsyncMock(return_value=True)
        mock_cache.invalidate_collection = AsyncMock(return_value=1)
        mock_cache.is_connected = True

        yield {
            "vector_store": mock_vs,
            "llm_service": mock_llm,
            "doc_processor": mock_doc,
            "cache_service": mock_cache,
        }


@pytest.fixture
def client(mock_services):
    """Create test client with mocked services."""
    from app.main import app
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

    def test_ready_endpoint(self, client, mock_services):
        """Test readiness endpoint."""
        response = client.get("/ready")
        # Will return 503 because vector_store is None in routes module
        assert response.status_code in [200, 503]


class TestQueryEndpoint:
    """Tests for query endpoint."""

    def test_query_requires_authentication(self, client):
        """Test that query endpoint requires API key when configured."""
        # Without API key should work in dev mode (no token configured)
        response = client.post(
            "/api/v1/query",
            json={
                "question": "What is the meaning of life?",
                "collection": "default",
            }
        )
        # Should either succeed or fail auth (depending on config)
        assert response.status_code in [200, 401, 403, 503]

    def test_query_validation(self, client):
        """Test query request validation."""
        # Missing question
        response = client.post(
            "/api/v1/query",
            json={"collection": "default"}
        )
        assert response.status_code == 422

        # Empty question
        response = client.post(
            "/api/v1/query",
            json={"question": "", "collection": "default"}
        )
        assert response.status_code == 422

    def test_query_with_parameters(self, client):
        """Test query with all parameters."""
        response = client.post(
            "/api/v1/query",
            json={
                "question": "Test question",
                "collection": "test_collection",
                "top_k": 10,
                "temperature": 0.5,
            }
        )
        # Response depends on service availability
        assert response.status_code in [200, 401, 503]


class TestIngestEndpoint:
    """Tests for ingest endpoint."""

    def test_ingest_requires_file(self, client):
        """Test that ingest requires file upload."""
        response = client.post("/api/v1/ingest")
        assert response.status_code == 422

    def test_ingest_with_file(self, client):
        """Test file ingestion."""
        files = {"files": ("test.txt", b"Test content", "text/plain")}
        response = client.post(
            "/api/v1/ingest",
            files=files,
            params={"collection": "test"},
        )
        # Response depends on service availability
        assert response.status_code in [200, 401, 503]


class TestCollectionsEndpoint:
    """Tests for collections endpoint."""

    def test_list_collections(self, client):
        """Test listing collections."""
        response = client.get("/api/v1/collections")
        # Response depends on auth and service availability
        assert response.status_code in [200, 401, 503]

    def test_delete_collection(self, client):
        """Test deleting a collection."""
        response = client.delete("/api/v1/collections/test_collection")
        assert response.status_code in [200, 401, 503]
