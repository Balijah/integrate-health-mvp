# Implementation Phases - Integrate Health MVP

## Overview

Build the MVP in 7 sequential phases over approximately 20 days. Each phase builds on the previous one and has clear acceptance criteria.

**Total Estimated Time:** 17-20 days
**Approach:** One phase at a time, test before moving forward

---

## Phase 1: Project Foundation

**Duration:** Days 1-2
**Goal:** Set up complete development environment

### Tasks

1. **Create Project Structure**
   ```bash
   mkdir -p backend/app/{models,schemas,api,services,utils}
   mkdir -p backend/tests
   mkdir -p backend/alembic/versions
   mkdir -p frontend/src/{api,components,pages,store,hooks,types,utils}
   mkdir -p frontend/public
   mkdir -p docs
   mkdir -p scripts
   ```

2. **Create Configuration Files**
   - `.gitignore` (Python, Node, env files)
   - `.env.example` (template with all required vars)
   - `docker-compose.yml` (postgres, backend, frontend)
   - `backend/Dockerfile`
   - `backend/requirements.txt`
   - `frontend/Dockerfile`
   - `frontend/package.json`
   - `frontend/tsconfig.json`
   - `frontend/vite.config.ts`
   - `frontend/tailwind.config.js`

3. **Backend Core Setup**
   - `backend/app/config.py` - Settings management with Pydantic
   - `backend/app/database.py` - Async SQLAlchemy setup
   - `backend/app/main.py` - FastAPI app with CORS, health check

4. **Frontend Core Setup**
   - `frontend/src/main.tsx` - React entry point
   - `frontend/src/App.tsx` - Root component with routing
   - `frontend/index.html` - HTML template

5. **Database Setup**
   - `alembic.ini` - Alembic configuration
   - `alembic/env.py` - Alembic environment
   - Initial migration: Create users, visits, notes tables
   - See @docs/DATABASE_SCHEMA.md for exact schema

### Acceptance Criteria

- [ ] `docker-compose up` starts all services without errors
- [ ] `GET http://localhost:8000/health` returns `{"status": "healthy"}`
- [ ] Frontend loads at http://localhost:3000 (shows placeholder page)
- [ ] Database tables created: `docker-compose exec backend alembic upgrade head`
- [ ] Can connect to database: `docker-compose exec backend python -c "from app.database import engine; print('Connected')"`

### Commands to Verify

```bash
# Health check
curl http://localhost:8000/health

# Database
docker-compose exec db psql -U postgres -d integrate_health -c "\dt"
# Should show: users, visits, notes, alembic_version

# Frontend
curl http://localhost:3000
# Should return HTML
```

---

## Phase 2: Authentication

**Duration:** Days 3-4
**Goal:** User registration, login, and JWT auth working

### Tasks

1. **Backend - Auth Models & Schemas**
   - `backend/app/models/user.py` - User SQLAlchemy model
   - `backend/app/schemas/user.py` - UserCreate, UserResponse Pydantic models
   - `backend/app/schemas/auth.py` - LoginRequest, TokenResponse

2. **Backend - Auth Service**
   - `backend/app/services/auth.py`
     - `hash_password(password: str) -> str` - Bcrypt hashing
     - `verify_password(plain: str, hashed: str) -> bool`
     - `create_access_token(user_id: str) -> str` - JWT generation
     - `authenticate_user(email: str, password: str) -> User`

3. **Backend - Auth Endpoints**
   - `backend/app/api/deps.py` - `get_current_user()` dependency
   - `backend/app/api/auth.py`:
     - `POST /auth/register`
     - `POST /auth/login`
     - `GET /auth/me`

4. **Frontend - Auth Store**
   - `frontend/src/store/authStore.ts` - Zustand store for token, user

5. **Frontend - Auth Pages**
   - `frontend/src/pages/Login.tsx` - Login form
   - `frontend/src/api/auth.ts` - Auth API calls
   - Protected route wrapper component

### Acceptance Criteria

- [ ] Can register new user: `POST /auth/register` with email, password, full_name
- [ ] Can login: `POST /auth/login` returns valid JWT token
- [ ] Token stored in frontend (localStorage or cookie)
- [ ] Protected endpoints reject requests without token (401)
- [ ] `GET /auth/me` returns current user info
- [ ] Frontend redirects to /login when unauthenticated
- [ ] Token persists across page refresh
- [ ] Password hashing uses bcrypt with 12 rounds

