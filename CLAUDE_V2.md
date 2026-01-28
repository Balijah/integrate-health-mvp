# CLAUDE.md - Integrate Health Enhanced MVP (Phase 2)

## Overview

This document specifies **Phase 2** of the Integrate Health MVP, building on the foundational system completed in Phase 1. Phase 2 adds two critical features:

1. **Live Transcription**: Real-time speech-to-text during patient visits with pause/resume controls
2. **EHR Integration**: Automatic push of SOAP notes to Practice Fusion

These features transform the system from a post-visit documentation tool into an integrated, real-time clinical assistant.

---

## What's New in Phase 2

### Live Transcription
- **Real-time streaming**: Audio streamed to Deepgram during the visit
- **Instant display**: Transcript appears as the conversation happens
- **Pause/Resume**: Provider can pause transcription for private discussions
- **Speaker diarization**: Distinguish between provider and patient speech
- **Edit during visit**: Provider can make corrections in real-time

### EHR Integration (Practice Fusion)
- **SOAP note push**: Generated notes sent directly to Practice Fusion
- **Patient matching**: Search Practice Fusion by name/DOB to link encounters
- **Encounter creation**: Automatically create new patient encounters
- **Status tracking**: Monitor push status with retry on failure
- **Provider notifications**: Alert provider of successful/failed EHR syncs

---

## Architecture Updates

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│                   React + TypeScript                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   Auth    │  │  Live     │  │  Notes    │  │  History  │    │
│  │  Pages    │  │  Record   │  │  Editor   │  │   View    │    │
│  │           │  │  + Stream │  │  + EHR    │  │           │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
│                   FastAPI + Python                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   Auth    │  │  Visits   │  │  Live     │  │   Notes   │    │
│  │  Service  │  │  Service  │  │  Stream   │  │  Service  │    │
│  │           │  │           │  │  Service  │  │  + EHR    │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              EHR Integration Service                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│  │  │   Patient    │  │   Encounter  │  │     Retry    │    │  │
│  │  │   Search     │  │   Creation   │  │     Queue    │    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┬──────────────┐
              ▼               ▼               ▼              ▼
       ┌───────────┐   ┌───────────┐   ┌───────────┐  ┌──────────┐
       │ PostgreSQL│   │ Deepgram  │   │  Claude   │  │ Practice │
       │  Database │   │  Streaming│   │    API    │  │  Fusion  │
       │  + Queue  │   │    API    │   │           │  │   API    │
       └───────────┘   └───────────┘   └───────────┘  └──────────┘
```

---

## Tech Stack Additions

### New Backend Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| websockets | 12.0+ | WebSocket support for live streaming |
| aiofiles | 23.0+ | Async file operations |
| redis | 5.0+ | Job queue for EHR retry logic |
| celery | 5.3+ | Background task processing |
| requests-oauthlib | 1.3+ | OAuth for Practice Fusion API |

### New Frontend Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| socket.io-client | 4.6+ | WebSocket client for live transcription |
| react-use-websocket | 4.5+ | React hooks for WebSocket |
| @tanstack/react-query | 5.0+ | Server state management |

### External Services (New)
| Service | Provider | Purpose |
|---------|----------|---------|
| EHR API | Practice Fusion | Patient/encounter management |
| Redis | Redis Labs / Local | Task queue and caching |

---

## Database Schema Changes

### New Tables

#### ehr_credentials
```sql
CREATE TABLE ehr_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_name VARCHAR(255) NOT NULL,
    ehr_system VARCHAR(50) DEFAULT 'practice_fusion',
    client_id VARCHAR(255) NOT NULL,
    client_secret VARCHAR(255) NOT NULL,  -- Encrypted
    access_token TEXT,  -- Encrypted
    refresh_token TEXT,  -- Encrypted
    token_expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Only one active credential set per clinic
CREATE UNIQUE INDEX idx_ehr_active ON ehr_credentials(clinic_name, is_active) 
WHERE is_active = TRUE;
```

#### ehr_sync_logs
```sql
CREATE TABLE ehr_sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    ehr_patient_id VARCHAR(255),  -- Practice Fusion patient ID
    ehr_encounter_id VARCHAR(255),  -- Practice Fusion encounter ID
    sync_status VARCHAR(50) DEFAULT 'pending',
    -- Status: pending, in_progress, completed, failed, retrying
    attempt_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    request_payload JSONB,
    response_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ehr_sync_note ON ehr_sync_logs(note_id);
CREATE INDEX idx_ehr_sync_status ON ehr_sync_logs(sync_status);
```

#### transcription_sessions
```sql
CREATE TABLE transcription_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id UUID NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    session_status VARCHAR(50) DEFAULT 'active',
    -- Status: active, paused, completed, failed
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    total_duration_seconds INTEGER,
    pause_count INTEGER DEFAULT 0,
    websocket_connection_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transcription_session_visit ON transcription_sessions(visit_id);
CREATE INDEX idx_transcription_session_status ON transcription_sessions(session_status);
```

### Modified Tables

#### visits (add columns)
```sql
ALTER TABLE visits 
ADD COLUMN is_live_transcription BOOLEAN DEFAULT FALSE,
ADD COLUMN transcription_session_id UUID REFERENCES transcription_sessions(id);
```

#### notes (add columns)
```sql
ALTER TABLE notes
ADD COLUMN ehr_sync_status VARCHAR(50) DEFAULT 'not_synced',
-- Status: not_synced, syncing, synced, failed
ADD COLUMN ehr_synced_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN ehr_patient_id VARCHAR(255),
ADD COLUMN ehr_encounter_id VARCHAR(255);

