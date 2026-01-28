"""
Live Transcription service using Deepgram Streaming API.

Provides real-time audio transcription with WebSocket streaming.
"""

import asyncio
import logging
import threading
import queue
from datetime import datetime
from typing import Any
from uuid import UUID

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

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
    """Manage live transcription sessions with Deepgram streaming."""

    def __init__(self):
        settings = get_settings()
        if not settings.deepgram_api_key:
            raise LiveTranscriptionError(
                "Deepgram API key not configured. Set DEEPGRAM_API_KEY in environment."
            )
        self.deepgram = DeepgramClient(settings.deepgram_api_key)
        self.active_sessions: dict[str, LiveTranscriptionSession] = {}
        self._lock = threading.Lock()

    def start_session(
        self,
        session_id: str,
        visit_id: UUID,
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ) -> LiveTranscriptionSession:
        """
        Start a live transcription session (synchronous).

        Args:
            session_id: Unique session identifier.
            visit_id: Associated visit UUID.
            sample_rate: Audio sample rate (default 16000).
            encoding: Audio encoding format (default linear16).

        Returns:
            LiveTranscriptionSession instance.
        """
        with self._lock:
            if session_id in self.active_sessions:
                raise LiveTranscriptionError(f"Session {session_id} already exists")

        # Create session object
        session = LiveTranscriptionSession(session_id=session_id, visit_id=visit_id)

        try:
            # Configure Deepgram streaming options
            options = LiveOptions(
                model="nova-2-medical",
                language="en-US",
                punctuate=True,
                smart_format=True,
                interim_results=True,
                utterance_end_ms="1000",
                diarize=True,
                encoding=encoding,
                sample_rate=sample_rate,
            )

            # Create Deepgram live connection
            dg_connection = self.deepgram.listen.live.v("1")

            # Define event handlers (these run in Deepgram's thread)
            def on_message(ws_self, result, **kwargs):
                """Handle incoming transcript from Deepgram."""
                try:
                    if not result.channel or not result.channel.alternatives:
                        return

                    alternative = result.channel.alternatives[0]
                    transcript_text = alternative.transcript

                    if not transcript_text:
                        return

                    speaker = self._identify_speaker(result)

                    transcript_data = {
                        "type": "transcript",
                        "text": transcript_text,
                        "is_final": result.is_final,
                        "speaker": speaker,
                        "confidence": alternative.confidence if alternative.confidence else 0.0,
                        "timestamp": result.start if hasattr(result, 'start') else 0,
                    }

                    # Add to session (thread-safe)
                    session.add_transcript(transcript_data)
                    logger.debug(f"Transcript: {transcript_text[:50]}... (final={result.is_final})")

                except Exception as e:
                    logger.error(f"Error processing transcript: {e}")

            def on_metadata(ws_self, metadata, **kwargs):
                logger.debug(f"Deepgram metadata received")

            def on_speech_started(ws_self, speech_started, **kwargs):
                logger.debug(f"Speech started")

            def on_utterance_end(ws_self, utterance_end, **kwargs):
                logger.debug(f"Utterance ended")

            def on_error_event(ws_self, error, **kwargs):
                error_msg = str(error)
                logger.error(f"Deepgram error: {error_msg}")
                session.message_queue.put({
                    "type": "error",
                    "message": error_msg
                })

            def on_close(ws_self, close, **kwargs):
                logger.info(f"Deepgram connection closed for session {session_id}")

            # Register event handlers
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error_event)
            dg_connection.on(LiveTranscriptionEvents.Close, on_close)

            # Start the connection
            if not dg_connection.start(options):
                raise LiveTranscriptionError("Failed to start Deepgram connection")

            # Store connection in session
            session.connection = dg_connection
            session.status = "active"
            session.started_at = datetime.utcnow()

            # Store session
            with self._lock:
                self.active_sessions[session_id] = session

            logger.info(f"Live transcription session started: {session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to start live transcription session: {e}")
            raise LiveTranscriptionError(f"Failed to start session: {e}") from e

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
        """Identify speaker from diarization data."""
        if hasattr(result, 'channel') and result.channel:
            alternatives = result.channel.alternatives
            if alternatives and len(alternatives) > 0:
                words = alternatives[0].words
                if words and len(words) > 0:
                    speaker_counts: dict[int, int] = {}
                    for word in words:
                        if hasattr(word, 'speaker'):
                            speaker_counts[word.speaker] = speaker_counts.get(word.speaker, 0) + 1

                    if speaker_counts:
                        dominant_speaker = max(speaker_counts, key=speaker_counts.get)
                        return "provider" if dominant_speaker == 0 else "patient"

        return "provider"


# Global service instance
_live_transcription_service: LiveTranscriptionService | None = None


def get_live_transcription_service() -> LiveTranscriptionService:
    """Get or create the global LiveTranscriptionService instance."""
    global _live_transcription_service
    if _live_transcription_service is None:
        _live_transcription_service = LiveTranscriptionService()
    return _live_transcription_service
