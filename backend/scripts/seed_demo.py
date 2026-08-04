"""Create or reset the isolated synthetic demo account and flagship visit."""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from email_validator import validate_email
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.note import Note
from app.models.user import User
from app.models.visit import Visit
from app.services.auth import hash_password

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "demo_fixtures" / "flagship_visit.json"
DEMO_NAMESPACE = uuid.UUID("9c4f50e6-60a4-4e8c-9ea4-0cc76edcb221")


def load_demo_credentials() -> tuple[str, str, str]:
    """Load required credentials without providing unsafe committed defaults."""
    email = os.getenv("DEMO_USER_EMAIL", "").strip().lower()
    password = os.getenv("DEMO_USER_PASSWORD", "")
    full_name = os.getenv("DEMO_USER_NAME", "").strip()

    if not email or not password or not full_name:
        raise RuntimeError("DEMO_USER_EMAIL, DEMO_USER_PASSWORD, and DEMO_USER_NAME are required")
    validate_email(email, check_deliverability=False)
    if len(password) < 12:
        raise RuntimeError("DEMO_USER_PASSWORD must contain at least 12 characters")
    return email, password, full_name


def load_fixture() -> dict:
    """Load the checked-in, explicitly synthetic flagship encounter."""
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if "Entirely synthetic" not in fixture.get("fixture_notice", ""):
        raise RuntimeError("Demo fixture must carry the synthetic-data notice")
    return fixture


async def reset_demo(session_factory=None) -> None:
    settings = get_settings()
    if not settings.demo_mode:
        raise RuntimeError("Refusing to seed: DEMO_MODE is not enabled")

    email, password, full_name = load_demo_credentials()
    fixture = load_fixture()
    user_id = uuid.uuid5(DEMO_NAMESPACE, email)
    visit_id = uuid.uuid5(DEMO_NAMESPACE, f"{email}:flagship-visit")
    note_id = uuid.uuid5(DEMO_NAMESPACE, f"{email}:flagship-note")
    segments = fixture["transcript_segments"]
    transcript = "\n".join(
        f"{segment['speaker'].title()}: {segment['text']}" for segment in segments
    )

    session_factory = session_factory or AsyncSessionLocal
    async with session_factory() as session, session.begin():
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id=user_id, email=email, full_name=full_name, hashed_password=hash_password(password))
            session.add(user)
            await session.flush()
        else:
            user.full_name = full_name
            user.hashed_password = hash_password(password)
            user.is_active = True

        await session.execute(delete(Visit).where(Visit.user_id == user.id))
        visit = Visit(
            id=visit_id,
            user_id=user.id,
            patient_ref=fixture["patient_ref"],
            visit_date=datetime.now(timezone.utc) - timedelta(days=2),
            chief_complaint=fixture["chief_complaint"],
            audio_duration_seconds=fixture["audio_duration_seconds"],
            transcript=transcript,
            transcript_segments=segments,
            transcription_status="completed",
            transcription_confidence=1.0,
            num_speakers=2,
            is_live_transcription=False,
        )
        session.add(visit)
        await session.flush()
        session.add(
            Note(
                id=note_id,
                visit_id=visit.id,
                content=fixture["soap_note"],
                note_type="soap",
                status="draft",
                synced_sections={},
            )
        )

    print(f"Synthetic demo reset complete for {email}; visit_id={visit_id}")


if __name__ == "__main__":
    asyncio.run(reset_demo())
