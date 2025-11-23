import asyncio
from unittest.mock import Mock

import pytest

from app.services.vector_store import VectorStoreService


@pytest.mark.asyncio
async def test_store_documents_calls_qdrant_upsert():
    # Arrange
    mock_qdrant = Mock()
    mock_qdrant.upsert = Mock()

    # embedder returns deterministic vectors
    def fake_embed(texts):
        return [[len(t)] * 4 for t in texts]

    svc = VectorStoreService(qdrant_client=mock_qdrant, embedder=fake_embed)

    docs = [{"id": "1", "text": "hello", "meta": "m"}, {"id": "2", "text": "world"}]

    # Act
    await svc.store_documents(docs, collection="testcol")

    # Assert
    assert mock_qdrant.upsert.called
    called_args, called_kwargs = mock_qdrant.upsert.call_args
    assert called_kwargs.get("collection_name") == "testcol"
    points = called_kwargs.get("points")
    assert len(points) == 2


@pytest.mark.asyncio
async def test_similarity_search_normalizes_payloads():
    mock_qdrant = Mock()

    # search returns list of mock objects with payload
    item1 = Mock()
    item1.payload = {"id": "1", "text": "a"}
    item2 = {"payload": {"id": "2", "text": "b"}}
    mock_qdrant.search = Mock(return_value=[item1, item2])

    def fake_embed(texts):
        return [[1.0]]

    svc = VectorStoreService(qdrant_client=mock_qdrant, embedder=fake_embed)

    res = await svc.similarity_search("query", collection="c", k=2)

    assert isinstance(res, list)
    assert res[0]["id"] == "1"
    assert res[1]["id"] == "2"


def test_list_collections_with_mock():
    mock_qdrant = Mock()
    # simulate get_collections returning an object with collections attribute
    coll = Mock()
    coll.name = "c1"
    obj = Mock()
    obj.collections = [coll]
    mock_qdrant.get_collections = Mock(return_value=obj)

    svc = VectorStoreService(qdrant_client=mock_qdrant, embedder=lambda t: [[0.0]])

    res = asyncio.run(svc.list_collections())
    assert res == ["c1"]
