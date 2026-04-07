"""
Transcription API endpoints.

Handles audio transcription operations for visits, including live streaming.
"""

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.visit import Visit
from app.models.transcription_session import TranscriptionSession
from app.services.transcription import TranscriptionError, transcribe_audio_file
from app.services.live_transcription import (
    get_live_transcription_service,
    LiveTranscriptionError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class TranscriptionStatusResponse(BaseModel):
    """Response schema for transcription status."""

    visit_id: uuid.UUID
    status: str
    transcript: str | None = None
    error_message: str | None = None
    confidence: float | None = None
    num_speakers: int | None = None
    segments: list | None = None


class TranscribeResponse(BaseModel):
    """Response schema for triggering transcription."""

    visit_id: uuid.UUID
    status: str
    message: str


# Live Transcription Schemas
class StartLiveTranscriptionRequest(BaseModel):
    """Request schema for starting live transcription."""

    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    encoding: str = Field(default="linear16")


class StartLiveTranscriptionResponse(BaseModel):
    """Response schema for starting live transcription."""

    session_id: str
    websocket_url: str
    status: str


class LiveTranscriptionStatusResponse(BaseModel):
    """Response schema for live transcription status."""

    session_id: str
    status: str
    duration_seconds: int


class StopLiveTranscriptionResponse(BaseModel):
    """Response schema for stopping live transcription."""

    session_id: str
    status: str
    total_duration_seconds: int
    transcript: str
    word_count: int


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

            from app.config import get_settings
            from app.services.transcription import transcribe_from_s3
            settings = get_settings()

            if settings.storage_mode == "s3":
                transcription_result = transcribe_from_s3(audio_path)
            else:
                transcription_result = transcribe_audio_file(audio_path)

            # Validate transcript has content before marking completed
            raw_transcript = transcription_result.get("transcript", "")
            if not raw_transcript.strip():
                logger.error(
                    f"Transcription for visit {visit_id} returned empty transcript. "
                    f"Audio duration: {transcription_result.get('metadata', {}).get('duration_seconds')}s"
                )
                visit.transcription_status = "failed"
                visit.transcription_error = "Transcription returned no text. Please try again — if this persists, the audio may not have been captured correctly."
                await db.commit()
                return

            # Update visit with transcript and Deepgram metadata
            visit.transcript = raw_transcript
            visit.transcription_status = "completed"
            visit.transcription_error = None

            metadata = transcription_result.get("metadata", {})
            if metadata.get("duration_seconds"):
                visit.audio_duration_seconds = int(metadata["duration_seconds"])
            if metadata.get("confidence") is not None:
                visit.transcription_confidence = metadata["confidence"]
            if metadata.get("num_speakers") is not None:
                visit.num_speakers = metadata["num_speakers"]
            visit.transcript_segments = transcription_result.get("speakers") or []

            await db.commit()
            logger.info(f"Transcription completed for visit {visit_id}")

        except TranscriptionError as e:
            logger.error(f"Transcription failed for visit {visit_id}")
            try:
                visit.transcription_status = "failed"
                visit.transcription_error = str(e)
                await db.commit()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Unexpected error transcribing visit {visit_id}: {type(e).__name__}")
            try:
                visit.transcription_status = "failed"
                visit.transcription_error = str(e)
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

    response = TranscriptionStatusResponse(
        visit_id=visit.id,
        status=visit.transcription_status,
        transcript=visit.transcript if visit.transcription_status == "completed" else None,
        error_message=visit.transcription_error if visit.transcription_status == "failed" else None,
    )

    if visit.transcription_status == "completed":
        response.confidence = visit.transcription_confidence
        response.num_speakers = visit.num_speakers
        response.segments = (visit.transcript_segments or [])[:10]
    elif visit.transcription_status == "failed":
        response.error_message = visit.transcription_error or "Transcription failed. Please try again."

    return response


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


# ============================================================================
# Live Transcription Endpoints
# ============================================================================


@router.post(
    "/{visit_id}/transcription/start-live",
    response_model=StartLiveTranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Start live transcription",
    description="Start a live transcription session for real-time audio streaming.",
)
async def start_live_transcription(
    visit_id: uuid.UUID,
    request: StartLiveTranscriptionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> StartLiveTranscriptionResponse:
    """
    Start live transcription session.

    Creates a new transcription session and returns WebSocket URL for streaming.

    Args:
        visit_id: Visit UUID
        request: Configuration for live transcription
        current_user: Authenticated user
        db: Database session

    Returns:
        StartLiveTranscriptionResponse: Session info with WebSocket URL

    Raises:
        HTTPException: 404 if visit not found
        HTTPException: 400 if visit already has active session
    """
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

    # Check for existing active session
    existing_session = await db.execute(
        select(TranscriptionSession).where(
            TranscriptionSession.visit_id == visit_id,
            TranscriptionSession.session_status.in_(["active", "paused"]),
        )
    )
    if existing_session.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit already has an active transcription session",
        )

    # Create database session record
    db_session = TranscriptionSession(
        visit_id=visit_id,
        session_status="active",
        started_at=datetime.utcnow(),
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)

    session_id = str(db_session.id)

    # Mark visit as live transcription
    visit.is_live_transcription = True
    visit.transcription_session_id = db_session.id
    visit.transcription_status = "transcribing"
    await db.commit()

    # Start the live transcription service session
    service = get_live_transcription_service()

    try:
        service.start_session(
            session_id=session_id,
            visit_id=visit_id,
            sample_rate=request.sample_rate,
            encoding=request.encoding,
        )
    except LiveTranscriptionError as e:
        # Rollback database changes
        db_session.session_status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start live transcription: {str(e)}",
        )

    # Update database session with connection info
    db_session.websocket_connection_id = session_id
    await db.commit()

    return StartLiveTranscriptionResponse(
        session_id=session_id,
        websocket_url=f"ws://localhost:8000/ws/transcription/{session_id}",
        status="active",
    )


