# Architecture - Integrate Health MVP

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│                   React + TypeScript                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   Auth    │  │  Record   │  │  Notes    │  │  History  │    │
│  │  Pages    │  │   View    │  │  Editor   │  │   View    │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
│                   FastAPI + Python                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   Auth    │  │  Visits   │  │ Transcribe│  │   Notes   │    │
│  │  Service  │  │  Service  │  │  Service  │  │  Service  │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌───────────┐   ┌───────────┐   ┌───────────┐
       │ PostgreSQL│   │ Deepgram  │   │  Claude   │
       │  Database │   │    API    │   │    API    │
       └───────────┘   └───────────┘   └───────────┘
```

---

## Data Flow

### Complete Visit Flow

```
┌─────────────┐
│  Provider   │
│   opens     │
│  new visit  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ 1. Create Visit Record  │
│    - Patient ref        │
│    - Visit date         │
│    - Chief complaint    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ 2. Record Audio         │
│    - Browser captures   │
│    - Show timer         │
│    - Stop recording     │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ 3. Upload Audio         │
│    - POST audio blob    │
│    - Store file         │
│    - Update visit       │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ 4. Transcribe (Async)   │
│    - Send to Deepgram   │
│    - Poll for status    │
│    - Store transcript   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ 5. Generate Note        │
│    - Send to Claude     │
│    - Parse SOAP JSON    │
│    - Store structured   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│ 6. Edit & Export        │
│    - Provider reviews   │
│    - Makes edits        │
│    - Exports note       │
└─────────────────────────┘
```

---

## Component Breakdown

### Frontend Components

#### Authentication Flow
```
Login Page
    │
    ├─> POST /auth/login
    │   └─> Receive JWT token
    │
    ├─> Store token (httpOnly cookie or localStorage)
    │
    └─> Redirect to Dashboard
```

#### Recording Flow
```
NewVisit Page
    │
    ├─> AudioRecorder Component
    │   ├─> MediaRecorder API
    │   ├─> Timer display
    │   └─> Blob output
    │
    ├─> POST /visits/{id}/audio
    │   └─> Upload audio file
    │
    └─> Navigate to Visit Detail
```

#### Note Viewing Flow
```
VisitDetail Page
    │
    ├─> Poll GET /visits/{id}/transcription/status
    │   └─> Show progress
    │
    ├─> When complete: POST /visits/{id}/notes/generate
    │
    ├─> GET /visits/{id}/notes
    │   └─> Display in NoteEditor
    │
    └─> Allow edits and export
```

---

### Backend Services

#### Auth Service
**Responsibilities:**
- User registration
- Password hashing (bcrypt, 12 rounds)
- JWT token generation
- Token validation

**Key Functions:**
```python
async def register_user(email, password, full_name) -> User
async def authenticate_user(email, password) -> User
def create_access_token(user_id: str) -> str
async def get_current_user(token: str) -> User
```

---

#### Visit Service
**Responsibilities:**
- Visit CRUD operations
- Audio file management
- Status tracking

**Key Functions:**
```python
async def create_visit(user_id, patient_ref, visit_date) -> Visit
async def list_visits(user_id, filters) -> List[Visit]
async def get_visit(visit_id) -> Visit
async def save_audio_file(visit_id, audio_bytes) -> str
async def delete_visit(visit_id) -> None
```

---

#### Transcription Service
**Responsibilities:**
- Deepgram API integration
- Async transcription processing
- Status updates

**Key Functions:**
```python
async def transcribe_audio(audio_bytes, mime_type) -> dict
async def start_transcription(visit_id) -> None
async def get_transcription_status(visit_id) -> str
async def store_transcript(visit_id, transcript) -> None
```

**Deepgram Configuration:**
- Model: `nova-2-medical` (medical terminology optimized)
- Diarization: Enabled (speaker separation)
- Smart formatting: Enabled (punctuation, capitalization)
- Utterances: Enabled (sentence boundaries)

---

#### Note Generation Service
**Responsibilities:**
- Claude API integration
- SOAP note structure generation
- JSON parsing and validation

**Key Functions:**
```python
async def generate_soap_note(transcript, context) -> dict
async def create_note_from_visit(visit_id, context) -> Note
async def update_note(note_id, content) -> Note
async def export_note(note_id, format) -> str
```

**Claude Configuration:**
- Model: `claude-sonnet-4-20250514`
- Max tokens: 4096
- Temperature: 0.3 (for consistency)
- System prompt: Functional medicine specialist

---

## Database Architecture

### Entity Relationships

```
        ┌─────────────┐
        │    users    │
        │ (providers) │
        └──────┬──────┘
               │ 1
               │
               │ *
        ┌──────┴──────┐
        │   visits    │
        │  (patient   │
        │   visits)   │
        └──────┬──────┘
               │ 1
               │
               │ 1
        ┌──────┴──────┐
        │    notes    │
        │    (SOAP)   │
        └─────────────┘
```

### Key Design Decisions

1. **UUIDs for Primary Keys**
   - Better for distributed systems
   - No sequential enumeration
   - URL-safe identifiers

2. **JSONB for SOAP Notes**
   - Flexible structure
   - Queryable with PostgreSQL JSONB operators
   - Easy to evolve schema

3. **Soft Deletes (Future)**
   - Not in MVP
   - Add `deleted_at` timestamp
   - Preserve audit trail

4. **No Patient Table**
   - MVP uses `patient_ref` string
   - Non-PHI identifier
   - Future: full patient management

---

## API Architecture

### RESTful Design

**Resource Hierarchy:**
```
/api/v1
  /auth
    POST /register
    POST /login
    GET  /me
  
  /visits
    POST   /                    Create visit
    GET    /                    List visits
    GET    /{id}                Get visit
    DELETE /{id}                Delete visit
    
    POST   /{id}/audio          Upload audio
    GET    /{id}/transcription/status
    
    POST   /{id}/notes/generate
    GET    /{id}/notes
    PUT    /{id}/notes/{note_id}
    POST   /{id}/notes/{note_id}/export
