"""
Live Transcription service.

Manages live transcription sessions using Deepgram's streaming API.
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

    def get_transcript_segments(self) -> list[dict]:
        """Return final segments with speaker data; fall back to all segments if none are final."""
        with self._lock:
            final_segs = [seg for seg in self.transcript_buffer if seg.get("is_final") and seg.get("text")]
            if final_segs:
                return final_segs
            return [seg for seg in self.transcript_buffer if seg.get("text")]

    def get_full_transcript(self) -> str:
        """Combine transcript segments into diarized text with speaker labels.

        Consecutive segments from the same speaker are grouped into a single block
        so Claude receives a clearly attributed conversation rather than a flat paragraph.

        Format:
            [PROVIDER]: <text>
            [PATIENT]: <text>
        """
        segments = self.get_transcript_segments()
        if not segments:
            return ""

        parts: list[str] = []
        current_speaker: str | None = None
        current_texts: list[str] = []

        for seg in segments:
            speaker = seg.get("speaker", "provider")
            text = seg.get("text", "").strip()
            if not text:
                continue
            if speaker != current_speaker:
                if current_texts and current_speaker is not None:
                    label = "PROVIDER" if current_speaker == "provider" else "PATIENT"
                    parts.append(f"[{label}]: {' '.join(current_texts)}")
                current_speaker = speaker
                current_texts = [text]
            else:
                current_texts.append(text)

        if current_texts and current_speaker is not None:
            label = "PROVIDER" if current_speaker == "provider" else "PATIENT"
            parts.append(f"[{label}]: {' '.join(current_texts)}")

        return "\n".join(parts)

    def add_transcript(self, data: dict) -> None:
        """Add a transcript segment (thread-safe)."""
        with self._lock:
            self.transcript_buffer.append(data)   # store all, not just final
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
    """Manage live transcription sessions via Deepgram streaming API."""

    def __init__(self):
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
        Start a live transcription session connected to Deepgram.

        Args:
            session_id: Unique session identifier.
            visit_id: Associated visit UUID.
            sample_rate: Audio sample rate (default 16000).
            encoding: Audio encoding format (default linear16).

        Returns:
            LiveTranscriptionSession: The started session.

        Raises:
            LiveTranscriptionError: If Deepgram connection fails.
        """
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        settings = get_settings()

        if not settings.deepgram_api_key:
            raise LiveTranscriptionError("Deepgram API key not configured.")

        session = LiveTranscriptionSession(session_id=session_id, visit_id=visit_id)
        session.status = "active"
        session.started_at = datetime.utcnow()

        deepgram = DeepgramClient(settings.deepgram_api_key)
        dg_connection = deepgram.listen.websocket.v("1")

        def on_transcript(self_dg, result, **kwargs):
            try:
                alternatives = result.channel.alternatives
                if not alternatives:
                    return
                alt = alternatives[0]
                if not alt.transcript:
                    return

                words = alt.words or []
                is_final = getattr(result, "is_final", False)

                if words:
                    counts: dict[int, int] = {}
                    for w in words:
                        spk = int(getattr(w, "speaker", 0) or 0)
                        counts[spk] = counts.get(spk, 0) + 1
                    dominant = max(counts, key=counts.get)
                    speaker_label = self._identify_speaker(dominant)
                else:
                    speaker_label = "provider"

                confidence = round(float(getattr(alt, "confidence", 0.0) or 0.0), 4)

                session.add_transcript({
                    "type": "transcript",
                    "speaker": speaker_label,
                    "text": alt.transcript,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    "is_final": is_final,
                    "confidence": confidence,
                })
            except Exception as e:
                logger.error(f"Error in transcript callback for session {session_id}: {e}")

        def on_error(self_dg, error, **kwargs):
            logger.error(f"Deepgram streaming error for session {session_id}: {error}")
            session.message_queue.put({"type": "error", "message": str(error)})

        def on_close(self_dg, close, **kwargs):
            logger.info(f"Deepgram connection closed for session {session_id}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        options = LiveOptions(
            model=settings.deepgram_model,
            language=settings.deepgram_language,
            smart_format=True,
            punctuate=True,
            diarize=True,
            encoding=encoding,
            sample_rate=sample_rate,
            channels=1,
            interim_results=True,
        )

        if not dg_connection.start(options):
            raise LiveTranscriptionError("Failed to open Deepgram streaming connection.")

        session.connection = dg_connection

        with self._lock:
            self.active_sessions[session_id] = session

        logger.info(f"Live transcription session started: {session_id} (visit {visit_id})")
        return session

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

            # Get final transcript and segments
            transcript_segments = session.get_transcript_segments()
            full_transcript = session.get_full_transcript()
            word_count = len(full_transcript.split()) if full_transcript else 0

            result = {
                "session_id": session_id,
                "status": "completed",
                "total_duration_seconds": session.duration_seconds,
                "transcript": full_transcript,
                "transcript_segments": transcript_segments,
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

    def _identify_speaker(self, speaker_index: int) -> str:
        """Map Deepgram speaker index to clinical label. Index 0 = first to speak = Provider."""
        return "provider" if speaker_index == 0 else "patient"


# Global service instance
_live_transcription_service: LiveTranscriptionService | None = None


def get_live_transcription_service() -> LiveTranscriptionService:
    """Get or create the global LiveTranscriptionService instance."""
    global _live_transcription_service
    if _live_transcription_service is None:
        _live_transcription_service = LiveTranscriptionService()
    return _live_transcription_service
