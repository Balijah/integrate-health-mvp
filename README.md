# Integrate Health MVP

HIPAA-compliant AI assistant for functional medicine providers. Automates clinical documentation by capturing visit audio, transcribing it, and generating structured SOAP notes.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Setup

1. **Clone and configure environment**
   ```bash
   cd integrate-health-mvp
   cp .env.example .env
   ```

2. **Start all services**
   ```bash
   docker compose up -d
   ```

3. **Run database migration**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. **Verify setup**
   ```bash
   # Health check
   curl http://localhost:8000/health
   # Should return: {"status": "healthy"}

   # Database tables
   docker compose exec db psql -U postgres -d integrate_health -c "\dt"
   # Should show: users, visits, notes, alembic_version

   # Frontend
   open http://localhost:3000
   ```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | React application |
| Backend | http://localhost:8000 | FastAPI application |
| API Docs | http://localhost:8000/docs | Swagger documentation |
| Database | localhost:5432 | PostgreSQL 15 |

## Project Structure

```
integrate-health-mvp/
├── backend/               # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── models/       # Database models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── api/          # API routes
│   │   ├── services/     # Business logic
│   │   └── utils/        # Helpers
│   ├── alembic/          # Database migrations
│   └── tests/            # Backend tests
├── frontend/             # React + TypeScript + Vite
│   └── src/
│       ├── api/          # API client
│       ├── components/   # React components
│       ├── pages/        # Page components
│       ├── store/        # Zustand stores
│       ├── hooks/        # Custom hooks
│       └── types/        # TypeScript types
├── docs/                 # Documentation
└── uploads/              # Audio file storage
```

## Development

### Backend commands
```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Run tests
docker compose exec backend pytest

# Check logs
docker compose logs backend -f
```

### Frontend commands
```bash
# Check logs
docker compose logs frontend -f

# Run tests
docker compose exec frontend npm test
```

### Troubleshooting

**Services won't start:**
```bash
docker compose down -v
docker compose up --build
```

**Database issues:**
```bash
docker compose down -v
docker compose up db -d
docker compose exec backend alembic upgrade head
```

**Port already in use:**
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Alembic
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand
- **External:** Deepgram (transcription), Claude (note generation)

## Implementation Phases

1. **Phase 1: Project Foundation** - ✅ Complete
2. **Phase 2: Authentication** - Pending
3. **Phase 3: Visit Management** - Pending
4. **Phase 4: Audio Recording & Upload** - Pending
5. **Phase 5: Transcription** - Pending
6. **Phase 6: SOAP Note Generation** - Pending
7. **Phase 7: Polish & Testing** - Pending

See [docs/PHASES.md](docs/PHASES.md) for detailed implementation plan.

## Documentation

- [CLAUDE.md](CLAUDE.md) - Project overview and conventions
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) - Database schema
- [docs/API_SPEC.md](docs/API_SPEC.md) - API specification
- [docs/PHASES.md](docs/PHASES.md) - Implementation phases

## License

Proprietary - All rights reserved
