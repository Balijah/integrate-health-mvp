"""
Live Transcription service.

Note: Live transcription is currently disabled in AWS deployment.
The application uses batch transcription via Whisper service instead.
This module provides stub implementations to maintain API compatibility.
"""

import logging
import threading
import queue
from datetime import datetime
from uuid import UUID

from app.config import get_settings

logger = logging.getLogger(__name__)


class LiveTranscriptionError(Exception):
    """Custom exception for live transcription failures."""
    pass


class LiveTranscriptionSession:
    """Represents a single live transcription session."""

    def __init__(self, session_id: str, visit_id: UUID):
        self.session_id = session_id
        self.visit_id = visit_id
        self.status = "initializing"
        self.connection = None
        self.transcript_buffer: list[dict] = []
        self.message_queue: queue.Queue = queue.Queue()
        self.started_at: datetime | None = None
        self.paused_at: datetime | None = None
        self.total_pause_duration: float = 0.0
        self.pause_count: int = 0
        self._lock = threading.Lock()

    @property
    def duration_seconds(self) -> int:
        """Calculate total active recording duration (excluding pauses)."""
        if not self.started_at:
            return 0

        total_elapsed = (datetime.utcnow() - self.started_at).total_seconds()

        if self.status == "paused" and self.paused_at:
            current_pause = (datetime.utcnow() - self.paused_at).total_seconds()
            return int(total_elapsed - self.total_pause_duration - current_pause)

        return int(total_elapsed - self.total_pause_duration)

    def get_full_transcript(self) -> str:
        """Combine all final transcript segments."""
        with self._lock:
            final_segments = [
                seg["text"] for seg in self.transcript_buffer if seg.get("is_final", False)
            ]
            return " ".join(final_segments)

    def add_transcript(self, data: dict) -> None:
        """Add a transcript segment (thread-safe)."""
        with self._lock:
            if data.get("is_final", False):
                self.transcript_buffer.append(data)
            # Put in queue for WebSocket to consume
            self.message_queue.put(data)

    def get_pending_messages(self) -> list[dict]:
        """Get all pending messages from the queue."""
        messages = []
        while not self.message_queue.empty():
            try:
                messages.append(self.message_queue.get_nowait())
            except queue.Empty:
                break
        return messages


class LiveTranscriptionService:
    """
    Manage live transcription sessions.

    Note: Live transcription is disabled in AWS deployment.
    Use batch transcription via /visits/{id}/transcribe endpoint instead.
    """

    def __init__(self):
        self.active_sessions: dict[str, LiveTranscriptionSession] = {}
        self._lock = threading.Lock()
        self._disabled = True  # Live transcription disabled in AWS mode
        logger.warning("Live transcription is disabled in AWS deployment mode")

    def start_session(
        self,
        session_id: str,
        visit_id: UUID,
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ) -> LiveTranscriptionSession:
        """
        Start a live transcription session.

        Note: Live transcription is currently disabled in AWS deployment.
        Use batch transcription via the /visits/{id}/transcribe endpoint instead.

        Args:
            session_id: Unique session identifier.
            visit_id: Associated visit UUID.
            sample_rate: Audio sample rate (default 16000).
            encoding: Audio encoding format (default linear16).

        Raises:
            LiveTranscriptionError: Always raised as live transcription is disabled.
        """
        raise LiveTranscriptionError(
            "Live transcription is not available in AWS deployment. "
            "Please use batch transcription: upload audio and call POST /visits/{id}/transcribe"
        )

    def send_audio_chunk(self, session_id: str, audio_data: bytes) -> bool:
        """
        Send audio chunk to Deepgram for transcription.

        Args:
            session_id: Session identifier.
            audio_data: Raw audio bytes.

        Returns:
            True if sent successfully, False otherwise.
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return False

        if session.status != "active":
            return False

        if session.connection is None:
            return False

        try:
            session.connection.send(audio_data)
            return True
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")
            return False

    def pause_session(self, session_id: str) -> dict:
        """Pause transcription session."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise LiveTranscriptionError(f"Session {session_id} not found")

        if session.status == "paused":
            return {
                "session_id": session_id,
                "status": "paused",
                "duration_seconds": session.duration_seconds,
            }

        session.status = "paused"
        session.paused_at = datetime.utcnow()
        session.pause_count += 1

        logger.info(f"Session {session_id} paused")

        return {
            "session_id": session_id,
            "status": "paused",
            "duration_seconds": session.duration_seconds,
        }

    def resume_session(self, session_id: str) -> dict:
        """Resume paused transcription session."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise LiveTranscriptionError(f"Session {session_id} not found")

        if session.status != "paused":
            return {
                "session_id": session_id,
                "status": session.status,
                "duration_seconds": session.duration_seconds,
            }

        if session.paused_at:
            pause_duration = (datetime.utcnow() - session.paused_at).total_seconds()
            session.total_pause_duration += pause_duration

        session.status = "active"
        session.paused_at = None

        logger.info(f"Session {session_id} resumed")

        return {
            "session_id": session_id,
            "status": "active",
            "duration_seconds": session.duration_seconds,
        }

    def end_session(self, session_id: str) -> dict:
        """End transcription session and return final transcript."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise LiveTranscriptionError(f"Session {session_id} not found")

        try:
            # Close Deepgram connection
            if session.connection:
                try:
                    session.connection.finish()
                except Exception as e:
                    logger.warning(f"Error finishing Deepgram connection: {e}")

            # Get final transcript
            full_transcript = session.get_full_transcript()
            word_count = len(full_transcript.split()) if full_transcript else 0

            result = {
                "session_id": session_id,
                "status": "completed",
                "total_duration_seconds": session.duration_seconds,
                "transcript": full_transcript,
                "word_count": word_count,
                "pause_count": session.pause_count,
            }

            logger.info(f"Session {session_id} ended. Duration: {session.duration_seconds}s")
            return result

        finally:
            # Cleanup session
            with self._lock:
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]

    def get_session(self, session_id: str) -> LiveTranscriptionSession | None:
        """Get a session by ID."""
        return self.active_sessions.get(session_id)

    def get_session_status(self, session_id: str) -> dict | None:
        """Get current status of a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session_id,
            "visit_id": str(session.visit_id),
            "status": session.status,
            "duration_seconds": session.duration_seconds,
            "pause_count": session.pause_count,
            "transcript_segments": len(session.transcript_buffer),
        }

    def _identify_speaker(self, result) -> str:
        """Identify speaker from diarization data (stub - not implemented in AWS mode)."""
        return "provider"


# Global service instance
_live_transcription_service: LiveTranscriptionService | None = None


def get_live_transcription_service() -> LiveTranscriptionService:
    """Get or create the global LiveTranscriptionService instance."""
    global _live_transcription_service
    if _live_transcription_service is None:
        _live_transcription_service = LiveTranscriptionService()
    return _live_transcription_service
