# Local Synthetic Demo Environment

This environment is for local, screen-shared product demonstrations. Its patient, transcript, labs, and SOAP note are entirely fictional. Never add real patient information or production credentials.

## First-time setup

1. Copy `.env.demo.example` to `.env.demo` and replace every placeholder. The demo password must contain at least 12 characters.
2. Start the isolated stack:

   ```bash
   docker compose -p integrate-health-demo --env-file .env.demo \
     -f docker-compose.yml -f docker-compose.demo.yml up -d --build
   ```

3. Apply migrations and seed the canonical demo:

   ```bash
   docker compose -p integrate-health-demo --env-file .env.demo \
     -f docker-compose.yml -f docker-compose.demo.yml exec backend alembic upgrade head
   docker compose -p integrate-health-demo --env-file .env.demo \
     -f docker-compose.yml -f docker-compose.demo.yml exec backend python -m scripts.seed_demo
   ```

4. Open <http://localhost:3001> and sign in with `DEMO_USER_EMAIL` and `DEMO_USER_PASSWORD` from `.env.demo`.

The `-p integrate-health-demo` project name and `demo_postgres_data` volume isolate this data from ordinary development. Its loopback-only defaults are frontend `3001`, backend `8001`, and PostgreSQL `5433`, so it can run beside the normal development stack. Override them in `.env.demo` if needed.

## Walkthrough

After login, open `SYNTHETIC-DEMO-001` from Recent Activity. The visit starts on the summarization step because its SOAP note is already available. Select **speak** to show the labelled fictional conversation, then return to **summarize** to demonstrate the SOAP sections and section-copy/sync workflow.

Demo mode blocks recording, transcription, SOAP generation, support email, and patient-summary email in both the UI and backend. The checked-in transcript and SOAP note consume no API tokens.

## Reset between demonstrations

The reset is idempotent and deletes only visits owned by the configured demo account:

```bash
docker compose -p integrate-health-demo --env-file .env.demo \
  -f docker-compose.yml -f docker-compose.demo.yml exec backend python -m scripts.seed_demo
```

Run it after changing dates, sync state, or deleting/creating visits. SOAP textarea edits follow the current product behavior and last only in the open browser view.

## Stop or fully remove

Stop while preserving demo data:

```bash
docker compose -p integrate-health-demo --env-file .env.demo \
  -f docker-compose.yml -f docker-compose.demo.yml down
```

Remove only the isolated demo database volume (the next start requires migrations and seeding again):

```bash
docker compose -p integrate-health-demo --env-file .env.demo \
  -f docker-compose.yml -f docker-compose.demo.yml down --volumes
```

## Troubleshooting

- A startup validation error means demo mode detected production-like configuration, S3 storage, SQS, or an external API key. Clear that setting in the demo Compose configuration; do not weaken the guard.
- If ports `3001`, `8001`, or `5433` are busy, change the corresponding `DEMO_*_PORT` value in `.env.demo`.
- If login fails after changing credentials, rerun the reset command so the password hash is refreshed.
- Verify safety with `curl http://localhost:8001/health`; external-action endpoints should respond with HTTP `403` and `External integrations are disabled in demo mode.`
