# CLAUDE.md

Repository instructions for Integrate Health MVP.

## Product and safety context

This application handles clinical visit audio, transcripts, SOAP notes, and patient summaries. Treat all real clinical data as PHI.

- Never log or commit PHI, credentials, tokens, `.env` files, recordings, transcripts, or generated notes.
- Do not describe the product as HIPAA compliant based on code alone. Compliance also depends on infrastructure, agreements, policies, and operations.
- Preserve authentication, ownership checks, audit behavior, input validation, and error handling at trust boundaries.
- Do not add clinical facts, diagnoses, or recommendations that are absent from the source transcript or provider input.

## Current architecture

- Frontend: React 18, TypeScript, Vite, Tailwind, React Router, Zustand
- API: FastAPI, Pydantic, async SQLAlchemy, PostgreSQL, Alembic
- Transcription: Deepgram for live and prerecorded audio
- Note generation: Claude through AWS Bedrock using streaming responses
- Storage: local filesystem in development or S3 in production
- Async work: SQS worker when configured, in-process background task fallback otherwise
- Email: AWS SES
- Production: AWS infrastructure under `terraform/`, with API and worker systemd units and nginx/CloudFront frontend delivery

See `docs/ARCHITECTURE.md` for the current flow. The generated OpenAPI document at `/docs` is the source of truth for API routes.

## Working rules

1. Read the code and every caller before changing shared behavior.
2. Prefer the smallest complete change and existing project patterns.
3. Keep database access async and scope all user-owned records to the authenticated user.
4. Add an Alembic migration for schema changes; never edit an applied migration.
5. Keep note-generation parsing defensive because model output is an external trust boundary.
6. Avoid logging request bodies, transcripts, SOAP content, patient summaries, or email content.
7. Do not add dependencies unless the standard library and installed packages are insufficient.
8. Update README, architecture, configuration examples, and tests when behavior or setup changes.

## Commands

```bash
# Start local services and apply migrations
docker compose up -d --build
docker compose exec backend alembic upgrade head

# Backend checks
cd backend
ruff check app/
pytest tests/ -q

# Frontend checks
cd ../frontend
npm ci
npx tsc --noEmit
npm test -- --run
npm run build
```

The CI workflow in `.github/workflows/ci.yml` is authoritative for required checks. Before opening a pull request, also run `git diff --check` and inspect the diff for secrets or PHI.

## Configuration

Configuration is loaded by `backend/app/config.py`. Keep `.env.example` aligned with it.

- JWT access tokens default to 8 hours; refresh tokens default to 7 days.
- Deepgram is the primary transcription provider.
- Bedrock is the active LLM provider. The direct Anthropic key remains a legacy compatibility setting.
- The Whisper and AWS Transcribe settings are deprecated compatibility fields.
- Empty `SQS_QUEUE_URL` uses the local background-task fallback.

For local SOAP generation, the backend process must have AWS credentials with access to the configured Bedrock model. Do not add static production credentials to Compose, source files, or documentation.

## Important paths

- `backend/app/main.py` — application and router registration
- `backend/app/config.py` — settings and defaults
- `backend/app/api/` — HTTP and WebSocket endpoints
- `backend/app/services/note_generation.py` — Bedrock prompt, streaming, parsing, and cost helpers
- `backend/app/services/transcription.py` — prerecorded Deepgram integration
- `backend/app/services/live_transcription.py` — live Deepgram sessions
- `backend/app/worker.py` — SQS note-generation worker
- `frontend/src/pages/VisitDetail.tsx` — recording, transcript, SOAP note, and patient-summary workflow
- `frontend/src/components/LiveRecorder/` — browser recording UI
- `backend/tests/` — backend regression suite
- `frontend/src/**/*.test.ts` — frontend unit tests

## Documentation status

`docs/PHASES.md` is historical and must not be used as current implementation guidance. Older files under `instruction_files/` are planning artifacts unless a task explicitly names one. Verify any claim from those files against current code before acting.
