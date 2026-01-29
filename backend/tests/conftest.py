"""
Pytest configuration and fixtures.

Provides test database setup and common fixtures.
"""

import asyncio
import os
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.visit import Visit
from app.models.note import Note
from app.services.auth import hash_password, create_access_token


# Use PostgreSQL for testing (same as dev but with test_ prefix tables)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/integrate_health_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up by truncating tables instead of dropping to avoid circular dependency issues
    async with engine.begin() as conn:
        # Truncate in reverse dependency order
        await conn.execute(text("TRUNCATE TABLE notes CASCADE"))
        await conn.execute(text("TRUNCATE TABLE transcription_sessions CASCADE"))
        await conn.execute(text("TRUNCATE TABLE visits CASCADE"))
        await conn.execute(text("TRUNCATE TABLE users CASCADE"))

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing API endpoints.

    Overrides the database dependency to use test database.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_token(test_user: User) -> str:
    """Create access token for test user."""
    return create_access_token(str(test_user.id))


@pytest_asyncio.fixture
async def auth_headers(test_user_token: str) -> dict:
    """Create authorization headers."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest_asyncio.fixture
async def test_visit(db_session: AsyncSession, test_user: User) -> Visit:
    """Create a test visit."""
    from datetime import datetime

    visit = Visit(
        id=uuid.uuid4(),
        user_id=test_user.id,
        patient_ref="PT-TEST-001",
        visit_date=datetime.utcnow(),
        chief_complaint="Test complaint",
        transcription_status="pending",
    )
    db_session.add(visit)
    await db_session.commit()
    await db_session.refresh(visit)
    return visit


@pytest_asyncio.fixture
async def test_visit_with_transcript(db_session: AsyncSession, test_user: User) -> Visit:
    """Create a test visit with transcript."""
    from datetime import datetime

    visit = Visit(
        id=uuid.uuid4(),
        user_id=test_user.id,
        patient_ref="PT-TEST-002",
        visit_date=datetime.utcnow(),
        chief_complaint="Fatigue and brain fog",
        transcript="Doctor: Hello, how are you feeling today? Patient: I've been experiencing fatigue for the past few weeks.",
        transcription_status="completed",
        audio_duration_seconds=120,
    )
    db_session.add(visit)
    await db_session.commit()
    await db_session.refresh(visit)
    return visit
