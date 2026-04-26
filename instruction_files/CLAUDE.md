# CLAUDE.md - Integrate Health MVP

## Project Overview

**Integrate Health** is a HIPAA-compliant AI assistant for functional medicine providers. The MVP automates clinical documentation by capturing visit audio, transcribing it, and generating structured SOAP notes.

### Core Problem
Functional medicine providers spend excessive time on documentation, leading to burnout and reduced patient capacity. Existing tools don't understand functional medicine's root-cause, longitudinal approach.

### MVP Goal
Build a working prototype that:
1. Records audio during patient visits
2. Transcribes audio after the visit ends
3. Generates draft SOAP notes using AI
4. Allows provider to edit and export notes

**Pilot Client:** Kare Health (confirmed) - single clinic pilot

---

## Quick Reference

### Current Phase
**Phase 1:** Project Foundation (see @docs/PHASES.md)

### Key Commands
```bash
# Start all services
docker-compose up -d

# Backend
docker-compose exec backend alembic upgrade head
docker-compose exec backend pytest

# Frontend
docker-compose exec frontend npm test

# Verify setup
curl http://localhost:8000/health
```

### Important URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Tech Stack

### Backend
- **Framework:** FastAPI 0.109+
- **Language:** Python 3.11+
- **Database:** PostgreSQL 15 with SQLAlchemy 2.0+
- **Auth:** JWT via python-jose
- **Migrations:** Alembic 1.13+

### Frontend
- **Framework:** React 18+ with TypeScript 5.0+
- **Build:** Vite 5.0+
- **Routing:** React Router 6+
- **State:** Zustand 4+
- **Styling:** Tailwind CSS 3.4+
- **Audio:** MediaRecorder API (native)

### External Services
- **Transcription:** Deepgram (nova-2-medical model)
- **LLM:** Anthropic Claude (Sonnet 4)

---

## Project Structure

```
integrate-health-mvp/
├── CLAUDE.md                    # This file
├── README.md
├── docker-compose.yml
├── .env.example
│
├── docs/                        # Detailed specifications
│   ├── ARCHITECTURE.md          # System design
│   ├── DATABASE_SCHEMA.md       # Schema & ERD
│   ├── API_SPEC.md             # Full API docs
│   ├── EXTERNAL_SERVICES.md    # Integration details
│   ├── SECURITY.md             # Security requirements
│   ├── TESTING.md              # Test strategy
│   ├── DEPLOYMENT.md           # Setup guide
│   └── PHASES.md               # Implementation plan
│
├── backend/
│   ├── app/
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── api/                # Route handlers
│   │   ├── services/           # Business logic
│   │   └── utils/              # Helpers
│   └── tests/
│
└── frontend/
    └── src/
        ├── api/                # API client
        ├── components/         # Reusable components
        ├── pages/              # Page components
        ├── store/              # Zustand stores
        ├── hooks/              # Custom hooks
        └── types/              # TypeScript types
```

---

## Code Style & Conventions

### Backend (Python)
- Use **async/await** for all I/O operations
- **Type hints** on all function signatures
- **Docstrings** for all public functions (Google style)
- Variable naming: `snake_case` for variables, `PascalCase` for classes
- Use Pydantic models for validation
- Prefer explicit over implicit

Example:
```python
async def transcribe_audio(audio_bytes: bytes, mime_type: str) -> dict:
    """
    Transcribe audio using Deepgram's medical model.
    
    Args:
        audio_bytes: Raw audio file bytes
        mime_type: Audio MIME type (audio/wav, audio/mp3, etc.)
    
    Returns:
        dict with 'transcript' and 'metadata'
    """
    # Implementation...
```

### Frontend (TypeScript)
- **Functional components** only (no class components)
- **TypeScript strict mode** enabled
- Use **named exports** (not default exports)
- Props interfaces defined for all components
- Tailwind CSS utility classes only (no custom CSS)
- Organize imports: React, third-party, local

Example:
```typescript
interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  maxDurationSeconds?: number;
}

export const AudioRecorder = ({ 
  onRecordingComplete,
  maxDurationSeconds = 3600 
}: AudioRecorderProps) => {
  // Implementation...
}
```

---

## Critical Constraints

### Security (HIPAA Compliance)
⚠️ **NEVER:**
- Log full transcripts or any PHI in application logs
- Store passwords in plain text
- Use default API keys in any environment
- Skip input validation on user-provided data
- Commit .env files to git

✅ **ALWAYS:**
- Hash passwords with bcrypt (12 rounds)
- Use JWT tokens with 24-hour expiration
- Validate all API inputs
- Use UUIDs for primary keys
- Reference patients by non-PHI identifier (patient_ref)

