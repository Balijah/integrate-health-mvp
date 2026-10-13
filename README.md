# Integrate Health MVP

Clinical documentation software for functional medicine providers. The application records and transcribes visits, generates draft SOAP notes and patient summaries, and lets providers review and export the result.

> This repository is designed for workflows that may contain protected health information (PHI). Running this software does not by itself establish HIPAA compliance; compliance also depends on deployment, access controls, agreements, policies, and operational practices.

## What is included

- React 18 + TypeScript provider portal
- FastAPI API with JWT authentication and PostgreSQL persistence
- Live and prerecorded transcription through Deepgram
- Streaming SOAP note generation through Claude on AWS Bedrock
- Editable SOAP sections and patient summaries, including PDF export and email delivery
- Local or S3 audio storage
- Optional SQS-backed note-generation worker in production
- AWS deployment scripts and infrastructure definitions

## Local quick start

### Prerequisites

- Docker with Compose
- Node.js 20+ for frontend work outside Docker
- Python 3.11+ for backend work outside Docker

### Start the application

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Verify the database-backed health check:

```bash
curl http://localhost:8000/health
# {"status":"healthy","db":"ok"}
```

Local URLs:

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

Deepgram operations require `DEEPGRAM_API_KEY`. SOAP generation uses the AWS SDK credential chain and requires access to the configured Bedrock model. The default Compose setup does not inject a host AWS profile into the backend container; use an explicitly configured development credential mechanism or run the backend in an authenticated local environment. Never commit credentials.

## Verification

These commands mirror the important CI checks:

```bash
# Backend
cd backend
ruff check app/
pytest tests/ -q

# Frontend
cd ../frontend
npm ci
npx tsc --noEmit
npm test -- --run
npm run build
```

CI also runs Gitleaks secret scanning. Backend CI applies migrations against PostgreSQL before running tests and enforces the current coverage floor.

## Project layout

```text
backend/
  app/
    api/          FastAPI routes
    models/       SQLAlchemy models
    schemas/      Pydantic request/response models
    services/     transcription, note generation, storage, and auth
    worker.py     optional SQS note-generation worker
  alembic/        database migrations
  tests/          backend regression tests
frontend/
  src/
    api/          typed API clients
    components/   shared UI and live recorder
    pages/        routed provider screens
    store/        authentication state
    hooks/        live and polling hooks
    utils/        frontend helpers and tests
deployment/       systemd and nginx configuration
docs/             current architecture, schema, and historical phase plan
terraform/        AWS infrastructure
whisper-service/  deprecated self-hosted transcription service
```

## Configuration

Copy `.env.example` to `.env` for local development. Important settings include:

- `DATABASE_URL`
- `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY`
- `DEEPGRAM_API_KEY`, `DEEPGRAM_MODEL`, and `TRANSCRIPTION_PROVIDER`
- `AWS_REGION`, `BEDROCK_MODEL_ID`, and Bedrock generation settings
- `STORAGE_MODE`, `S3_BUCKET_NAME`, and `S3_AUDIO_PREFIX`
- `SQS_QUEUE_URL` for the production worker
- `SES_FROM_EMAIL`, `FRONTEND_URL`, and `BACKEND_URL`

Application defaults are defined in `backend/app/config.py`; `.env.example` documents the supported environment overrides.

## Deployment

`deploy.sh` packages the backend, applies Alembic migrations, restarts the API and worker services, verifies health, deploys the frontend through nginx, and invalidates CloudFront. It targets the existing Integrate Health AWS environment and is not a generic first-time provisioning script.

Infrastructure definitions live in `terraform/`. Review the plan and environment-specific values before applying or deploying. Production changes should go through CI and the repository's deployment workflow rather than an unreviewed local command.

## Documentation

- [CLAUDE.md](CLAUDE.md) — repository instructions for Claude Code and other coding agents
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — current system and data flow
- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) — database schema reference
- [docs/PHASES.md](docs/PHASES.md) — historical MVP implementation plan
- [whisper-service/README.md](whisper-service/README.md) — deprecated Whisper service reference

The generated OpenAPI document at `/docs` is the source of truth for current API routes.

## License

Proprietary — all rights reserved.