CREATE INDEX idx_notes_ehr_sync_status ON notes(ehr_sync_status);
```

---

## API Specification - New Endpoints

### Live Transcription

#### POST /visits/{visit_id}/transcription/start-live
Start live transcription session.

**Request:**
```json
{
  "sample_rate": 16000,
  "encoding": "linear16"
}
```

**Response (200):**
```json
{
  "session_id": "uuid",
  "websocket_url": "ws://localhost:8000/ws/transcription/{session_id}",
  "status": "active"
}
```

#### WebSocket /ws/transcription/{session_id}
Real-time bidirectional communication for audio streaming and transcript delivery.

**Client → Server (Audio Data):**
```json
{
  "type": "audio_chunk",
  "data": "base64_encoded_audio",
  "timestamp": 1234567890
}
```

**Server → Client (Transcript Chunks):**
```json
{
  "type": "transcript",
  "speaker": "provider",
  "text": "How are you feeling today?",
  "is_final": true,
  "timestamp": 1234567890,
  "confidence": 0.95
}
```

**Client → Server (Control Commands):**
```json
{
  "type": "pause"
}
// or
{
  "type": "resume"
}
// or
{
  "type": "stop"
}
```

**Server → Client (Status Updates):**
```json
{
  "type": "status",
  "session_status": "paused",
  "duration_seconds": 145
}
```

#### POST /visits/{visit_id}/transcription/pause-live
Pause active live transcription.

**Response (200):**
```json
{
  "session_id": "uuid",
  "status": "paused",
  "duration_seconds": 145
}
```

#### POST /visits/{visit_id}/transcription/resume-live
Resume paused live transcription.

**Response (200):**
```json
{
  "session_id": "uuid",
  "status": "active"
}
```

#### POST /visits/{visit_id}/transcription/stop-live
End live transcription session.

**Response (200):**
```json
{
  "session_id": "uuid",
  "status": "completed",
  "total_duration_seconds": 1847,
  "transcript": "Full combined transcript...",
  "word_count": 2453
}
```

---

### EHR Integration - Setup

#### POST /ehr/credentials
Configure Practice Fusion credentials for the clinic.

**Request:**
```json
{
  "clinic_name": "Kare Health",
  "client_id": "pf_client_abc123",
  "client_secret": "pf_secret_xyz789"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "clinic_name": "Kare Health",
  "ehr_system": "practice_fusion",
  "is_active": true,
  "token_expires_at": "2024-02-15T10:30:00Z"
}
```

#### GET /ehr/credentials/status
Check EHR connection status.

**Response (200):**
```json
{
  "is_configured": true,
  "ehr_system": "practice_fusion",
  "connection_status": "active",
  "token_expires_in_hours": 168,
  "last_successful_sync": "2024-01-15T14:30:00Z"
}
```

#### POST /ehr/credentials/refresh
Manually refresh OAuth token.

**Response (200):**
```json
{
  "status": "success",
  "token_expires_at": "2024-02-22T10:30:00Z"
}
```

---

### EHR Integration - Patient Search

#### GET /ehr/patients/search
Search for patients in Practice Fusion.

**Query Parameters:**
- `first_name` (required): Patient first name
- `last_name` (required): Patient last name
- `date_of_birth` (required): Format YYYY-MM-DD

**Response (200):**
```json
{
  "patients": [
    {
      "ehr_patient_id": "pf_12345",
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "1980-05-15",
      "gender": "M",
      "mrn": "MRN-001234"
    }
  ],
  "total": 1
}
```

---

### EHR Integration - Sync Operations

#### POST /notes/{note_id}/sync-to-ehr
Push SOAP note to Practice Fusion.

**Request:**
```json
{
  "ehr_patient_id": "pf_12345",
  "encounter_date": "2024-01-15T14:00:00Z",
  "encounter_type": "office_visit",
  "chief_complaint": "Fatigue and brain fog"
}
```

**Response (202):**
```json
{
  "sync_log_id": "uuid",
  "status": "pending",
  "message": "EHR sync initiated. This may take a few moments."
}
```

#### GET /notes/{note_id}/sync-status
Check EHR sync status for a note.

**Response (200):**
```json
{
  "note_id": "uuid",
  "sync_status": "completed",
  "ehr_encounter_id": "pf_enc_67890",
  "synced_at": "2024-01-15T15:45:00Z",
  "attempt_count": 1
}
```
**OR if failed:**
```json
{
  "note_id": "uuid",
  "sync_status": "failed",
  "error_message": "Authentication failed: Token expired",
  "attempt_count": 3,
  "next_retry_at": "2024-01-15T16:00:00Z"
}
```

#### POST /notes/{note_id}/retry-sync
Manually retry failed EHR sync.

**Response (202):**
```json
{
  "sync_log_id": "uuid",
  "status": "retrying",
  "attempt_count": 4
}
```

#### GET /ehr/sync-logs
Get recent EHR sync history.

**Query Parameters:**
- `status` (optional): Filter by sync_status
- `limit` (default: 20): Number of results

**Response (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "note_id": "uuid",
      "patient_ref": "PT-001",
      "sync_status": "completed",
      "ehr_encounter_id": "pf_enc_67890",
      "synced_at": "2024-01-15T15:45:00Z"
    }
  ],
  "total": 5
}
```

---

## Practice Fusion API Integration

### Overview
Practice Fusion provides a REST API with OAuth 2.0 authentication for third-party integrations. The API allows creating encounters, managing patients, and posting clinical notes.

### Authentication Flow

```python
# backend/app/services/ehr/practice_fusion_auth.py

from requests_oauthlib import OAuth2Session
from app.config import settings

class PracticeFusionAuth:
    """Handle OAuth2 authentication with Practice Fusion."""
    
    AUTH_URL = "https://api.practicefusion.com/oauth/authorize"
    TOKEN_URL = "https://api.practicefusion.com/oauth/token"
    API_BASE = "https://api.practicefusion.com/v1"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
    
    async def get_access_token(self, refresh_token: str = None) -> dict:
        """
        Get access token using client credentials or refresh token.
        
        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_in": 604800  # 7 days
            }
        """
        oauth = OAuth2Session(
            client_id=self.client_id,
            auto_refresh_url=self.TOKEN_URL
        )
        
        if refresh_token:
            # Refresh existing token
            token = oauth.refresh_token(
                self.TOKEN_URL,
                refresh_token=refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        else:
            # Get new token using client credentials
            token = oauth.fetch_token(
                self.TOKEN_URL,
                client_id=self.client_id,
                client_secret=self.client_secret,
                grant_type='client_credentials'
            )
        
        return token
```

### Patient Search

```python
# backend/app/services/ehr/practice_fusion_client.py

import httpx
from typing import List, Dict

class PracticeFusionClient:
    """Client for Practice Fusion API operations."""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.practicefusion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    async def search_patients(
        self,
        first_name: str,
        last_name: str,
        date_of_birth: str
    ) -> List[Dict]:
        """
        Search for patients by demographics.
        
        Args:
            first_name: Patient first name
            last_name: Patient last name
            date_of_birth: DOB in YYYY-MM-DD format
        
        Returns:
            List of matching patient records
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/patients/search",
                headers=self.headers,
                params={
                    "firstName": first_name,
                    "lastName": last_name,
                    "dateOfBirth": date_of_birth
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("patients", [])
```

### Encounter Creation

