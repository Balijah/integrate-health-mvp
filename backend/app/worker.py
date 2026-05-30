"""SQS worker — polls for and processes note generation tasks.

Run as a separate process alongside the API:
    python -m app.worker

One message is processed at a time, which serializes Bedrock requests and
prevents concurrent large-transcript jobs from competing for capacity.
"""

import asyncio
import json
import logging
import signal
import threading
import time
import uuid

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.note import Note
from app.models.visit import Visit
from app.services.note_generation import NoteGenerationError, generate_soap_note

logger = logging.getLogger(__name__)

_shutdown = threading.Event()


def _handle_sigterm(sig, frame):
    logger.info("[WORKER] SIGTERM received — will exit after current job completes")
    _shutdown.set()


def _heartbeat(
    sqs_client,
    queue_url: str,
    receipt_handle: str,
    stop_event: threading.Event,
) -> None:
    """Extend SQS message visibility every 4 minutes while a job is running.

    SQS visibility timeout is 10 minutes (600s). Without this, a job longer
    than 10 minutes would become visible again and be re-delivered while still
    processing. The heartbeat keeps extending it so long-running generations
    stay invisible until the worker explicitly deletes the message.
    """
    while not stop_event.wait(240):  # every 4 minutes
        if stop_event.is_set():
            break
        try:
            sqs_client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=600,
            )
            logger.debug("[WORKER HEARTBEAT] Visibility timeout extended")
        except Exception as e:
            logger.warning(f"[WORKER HEARTBEAT] Failed to extend visibility: {e}")
            break


async def _handle_generate_note(body: dict) -> None:
    """Process a generate_note task message."""
    settings = get_settings()
    note_uuid = uuid.UUID(body["note_id"])
    additional_context = body.get("additional_context", "")

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Fetch note and visit in a single read session
        async with session_factory() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_uuid))
            ).scalar_one_or_none()

            if note is None:
                logger.warning(f"[WORKER] Note {note_uuid} not found — skipping")
                return

            # Idempotency: if a previous delivery already completed generation, skip
            if note.status == "draft":
                logger.info(f"[WORKER] Note {note_uuid} already draft — idempotent skip")
                return

            visit = (
                await session.execute(select(Visit).where(Visit.id == note.visit_id))
            ).scalar_one_or_none()

            if visit is None or not visit.transcript:
                logger.error(f"[WORKER] Missing transcript for note {note_uuid} — marking failed")
                async with session_factory() as s2:
                    async with s2.begin():
                        n = (
                            await s2.execute(select(Note).where(Note.id == note_uuid))
                        ).scalar_one_or_none()
                        if n:
                            n.status = "failed"
                return

            transcript = visit.transcript

        logger.info(
            f"[WORKER] Generating note {note_uuid} transcript_len={len(transcript)}"
        )

        try:
            content = await asyncio.wait_for(
                asyncio.to_thread(generate_soap_note, transcript, additional_context),
                timeout=600.0,  # 10 minutes max; matches SQS visibility timeout
            )
            new_status = "draft"
        except (NoteGenerationError, asyncio.TimeoutError) as e:
            logger.error(f"[WORKER] Generation failed for note {note_uuid}: {e}")
            content = {}
            new_status = "failed"

        # Persist result
        async with session_factory() as session:
            async with session.begin():
                note = (
                    await session.execute(select(Note).where(Note.id == note_uuid))
                ).scalar_one_or_none()
                if note:
                    note.content = content
                    note.status = new_status
                    logger.info(f"[WORKER] Note {note_uuid} → status={new_status}")
    finally:
        await engine.dispose()


def run_worker() -> None:
    """Main worker loop — polls SQS and dispatches tasks one at a time."""
    signal.signal(signal.SIGTERM, _handle_sigterm)

    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    queue_url = settings.sqs_queue_url

    logger.info(f"[WORKER] Started — queue={queue_url}")

    while not _shutdown.is_set():
        # Long-poll: blocks up to 20s waiting for a message, reducing empty API calls
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=600,
            )
        except Exception as e:
            logger.error(f"[WORKER] SQS receive error: {e}")
            time.sleep(5)
            continue

        messages = response.get("Messages", [])
        if not messages:
            continue  # long poll returned empty; loop and poll again

        message = messages[0]
        receipt = message["ReceiptHandle"]
        body = json.loads(message["Body"])
        task_type = body.get("task_type", "unknown")

        logger.info(
            f"[WORKER] Processing task_type={task_type} note_id={body.get('note_id')}"
        )

        # Start heartbeat to keep the message invisible while the job runs
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=_heartbeat,
            args=(sqs, queue_url, receipt, stop_heartbeat),
            daemon=True,
        )
        heartbeat.start()

        try:
            if task_type == "generate_note":
                asyncio.run(_handle_generate_note(body))
            else:
                logger.warning(f"[WORKER] Unknown task_type={task_type} — discarding")

            # Success (or known-permanent failure inside the handler): delete from queue
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
            logger.info(f"[WORKER] Message deleted (success) task_type={task_type}")

        except Exception as e:
            # Unhandled crash (DB error, network blip, etc.)
            # Do NOT delete — visibility timeout expires and SQS re-delivers
            # (up to maxReceiveCount=3, then moves to DLQ)
            logger.error(
                f"[WORKER] Unhandled crash task_type={task_type}: {e}", exc_info=True
            )
        finally:
            stop_heartbeat.set()

    logger.info("[WORKER] Shutdown complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_worker()
