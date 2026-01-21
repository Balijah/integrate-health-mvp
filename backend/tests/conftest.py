"""
Pytest configuration and fixtures.

Provides test database setup and common fixtures.
"""

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest.fixture
async def client():
    """
    Async HTTP client for testing API endpoints.

    Yields:
        AsyncClient: Test client for making requests
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