```python
async def create_encounter(
    self,
    patient_id: str,
    encounter_date: str,
    encounter_type: str,
    chief_complaint: str
) -> Dict:
    """
    Create new patient encounter.
    
    Args:
        patient_id: Practice Fusion patient ID
        encounter_date: ISO datetime string
        encounter_type: e.g., "office_visit"
        chief_complaint: Reason for visit
    
    Returns:
        Created encounter with ID
    """
    payload = {
        "patientId": patient_id,
        "encounterDate": encounter_date,
        "encounterType": encounter_type,
        "chiefComplaint": chief_complaint,
        "status": "open"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.base_url}/encounters",
            headers=self.headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

### Clinical Note Upload

```python
async def post_clinical_note(
    self,
    encounter_id: str,
    note_content: str,
    note_type: str = "SOAP"
) -> Dict:
    """
    Post clinical note to encounter.
    
    Args:
        encounter_id: Practice Fusion encounter ID
        note_content: Formatted SOAP note text
        note_type: Note type identifier
    
    Returns:
        Created note metadata
    """
    payload = {
        "encounterId": encounter_id,
        "noteType": note_type,
        "noteText": note_content,
        "author": {
            "type": "provider",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.base_url}/clinical-notes",
            headers=self.headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

### SOAP Note Formatting for Practice Fusion

```python
# backend/app/services/ehr/note_formatter.py

def format_soap_for_ehr(soap_content: dict) -> str:
    """
    Convert structured SOAP JSON to Practice Fusion text format.
    
    Practice Fusion expects plain text with clear section headers.
    """
    sections = []
    
    # Subjective
    sections.append("SUBJECTIVE")
    sections.append("-" * 40)
    subj = soap_content.get("subjective", {})
    if subj.get("chief_complaint"):
        sections.append(f"Chief Complaint: {subj['chief_complaint']}")
    if subj.get("history_of_present_illness"):
        sections.append(f"\nHPI: {subj['history_of_present_illness']}")
    if subj.get("medications"):
        sections.append(f"\nMedications: {', '.join(subj['medications'])}")
    # ... continue for other subjective fields
    
    sections.append("\n\nOBJECTIVE")
    sections.append("-" * 40)
    obj = soap_content.get("objective", {})
    if obj.get("vitals"):
        vitals = obj["vitals"]
        sections.append("Vitals:")
        for key, value in vitals.items():
            sections.append(f"  {key.replace('_', ' ').title()}: {value}")
    # ... continue for other objective fields
    
    sections.append("\n\nASSESSMENT")
    sections.append("-" * 40)
    assess = soap_content.get("assessment", {})
    if assess.get("diagnoses"):
        sections.append("Diagnoses:")
        for idx, dx in enumerate(assess["diagnoses"], 1):
            sections.append(f"  {idx}. {dx}")
    # ... continue
    
    sections.append("\n\nPLAN")
    sections.append("-" * 40)
    plan = soap_content.get("plan", {})
    if plan.get("treatment_plan"):
        sections.append(f"Treatment: {plan['treatment_plan']}")
    # ... continue
    
    return "\n".join(sections)
```

---

## Live Transcription Implementation

### Deepgram Streaming Integration

```python
# backend/app/services/live_transcription.py

from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from app.config import settings
import asyncio

class LiveTranscriptionService:
    """Manage live transcription sessions with Deepgram."""
    
    def __init__(self):
        self.deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.active_sessions = {}
    
    async def start_session(self, session_id: str, websocket) -> None:
        """
        Start live transcription session.
        
        Args:
            session_id: Unique session identifier
            websocket: Client WebSocket connection
        """
        # Configure Deepgram streaming options
        options = LiveOptions(
            model="nova-2-medical",
            punctuate=True,
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1000,
            diarize=True,  # Speaker separation
            language="en-US",
            encoding="linear16",
            sample_rate=16000
        )
        
        # Create Deepgram connection
        dg_connection = self.deepgram.listen.live.v("1")
        
        # Event handlers
        def on_message(self, result, **kwargs):
            """Handle incoming transcript from Deepgram."""
            transcript_data = {
                "type": "transcript",
                "text": result.channel.alternatives[0].transcript,
                "is_final": result.is_final,
                "speaker": self._identify_speaker(result),
                "confidence": result.channel.alternatives[0].confidence,
                "timestamp": result.start
            }
            
            # Send to client via WebSocket
            asyncio.create_task(
                websocket.send_json(transcript_data)
            )
        
        def on_error(self, error, **kwargs):
            """Handle Deepgram errors."""
            error_data = {
                "type": "error",
                "message": str(error)
            }
            asyncio.create_task(
                websocket.send_json(error_data)
            )
        
        # Register event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        
        # Start connection
        if not dg_connection.start(options):
            raise Exception("Failed to start Deepgram connection")
        
        # Store active session
        self.active_sessions[session_id] = {
            "connection": dg_connection,
            "websocket": websocket,
            "transcript_buffer": [],
            "status": "active"
        }
    
    async def send_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes
    ) -> None:
        """Send audio chunk to Deepgram for transcription."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            if session["status"] == "active":
                session["connection"].send(audio_data)
    
    async def pause_session(self, session_id: str) -> None:
        """Pause transcription (stop sending audio)."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = "paused"
    
    async def resume_session(self, session_id: str) -> None:
        """Resume transcription."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = "active"
    
    async def end_session(self, session_id: str) -> str:
        """
        End transcription session and return full transcript.
        
        Returns:
            Combined transcript text
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            # Close Deepgram connection
            session["connection"].finish()
            
            # Combine transcript buffer
            full_transcript = " ".join(
                item["text"] for item in session["transcript_buffer"]
                if item["is_final"]
            )
            
            # Cleanup
            del self.active_sessions[session_id]
            
            return full_transcript
        
        return ""
    
    def _identify_speaker(self, result) -> str:
        """
        Identify speaker from diarization data.
        Returns 'provider' or 'patient'.
        """
        # Deepgram assigns speaker numbers (0, 1, etc.)
        # We'll assume speaker 0 is provider for MVP
        # This can be improved with voice enrollment
        speaker_num = getattr(result, "speaker", 0)
        return "provider" if speaker_num == 0 else "patient"
```

### WebSocket Endpoint

```python
# backend/app/api/websockets.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.services.live_transcription import LiveTranscriptionService
from app.api.deps import get_current_user
import base64

router = APIRouter()
transcription_service = LiveTranscriptionService()

@router.websocket("/ws/transcription/{session_id}")
async def transcription_websocket(
    websocket: WebSocket,
    session_id: str,
    # Note: WebSocket auth is tricky, we'll pass token in initial message
):
    """WebSocket endpoint for live transcription."""
    await websocket.accept()
    
    try:
        # Start Deepgram session
        await transcription_service.start_session(session_id, websocket)
        
        # Listen for audio chunks from client
        while True:
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "audio_chunk":
                # Decode base64 audio and send to Deepgram
                audio_bytes = base64.b64decode(data["data"])
                await transcription_service.send_audio_chunk(
                    session_id,
                    audio_bytes
                )
            
            elif message_type == "pause":
                await transcription_service.pause_session(session_id)
                await websocket.send_json({
                    "type": "status",
                    "session_status": "paused"
                })
            
            elif message_type == "resume":
                await transcription_service.resume_session(session_id)
                await websocket.send_json({
                    "type": "status",
                    "session_status": "active"
                })
            
            elif message_type == "stop":
                full_transcript = await transcription_service.end_session(
                    session_id
                )
                await websocket.send_json({
                    "type": "complete",
                    "transcript": full_transcript
                })
                break
    
    except WebSocketDisconnect:
        # Cleanup on disconnect
        await transcription_service.end_session(session_id)
    
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await transcription_service.end_session(session_id)
```

---

## EHR Sync Service with Retry Queue

### Celery Configuration

```python
# backend/app/celery_app.py

from celery import Celery
from app.config import settings

celery_app = Celery(
    "integrate_health",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute timeout
    task_acks_late=True,
    worker_prefetch_multiplier=1
)
```

### EHR Sync Task

```python
# backend/app/tasks/ehr_sync.py

from app.celery_app import celery_app
from app.services.ehr.practice_fusion_client import PracticeFusionClient
from app.services.ehr.practice_fusion_auth import PracticeFusionAuth
from app.services.ehr.note_formatter import format_soap_for_ehr
from app.database import SessionLocal
from app.models.note import Note
from app.models.ehr_sync_log import EHRSyncLog
from app.models.ehr_credentials import EHRCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes
    max_retries=5
)
def sync_note_to_ehr(
    self,
    note_id: str,
    ehr_patient_id: str,
    encounter_date: str,
    encounter_type: str,
    chief_complaint: str
):
    """
    Background task to sync SOAP note to Practice Fusion.
    
    Args:
        note_id: UUID of note to sync
        ehr_patient_id: Practice Fusion patient ID
        encounter_date: ISO datetime string
        encounter_type: e.g., "office_visit"
        chief_complaint: Reason for visit
    """
    db: Session = SessionLocal()
    
    try:
        # Get note
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise ValueError(f"Note {note_id} not found")
        
        # Get or create sync log
        sync_log = db.query(EHRSyncLog).filter(
            EHRSyncLog.note_id == note_id
        ).first()
        
        if not sync_log:
            sync_log = EHRSyncLog(
                note_id=note_id,
                ehr_patient_id=ehr_patient_id,
                sync_status="in_progress"
            )
            db.add(sync_log)
        else:
            sync_log.sync_status = "in_progress"
        
        sync_log.attempt_count += 1
        sync_log.last_attempt_at = datetime.utcnow()
        db.commit()
        
        # Get EHR credentials
        credentials = db.query(EHRCredentials).filter(
            EHRCredentials.is_active == True
        ).first()
        
        if not credentials:
            raise ValueError("No active EHR credentials configured")
        
        # Refresh token if needed
        if credentials.token_expires_at < datetime.utcnow() + timedelta(hours=1):
            auth = PracticeFusionAuth(
                credentials.client_id,
                credentials.client_secret
            )
            token_data = await auth.get_access_token(
                refresh_token=credentials.refresh_token
            )
            credentials.access_token = token_data["access_token"]
            credentials.refresh_token = token_data["refresh_token"]
            credentials.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data["expires_in"]
            )
            db.commit()
        
        # Initialize client
        client = PracticeFusionClient(credentials.access_token)
        
        # Create encounter
        encounter = await client.create_encounter(
            patient_id=ehr_patient_id,
            encounter_date=encounter_date,
            encounter_type=encounter_type,
            chief_complaint=chief_complaint
        )
        
        sync_log.ehr_encounter_id = encounter["encounterId"]
        db.commit()
        
        # Format and post note
        formatted_note = format_soap_for_ehr(note.content)
        note_response = await client.post_clinical_note(
            encounter_id=encounter["encounterId"],
            note_content=formatted_note,
            note_type="SOAP"
        )
        
        # Update sync log - SUCCESS
        sync_log.sync_status = "completed"
        sync_log.response_payload = note_response
        
        # Update note
        note.ehr_sync_status = "synced"
        note.ehr_synced_at = datetime.utcnow()
        note.ehr_patient_id = ehr_patient_id
        note.ehr_encounter_id = encounter["encounterId"]
        
        db.commit()
        
        logger.info(f"Successfully synced note {note_id} to EHR")
        
    except Exception as e:
        # Update sync log - FAILED
        sync_log.sync_status = "failed"
        sync_log.error_message = str(e)
        db.commit()
        
        logger.error(f"Failed to sync note {note_id}: {str(e)}")
        
        # Re-raise for Celery retry
        raise
    
    finally:
        db.close()
```

### Sync Service Wrapper

```python
# backend/app/services/ehr_sync_service.py

from app.tasks.ehr_sync import sync_note_to_ehr
from app.models.ehr_sync_log import EHRSyncLog
from app.database import SessionLocal
from datetime import datetime

class EHRSyncService:
    """High-level service for EHR synchronization operations."""
    
    def initiate_sync(
        self,
        note_id: str,
        ehr_patient_id: str,
        encounter_date: str,
        encounter_type: str,
        chief_complaint: str
    ) -> str:
        """
        Initiate EHR sync (queues background task).
        
        Returns:
            sync_log_id for tracking
        """
        db = SessionLocal()
        try:
            # Create initial sync log
            sync_log = EHRSyncLog(
                note_id=note_id,
                ehr_patient_id=ehr_patient_id,
                sync_status="pending",
                request_payload={
                    "encounter_date": encounter_date,
                    "encounter_type": encounter_type,
                    "chief_complaint": chief_complaint
                }
            )
            db.add(sync_log)
            db.commit()
            db.refresh(sync_log)
            
            # Queue Celery task
            sync_note_to_ehr.delay(
                note_id=note_id,
                ehr_patient_id=ehr_patient_id,
                encounter_date=encounter_date,
                encounter_type=encounter_type,
                chief_complaint=chief_complaint
            )
            
            return str(sync_log.id)
        
        finally:
            db.close()
    
    def get_sync_status(self, sync_log_id: str) -> dict:
        """Get current status of sync operation."""
        db = SessionLocal()
        try:
            sync_log = db.query(EHRSyncLog).filter(
                EHRSyncLog.id == sync_log_id
            ).first()
            
            if not sync_log:
                return {"error": "Sync log not found"}
            
            return {
                "sync_status": sync_log.sync_status,
                "attempt_count": sync_log.attempt_count,
                "error_message": sync_log.error_message,
                "ehr_encounter_id": sync_log.ehr_encounter_id,
                "last_attempt_at": sync_log.last_attempt_at
            }
        finally:
            db.close()
    
    def retry_failed_sync(self, sync_log_id: str) -> bool:
        """Manually retry a failed sync."""
        db = SessionLocal()
        try:
            sync_log = db.query(EHRSyncLog).filter(
                EHRSyncLog.id == sync_log_id,
                EHRSyncLog.sync_status == "failed"
            ).first()
            
            if not sync_log:
                return False
            
            # Re-queue task
            request_data = sync_log.request_payload
            sync_note_to_ehr.delay(
                note_id=str(sync_log.note_id),
                ehr_patient_id=sync_log.ehr_patient_id,
                encounter_date=request_data["encounter_date"],
                encounter_type=request_data["encounter_type"],
                chief_complaint=request_data["chief_complaint"]
            )
            
            return True
        
        finally:
            db.close()
```

---

## Frontend Implementation

### Updated Project Structure

```
frontend/src/
├── components/
│   ├── LiveRecorder/
│   │   ├── LiveRecorder.tsx          # Main live recording component
│   │   ├── LiveTranscript.tsx        # Real-time transcript display
│   │   ├── RecorderControls.tsx      # Play/Pause/Stop controls
│   │   └── SpeakerBadge.tsx          # Provider/Patient indicators
│   │
│   ├── EHRIntegration/
│   │   ├── EHRSetup.tsx              # Credentials configuration
│   │   ├── PatientSearch.tsx         # Search Practice Fusion patients
│   │   ├── SyncModal.tsx             # Sync confirmation modal
│   │   └── SyncStatus.tsx            # Sync progress indicator
│   │
│   └── ... (existing components)
│
├── hooks/
│   ├── useLiveTranscription.ts       # WebSocket + audio streaming
│   ├── useEHRSync.ts                 # EHR sync operations
│   └── usePatientSearch.ts           # Patient search functionality
│
├── pages/
│   ├── LiveVisit.tsx                 # New: Live recording page
│   ├── EHRSettings.tsx               # New: EHR configuration
│   └── ... (existing pages)
│
└── api/
    ├── liveTranscription.ts          # Live transcription API calls
    ├── ehr.ts                        # EHR API calls
    └── ... (existing API modules)
```

### useLiveTranscription Hook

```typescript
// frontend/src/hooks/useLiveTranscription.ts

import { useState, useEffect, useRef, useCallback } from 'react';
import useWebSocket from 'react-use-websocket';

interface TranscriptSegment {
  speaker: 'provider' | 'patient';
  text: string;
  timestamp: number;
  isFinal: boolean;
  confidence: number;
}

interface UseLiveTranscriptionReturn {
  isConnected: boolean;
  isRecording: boolean;
  isPaused: boolean;
  transcript: TranscriptSegment[];
  duration: number;
  startRecording: () => Promise<void>;
  pauseRecording: () => void;
  resumeRecording: () => void;
  stopRecording: () => Promise<string>;
  error: string | null;
}

export const useLiveTranscription = (
  visitId: string
): UseLiveTranscriptionReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [duration, setDuration] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const durationIntervalRef = useRef<number | null>(null);
  
  // WebSocket connection
  const { sendJsonMessage, lastJsonMessage, readyState } = useWebSocket(
    sessionId ? `ws://localhost:8000/ws/transcription/${sessionId}` : null,
    {
      shouldReconnect: () => false,
      onOpen: () => console.log('WebSocket connected'),
      onClose: () => console.log('WebSocket disconnected'),
      onError: (event) => setError('WebSocket error occurred'),
    }
  );
  
  const isConnected = readyState === WebSocket.OPEN;
  
  // Handle incoming transcript messages
  useEffect(() => {
    if (lastJsonMessage) {
      const message = lastJsonMessage as any;
      
      if (message.type === 'transcript') {
        setTranscript(prev => {
          // Update or append transcript segment
          const existingIndex = prev.findIndex(
            seg => seg.timestamp === message.timestamp && !seg.isFinal
          );
          
          const newSegment: TranscriptSegment = {
            speaker: message.speaker,
            text: message.text,
            timestamp: message.timestamp,
            isFinal: message.is_final,
            confidence: message.confidence
          };
          
          if (existingIndex >= 0) {
            // Update existing interim result
            const updated = [...prev];
            updated[existingIndex] = newSegment;
            return updated;
          } else {
            // Append new segment
            return [...prev, newSegment];
          }
        });
      } else if (message.type === 'error') {
        setError(message.message);
      }
    }
  }, [lastJsonMessage]);
  
  const startRecording = useCallback(async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });
      
      // Initialize Audio Context
      audioContextRef.current = new AudioContext({ sampleRate: 16000 });
      const source = audioContextRef.current.createMediaStreamSource(stream);
      
      // Start session via API
      const response = await fetch(
        `http://localhost:8000/api/v1/visits/${visitId}/transcription/start-live`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify({
            sample_rate: 16000,
            encoding: 'linear16'
          })
        }
      );
      
      const data = await response.json();
      setSessionId(data.session_id);
      
      // Set up MediaRecorder to capture audio chunks
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm'
      });
      
      mediaRecorderRef.current.ondataavailable = async (event) => {
        if (event.data.size > 0 && isConnected && !isPaused) {
          // Convert blob to base64 and send via WebSocket
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = (reader.result as string).split(',')[1];
            sendJsonMessage({
              type: 'audio_chunk',
              data: base64,
              timestamp: Date.now()
            });
          };
          reader.readAsDataURL(event.data);
        }
      };
      
      // Start recording with 100ms chunks
      mediaRecorderRef.current.start(100);
      
      setIsRecording(true);
      setTranscript([]);
      setDuration(0);
      
      // Start duration timer
      durationIntervalRef.current = window.setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);
      
    } catch (err) {
      setError(`Failed to start recording: ${err}`);
    }
  }, [visitId, isConnected, isPaused, sendJsonMessage]);
  
  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.pause();
      sendJsonMessage({ type: 'pause' });
      setIsPaused(true);
      
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
    }
  }, [isRecording, sendJsonMessage]);
  
  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && isPaused) {
      mediaRecorderRef.current.resume();
      sendJsonMessage({ type: 'resume' });
      setIsPaused(false);
      
      durationIntervalRef.current = window.setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);
    }
  }, [isPaused, sendJsonMessage]);
  
  const stopRecording = useCallback(async (): Promise<string> => {
    return new Promise((resolve) => {
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
        sendJsonMessage({ type: 'stop' });
        
        // Wait for final transcript from server
        const checkForComplete = setInterval(() => {
          if (lastJsonMessage && (lastJsonMessage as any).type === 'complete') {
            clearInterval(checkForComplete);
            const fullTranscript = (lastJsonMessage as any).transcript;
            resolve(fullTranscript);
          }
        }, 100);
        
        setIsRecording(false);
        setIsPaused(false);
        
        if (durationIntervalRef.current) {
          clearInterval(durationIntervalRef.current);
        }
        
        // Cleanup
        if (audioContextRef.current) {
          audioContextRef.current.close();
        }
      }
    });
  }, [isRecording, sendJsonMessage, lastJsonMessage]);
  
  return {
    isConnected,
    isRecording,
    isPaused,
    transcript,
    duration,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    error
  };
};
```

### LiveRecorder Component

```typescript
// frontend/src/components/LiveRecorder/LiveRecorder.tsx