### Test Sequence

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","full_name":"Test User"}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
# Save the access_token

# 3. Get current user
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Phase 3: Visit Management

**Duration:** Days 5-6
**Goal:** CRUD operations for visits working

### Tasks

1. **Backend - Visit Models & Schemas**
   - `backend/app/models/visit.py` - Visit SQLAlchemy model
   - `backend/app/schemas/visit.py` - VisitCreate, VisitResponse, VisitList

2. **Backend - Visit Endpoints**
   - `backend/app/api/visits.py`:
     - `POST /visits` - Create new visit
     - `GET /visits` - List visits (with pagination)
     - `GET /visits/{visit_id}` - Get single visit
     - `DELETE /visits/{visit_id}` - Delete visit

3. **Frontend - Visit Store**
   - `frontend/src/store/visitStore.ts` - Zustand store for visits

4. **Frontend - Visit Pages**
   - `frontend/src/pages/Dashboard.tsx` - List of visits
   - `frontend/src/pages/NewVisit.tsx` - Create visit form
   - `frontend/src/pages/VisitDetail.tsx` - Visit details view
   - `frontend/src/api/visits.ts` - Visit API calls

5. **Frontend - Components**
   - `frontend/src/components/Layout/Layout.tsx` - App layout with header
   - `frontend/src/components/common/Button.tsx` - Reusable button
   - `frontend/src/components/common/Input.tsx` - Reusable input
   - `frontend/src/components/common/Card.tsx` - Reusable card

### Acceptance Criteria

- [ ] Can create new visit with patient_ref, visit_date, chief_complaint
- [ ] Dashboard shows list of all visits for logged-in user
- [ ] Click on visit navigates to detail page
- [ ] Visit detail shows full visit information
- [ ] Can delete visit (soft delete or hard delete)
- [ ] Visit list is paginated (20 per page)
- [ ] Visits are ordered by visit_date DESC (most recent first)
- [ ] Only user's own visits are visible

### Test Sequence

```bash
# 1. Create visit
curl -X POST http://localhost:8000/api/v1/visits \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_ref":"PT-001","visit_date":"2024-01-15T14:00:00Z","chief_complaint":"Fatigue"}'

# 2. List visits
curl http://localhost:8000/api/v1/visits?limit=20&offset=0 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Get single visit
curl http://localhost:8000/api/v1/visits/VISIT_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. Delete visit
curl -X DELETE http://localhost:8000/api/v1/visits/VISIT_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Phase 4: Audio Recording & Upload

**Duration:** Days 7-9
**Goal:** Record audio in browser and upload to backend

### Tasks

1. **Frontend - Audio Recorder Hook**
   - `frontend/src/hooks/useAudioRecorder.ts`
     - Use MediaRecorder API
     - States: idle, recording, paused, stopped
     - Timer tracking
     - Blob output

2. **Frontend - Audio Recorder Component**
   - `frontend/src/components/AudioRecorder/AudioRecorder.tsx`
     - Start/Stop/Pause buttons
     - Timer display (MM:SS format)
     - Audio preview player
     - File size indicator

3. **Backend - Audio Upload**
   - `backend/app/api/visits.py`:
     - `POST /visits/{visit_id}/audio` - Upload audio file
   - `backend/app/utils/audio.py` - Audio validation utilities
   - File storage in ./uploads directory
   - Update visit record with audio_file_path

4. **Frontend - Integration**
   - Add AudioRecorder to NewVisit page
   - Upload audio after recording complete
   - Show upload progress

### Acceptance Criteria

- [ ] Can record audio using browser microphone
- [ ] Recording shows elapsed time (updates every second)
- [ ] Can stop recording and preview audio
- [ ] Audio blob is valid (WAV, WebM, or MP3)
- [ ] Can upload audio to backend
- [ ] Backend saves audio file to disk
- [ ] Backend updates visit record with file path
- [ ] Audio file is under max size (100MB)
- [ ] Supports formats: WAV, MP3, M4A, WEBM
- [ ] Error handling for permission denied, no microphone, etc.

### Test Flow

```bash
# In browser:
# 1. Go to New Visit page
# 2. Fill in visit details
# 3. Click "Start Recording"
# 4. Speak for 30 seconds
# 5. Click "Stop Recording"
# 6. Preview audio playback
# 7. Click "Upload"
# 8. Verify visit detail shows audio uploaded