@router.post(
    "/{visit_id}/transcription/pause-live",
    response_model=LiveTranscriptionStatusResponse,
    summary="Pause live transcription",
    description="Pause an active live transcription session.",
)
async def pause_live_transcription(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> LiveTranscriptionStatusResponse:
    """
    Pause active live transcription.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        LiveTranscriptionStatusResponse: Updated session status

    Raises:
        HTTPException: 404 if visit or session not found
    """
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

    # Get active session
    session_result = await db.execute(
        select(TranscriptionSession).where(
            TranscriptionSession.visit_id == visit_id,
            TranscriptionSession.session_status == "active",
        )
    )
    db_session = session_result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active transcription session found",
        )

    session_id = str(db_session.id)
    service = get_live_transcription_service()

    try:
        result = service.pause_session(session_id)
    except LiveTranscriptionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Update database
    db_session.session_status = "paused"
    db_session.pause_count += 1
    await db.commit()

    return LiveTranscriptionStatusResponse(
        session_id=session_id,
        status="paused",
        duration_seconds=result["duration_seconds"],
    )


@router.post(
    "/{visit_id}/transcription/resume-live",
    response_model=LiveTranscriptionStatusResponse,
    summary="Resume live transcription",
    description="Resume a paused live transcription session.",
)
async def resume_live_transcription(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> LiveTranscriptionStatusResponse:
    """
    Resume paused live transcription.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        LiveTranscriptionStatusResponse: Updated session status

    Raises:
        HTTPException: 404 if visit or session not found
    """
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

    # Get paused session
    session_result = await db.execute(
        select(TranscriptionSession).where(
            TranscriptionSession.visit_id == visit_id,
            TranscriptionSession.session_status == "paused",
        )
    )
    db_session = session_result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No paused transcription session found",
        )

    session_id = str(db_session.id)
    service = get_live_transcription_service()

    try:
        result = service.resume_session(session_id)
    except LiveTranscriptionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Update database
    db_session.session_status = "active"
    await db.commit()

    return LiveTranscriptionStatusResponse(
        session_id=session_id,
        status="active",
        duration_seconds=result["duration_seconds"],
    )


@router.post(
    "/{visit_id}/transcription/stop-live",
    response_model=StopLiveTranscriptionResponse,
    summary="Stop live transcription",
    description="End a live transcription session and get the full transcript.",
)
async def stop_live_transcription(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> StopLiveTranscriptionResponse:
    """
    End live transcription session.

    Closes the Deepgram connection and returns the full combined transcript.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        StopLiveTranscriptionResponse: Full transcript and session metadata

    Raises:
        HTTPException: 404 if visit or session not found
    """
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

    # Get active or paused session
    session_result = await db.execute(
        select(TranscriptionSession).where(
            TranscriptionSession.visit_id == visit_id,
            TranscriptionSession.session_status.in_(["active", "paused"]),
        )
    )
    db_session = session_result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active transcription session found",
        )

    session_id = str(db_session.id)
    service = get_live_transcription_service()

    try:
        result = service.end_session(session_id)
    except LiveTranscriptionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Update database session
    db_session.session_status = "completed"
    db_session.ended_at = datetime.utcnow()
    db_session.total_duration_seconds = result["total_duration_seconds"]
    await db.commit()

    # Update visit with transcript
    visit.transcript = result["transcript"]
    visit.transcription_status = "completed"
    visit.audio_duration_seconds = result["total_duration_seconds"]
    await db.commit()

    return StopLiveTranscriptionResponse(
        session_id=session_id,
        status="completed",
        total_duration_seconds=result["total_duration_seconds"],
        transcript=result["transcript"],
        word_count=result["word_count"],
    )


@router.get(
    "/{visit_id}/transcription/live-status",
    response_model=LiveTranscriptionStatusResponse,
    summary="Get live transcription status",
    description="Get the current status of a live transcription session.",
)
async def get_live_transcription_status(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> LiveTranscriptionStatusResponse:
    """
    Get current status of live transcription session.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        LiveTranscriptionStatusResponse: Current session status

    Raises:
        HTTPException: 404 if visit or session not found
    """
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

    # Get session (active, paused, or most recent)
    session_result = await db.execute(
        select(TranscriptionSession)
        .where(TranscriptionSession.visit_id == visit_id)
        .order_by(TranscriptionSession.created_at.desc())
    )
    db_session = session_result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No transcription session found",
        )

    session_id = str(db_session.id)
    service = get_live_transcription_service()

    # Try to get live status from service
    service_status = service.get_session_status(session_id)

    if service_status:
        return LiveTranscriptionStatusResponse(
            session_id=session_id,
            status=service_status["status"],
            duration_seconds=service_status["duration_seconds"],
        )

    # Fall back to database status
    duration = db_session.total_duration_seconds or 0
    return LiveTranscriptionStatusResponse(
        session_id=session_id,
        status=db_session.session_status,
        duration_seconds=duration,
    )