import React from 'react';
import { useLiveTranscription } from '../../hooks/useLiveTranscription';
import { RecorderControls } from './RecorderControls';
import { LiveTranscript } from './LiveTranscript';

interface LiveRecorderProps {
  visitId: string;
  onComplete: (transcript: string) => void;
}

export const LiveRecorder: React.FC<LiveRecorderProps> = ({
  visitId,
  onComplete
}) => {
  const {
    isConnected,
    isRecording,
    isPaused,
    transcript,
    duration,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    error
  } = useLiveTranscription(visitId);
  
  const handleStop = async () => {
    const fullTranscript = await stopRecording();
    onComplete(fullTranscript);
  };
  
  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-red-500'
          }`} />
          <span className="text-sm text-gray-600">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        
        {/* Duration */}
        {isRecording && (
          <div className="text-lg font-mono">
            {Math.floor(duration / 60)}:{(duration % 60).toString().padStart(2, '0')}
          </div>
        )}
      </div>
      
      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}
      
      {/* Controls */}
      <RecorderControls
        isRecording={isRecording}
        isPaused={isPaused}
        onStart={startRecording}
        onPause={pauseRecording}
        onResume={resumeRecording}
        onStop={handleStop}
        disabled={!isConnected}
      />
      
      {/* Live Transcript */}
      {isRecording && (
        <LiveTranscript segments={transcript} />
      )}
    </div>
  );
};
```

