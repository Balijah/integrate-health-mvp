# /onboard_patient_flow

Verify the complete first-visit flow for a new patient. This is the highest-stakes user path. Trace every step through actual code files.

## Step 1: Provider Login
Read `frontend/src/pages/Login.tsx`, `frontend/src/store/authStore.ts`, `backend/app/api/auth.py`.
- Login submits to `POST /auth/login`?
- JWT stored correctly (not in localStorage)?
- Failed login shows clear error (not raw 401 or stack trace)?
- Login form resets on 401 so provider can re-enter credentials?
- Successful login redirects to dashboard?

## Step 2: Create New Visit
Read `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/NewVisit.tsx`, `backend/app/api/visits.py`.
- "New Visit" CTA visible on dashboard?
- Form requires `patient_ref` and `visit_date`?
- Client-side validation before submit?
- `POST /visits` called with correct payload?
- Redirects to visit detail or recording screen on success?
- New visit appears in sidebar immediately?

## Step 3: Record Audio
Read `frontend/src/components/AudioRecorder/AudioRecorder.tsx`, `frontend/src/hooks/useAudioRecorder.ts`.
- Recording starts on button click?
- Elapsed time in MM:SS?
- Stop works cleanly?
- Confirmation before discarding?
- Blob passed to upload handler?

## Step 4: Upload & Transcription
Read `backend/app/api/transcription.py`, `backend/app/services/transcription.py`.
- `POST /visits/{visit_id}/audio` accepts blob?
- File type and size validated server-side?
- Deepgram Nova-2 Medical called with diarization enabled?
- Status set to `transcribing` immediately?
- Frontend polls or subscribes to status?
- Provider sees loading state?
- Transcript displayed on completion?

## Step 5: Generate SOAP Note
Read `backend/app/api/notes.py`, `backend/app/services/note_generation.py`.
- "Generate Note" only available after transcript complete?
- Prompt includes functional medicine instructions?
- Uses "clinical rationale" framing (not "citations")?
- Empty fields omitted (not "N/A" or empty strings)?
- Note stored in `notes.content` JSONB?
- Blue dot sync state initialized for all four SOAP sections?

## Step 6: Review & Edit
Read `frontend/src/components/NoteEditor/NoteEditor.tsx`.
- All four SOAP sections editable?
- Edits saved via `PUT /visits/{visit_id}/notes/{note_id}`?
- Saving a section updates blue dot sync state in DB?
- Edits persist after page refresh?
- Export as markdown works?

## Step 7: Navigation & Session Isolation
- Navigating away from visit clears previous visit's state?
- Returning to visit loads correct saved note?
- Blue dot state correctly reflects sync status?

## Edge Cases
- Provider navigates away mid-recording — is there a warning?
- Deepgram transcription fails — is there a retry?
- Note generation times out — can provider retry?
- Provider tries to generate note before transcription complete?
- Transcript is empty or very short (< 100 words)?

## Output
```
## PATIENT ONBOARDING FLOW AUDIT — [DATE]

### FLOW STATUS: [✅ PASSING / ❌ BROKEN / ⚠️ DEGRADED]

### Step-by-Step Results
[For each step: ✅ Pass, ❌ Fail, ⚠️ Warning with details and file:line]

### Critical Blockers
[Steps that prevent completing a visit]

### Edge Case Results

### Recommendations
[Ordered fix list]
```
