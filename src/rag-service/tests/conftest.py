"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {
            "content": "This is the first test document about Python programming.",
            "metadata": {"source": "test1.txt", "category": "programming"},
        },
        {
            "content": "This document discusses machine learning and AI concepts.",
            "metadata": {"source": "test2.txt", "category": "ml"},
        },
        {
            "content": "RAG systems combine retrieval with language generation.",
            "metadata": {"source": "test3.txt", "category": "ai"},
        },
    ]


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return {
        "question": "What is RAG?",
        "collection": "test_collection",
        "top_k": 5,
        "temperature": 0.7,
    }


@pytest.fixture
def mock_embedding():
    """Mock embedding function."""
    def embed(texts):
        return [[0.1] * 1536 for _ in texts]
    return embed