### LiveTranscript Component

```typescript
// frontend/src/components/LiveRecorder/LiveTranscript.tsx

import React, { useEffect, useRef } from 'react';
import { SpeakerBadge } from './SpeakerBadge';

interface TranscriptSegment {
  speaker: 'provider' | 'patient';
  text: string;
  timestamp: number;
  isFinal: boolean;
  confidence: number;
}

interface LiveTranscriptProps {
  segments: TranscriptSegment[];
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({ segments }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom on new segments
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [segments]);
  
  return (
    <div
      ref={containerRef}
      className="bg-white border border-gray-200 rounded-lg p-4 h-96 overflow-y-auto"
    >
      <div className="space-y-3">
        {segments.map((segment, index) => (
          <div
            key={`${segment.timestamp}-${index}`}
            className={`flex items-start space-x-2 ${
              !segment.isFinal ? 'opacity-60' : ''
            }`}
          >
            <SpeakerBadge speaker={segment.speaker} />
            
            <div className="flex-1">
              <p className="text-gray-800">
                {segment.text}
              </p>
              
              {!segment.isFinal && (
                <span className="text-xs text-gray-400 italic">
                  (interim)
                </span>
              )}
            </div>
          </div>
        ))}
        
        {segments.length === 0 && (
          <p className="text-gray-400 text-center py-8">
            Transcript will appear here as you speak...
          </p>
        )}
      </div>
    </div>
  );
};
```