```

### Authentication Flow

```
Client                   Backend
  │                         │
  │  POST /auth/login       │
  ├────────────────────────>│
  │                         │
  │    Validate credentials │
  │    Generate JWT         │
  │                         │
  │  <JWT Token>            │
  │<────────────────────────┤
  │                         │
  │  GET /visits            │
  │  Authorization: Bearer  │
  ├────────────────────────>│
  │                         │
  │    Validate JWT         │
  │    Get user from token  │
  │    Query user's visits  │
  │                         │
  │  <Visit List>           │
  │<────────────────────────┤
```

### Async Processing

**Background Tasks Pattern:**
```
Client                   API                  Worker
  │                       │                      │
  │  POST /audio          │                      │
  ├──────────────────────>│                      │
  │                       │                      │
  │  <202 Accepted>       │                      │
  │<────────────────────  │                      │
  │                       │   Trigger task       │
  │                       ├─────────────────────>│
  │                       │                      │
  │                       │              Process │
  │                       │              Update  │
  │                       │              Status  │
  │                       │                      │
  │  GET /status          │                      │
  ├──────────────────────>│                      │
  │                       │   Check DB           │
  │  <Status: complete>   │                      │
  │<────────────────────  │                      │
```

Note: MVP uses inline processing, not true background workers.
Future: Add Celery or FastAPI BackgroundTasks.

---

## Security Architecture

### Authentication & Authorization

```
┌──────────────────────────────────────────────────┐
│              JWT Token Structure                  │
├──────────────────────────────────────────────────┤
│ Header:                                          │
│   {                                              │
│     "alg": "HS256",                              │
│     "typ": "JWT"                                 │
│   }                                              │
│                                                  │
│ Payload:                                         │
│   {                                              │
│     "sub": "user_id (UUID)",                     │
│     "exp": "expiration_timestamp",               │
│     "iat": "issued_at_timestamp"                 │
│   }                                              │
│                                                  │
│ Signature: HMACSHA256(header + payload + secret) │
└──────────────────────────────────────────────────┘
```

### Data Protection Layers

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  - Input validation                     │
│  - Authentication checks                │
│  - Authorization rules                  │
└────────────┬────────────────────────────┘
             │
┌────────────┴────────────────────────────┐
│         Transport Layer                 │
│  - HTTPS (TLS 1.3)                      │
│  - Certificate pinning (production)     │
└────────────┬────────────────────────────┘
             │
┌────────────┴────────────────────────────┐
│         Storage Layer                   │
│  - Database encryption at rest          │
│  - Encrypted audio files                │
│  - Secure key management                │
└─────────────────────────────────────────┘
```

---

## Scalability Considerations

### Current MVP Limits
- Single server deployment
- Inline processing (no queue)
- Local file storage
- Single database instance

### Future Scaling Path

**Phase 1: Horizontal Backend**
```
Load Balancer
    │
    ├─> Backend Instance 1
    ├─> Backend Instance 2
    └─> Backend Instance 3
         │
         └─> Shared PostgreSQL
             Shared S3 Storage
```

**Phase 2: Async Processing**
```
API Servers ──> Redis Queue ──> Celery Workers
                                     │
                                     ├─> Transcription Workers
                                     └─> Note Generation Workers
```

**Phase 3: Multi-Tenant**
```
Tenant A ──> Database A
Tenant B ──> Database B
Tenant C ──> Database C

Shared: S3, Monitoring, Auth Service
```

---

## Technology Choices Rationale

### Why FastAPI?
- Native async support (critical for external API calls)
- Automatic API documentation (OpenAPI/Swagger)
- Pydantic validation (type safety)
- High performance
- Great developer experience

### Why React + Vite?
- Fast development server (HMR)
- Modern build tooling
- Mature ecosystem
- TypeScript support
- Large talent pool

### Why PostgreSQL?
- JSONB support (flexible SOAP structure)
- ACID compliance (data integrity)
- Mature, battle-tested
- Strong ecosystem
- Good performance for MVP scale

### Why Deepgram?
- Medical model available (specialized vocabulary)
- Fast turnaround
- Diarization (speaker separation)
- Competitive pricing
- Good API design

### Why Claude (Anthropic)?
- Strong medical reasoning
- Long context window (full transcripts)
- JSON mode (structured output)
- Safety-focused (important for healthcare)
- Constitutional AI approach

---

## Deployment Architecture (Local Dev)

```
Docker Host
  │
  ├─> Container: PostgreSQL
  │     Port: 5432
  │     Volume: postgres_data
  │
  ├─> Container: Backend (FastAPI)
  │     Port: 8000
  │     Volumes: ./backend, ./uploads
  │     Depends: PostgreSQL
  │
  └─> Container: Frontend (React)
        Port: 3000
        Volume: ./frontend
        Depends: Backend
```

**Network:**
- Default bridge network
- Services communicate via service names
- Frontend → Backend via localhost:8000 (dev) or internal network

**Volumes:**
- `postgres_data`: Database persistence
- `./backend`: Live code reload
- `./frontend`: Live code reload
- `./uploads`: Audio file storage

---

## Monitoring & Observability (Future)

### Key Metrics to Track
- API response times
- Transcription success rate
- Note generation success rate
- Error rates by endpoint
- Token usage (Claude API)
- Active users
- Visits per day

### Logging Strategy
- Structured JSON logs
- No PHI in logs
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized log aggregation (future)

### Health Checks
```
GET /health
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

This architecture supports the MVP requirements while providing clear paths for future scaling and enhancement.