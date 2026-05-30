"""
Unit tests for the SQS worker and API enqueue logic.
No real DB or SQS connections — everything is mocked.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.note_generation import NoteGenerationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqs_message(body: dict, receipt: str = "receipt-handle-abc") -> dict:
    return {
        "ReceiptHandle": receipt,
        "Body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Tests: API enqueue path
# ---------------------------------------------------------------------------

class TestApiEnqueuePath:
    """Verify notes.py routes to SQS vs BackgroundTasks based on sqs_queue_url."""

    def test_enqueue_sends_correct_sqs_message(self):
        """When sqs_queue_url is set, _enqueue_note_generation sends the right body."""
        from app.api.notes import _enqueue_note_generation

        mock_sqs = MagicMock()
        with patch("app.api.notes.boto3.client", return_value=mock_sqs):
            with patch("app.api.notes.get_settings") as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                mock_settings.return_value.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/integrate-health-notes"
                note_id = str(uuid.uuid4())
                _enqueue_note_generation(note_id, "extra context")

        mock_sqs.send_message.assert_called_once()
        call_kwargs = mock_sqs.send_message.call_args[1]
        sent_body = json.loads(call_kwargs["MessageBody"])
        assert sent_body["task_type"] == "generate_note"
        assert sent_body["note_id"] == note_id
        assert sent_body["additional_context"] == "extra context"

    def test_enqueue_uses_configured_queue_url(self):
        """_enqueue_note_generation sends to the configured SQS_QUEUE_URL."""
        from app.api.notes import _enqueue_note_generation

        queue_url = "https://sqs.us-east-1.amazonaws.com/999/my-queue"
        mock_sqs = MagicMock()
        with patch("app.api.notes.boto3.client", return_value=mock_sqs):
            with patch("app.api.notes.get_settings") as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                mock_settings.return_value.sqs_queue_url = queue_url
                _enqueue_note_generation("note-id-123", "")

        assert mock_sqs.send_message.call_args[1]["QueueUrl"] == queue_url


# ---------------------------------------------------------------------------
# Tests: worker dispatch logic
# ---------------------------------------------------------------------------

class TestWorkerHandleGenerateNote:
    """Unit tests for _handle_generate_note coroutine."""

    def _make_note(self, status="generating"):
        note = MagicMock()
        note.id = uuid.uuid4()
        note.visit_id = uuid.uuid4()
        note.status = status
        note.content = {}
        return note

    def _make_visit(self, transcript="Doctor: Hi. Patient: I feel tired."):
        visit = MagicMock()
        visit.id = uuid.uuid4()
        visit.transcript = transcript
        return visit

    def _build_session_factory(self, note, visit):
        """Return a mock async session factory that yields note and visit."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        note_result = MagicMock()
        note_result.scalar_one_or_none.return_value = note

        visit_result = MagicMock()
        visit_result.scalar_one_or_none.return_value = visit

        # First two execute calls return note then visit; third returns note again for update
        mock_session.execute = AsyncMock(
            side_effect=[note_result, visit_result, note_result]
        )

        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        return mock_factory, mock_session

    def test_skips_already_draft_note(self):
        """Handler returns without calling generate_soap_note if note.status == 'draft'."""
        from app.worker import _handle_generate_note

        note = self._make_note(status="draft")
        visit = self._make_visit()
        mock_factory, mock_session = self._build_session_factory(note, visit)

        mock_engine = AsyncMock()
        with patch("app.worker.create_async_engine", return_value=mock_engine):
            with patch("app.worker.async_sessionmaker", return_value=mock_factory):
                with patch("app.worker.generate_soap_note") as mock_generate:
                    asyncio.run(_handle_generate_note({"note_id": str(note.id)}))

        mock_generate.assert_not_called()

    def test_marks_failed_on_note_generation_error(self):
        """NoteGenerationError during generation results in note.status = 'failed'."""
        from app.worker import _handle_generate_note

        note = self._make_note(status="generating")
        visit = self._make_visit()
        mock_factory, mock_session = self._build_session_factory(note, visit)

        mock_engine = AsyncMock()
        with patch("app.worker.create_async_engine", return_value=mock_engine):
            with patch("app.worker.async_sessionmaker", return_value=mock_factory):
                with patch(
                    "app.worker.generate_soap_note",
                    side_effect=NoteGenerationError("Boom"),
                ):
                    asyncio.run(_handle_generate_note({"note_id": str(note.id)}))

        assert note.status == "failed"


# ---------------------------------------------------------------------------
# Tests: worker main loop
# ---------------------------------------------------------------------------

class TestWorkerLoop:
    """Tests for the run_worker() main loop message handling."""

    def _make_sqs_client(self, messages=None, receive_error=None):
        mock_sqs = MagicMock()
        if receive_error:
            mock_sqs.receive_message.side_effect = receive_error
        else:
            mock_sqs.receive_message.return_value = {"Messages": messages or []}
        mock_sqs.delete_message = MagicMock()
        mock_sqs.change_message_visibility = MagicMock()
        return mock_sqs

    def test_deletes_message_on_success(self):
        """Worker calls sqs.delete_message after successful task dispatch."""
        from app.worker import _shutdown

        note_id = str(uuid.uuid4())
        message = _make_sqs_message({"task_type": "generate_note", "note_id": note_id})
        mock_sqs = self._make_sqs_client(messages=[message])

        call_count = {"n": 0}

        def receive_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"Messages": [message]}
            _shutdown.set()
            return {"Messages": []}

        mock_sqs.receive_message.side_effect = receive_side_effect

        with patch("app.worker.boto3.client", return_value=mock_sqs):
            with patch("app.worker.get_settings") as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                mock_settings.return_value.sqs_queue_url = "https://sqs/queue"
                mock_settings.return_value.database_url = "postgresql+asyncpg://localhost/test"
                with patch("app.worker.asyncio.run"):  # don't actually run the handler
                    from app import worker as worker_mod
                    worker_mod._shutdown.clear()
                    worker_mod.run_worker()

        mock_sqs.delete_message.assert_called_once()
        worker_mod._shutdown.clear()

    def test_does_not_delete_message_on_unhandled_crash(self):
        """Worker does NOT call delete_message when dispatch raises an unexpected exception."""
        from app import worker as worker_mod

        note_id = str(uuid.uuid4())
        message = _make_sqs_message({"task_type": "generate_note", "note_id": note_id})

        call_count = {"n": 0}

        def receive_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"Messages": [message]}
            worker_mod._shutdown.set()
            return {"Messages": []}

        mock_sqs = MagicMock()
        mock_sqs.receive_message.side_effect = receive_side_effect
        mock_sqs.delete_message = MagicMock()
        mock_sqs.change_message_visibility = MagicMock()

        with patch("app.worker.boto3.client", return_value=mock_sqs):
            with patch("app.worker.get_settings") as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                mock_settings.return_value.sqs_queue_url = "https://sqs/queue"
                mock_settings.return_value.database_url = "postgresql+asyncpg://localhost/test"
                with patch("app.worker.asyncio.run", side_effect=RuntimeError("DB exploded")):
                    worker_mod._shutdown.clear()
                    worker_mod.run_worker()

        mock_sqs.delete_message.assert_not_called()
        worker_mod._shutdown.clear()