### useEHRSync Hook

```typescript
// frontend/src/hooks/useEHRSync.ts

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import * as ehrApi from '../api/ehr';

interface SyncParams {
  noteId: string;
  ehrPatientId: string;
  encounterDate: string;
  encounterType: string;
  chiefComplaint: string;
}

export const useEHRSync = () => {
  const [syncLogId, setSyncLogId] = useState<string | null>(null);
  
  // Initiate sync mutation
  const syncMutation = useMutation({
    mutationFn: ehrApi.syncNoteToEHR,
    onSuccess: (data) => {
      setSyncLogId(data.sync_log_id);
    }
  });
  
  // Poll sync status
  const { data: syncStatus, isLoading: isCheckingStatus } = useQuery({
    queryKey: ['ehrSyncStatus', syncLogId],
    queryFn: () => ehrApi.getSyncStatus(syncLogId!),
    enabled: !!syncLogId,
    refetchInterval: (data) => {
      // Stop polling once completed or failed
      if (data?.sync_status === 'completed' || data?.sync_status === 'failed') {
        return false;
      }
      return 2000; // Poll every 2 seconds
    }
  });
  
  // Retry failed sync
  const retryMutation = useMutation({
    mutationFn: (syncLogId: string) => ehrApi.retrySyncToEHR(syncLogId),
    onSuccess: () => {
      // Will trigger status polling again
    }
  });
  
  return {
    initiateSync: syncMutation.mutate,
    retrySyncfailed: retryMutation.mutate,
    syncStatus,
    isCheckingStatus,
    isSyncing: syncMutation.isPending,
    error: syncMutation.error
  };
};
```

### PatientSearch Component

```typescript
// frontend/src/components/EHRIntegration/PatientSearch.tsx

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as ehrApi from '../../api/ehr';

interface Patient {
  ehr_patient_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  mrn: string;
}

interface PatientSearchProps {
  onSelectPatient: (patient: Patient) => void;
}

export const PatientSearch: React.FC<PatientSearchProps> = ({
  onSelectPatient
}) => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [dob, setDob] = useState('');
  const [shouldSearch, setShouldSearch] = useState(false);
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['patientSearch', firstName, lastName, dob],
    queryFn: () => ehrApi.searchPatients(firstName, lastName, dob),
    enabled: shouldSearch && !!firstName && !!lastName && !!dob
  });
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setShouldSearch(true);
  };
  
  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              First Name
            </label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Last Name
            </label>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              required
            />
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date of Birth
          </label>
          <input
            type="date"
            value={dob}
            onChange={(e) => setDob(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
        </div>
        
        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? 'Searching...' : 'Search Practice Fusion'}
        </button>
      </form>
      
      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-red-800 text-sm">
            Search failed: {(error as Error).message}
          </p>
        </div>
      )}
      
      {/* Results */}
      {data && data.patients && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">
            Found {data.patients.length} patient(s)
          </p>
          
          {data.patients.map((patient: Patient) => (
            <button
              key={patient.ehr_patient_id}
              onClick={() => onSelectPatient(patient)}
              className="w-full text-left p-3 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium">
                    {patient.first_name} {patient.last_name}
                  </p>
                  <p className="text-sm text-gray-600">
                    DOB: {patient.date_of_birth} • MRN: {patient.mrn}
                  </p>
                </div>
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                  Select
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
```

---

## Environment Variables (Updated)

Add to `.env`:

```bash
# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# Practice Fusion EHR
PRACTICE_FUSION_CLIENT_ID=your_client_id
PRACTICE_FUSION_CLIENT_SECRET=your_client_secret

# WebSocket
WEBSOCKET_MAX_CONNECTIONS=100
```

---

## Docker Compose Updates

```yaml
# docker-compose.yml (additions)

services:
  # ... existing services ...
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    command: celery -A app.celery_app worker --loglevel=info
  
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    command: celery -A app.celery_app beat --loglevel=info

volumes:
  postgres_data:
  redis_data:  # Add this
```

---

## Implementation Phases

### Phase 1: Live Transcription Foundation (Days 1-3)

**Tasks:**
1. Add WebSocket support to FastAPI backend
2. Create TranscriptionSession model and migration
3. Implement LiveTranscriptionService with Deepgram streaming
4. Create WebSocket endpoint for bidirectional audio/transcript
5. Build useLiveTranscription hook in frontend
6. Create basic LiveRecorder component

**Acceptance Criteria:**
- [ ] WebSocket connection establishes successfully
- [ ] Audio streams from browser to backend
- [ ] Deepgram connection starts and receives audio
- [ ] Transcript chunks flow back to frontend via WebSocket
- [ ] Connection status indicators work correctly

**Testing:**
- Test audio streaming with 1-minute test recording
- Verify WebSocket reconnection on disconnect
- Check memory usage during 10-minute stream
- Test with multiple concurrent sessions (2-3 users)

---

### Phase 2: Live Transcription UI & Controls (Days 4-6)

**Tasks:**
1. Build RecorderControls component (start/pause/resume/stop)
2. Build LiveTranscript component with auto-scroll
3. Implement SpeakerBadge component
4. Add pause/resume functionality to LiveTranscriptionService
5. Create LiveVisit page integrating all components
6. Add duration timer and visual feedback
7. Handle interim vs. final transcript segments

**Acceptance Criteria:**
- [ ] Start button begins recording and opens WebSocket
- [ ] Pause button halts transcription without closing connection
- [ ] Resume button continues transcription
- [ ] Stop button ends session and returns full transcript
- [ ] Transcript displays in real-time with speaker labels
- [ ] Duration timer updates every second
- [ ] Interim results show as "in progress"

**Testing:**
- Record 5-minute test conversation with pauses
- Verify transcript accuracy with medical terminology
- Test pause/resume maintains continuity
- Check UI responsiveness during streaming

---

### Phase 3: Live Transcription Integration (Days 7-8)

**Tasks:**
1. Update visits table with live transcription flags
2. Modify visit creation to support live vs. upload modes
3. Store final transcript in visit record on completion
4. Update Dashboard to show live vs. uploaded visits
5. Add "Convert to SOAP note" button after live session
6. Handle error cases (connection drops, timeout, etc.)

**Acceptance Criteria:**
- [ ] User can choose "Start Live Visit" vs "Upload Audio"
- [ ] Live session data persists in transcription_sessions table
- [ ] Final transcript saves to visit.transcript field
- [ ] Visit detail page shows live session metadata
- [ ] SOAP note generation works with live transcript
- [ ] Errors display user-friendly messages

**Testing:**
- Complete end-to-end flow: start live → record 2 min → stop → generate SOAP
- Test connection drop recovery
- Verify transcript saved correctly in database
- Test with very long sessions (30+ minutes)

