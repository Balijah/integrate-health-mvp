"""
Transcription API endpoints.

Handles audio transcription operations for visits.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.visit import Visit
from app.services.transcription import TranscriptionError, transcribe_audio_file

logger = logging.getLogger(__name__)

router = APIRouter()


class TranscriptionStatusResponse(BaseModel):
    """Response schema for transcription status."""

    visit_id: uuid.UUID
    status: str
    transcript: str | None = None
    error_message: str | None = None


class TranscribeResponse(BaseModel):
    """Response schema for triggering transcription."""

    visit_id: uuid.UUID
    status: str
    message: str


def process_transcription(visit_id: uuid.UUID, db_url: str) -> None:
    """
    Background task to process transcription.

    This is a synchronous function that runs the async database operations
    using asyncio.run().

    Args:
        visit_id: Visit UUID to transcribe.
        db_url: Database URL for creating new session.
    """
    asyncio.run(_process_transcription_async(visit_id, db_url))


async def _process_transcription_async(visit_id: uuid.UUID, db_url: str) -> None:
    """
    Async implementation of transcription processing.

    Args:
        visit_id: Visit UUID to transcribe.
        db_url: Database URL for creating new session.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

    # Create a new database session for the background task
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        try:
            # Get the visit
            result = await db.execute(select(Visit).where(Visit.id == visit_id))
            visit = result.scalar_one_or_none()

            if not visit:
                logger.error(f"Visit {visit_id} not found for transcription")
                return

            if not visit.audio_file_path:
                logger.error(f"Visit {visit_id} has no audio file")
                visit.transcription_status = "failed"
                await db.commit()
                return

            # Update status to transcribing
            visit.transcription_status = "transcribing"
            await db.commit()

            # Perform transcription (sync function)
            logger.info(f"Starting transcription for visit {visit_id}")
            audio_path = visit.audio_file_path

            # Run sync transcription
            transcription_result = transcribe_audio_file(audio_path)

            # Update visit with transcript
            visit.transcript = transcription_result["transcript"]
            visit.transcription_status = "completed"

            # Update duration if we got a more accurate one from Deepgram
            if transcription_result["metadata"].get("duration_seconds"):
                visit.audio_duration_seconds = int(transcription_result["metadata"]["duration_seconds"])

            await db.commit()
            logger.info(f"Transcription completed for visit {visit_id}")

        except TranscriptionError as e:
            logger.error(f"Transcription failed for visit {visit_id}: {str(e)}")
            try:
                visit.transcription_status = "failed"
                await db.commit()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Unexpected error transcribing visit {visit_id}: {str(e)}", exc_info=True)
            try:
                visit.transcription_status = "failed"
                await db.commit()
            except Exception:
                pass

        finally:
            await engine.dispose()


@router.post(
    "/{visit_id}/transcribe",
    response_model=TranscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start transcription",
    description="Trigger transcription for a visit's audio file.",
)
async def start_transcription(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> TranscribeResponse:
    """
    Start transcription for a visit.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session
        background_tasks: FastAPI background tasks

    Returns:
        TranscribeResponse: Confirmation that transcription started

    Raises:
        HTTPException: 404 if visit not found
        HTTPException: 400 if no audio or already transcribed
    """
    from app.config import get_settings

    settings = get_settings()

    # Verify visit exists and belongs to user
    result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Check if audio exists
    if not visit.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file uploaded for this visit",
        )

    # Check current status
    if visit.transcription_status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcription already in progress",
        )

    if visit.transcription_status == "completed" and visit.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcription already completed. Delete visit to re-transcribe.",
        )

    # Queue background transcription task
    background_tasks.add_task(process_transcription, visit_id, settings.database_url)

    return TranscribeResponse(
        visit_id=visit_id,
        status="transcribing",
        message="Transcription started. Poll status endpoint for updates.",
    )


@router.get(
    "/{visit_id}/transcription/status",
    response_model=TranscriptionStatusResponse,
    summary="Get transcription status",
    description="Check the status of a visit's transcription.",
)
async def get_transcription_status(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> TranscriptionStatusResponse:
    """
    Get transcription status for a visit.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        TranscriptionStatusResponse: Current transcription status

    Raises:
        HTTPException: 404 if visit not found
    """
    result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    return TranscriptionStatusResponse(
        visit_id=visit.id,
        status=visit.transcription_status,
        transcript=visit.transcript if visit.transcription_status == "completed" else None,
        error_message="Transcription failed. Please try again." if visit.transcription_status == "failed" else None,
    )


@router.post(
    "/{visit_id}/transcription/retry",
    response_model=TranscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry transcription",
    description="Retry a failed transcription.",
)
async def retry_transcription(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> TranscribeResponse:
    """
    Retry a failed transcription.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session
        background_tasks: FastAPI background tasks

    Returns:
        TranscribeResponse: Confirmation that transcription restarted

    Raises:
        HTTPException: 404 if visit not found
        HTTPException: 400 if transcription not failed
    """
    from app.config import get_settings

    settings = get_settings()

    result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    if not visit.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file uploaded for this visit",
        )

    if visit.transcription_status not in ("failed", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry transcription with status: {visit.transcription_status}",
        )

    # Reset status and queue transcription
    visit.transcription_status = "pending"
    visit.transcript = None
    await db.commit()

    background_tasks.add_task(process_transcription, visit_id, settings.database_url)

    return TranscribeResponse(
        visit_id=visit_id,
        status="transcribing",
        message="Transcription restarted. Poll status endpoint for updates.",
    )
