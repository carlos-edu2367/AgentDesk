"""Tests for memory embeddings module."""
import json
import math
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.memory.embeddings import cosine_similarity, vector_to_json, json_to_vector, get_embedding_for_memory


def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_vector_roundtrip():
    vec = [0.1, 0.2, 0.3, -0.5]
    assert json_to_vector(vector_to_json(vec)) == vec


@pytest.mark.asyncio
async def test_get_embedding_for_memory_success():
    mock_embedding = [0.1, 0.2, 0.3]
    with patch("app.memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [mock_embedding]}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await get_embedding_for_memory("test text")
        assert result == mock_embedding


@pytest.mark.asyncio
async def test_get_embedding_for_memory_failure_returns_none():
    with patch("app.memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        result = await get_embedding_for_memory("test text")
        assert result is None
