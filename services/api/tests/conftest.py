"""Shared test fixtures for API service."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from src.app import app
from src.config import settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    mock = AsyncMock(spec=Redis)
    mock.ping.return_value = True
    return mock


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock OpenAI client."""
    mock = AsyncMock()
    
    # Mock models.list response
    mock_models = MagicMock()
    mock_models.data = [MagicMock(id="test-model")]
    mock.models.list.return_value = mock_models
    
    # Mock chat completions response
    mock_response = MagicMock()
    mock_response.id = "chatcmpl-test"
    mock_response.object = "chat.completion"
    mock_response.created = 1234567890
    mock_response.model = "test-model"
    mock_response.choices = [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Test response"},
            "finish_reason": "stop",
        }
    ]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    
    mock.chat.completions.create.return_value = mock_response
    
    return mock


@pytest.fixture
async def setup_clients(
    mock_redis: AsyncMock, mock_openai_client: AsyncMock
) -> AsyncGenerator[None, None]:
    """Setup mock clients for testing."""
    import src.app
    
    # Store original clients
    original_redis = src.app.redis_client
    original_openai = src.app.openai_client
    
    # Set mock clients
    src.app.redis_client = mock_redis
    src.app.openai_client = mock_openai_client
    
    yield
    
    # Restore original clients
    src.app.redis_client = original_redis
    src.app.openai_client = original_openai


@pytest.fixture
def sample_chat_request() -> dict:
    """Sample chat request payload."""
    return {
        "model": "test-model",
        "messages": [
            {"role": "user", "content": "Hello, world!"}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture
def sample_chat_response() -> dict:
    """Sample chat response payload."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Test response"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
