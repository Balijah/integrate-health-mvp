"""
WebSocket endpoints for live transcription.

Provides real-time bidirectional communication for audio streaming and transcript delivery.
"""

import asyncio
import base64
import logging
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


async def update_database_on_stop(session_id: str, transcript: str, duration: int, word_count: int, pause_count: int):
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
                    visit.transcript = transcript
                    visit.transcription_status = "completed"
                    visit.audio_duration_seconds = duration

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
    logger.info(f"WebSocket connected for session: {session_id}")

    service = get_live_transcription_service()
    session = service.get_session(session_id)

    if not session:
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

                    # Update database with final transcript
                    await update_database_on_stop(
                        session_id=session_id,
                        transcript=result["transcript"],
                        duration=result["total_duration_seconds"],
                        word_count=result["word_count"],
                        pause_count=result["pause_count"],
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
                    )
                    logger.info(f"Transcript saved on disconnect for session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session on disconnect: {e}")
