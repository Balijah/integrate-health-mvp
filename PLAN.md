# Phase 1: Project Foundation - Implementation Plan

## Overview
Set up complete development environment with Docker, FastAPI backend, React frontend, and PostgreSQL database.

---

## 1. Directory Structure to Create

```
integrate-health-mvp/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic settings
│   │   ├── database.py            # Async SQLAlchemy setup
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py            # User model (for migration)
│   │   │   ├── visit.py           # Visit model (for migration)
│   │   │   └── note.py            # Note model (for migration)
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   └── utils/
│   │       └── __init__.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── conftest.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── .gitkeep
│   │   ├── components/
│   │   │   └── .gitkeep
│   │   ├── pages/
│   │   │   └── .gitkeep
│   │   ├── store/
│   │   │   └── .gitkeep
│   │   ├── hooks/
│   │   │   └── .gitkeep
│   │   ├── types/
│   │   │   └── .gitkeep
│   │   ├── utils/
│   │   │   └── .gitkeep
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── vite-env.d.ts
│   ├── public/
│   │   └── .gitkeep
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── Dockerfile
│   └── .eslintrc.cjs
│
├── uploads/                       # Audio file storage (gitignored)
│   └── .gitkeep
├── scripts/
│   └── .gitkeep
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 2. Configuration Files Content Outline

### Root Level Files

#### `.gitignore`
- Python: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `venv/`, `.venv/`
- Node: `node_modules/`, `dist/`, `.npm/`
- Environment: `.env`, `.env.local`, `.env.*.local`
- IDE: `.vscode/`, `.idea/`
- OS: `.DS_Store`, `Thumbs.db`
- Project: `uploads/*`, `!uploads/.gitkeep`

#### `.env.example`
```
# Application
APP_SECRET_KEY=your-secret-key-min-32-chars-change-in-prod
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/integrate_health
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=integrate_health

# External Services (not needed for Phase 1)
DEEPGRAM_API_KEY=your-deepgram-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

#### `docker-compose.yml`
- **db service**: PostgreSQL 15, port 5432, volume for data persistence
- **backend service**: FastAPI on port 8000, depends on db, volume mounts for live reload
- **frontend service**: React/Vite on port 3000, depends on backend

### Backend Files

#### `backend/requirements.txt`
```
# Web Framework
fastapi==0.109.2
uvicorn[standard]==0.27.1
python-multipart==0.0.9

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
alembic==1.13.1

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.2

# Validation
pydantic==2.6.1
pydantic-settings==2.1.0
email-validator==2.1.0

# Testing
pytest==8.0.0
pytest-asyncio==0.23.4
httpx==0.26.0

# Utils
python-dotenv==1.0.1
```

#### `backend/Dockerfile`
- Base: `python:3.11-slim`
- Working directory: `/app`
- Copy requirements, install dependencies
- Copy app code
- Expose port 8000
- CMD: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

#### `backend/app/config.py`
- Pydantic BaseSettings class
- Environment variables: DATABASE_URL, APP_SECRET_KEY, JWT_SECRET_KEY, DEBUG
- JWT settings: algorithm HS256, expiration 24 hours

#### `backend/app/database.py`
- Async engine creation with asyncpg
- AsyncSessionLocal with sessionmaker
- Base declarative class
- `get_db()` async generator for dependency injection

#### `backend/app/main.py`
- FastAPI app instance
- CORS middleware (allow localhost:3000)
- Health check endpoint: `GET /health` returning `{"status": "healthy"}`
- API router prefix: `/api/v1`

### Frontend Files

#### `frontend/package.json`
```json
{
  "name": "integrate-health-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.1.0",
    "vitest": "^1.2.2"
  }
}
```

#### `frontend/tsconfig.json`
- Target: ES2020
- Module: ESNext
- Strict mode: true
- JSX: react-jsx
- Include: `src`

#### `frontend/vite.config.ts`
- React plugin
- Server port: 3000
- Proxy `/api` to `http://backend:8000`

#### `frontend/tailwind.config.js`
- Content: `./index.html`, `./src/**/*.{js,ts,jsx,tsx}`
- Theme extensions for brand colors (future)

#### `frontend/Dockerfile`
- Base: `node:20-slim`
- Working directory: `/app`
- Copy package.json, install dependencies
- Copy source
- Expose port 3000
- CMD: `npm run dev -- --host`

#### `frontend/src/App.tsx`
- React Router setup
- Placeholder home page with "Integrate Health MVP" title
- Basic layout structure

#### `frontend/src/main.tsx`
- ReactDOM.createRoot
- StrictMode wrapper
- App component import

---

## 3. Database Tables (from DATABASE_SCHEMA.md)

### Table: `users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL |
| full_name | VARCHAR(255) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |
| updated_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |

**Indexes:**
- `idx_users_email` UNIQUE on email
- `idx_users_active` on is_active WHERE is_active = TRUE