---

### Phase 4: EHR Integration - Setup & Auth (Days 9-11)

**Tasks:**
1. Create EHRCredentials model and migration
2. Create EHRSyncLog model and migration
3. Implement PracticeFusionAuth service
4. Build EHR credentials management API endpoints
5. Add Redis and Celery to docker-compose
6. Create EHRSettings page in frontend
7. Build credential input form with validation
8. Add token refresh background task

**Acceptance Criteria:**
- [ ] Admin can enter Practice Fusion client ID/secret
- [ ] System exchanges credentials for access token
- [ ] Token stored encrypted in database
- [ ] Token refresh works automatically before expiry
- [ ] Connection status endpoint shows "connected"
- [ ] Celery worker starts and processes tasks

**Testing:**
- Test OAuth flow with valid credentials
- Verify token refresh 1 hour before expiry
- Test with invalid credentials (proper error handling)
- Check token encryption in database

---

### Phase 5: EHR Integration - Patient Search (Days 12-13)

**Tasks:**
1. Implement PracticeFusionClient.search_patients()
2. Create patient search API endpoint
3. Build PatientSearch component
4. Add patient search to note editor flow
5. Handle multiple matches and no matches
6. Add patient selection confirmation

**Acceptance Criteria:**
- [ ] User can search by first name, last name, DOB
- [ ] Search returns matching patients from Practice Fusion
- [ ] UI displays patient demographics clearly
- [ ] User can select correct patient
- [ ] Selected patient ID stored for sync
- [ ] No match scenario handled gracefully

**Testing:**
- Search for test patient in Practice Fusion sandbox
- Test with multiple matches
- Test with no matches
- Verify proper error messages

---

### Phase 6: EHR Integration - Sync Operations (Days 14-17)

**Tasks:**
1. Implement PracticeFusionClient.create_encounter()
2. Implement PracticeFusionClient.post_clinical_note()
3. Create format_soap_for_ehr() function
4. Build Celery task for sync with retries
5. Create EHRSyncService wrapper
6. Build sync API endpoints
7. Update notes table with EHR fields
8. Create SyncModal component
9. Add sync status polling in frontend
10. Build SyncStatus component with progress

**Acceptance Criteria:**
- [ ] User can initiate sync from note editor
- [ ] System creates encounter in Practice Fusion
- [ ] SOAP note posts to created encounter
- [ ] Sync status updates in real-time
- [ ] Failed syncs retry automatically (up to 5 times)
- [ ] User sees success/failure notifications
- [ ] Encounter ID stored in notes table

**Testing:**
- Complete full sync flow with test patient
- Verify encounter created in Practice Fusion
- Check note appears correctly in EHR
- Test retry logic by simulating API failure
- Test concurrent syncs (multiple notes)

---

### Phase 7: EHR Integration - Error Handling & Monitoring (Days 18-19)

**Tasks:**
1. Add comprehensive error handling to all EHR operations
2. Create notification system for sync failures
3. Build retry queue management UI
4. Add EHR sync logs page
5. Implement manual retry functionality
6. Add sync analytics/statistics

**Acceptance Criteria:**
- [ ] All EHR errors logged with details
- [ ] Provider notified of failed syncs via UI
- [ ] Admin can view sync history
- [ ] Failed syncs can be manually retried
- [ ] Logs show request/response payloads (for debugging)
- [ ] Statistics show success/failure rates

**Testing:**
- Simulate various API failures (timeout, auth, invalid data)
- Verify all failures logged correctly
- Test manual retry functionality
- Check notification system works

---

### Phase 8: Integration Testing & Polish (Days 20-23)

**Tasks:**
1. End-to-end testing: Live visit → SOAP note → EHR sync
2. Performance optimization for live transcription
3. UI/UX refinements based on testing
4. Add loading states and error boundaries
5. Write integration tests for critical paths
6. Update documentation with new features
7. Create user guide for live recording
8. Create admin guide for EHR setup

**Acceptance Criteria:**
- [ ] Complete workflow works smoothly start-to-finish
- [ ] No memory leaks during long recording sessions
- [ ] All loading states provide clear feedback
- [ ] Error messages are actionable
- [ ] Integration tests pass consistently
- [ ] Documentation complete and accurate

**Testing:**
- 5 complete end-to-end test scenarios
- Load test with 3 concurrent users
- Test with 45-minute live recording
- Verify Practice Fusion data appears correctly
- User acceptance testing with pilot clinic staff

---

## Testing Strategy

### Live Transcription Testing

**Unit Tests:**
```python
# backend/tests/test_live_transcription.py

import pytest
from app.services.live_transcription import LiveTranscriptionService

@pytest.mark.asyncio
async def test_start_session():
    service = LiveTranscriptionService()
    # Mock WebSocket
    mock_ws = MockWebSocket()
    
    await service.start_session("test_session_1", mock_ws)
    
    assert "test_session_1" in service.active_sessions
    assert service.active_sessions["test_session_1"]["status"] == "active"

@pytest.mark.asyncio
async def test_pause_resume():
    service = LiveTranscriptionService()
    mock_ws = MockWebSocket()
    
    await service.start_session("test_session_1", mock_ws)
    await service.pause_session("test_session_1")
    
    assert service.active_sessions["test_session_1"]["status"] == "paused"
    
    await service.resume_session("test_session_1")
    
    assert service.active_sessions["test_session_1"]["status"] == "active"
```

**Integration Tests:**
```python
# backend/tests/test_websocket.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_websocket_connection():
    client = TestClient(app)
    
    with client.websocket_connect("/ws/transcription/test_123") as websocket:
        # Send audio chunk
        websocket.send_json({
            "type": "audio_chunk",
            "data": "base64_audio_data",
            "timestamp": 1234567890
        })
        
        # Receive transcript
        data = websocket.receive_json()
        assert data["type"] == "transcript"
        assert "text" in data
```

### EHR Integration Testing

**Mock Practice Fusion Responses:**
```python
# backend/tests/mocks/practice_fusion_mock.py

class MockPracticeFusionClient:
    """Mock Practice Fusion API for testing."""
    
    async def search_patients(self, first_name, last_name, dob):
        return [
            {
                "ehr_patient_id": "pf_test_123",
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": dob,
                "gender": "F",
                "mrn": "TEST-001"
            }
        ]
    
    async def create_encounter(self, patient_id, encounter_date, **kwargs):
        return {
            "encounterId": "pf_enc_test_456",
            "patientId": patient_id,
            "encounterDate": encounter_date,
            "status": "open"
        }
    
    async def post_clinical_note(self, encounter_id, note_content, **kwargs):
        return {
            "noteId": "pf_note_test_789",
            "encounterId": encounter_id,
            "status": "posted"
        }
```

