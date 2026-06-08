"""
WebSocket endpoints for live transcription.

Provides real-time bidirectional communication for audio streaming and transcript delivery.
"""

import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.visit import Visit
from app.models.transcription_session import TranscriptionSession
from app.services.live_transcription import (
    get_live_transcription_service,
    LiveTranscriptionError,
)

logger = logging.getLogger(__name__)


async def update_database_on_stop(
    session_id: str,
    transcript: str,
    duration: int,
    word_count: int,
    pause_count: int,
    transcript_segments: list | None = None,
):
    """Update database records when transcription stops."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as db:
        try:
            # Update transcription session
            result = await db.execute(
                select(TranscriptionSession).where(TranscriptionSession.id == uuid.UUID(session_id))
            )
            db_session = result.scalar_one_or_none()

            if db_session:
                db_session.session_status = "completed"
                db_session.ended_at = datetime.utcnow()
                db_session.total_duration_seconds = duration

                # Update associated visit
                visit_result = await db.execute(
                    select(Visit).where(Visit.id == db_session.visit_id)
                )
                visit = visit_result.scalar_one_or_none()

                if visit:
                    # Append rather than overwrite. If a session was lost mid-visit (e.g. the
                    # connection dropped during a pause) its partial transcript is already saved
                    # here; a later reconnect session must CONTINUE that text, not replace it,
                    # because note generation reads the authoritative DB transcript.
                    existing = (visit.transcript or "").strip()
                    if existing and transcript:
                        visit.transcript = f"{existing}\n{transcript}"
                    else:
                        visit.transcript = transcript or existing

                    visit.transcription_status = "completed"
                    visit.audio_duration_seconds = (visit.audio_duration_seconds or 0) + duration
                    if transcript_segments is not None:
                        visit.transcript_segments = (visit.transcript_segments or []) + transcript_segments

                await db.commit()
                logger.info(f"Database updated for session {session_id}")

        except Exception as e:
            logger.error(f"Error updating database on stop: {e}")
            await db.rollback()
        finally:
            await engine.dispose()

router = APIRouter()


@router.websocket("/ws/transcription/{session_id}")
async def transcription_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for live transcription.

    Handles bidirectional communication:
    - Client -> Server: Audio chunks (base64 encoded), control commands
    - Server -> Client: Transcript chunks, status updates, errors
    """
    await websocket.accept()
    # [PHASE0-DIAG] Log the worker pid handling this WS. If it differs from the pid that
    # logged "Session ... started" (the REST start-live call), the session lives on another
    # worker and get_session() below will miss it — the multi-worker bug.
    logger.info(f"[PHASE0-DIAG] WebSocket connected for session {session_id} (pid={os.getpid()})")

    service = get_live_transcription_service()
    session = service.get_session(session_id)

    if not session:
        logger.warning(
            f"[PHASE0-DIAG] Session {session_id} NOT FOUND on pid={os.getpid()} at WS connect — "
            f"likely created on a different uvicorn worker (--workers 2). Known sessions here: "
            f"{list(service.active_sessions.keys())}"
        )
        await websocket.send_json({
            "type": "error",
            "message": f"Session {session_id} not found. Start a session first via REST API."
        })
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Task to poll for messages from Deepgram and forward to client
    async def forward_messages():
        """Poll the session's message queue and forward to WebSocket."""
        while True:
            try:
                # Get pending messages from the session
                messages = session.get_pending_messages()
                for msg in messages:
                    try:
                        await websocket.send_json(msg)
                        if msg.get("type") == "connection_closed":
                            # [PHASE0-DIAG] The browser socket is being closed because the
                            # upstream Deepgram stream dropped. If this fires during a pause,
                            # it explains the unresponsive Resume.
                            logger.info(
                                f"[PHASE0-DIAG] Forwarding connection_closed for session "
                                f"{session_id} (pid={os.getpid()}); closing browser WS (1001)"
                            )
                            await websocket.close(code=1001)
                            return
                    except Exception as e:
                        logger.error(f"Error sending message to WebSocket: {e}")
                        return

                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.05)  # 50ms

            except Exception as e:
                logger.error(f"Error in message forwarding: {e}")
                break

    # Start the message forwarding task
    forward_task = asyncio.create_task(forward_messages())

    try:
        # Main message loop - receive from client
        while True:
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.warning(f"Error receiving message: {e}")
                break

            message_type = data.get("type")

            if message_type == "audio_chunk":
                # Decode base64 audio and send to Deepgram
                try:
                    audio_data = data.get("data", "")
                    if audio_data:
                        audio_bytes = base64.b64decode(audio_data)
                        success = service.send_audio_chunk(session_id, audio_bytes)
                        if not success:
                            logger.warning(f"Failed to send audio chunk for session {session_id}")
                except Exception as e:
                    logger.error(f"Error processing audio chunk: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing audio: {str(e)}"
                    })

            elif message_type == "pause":
                logger.info(
                    f"[PHASE0-DIAG] Received 'pause' for session {session_id} (pid={os.getpid()})"
                )
                try:
                    result = service.pause_session(session_id)
                    await websocket.send_json({
                        "type": "status",
                        "session_status": "paused",
                        "duration_seconds": result["duration_seconds"]
                    })
                except LiveTranscriptionError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

            elif message_type == "resume":
                try:
                    result = service.resume_session(session_id)
                    await websocket.send_json({
                        "type": "status",
                        "session_status": "active",
                        "duration_seconds": result["duration_seconds"]
                    })
                except LiveTranscriptionError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

            elif message_type == "stop":
                try:
                    result = service.end_session(session_id)

                    # Update database with final transcript and segments
                    await update_database_on_stop(
                        session_id=session_id,
                        transcript=result["transcript"],
                        duration=result["total_duration_seconds"],
                        word_count=result["word_count"],
                        pause_count=result["pause_count"],
                        transcript_segments=result.get("transcript_segments"),
                    )

                    await websocket.send_json({
                        "type": "complete",
                        "transcript": result["transcript"],
                        "total_duration_seconds": result["total_duration_seconds"],
                        "word_count": result["word_count"],
                        "pause_count": result["pause_count"]
                    })
                    # Close the WebSocket after stopping
                    await websocket.close()
                    return
                except LiveTranscriptionError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                logger.warning(f"Unknown message type: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except Exception:
            pass

    finally:
        # Cancel the forwarding task
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass

        # Clean up the session if still active (e.g., client disconnected without stop command)
        # and save transcript to DB so it isn't lost
        try:
            if service.get_session(session_id):
                result = service.end_session(session_id)
                if result.get("transcript"):
                    await update_database_on_stop(
                        session_id=session_id,
                        transcript=result["transcript"],
                        duration=result["total_duration_seconds"],
                        word_count=result["word_count"],
                        pause_count=result["pause_count"],
                        transcript_segments=result.get("transcript_segments"),
                    )
                    logger.info(f"Transcript saved on disconnect for session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session on disconnect: {e}")