# Backend verification:
ls ./uploads/
# Should show audio file

# Database verification:
docker-compose exec db psql -U postgres -d integrate_health \
  -c "SELECT audio_file_path, audio_duration_seconds FROM visits WHERE audio_file_path IS NOT NULL;"
```

---

## Phase 5: Transcription

**Duration:** Days 10-12
**Goal:** Transcribe audio using Deepgram

### Tasks

1. **Backend - Deepgram Integration**
   - `backend/app/services/transcription.py`
     - `transcribe_audio(audio_bytes, mime_type) -> dict`
     - Use Deepgram API (nova-2-medical model)
     - Enable diarization, smart formatting
   - Add Deepgram API key to .env

2. **Backend - Transcription Endpoints**
   - `backend/app/api/transcription.py`:
     - `POST /visits/{visit_id}/transcribe` - Trigger transcription
     - `GET /visits/{visit_id}/transcription/status` - Check status

3. **Backend - Async Processing**
   - Update visit.transcription_status: pending → transcribing → completed
   - Store transcript in visit.transcript field
   - Error handling with retry logic

4. **Frontend - Status Polling**
   - Poll transcription status every 5 seconds
   - Display progress indicator
   - Show transcript when complete

5. **Frontend - UI Updates**
   - Update VisitDetail to show transcript
   - Add loading states
   - Error messages for failed transcription

### Acceptance Criteria

- [ ] Uploaded audio triggers transcription automatically
- [ ] Deepgram API called with correct parameters (model: nova-2-medical)
- [ ] Transcription status updates: pending → transcribing → completed
- [ ] Completed transcript stored in database
- [ ] Frontend polls status endpoint and displays transcript
- [ ] Diarization enabled (speaker labels: Speaker 0, Speaker 1)
- [ ] Errors logged and user notified
- [ ] Can retry failed transcriptions

### Test Sequence

```bash
# 1. Upload audio (from Phase 4)
# Should automatically trigger transcription

# 2. Check status
curl http://localhost:8000/api/v1/visits/VISIT_ID/transcription/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Wait and check again (should show completed)
curl http://localhost:8000/api/v1/visits/VISIT_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
# Should include transcript field

# 4. Verify transcript in database
docker-compose exec db psql -U postgres -d integrate_health \
  -c "SELECT id, LEFT(transcript, 100) FROM visits WHERE transcript IS NOT NULL;"
```

---

## Phase 6: SOAP Note Generation

**Duration:** Days 13-16
**Goal:** Generate structured SOAP notes using Claude

### Tasks

1. **Backend - Note Model & Schemas**
   - `backend/app/models/note.py` - Note SQLAlchemy model
   - `backend/app/schemas/note.py` - NoteCreate, NoteResponse, SOAPContent

2. **Backend - Claude Integration**
   - `backend/app/services/note_generation.py`
     - `generate_soap_note(transcript, context) -> dict`
     - Use Claude Sonnet 4 model
     - Functional medicine prompt
     - Parse JSONB structure
   - Add Anthropic API key to .env

3. **Backend - Note Endpoints**
   - `backend/app/api/notes.py`:
     - `POST /visits/{visit_id}/notes/generate` - Generate note
     - `GET /visits/{visit_id}/notes` - Get note
     - `PUT /visits/{visit_id}/notes/{note_id}` - Update note
     - `POST /visits/{visit_id}/notes/{note_id}/export` - Export note

4. **Frontend - Note Editor Component**
   - `frontend/src/components/NoteEditor/NoteEditor.tsx`
     - Collapsible sections (S, O, A, P)
     - Editable text areas
     - Auto-save functionality
   - `frontend/src/api/notes.ts` - Note API calls

5. **Frontend - Note Editor Page**
   - `frontend/src/pages/NoteEditor.tsx` - Full page editor
   - Copy note button
   - Export as markdown button

### Acceptance Criteria

- [ ] Can trigger note generation from visit detail page
- [ ] Claude API called with transcript and prompt
- [ ] Generated note follows SOAP structure (see DATABASE_SCHEMA.md)
- [ ] Note stored in database with status='draft'
- [ ] Note displays in structured editor
- [ ] Can edit any section of the note
- [ ] Can mark note as 'reviewed'
- [ ] Can copy note to clipboard
- [ ] Can export note as markdown format
- [ ] Note includes metadata (model version, confidence)

### Test Sequence

```bash
# 1. Generate note
curl -X POST http://localhost:8000/api/v1/visits/VISIT_ID/notes/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"additional_context":"Patient has history of Hashimoto'"}'