### Data Handling
- Transcripts contain PHI - handle with care
- Audio files must be encrypted at rest (future: use S3)
- No PHI in error messages or logs
- Use JSONB for structured SOAP notes

### API Standards
- All endpoints except `/auth/*` require Bearer token
- Return proper HTTP status codes
- Include pagination for list endpoints
- Rate limit: 100 requests/minute per user

---

## Reference Documentation

When implementing specific features, reference these detailed docs:

### Architecture & Design
- **@docs/ARCHITECTURE.md** - System architecture, data flow diagrams
- **@docs/DATABASE_SCHEMA.md** - Complete schema with migrations

### Implementation Details
- **@docs/API_SPEC.md** - Full API specification with examples
- **@docs/EXTERNAL_SERVICES.md** - Deepgram & Claude integration code
- **@docs/SECURITY.md** - Detailed security requirements

### Development
- **@docs/TESTING.md** - Testing strategy, fixtures, test data
- **@docs/DEPLOYMENT.md** - Setup, troubleshooting, Docker config
- **@docs/PHASES.md** - Step-by-step implementation plan

---

## Development Workflow

### Starting a New Phase

1. **Read the phase requirements**
   ```
   > Read @docs/PHASES.md
   > I'm starting Phase [N]: [Phase Name]
   > Create a detailed task list with acceptance criteria
   ```

2. **Reference relevant specs**
   ```
   > For this phase, also read:
   > @docs/API_SPEC.md (for endpoints)
   > @docs/DATABASE_SCHEMA.md (for models)
   ```

3. **Implement incrementally**
   - Build one component at a time
   - Test each component before moving forward
   - Commit after each working feature

4. **Validate completion**
   - Run tests
   - Check acceptance criteria
   - Verify with manual testing

### Example Session

```bash
# Phase 2: Authentication
> We're implementing Phase 2: Authentication
> Reference @docs/PHASES.md for requirements
> Reference @docs/API_SPEC.md for endpoint specs
> Reference @docs/SECURITY.md for security requirements
> 
> Create an implementation plan, then we'll build step-by-step
```

---

## Environment Setup

### Required API Keys
1. **Deepgram API Key** - Sign up at deepgram.com
2. **Anthropic API Key** - Sign up at console.anthropic.com

### Environment Variables
Copy `.env.example` to `.env` and fill in:
```bash
# Application
APP_SECRET_KEY=your-secret-key-min-32-chars-change-in-prod
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars

# External Services
DEEPGRAM_API_KEY=your-deepgram-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Database (default for local dev)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/integrate_health
```

Full configuration details in @docs/DEPLOYMENT.md

---

## Testing Approach

### Without Real PHI
- Use synthetic audio with scripted visits
- Pre-written transcripts for note generation
- JSON fixtures for database seeding

See @docs/TESTING.md for sample data and test strategy

---

## Common Patterns

### Error Handling (Backend)
```python
from fastapi import HTTPException, status

# Validation error
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Invalid audio format"
)

# Not found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Visit not found"
)

# Authentication error
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"}
)
```

### API Response Format
```python
# Success with data
{
  "id": "uuid",
  "field": "value",
  "created_at": "ISO timestamp"
}

# Success with pagination
{
  "items": [...],
  "total": 100,
  "limit": 20,
  "offset": 0
}

# Error
{
  "detail": "Error message"
}
```

### Database Queries (use async)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_visits(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(Visit).where(Visit.user_id == user_id)
    )
    return result.scalars().all()
```

---

## Implementation Priority

Follow phases in order (see @docs/PHASES.md):

1. ✅ Phase 1: Project Foundation
2. ⏭️ Phase 2: Authentication
3. ⏭️ Phase 3: Visit Management
4. ⏭️ Phase 4: Audio Recording & Upload
5. ⏭️ Phase 5: Transcription
6. ⏭️ Phase 6: SOAP Note Generation
7. ⏭️ Phase 7: Polish & Testing

Each phase has detailed tasks and acceptance criteria in PHASES.md

---

## Troubleshooting Quick Reference

See @docs/DEPLOYMENT.md for full troubleshooting guide.

**Services won't start:**
```bash
docker-compose down -v
docker-compose up --build
```

**Database issues:**
```bash
# Reset database
docker-compose down -v
docker-compose up db -d
docker-compose exec backend alembic upgrade head
```

**API returns 401:**
- Check JWT token is valid and not expired
- Verify Authorization header format: `Bearer <token>`

---

## Contact & Questions

For specification clarifications, ask before implementing.

For Claude Code: Follow phases sequentially. Reference relevant docs for each phase. Ask for clarification if requirements are ambiguous. Commit working code frequently.