**Integration Test:**
```python
# backend/tests/test_ehr_sync.py

import pytest
from app.tasks.ehr_sync import sync_note_to_ehr
from app.models.note import Note
from unittest.mock import patch

@pytest.mark.asyncio
async def test_successful_sync(db_session, test_note):
    with patch('app.services.ehr.practice_fusion_client.PracticeFusionClient') as mock_client:
        mock_client.return_value.create_encounter.return_value = {
            "encounterId": "test_enc_123"
        }
        mock_client.return_value.post_clinical_note.return_value = {
            "noteId": "test_note_456"
        }
        
        sync_note_to_ehr(
            note_id=str(test_note.id),
            ehr_patient_id="pf_patient_123",
            encounter_date="2024-01-15T14:00:00Z",
            encounter_type="office_visit",
            chief_complaint="Test complaint"
        )
        
        db_session.refresh(test_note)
        assert test_note.ehr_sync_status == "synced"
        assert test_note.ehr_encounter_id == "test_enc_123"
```

### End-to-End Test Scenarios

**Scenario 1: Complete Live Visit with EHR Sync**
```
1. Provider creates new visit
2. Provider starts live recording
3. System streams audio and receives transcript
4. Provider pauses for 30 seconds (private discussion)
5. Provider resumes recording
6. Provider stops after 5 minutes
7. System generates SOAP note from transcript
8. Provider reviews and edits note
9. Provider searches for patient in Practice Fusion
10. Provider initiates EHR sync
11. System creates encounter and posts note
12. Provider receives sync success confirmation
```

**Scenario 2: Failed Sync with Retry**
```
1. Provider has completed SOAP note
2. Provider initiates EHR sync
3. Practice Fusion API returns 503 (service unavailable)
4. System logs failure and queues retry
5. System retries after 1 minute
6. Second attempt succeeds
7. Provider sees sync completed status
```

---

## HIPAA Compliance Notes

**Important:** The current MVP is designed for prototype/testing purposes. Before production deployment with real patient data, the following HIPAA compliance measures must be implemented:

### Required Before Production:
- **Business Associate Agreements (BAAs)**: Execute BAAs with Deepgram, Anthropic, and Practice Fusion
- **Encryption**: Implement encryption at rest for all PHI in database and file storage
- **Audit Logging**: Add comprehensive audit trails for all PHI access and modifications
- **Access Controls**: Implement role-based access control (RBAC) and multi-factor authentication
- **Data Retention**: Define and implement data retention and secure deletion policies
- **Breach Notification**: Establish procedures for breach detection and notification
- **Security Assessment**: Conduct third-party security audit and penetration testing

These items are noted for awareness but are not blocking for the current MVP phase.

---

## Deployment Considerations

### Practice Fusion Sandbox Setup

Before production, test with Practice Fusion sandbox environment:

1. **Register Developer Account**:
   - Go to Practice Fusion developer portal
   - Create sandbox account
   - Generate test credentials

2. **Configure Sandbox Environment**:
   ```bash
   # .env.sandbox
   PRACTICE_FUSION_API_BASE=https://sandbox.practicefusion.com/api/v1
   PRACTICE_FUSION_CLIENT_ID=sandbox_client_id
   PRACTICE_FUSION_CLIENT_SECRET=sandbox_secret
   ```

3. **Create Test Data**:
   - Create 2-3 test patients in sandbox
   - Document patient IDs for testing
   - Practice encounter creation flow

### Production Readiness Checklist

**Security:**
- [ ] All EHR credentials encrypted at rest
- [ ] API keys stored in secure vault (not .env)
- [ ] HTTPS enforced for all connections
- [ ] WebSocket connections use WSS
- [ ] Rate limiting on all API endpoints

**Performance:**
- [ ] Redis configured for production load
- [ ] Celery workers scaled appropriately
- [ ] Database connection pooling optimized
- [ ] Audio streaming buffer sizes tuned
- [ ] WebSocket connection limits set

**Monitoring:**
- [ ] Error logging for all EHR operations
- [ ] Performance metrics for live transcription
- [ ] Sync failure alerts configured
- [ ] Celery task monitoring active
- [ ] Database query performance tracked

---

## Troubleshooting

### Live Transcription Issues

**Problem:** Audio not streaming
```bash
# Check browser console for errors
# Verify microphone permissions granted
# Test with: chrome://webrtc-internals/

# Backend logs should show:
# "WebSocket connected: session_xyz"
# "Audio chunk received: 1024 bytes"
```

**Problem:** Transcript not appearing
```bash
# Verify Deepgram connection in logs:
# "Deepgram connection started for session_xyz"

# Check Deepgram API key is valid:
curl -H "Authorization: Token YOUR_KEY" \
  https://api.deepgram.com/v1/projects

# Test with sample audio file first
```

**Problem:** High latency in transcript
```bash
# Check network latency to Deepgram
# Consider using Deepgram's regional endpoints
# Optimize audio chunk size (100-500ms recommended)
```

### EHR Sync Issues

**Problem:** Authentication failed
```bash
# Check token hasn't expired:
SELECT token_expires_at FROM ehr_credentials WHERE is_active = TRUE;

# Manually refresh token:
curl -X POST http://localhost:8000/api/v1/ehr/credentials/refresh \
  -H "Authorization: Bearer YOUR_JWT"
```

**Problem:** Patient search returns empty
```bash
# Verify exact match on DOB format (YYYY-MM-DD)
# Check for extra spaces in first/last name
# Try searching in Practice Fusion UI directly
# Verify patient exists in correct Practice Fusion account
```

**Problem:** Sync stuck in "pending"
```bash
# Check Celery worker is running:
docker-compose logs celery_worker

# Check Redis connection:
redis-cli ping

# Manually retry stuck sync:
curl -X POST http://localhost:8000/api/v1/notes/{note_id}/retry-sync \
  -H "Authorization: Bearer YOUR_JWT"

# View Celery task status:
celery -A app.celery_app inspect active
```

**Problem:** Encounter created but note missing
```bash
# Check sync logs for specific error:
SELECT error_message, response_payload 
FROM ehr_sync_logs 
WHERE note_id = 'YOUR_NOTE_ID';

# Verify note format is valid:
# - Check for special characters that need escaping
# - Ensure note isn't too long (max 10,000 chars for Practice Fusion)
# - Validate all required fields present
```

---

## Future Enhancements (Post Phase 2)

### Voice Enrollment
- Train speaker recognition model on provider's voice
- Automatically assign "provider" label to enrolled voice
- More accurate speaker diarization

### Real-Time Suggestions
- AI suggests ICD-10 codes during visit
- Medication dosage lookups
- Lab ordering recommendations

### Multi-Provider Support
- Multiple providers using same clinic credentials
- Provider-specific EHR mappings
- Collaborative note review

### Advanced EHR Features
- Bi-directional sync (pull patient data from EHR)
- Update existing encounters instead of creating new
- Lab results integration
- Prescription writing integration

### Mobile App
- Native iOS/Android apps for recording
- Offline recording with later sync
- Push notifications for sync status

---

## Contact & Support

For questions about Phase 2 implementation:
- Live transcription: Reference Deepgram docs at docs.deepgram.com
- Practice Fusion API: Check developer portal at developers.practicefusion.com
- General implementation: Contact project lead

For Claude Code: 
- Follow phases sequentially
- Complete all acceptance criteria before moving to next phase
- Test each feature thoroughly before integration
- Ask for clarification if any requirement is ambiguous
- Pay special attention to error handling and edge cases

**Key Success Metrics:**
- Live transcription latency < 2 seconds
- Transcription accuracy > 90% for medical terms
- EHR sync success rate > 95%
- Average time from visit end to EHR sync < 5 minutes