### Table: `visits`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| user_id | UUID | FK users(id) ON DELETE CASCADE, NOT NULL |
| patient_ref | VARCHAR(255) | NOT NULL |
| visit_date | TIMESTAMP WITH TIME ZONE | NOT NULL |
| chief_complaint | TEXT | |
| audio_file_path | VARCHAR(500) | |
| audio_duration_seconds | INTEGER | |
| transcript | TEXT | |
| transcription_status | VARCHAR(50) | DEFAULT 'pending' |
| created_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |
| updated_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |

**Indexes:**
- `idx_visits_user_id` on user_id
- `idx_visits_status` on transcription_status
- `idx_visits_date` on visit_date DESC
- `idx_visits_patient_ref` on patient_ref

### Table: `notes`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| visit_id | UUID | FK visits(id) ON DELETE CASCADE, NOT NULL |
| content | JSONB | NOT NULL |
| note_type | VARCHAR(50) | DEFAULT 'soap' |
| status | VARCHAR(50) | DEFAULT 'draft' |
| created_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |
| updated_at | TIMESTAMP WITH TIME ZONE | DEFAULT NOW() |

**Indexes:**
- `idx_notes_visit_id` on visit_id
- `idx_notes_status` on status
- `idx_notes_content_gin` GIN on content

---

## 4. Verification Checklist

### Docker Services
- [ ] `docker-compose up -d` starts all 3 services without errors
- [ ] `docker-compose ps` shows db, backend, frontend all "Up"
- [ ] No error logs in `docker-compose logs`

### Backend Health
- [ ] `curl http://localhost:8000/health` returns `{"status": "healthy"}`
- [ ] `curl http://localhost:8000/docs` returns Swagger UI
- [ ] CORS allows requests from localhost:3000

### Frontend
- [ ] `curl http://localhost:3000` returns HTML
- [ ] Browser shows placeholder page at http://localhost:3000
- [ ] No console errors in browser

### Database
- [ ] `docker-compose exec backend alembic upgrade head` runs without errors
- [ ] `docker-compose exec db psql -U postgres -d integrate_health -c "\dt"` shows:
  - users
  - visits
  - notes
  - alembic_version
- [ ] All indexes created (verify with `\di`)
- [ ] Database connection works: `docker-compose exec backend python -c "from app.database import engine; print('Connected')"`

### File Structure
- [ ] All directories exist as specified
- [ ] All __init__.py files present
- [ ] .gitignore properly excludes .env, node_modules, __pycache__, uploads/*

---

## 5. Implementation Order

1. **Create directory structure** - All folders and placeholder files
2. **Root config files** - .gitignore, .env.example, docker-compose.yml
3. **Backend setup** - Dockerfile, requirements.txt, config.py, database.py, main.py
4. **Database models** - user.py, visit.py, note.py (SQLAlchemy models)
5. **Alembic setup** - alembic.ini, env.py, initial migration
6. **Frontend setup** - package.json, tsconfig, vite.config, tailwind
7. **Frontend code** - index.html, main.tsx, App.tsx, index.css
8. **Docker verification** - Build and test all services
9. **Database migration** - Run alembic upgrade head
10. **Final verification** - All acceptance criteria

---

## 6. Files to Create (Full List)

### Backend (18 files)
1. `backend/Dockerfile`
2. `backend/requirements.txt`
3. `backend/alembic.ini`
4. `backend/app/__init__.py`
5. `backend/app/config.py`
6. `backend/app/database.py`
7. `backend/app/main.py`
8. `backend/app/models/__init__.py`
9. `backend/app/models/user.py`
10. `backend/app/models/visit.py`
11. `backend/app/models/note.py`
12. `backend/app/schemas/__init__.py`
13. `backend/app/api/__init__.py`
14. `backend/app/services/__init__.py`
15. `backend/app/utils/__init__.py`
16. `backend/alembic/env.py`
17. `backend/alembic/script.py.mako`
18. `backend/alembic/versions/001_initial_schema.py`
19. `backend/tests/__init__.py`
20. `backend/tests/conftest.py`

### Frontend (16 files)
1. `frontend/Dockerfile`
2. `frontend/package.json`
3. `frontend/tsconfig.json`
4. `frontend/tsconfig.node.json`
5. `frontend/vite.config.ts`
6. `frontend/tailwind.config.js`
7. `frontend/postcss.config.js`
8. `frontend/.eslintrc.cjs`
9. `frontend/index.html`
10. `frontend/src/main.tsx`
11. `frontend/src/App.tsx`
12. `frontend/src/index.css`
13. `frontend/src/vite-env.d.ts`
14. `frontend/src/api/.gitkeep`
15. `frontend/src/components/.gitkeep`
16. `frontend/src/pages/.gitkeep`
17. `frontend/src/store/.gitkeep`
18. `frontend/src/hooks/.gitkeep`
19. `frontend/src/types/.gitkeep`
20. `frontend/src/utils/.gitkeep`
21. `frontend/public/.gitkeep`

### Root (5 files)
1. `.gitignore`
2. `.env.example`
3. `docker-compose.yml`
4. `README.md` (update existing or create)
5. `uploads/.gitkeep`
6. `scripts/.gitkeep`

**Total: ~44 files to create**

---

## Ready for Implementation

This plan covers all Phase 1 requirements. Upon approval, I will implement in the order specified above, verifying each component works before moving to the next.