# 2. Get generated note
curl http://localhost:8000/api/v1/visits/VISIT_ID/notes \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Update note
curl -X PUT http://localhost:8000/api/v1/visits/VISIT_ID/notes/NOTE_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":{...},"status":"reviewed"}'

# 4. Export note
curl -X POST http://localhost:8000/api/v1/visits/VISIT_ID/notes/NOTE_ID/export \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format":"markdown"}'
```

---

## Phase 7: Polish & Testing

**Duration:** Days 17-20
**Goal:** Production-ready MVP

### Tasks

1. **UI/UX Polish**
   - Add loading states to all async operations
   - Consistent error messages
   - Form validation on all inputs
   - Responsive design (mobile-friendly)
   - Accessibility improvements (ARIA labels, keyboard navigation)

2. **Error Handling**
   - Global error boundary in React
   - Toast notifications for errors
   - Retry mechanisms for failed API calls
   - Graceful degradation

3. **Testing**
   - Backend unit tests:
     - `tests/test_auth.py` - Auth service tests
     - `tests/test_visits.py` - Visit CRUD tests
     - `tests/test_transcription.py` - Transcription tests
     - `tests/test_notes.py` - Note generation tests
   - Target: 70%+ code coverage for services
   - Integration tests for critical flows

4. **Documentation**
   - Update README.md with setup instructions
   - API documentation (FastAPI auto-generates /docs)
   - Environment variable documentation
   - Troubleshooting guide

5. **Security Review**
   - Verify no PHI in logs
   - Check all inputs are validated
   - Ensure passwords are never logged
   - Review JWT expiration
   - Rate limiting on login endpoint

6. **Performance Optimization**
   - Add database indexes
   - Optimize slow queries
   - Frontend code splitting
   - Image optimization

### Acceptance Criteria

- [ ] All critical user flows work end-to-end without errors
- [ ] Loading indicators show for all async operations
- [ ] Error messages are user-friendly and actionable
- [ ] Forms validate inputs before submission
- [ ] Unit tests pass: `docker-compose exec backend pytest`
- [ ] Code coverage > 70% for services
- [ ] No PHI appears in application logs
- [ ] API documentation accessible at /docs
- [ ] README has complete setup instructions
- [ ] Mobile responsive (test on phone screen)

### Complete End-to-End Test

```
1. Register new account
2. Login successfully
3. Create new visit with patient info
4. Record 1-minute audio
5. Upload audio
6. Wait for transcription (check status polling works)
7. Generate SOAP note
8. Edit note (change a section)
9. Mark note as reviewed
10. Export note to clipboard
11. Logout
12. Login again (verify persistence)
```

---

## Development Workflow

### Daily Routine

```bash
# Morning: Start services
docker-compose up -d

# Pull latest changes
git pull

# Check service health
curl http://localhost:8000/health

# Work on current phase tasks...

# Run tests before committing
docker-compose exec backend pytest
docker-compose exec frontend npm test

# Commit working code
git add .
git commit -m "Implement [feature]"
git push
```

### Between Phases

```bash
# Review acceptance criteria
# ✓ Check off completed items

# Tag release
git tag phase-N-complete
git push --tags

# Clean slate for next phase
docker-compose down
docker-compose up --build
docker-compose exec backend alembic upgrade head
```

---

## Reference Other Documentation

- **@docs/API_SPEC.md** - Full API endpoint specifications
- **@docs/DATABASE_SCHEMA.md** - Complete schema and migrations
- **@docs/EXTERNAL_SERVICES.md** - Deepgram & Claude integration details
- **@docs/SECURITY.md** - Security requirements and best practices
- **@docs/TESTING.md** - Test strategy, fixtures, sample data
- **@docs/DEPLOYMENT.md** - Docker setup, troubleshooting, environment variables

---

Follow phases sequentially. Complete all acceptance criteria before moving to next phase.