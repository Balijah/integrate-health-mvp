"""Safety and repeatability tests for the isolated synthetic demo."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.demo import DEMO_EXTERNAL_SERVICES_DISABLED
from app.models.note import Note
from app.models.user import User
from app.models.visit import Visit
from app.services.auth import hash_password
from scripts import seed_demo


def test_demo_configuration_rejects_production() -> None:
    with pytest.raises(ValueError, match="may only be enabled"):
        Settings(demo_mode=True, environment="production")


def test_demo_configuration_rejects_external_services() -> None:
    with pytest.raises(ValueError, match="external service credentials"):
        Settings(demo_mode=True, environment="demo", deepgram_api_key="configured")

    with pytest.raises(ValueError, match="STORAGE_MODE=local"):
        Settings(demo_mode=True, environment="demo", storage_mode="s3")

    with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
        Settings(demo_mode=True, environment="demo", sqs_queue_url="configured")


def test_demo_credentials_are_required_and_password_is_long_enough(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_USER_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_USER_NAME", raising=False)
    with pytest.raises(RuntimeError, match="are required"):
        seed_demo.load_demo_credentials()

    monkeypatch.setenv("DEMO_USER_EMAIL", "demo.provider@example.com")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "too-short")
    monkeypatch.setenv("DEMO_USER_NAME", "Dr. Demo Provider")
    with pytest.raises(RuntimeError, match="at least 12 characters"):
        seed_demo.load_demo_credentials()


@pytest.mark.asyncio
async def test_demo_external_endpoints_are_blocked(client, auth_headers, test_visit, monkeypatch) -> None:
    monkeypatch.setattr("app.demo.get_settings", lambda: SimpleNamespace(demo_mode=True))
    monkeypatch.setattr("boto3.client", lambda *_args, **_kwargs: pytest.fail("AWS client was called"))
    monkeypatch.setattr(
        "app.api.transcription.get_live_transcription_service",
        lambda: pytest.fail("Deepgram live service was called"),
    )
    endpoints = [
        ("post", f"/api/v1/visits/{test_visit.id}/transcribe", None),
        ("post", f"/api/v1/visits/{test_visit.id}/transcription/retry", None),
        ("post", f"/api/v1/visits/{test_visit.id}/transcription/start-live", {}),
        ("post", f"/api/v1/visits/{test_visit.id}/notes/generate", {}),
        ("post", f"/api/v1/visits/{test_visit.id}/summary/send", {"email": "nobody@example.com", "summary": "Synthetic"}),
        ("post", "/api/v1/support", {"message": "Synthetic support request"}),
        ("post", "/api/v1/auth/forgot-password", {"email": "demo.provider@example.com"}),
    ]

    for method, url, body in endpoints:
        response = await client.request(method, url, headers=auth_headers, json=body)
        assert response.status_code == 403
        assert response.json()["detail"] == DEMO_EXTERNAL_SERVICES_DISABLED

    response = await client.post(
        f"/api/v1/visits/{test_visit.id}/audio",
        headers=auth_headers,
        files={"file": ("recording.webm", b"not-read-in-demo", "audio/webm")},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == DEMO_EXTERNAL_SERVICES_DISABLED


@pytest.mark.asyncio
async def test_seed_reset_is_idempotent_and_preserves_other_users(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(seed_demo, "get_settings", lambda: SimpleNamespace(demo_mode=True))
    monkeypatch.setenv("DEMO_USER_EMAIL", "demo.provider@example.com")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "local-demo-password")
    monkeypatch.setenv("DEMO_USER_NAME", "Dr. Demo Provider")
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        other = User(
            id=uuid.uuid4(),
            email="other@example.com",
            full_name="Other Provider",
            hashed_password=hash_password("another-password"),
        )
        session.add(other)
        await session.flush()
        session.add(Visit(
            user_id=other.id,
            patient_ref="OTHER-001",
            visit_date=datetime.now(timezone.utc),
            transcription_status="pending",
        ))
        await session.commit()

    await seed_demo.reset_demo(factory)
    await seed_demo.reset_demo(factory)

    async with factory() as session:
        demo_user = (await session.execute(
            select(User).where(User.email == "demo.provider@example.com")
        )).scalar_one()
        demo_visits = (await session.execute(
            select(func.count()).select_from(Visit).where(Visit.user_id == demo_user.id)
        )).scalar_one()
        demo_notes = (await session.execute(
            select(func.count()).select_from(Note).join(Visit).where(Visit.user_id == demo_user.id)
        )).scalar_one()
        other_visits = (await session.execute(
            select(func.count()).select_from(Visit).where(Visit.patient_ref == "OTHER-001")
        )).scalar_one()

    assert demo_visits == 1
    assert demo_notes == 1
    assert other_visits == 1
