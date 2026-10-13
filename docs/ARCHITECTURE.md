# Integrate Health Architecture

This document describes the current application on `main`. For exact routes, use the generated OpenAPI document at `/docs`; for configuration defaults, use `backend/app/config.py`.

## System overview

```text
Browser
  React + TypeScript
       |
       | HTTPS / WebSocket
       v
FastAPI API -------------------- AWS SES
  |     |     |                     email
  |     |     +----------------- AWS Bedrock
  |     |                           SOAP note + patient summary
  |     +----------------------- Deepgram
  |                                 live/prerecorded transcription
  +----------- PostgreSQL
  |
  +----------- local files or Amazon S3
  |
  +----------- Amazon SQS -> note-generation worker (production)
```

## Main visit flow

1. An authenticated provider creates or opens a visit.
2. `VisitDetail` starts the live recorder and requests a transcription session.
3. Browser audio is streamed over the application WebSocket to Deepgram.
4. Transcript segments are returned to the browser and persisted to the visit when the session ends. Prerecorded transcription endpoints also use Deepgram.
5. The provider requests a SOAP note. The API creates the note-generation job.
6. When `SQS_QUEUE_URL` is configured, the worker processes the job; otherwise the API uses its local background-task fallback.
7. The note-generation service streams a Claude response from AWS Bedrock, validates and normalizes the JSON, and stores the SOAP sections and patient summary.
8. The provider reviews and edits individual sections. The patient summary can be exported as PDF or sent through SES.

## Frontend

The frontend is a Vite React application. Current routed screens cover authentication, password reset, dashboard/patient navigation, settings, and visit details.

The primary clinical workflow lives in `frontend/src/pages/VisitDetail.tsx`. Recording UI is under `frontend/src/components/LiveRecorder/`; reusable API clients are under `frontend/src/api/`. Zustand is currently used for authentication state.

There is no separate `NewVisit`, legacy `AudioRecorder`, or `NoteEditor` flow. Those unused implementations were removed in PR #42.

## Backend

`backend/app/main.py` registers authentication, visits, transcription, notes, support, password reset, profile, and WebSocket routes.

The main service boundaries are:

- `services/auth.py` — password and token operations
- `services/transcription.py` — prerecorded Deepgram transcription
- `services/live_transcription.py` — in-memory live Deepgram connections
- `services/note_generation.py` — Bedrock prompt, streaming response handling, validation, and formatting
- `services/s3_storage.py` — S3 upload, download, presigning, and deletion
- `worker.py` — SQS job polling and note generation

PostgreSQL access uses async SQLAlchemy. Alembic migrations are the source of truth for schema evolution.

## Data and trust boundaries

- Audio, transcripts, notes, and patient summaries may contain PHI.
- Browser input, uploaded files, WebSocket frames, model output, and external-service responses are untrusted inputs.
- Authenticated data access must remain scoped to the owning user.
- Model output must be parsed and validated before persistence.
- Logs must not include PHI or secrets.
- Local storage is intended for development. Production storage uses S3 and the surrounding AWS security controls.

## Local versus production execution

Docker Compose starts PostgreSQL, FastAPI, and the Vite frontend for local development. Deepgram requires an API key. Bedrock calls require AWS credentials available to the backend process; the default Compose file does not mount a host AWS profile.

Production deployment uses the repository's AWS infrastructure and deployment scripts. The API and SQS worker run as separate systemd services. The frontend is served by nginx and distributed through CloudFront. RDS stores application data, S3 stores audio and deployment artifacts, and SES sends application email.

## Known architectural constraints

- Live Deepgram connection state is held in API process memory, so horizontal API scaling needs session affinity or an external session/stream coordinator.
- The local background-task path is a development fallback; durable production processing depends on SQS and the worker.
- `whisper-service/` and related configuration remain only as deprecated migration artifacts.
- HIPAA compliance cannot be established from this architecture document alone.
