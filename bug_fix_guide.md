# BUGFIX_CLAUDE_2.md — Integrate Health MVP Bug Fixes (Round 2)

## Overview

This document describes 6 bugs and features to implement in the deployed Integrate Health
MVP at app.integratehealth.ai. Follow each section sequentially. Complete ALL acceptance
criteria and run ALL specified tests for a given issue before moving to the next.
Do not modify any existing working functionality unless explicitly instructed.

---

## Testing Requirements (Global)

After completing ALL issues in this document, run the full test suite:

```bash
docker-compose exec backend pytest --cov=app --cov-report=term-missing
docker-compose exec frontend npm test -- --watchAll=false
```

Each individual issue also has its own testing requirements specified inline.
Do not skip tests. If a test fails, fix the underlying issue before proceeding.

---

## Issue 1 — Login Error Persists and Form Does Not Reset on Failure

### Problem
When a user enters an incorrect email or password, the app receives a 401 response
from `POST /api/v1/auth/login`. Instead of displaying the error persistently, the
form fully resets — clearing both the email and password fields and removing the
error message after a brief flash. This appears to be a state reset or re-render
triggered by the failed request.

### Expected Behavior
- On a failed login (401 or any non-200 response):
  - The email field retains the value the user typed
  - The password field is cleared (standard security practice)
  - An error message "Invalid email or password." is displayed below the form
    and remains visible until the user begins typing again or submits successfully
  - The form does NOT fully reset or re-render in a way that clears the email field
- On a successful login: existing behavior is preserved

### Instructions

1. Locate the login form component (`frontend/src/pages/Login.tsx` or equivalent)
2. Find the form submission handler and the state variables managing email, password,
   and error message
3. Identify what is causing the full form reset on 401 — likely one of:
   - A `setState` or store action that resets all form fields on any response
   - A component unmount/remount triggered by an auth store state change on failure
   - An error boundary or redirect logic firing on non-200 responses
4. Fix the 401 error path so that:
   - `email` state is preserved
   - `password` state is cleared (set to empty string)
   - An `errorMessage` state variable is set to "Invalid email or password."
   - The error message renders persistently below the submit button
5. Clear the error message when the user begins typing in either field (`onChange`)
6. Ensure the submit button re-enables after a failed attempt so the user can retry

### Testing
```
Manual test:
1. Navigate to /login
2. Enter a valid email with a wrong password
3. Click Sign In
4. Confirm: error message appears and persists
5. Confirm: email field still contains the email that was typed
6. Confirm: password field is empty
7. Confirm: form does not fully reset or flicker
8. Begin typing in the email field — confirm error message clears
9. Submit correct credentials — confirm successful login and no error shown
```

### Acceptance Criteria
- [ ] 401 response preserves email field value
- [ ] 401 response clears password field only
- [ ] "Invalid email or password." message is displayed and persists
- [ ] Error message clears when user begins typing in either field
- [ ] Form does not fully reset or re-render on failed login
- [ ] Existing successful login flow is unaffected

---

## Issue 2 — Start New Session Always Begins with Blank State

### Problem
When a user clicks "start new session" from within an existing visit detail page,
the new session is pre-populated with the previous visit's SOAP note content and
patient context. The current visit's data is being carried over into the new session
creation flow.

### Expected Behavior
Clicking "start new session" from anywhere in the application — the home dashboard
button, the top-right header button, or from within an existing visit detail page —
always creates a completely blank new session with no pre-populated patient data,
no SOAP content, and no reference to any previously viewed visit.

### Instructions

1. Locate the "start new session" button component(s). Based on the screenshots
   there are at least two: one on the home dashboard and one in the top-right header
   on the visit detail page
2. Trace what happens when the button is clicked — identify where the carryover
   is coming from. Likely causes:
   - The visit detail page is storing current visit data in a Zustand store slice
     that the new session form reads from on mount
   - The new session component is initializing its state from the store's
     `currentVisit` or equivalent rather than from a blank template
   - Navigation to the new session route is passing visit ID or state via
     React Router `location.state`
3. Fix the new session initialization so it always starts from a blank state:
   - Clear `currentVisit` (or equivalent store slice) before navigating to the
     new session route
   - Ensure the new session form/component initializes all fields to empty/null
     values on mount, regardless of store state
   - If React Router `location.state` is used to pass context, do not pass any
     visit-specific data when navigating from the "start new session" button
4. Verify the fix applies to ALL instances of the "start new session" button

### Testing
```
Manual test:
1. Create a visit, complete transcription, generate SOAP notes
2. While on the visit detail page with SOAP notes visible, click "start new session"
   in the top-right header
3. Confirm: new session form is completely blank — no patient name, no SOAP content
4. Return to home, click the large "start a new session" button
5. Confirm: same blank state
6. Complete a new session — confirm it saves independently with no data from
   the previous visit
```

### Acceptance Criteria
- [ ] Clicking "start new session" from a visit detail page creates a blank session
- [ ] Clicking "start new session" from the home dashboard creates a blank session
- [ ] No SOAP content from a previous visit appears in a new session
- [ ] No patient reference from a previous visit appears in a new session
- [ ] New session saves correctly and independently as its own record

---

## Issue 3 — Remove Sample Transcript Files and Audit Note Generation

### Problem
Two test files exist in `backend/scripts/` that are being unintentionally picked up
by the SOAP note generation service, causing hallucinated or incorrect content to
appear in generated notes for real patients:
- `backend/scripts/sample_transcript.txt`
- `backend/scripts/script_test.txt`

### Instructions

#### Step 1 — Delete the files
```bash
rm backend/scripts/sample_transcript.txt
rm backend/scripts/script_test.txt
```

Confirm both files are deleted before proceeding.

#### Step 2 — Audit the note generation service
Open `backend/app/services/note_generation.py` (or equivalent). Audit every location
where transcript content is assembled before being sent to the Claude API. Verify:

1. The transcript passed to the prompt is sourced **exclusively** from
   `visit.transcript` (the transcript field on the specific visit record being processed)
2. There are no hardcoded file paths, fallback file reads, or `open()` calls that
   could load content from the filesystem into the prompt
3. There is no default/fallback transcript string being used when `visit.transcript`
   is None or empty
4. If `visit.transcript` is None or empty, the service must raise an error or return
   early with a meaningful message — it must NOT fall back to any file or hardcoded string

#### Step 3 — Add a guard
In the note generation function, add an explicit guard at the top:

```python
async def generate_soap_note(transcript: str, additional_context: str = "") -> dict:
    if not transcript or not transcript.strip():
        raise ValueError(
            "Cannot generate SOAP note: transcript is empty or missing. "
            "Ensure transcription has completed successfully before generating notes."
        )
    # ... rest of function
```

#### Step 4 — Check scripts directory for any other test data
Scan the full `backend/scripts/` directory for any other `.txt`, `.json`, or audio
files that contain test/sample patient data. Remove any found. Document what was
removed in a comment in the PR.

### Testing
```bash
# Confirm files are gone
ls backend/scripts/sample_transcript.txt  # Should return: No such file or directory
ls backend/scripts/script_test.txt        # Should return: No such file or directory
```

```
Manual test:
1. Create a new visit
2. Attempt to generate a SOAP note WITHOUT completing transcription first
3. Confirm: system returns a clear error ("Transcription not yet complete")
   rather than generating a note with hallucinated content
4. Complete transcription for a visit, then generate a SOAP note
5. Confirm: generated note content matches only what was said in the actual recording
```

### Acceptance Criteria
- [ ] `sample_transcript.txt` is deleted from `backend/scripts/`
- [ ] `script_test.txt` is deleted from `backend/scripts/`
- [ ] Note generation service only uses `visit.transcript` from the database
- [ ] No filesystem reads or hardcoded fallback strings exist in the note generation path
- [ ] Attempting to generate a note with an empty transcript returns a clear error
- [ ] No other test data files remain in `backend/scripts/`

---

## Issue 4 — Blue Dot Sync State Tracked in Database and Clears Correctly

### Problem
The blue dot indicator next to a patient in the sidebar shows regardless of whether
the user has synced any SOAP sections. It is not being tracked anywhere — not in
the database, not in local state. As a result, it never clears even after all
sections have been synced.

### Expected Behavior
- The blue dot appears next to a patient in the sidebar when their most recent
  visit has at least one SOAP section (Subjective, Objective, Assessment, Plan)
  that has not yet been synced
- The blue dot clears when ALL FOUR sections have been individually synced
  (i.e., the user has clicked the sync/copy button for each section)
- "Patient Summary" does NOT count toward the sync state — it is separate
- Sync state is stored in the database and persists across page refreshes,
  browser sessions, and devices
- The blue dot is per-patient (based on their most recent visit)

### Backend Instructions

#### 1. Add synced_sections column to notes table
Create a new Alembic migration:
```bash
alembic revision --autogenerate -m "add synced_sections to notes"
```

In the migration file:
```python
op.add_column('notes', sa.Column(
    'synced_sections',
    postgresql.JSONB,
    nullable=False,
    server_default='{}')
)
```

Update the `Note` SQLAlchemy model:
```python
from sqlalchemy.dialects.postgresql import JSONB

synced_sections: Mapped[dict] = mapped_column(
    JSONB, nullable=False, default=dict, server_default="{}"
)
```

The `synced_sections` field stores which sections have been synced per note:
```json
{
  "subjective": true,
  "objective": false,
  "assessment": true,
  "plan": false
}
```

A note is considered fully synced when all four keys are `true`.

#### 2. Create endpoint to mark a section as synced
Add to `backend/app/api/notes.py` (or equivalent):

```python
from pydantic import BaseModel
from typing import Literal

SOAP_SECTIONS = {"subjective", "objective", "assessment", "plan"}

class SyncSectionRequest(BaseModel):
    section: Literal["subjective", "objective", "assessment", "plan"]

@router.post("/visits/{visit_id}/notes/{note_id}/sync-section")
async def sync_section(
    visit_id: str,
    note_id: str,
    payload: SyncSectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.visit_id == visit_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    # Merge new synced section into existing dict
    updated = dict(note.synced_sections or {})
    updated[payload.section] = True
    note.synced_sections = updated
    db.commit()
    db.refresh(note)

    all_synced = all(updated.get(s) for s in SOAP_SECTIONS)
    return {
        "synced_sections": note.synced_sections,
        "all_synced": all_synced,
    }
```

#### 3. Expose sync state in the visit/note response
Ensure `GET /visits/{visit_id}` and `GET /visits/{visit_id}/notes` responses
include `synced_sections` and a derived boolean `all_synced`:
```json
{
  "synced_sections": {
    "subjective": true,
    "objective": true,
    "assessment": true,
    "plan": true
  },
  "all_synced": true
}
```

Update the relevant Pydantic response schemas accordingly.

#### 4. Expose all_synced on the visits list endpoint
`GET /visits` (used to populate the sidebar patient list) should include
`all_synced` as a boolean field on each visit item so the sidebar can
determine dot visibility without an additional request per patient.

### Frontend Instructions

#### 1. Wire sync buttons to the new endpoint
Locate the sync/copy button for each SOAP section (Subjective, Objective,
Assessment, Plan) on the visit detail page.

When a sync button is clicked:
1. Perform the existing copy-to-clipboard behavior (do not remove this)
2. Additionally call `POST /api/v1/visits/{visit_id}/notes/{note_id}/sync-section`
   with `{ section: "subjective" }` (or whichever section was clicked)
3. On success, update the local store so the UI reflects the synced state
   (e.g., the sync button changes appearance to indicate it has been synced)
4. If all four sections are now synced, update the patient's `all_synced` flag
   in the store — this will cause the sidebar dot to clear

#### 2. Update sidebar to read all_synced from store
In the sidebar patient list component:
- Render the blue dot only when `all_synced === false` for the patient's
  most recent visit
- When `all_synced === true`, do not render the dot
- On initial load, read `all_synced` from the visits list API response
  (which now includes this field) — do not compute it client-side

#### 3. Sync button visual state
Each SOAP section's sync button should visually indicate whether that section
has already been synced:
- Unsynced: current appearance (green "sync" button)
- Synced: show "✓ synced" or equivalent, but still allow re-sync via
  "sync again" (do not block the user from re-copying)
- On page load, initialize button states from `note.synced_sections`

### Testing
```
Manual test:
1. Create a visit and generate SOAP notes
2. Confirm: blue dot appears next to the patient in the sidebar
3. Click sync on Subjective only
4. Refresh the page
5. Confirm: blue dot still shows (not all sections synced)
6. Confirm: Subjective sync button shows synced state; others do not
7. Click sync on Objective, Assessment, and Plan
8. Confirm: blue dot disappears from the sidebar immediately
9. Refresh the page
10. Confirm: blue dot remains gone after refresh
11. Log out, log back in on a different browser
12. Confirm: blue dot state is preserved (database-backed)
13. Confirm: Patient Summary sync button does NOT affect the blue dot
```

### Acceptance Criteria
- [ ] `synced_sections` JSONB column added to `notes` table via Alembic migration
- [ ] `POST /visits/{visit_id}/notes/{note_id}/sync-section` endpoint works correctly
- [ ] Sync state persists in database across page refreshes and sessions
- [ ] Blue dot shows when at least one of the four SOAP sections is unsynced
- [ ] Blue dot clears immediately when all four sections are synced
- [ ] Blue dot state is correct after page refresh (reads from database, not memory)
- [ ] Blue dot state is correct after logout and login on a new browser
- [ ] Patient Summary section does not affect blue dot state
- [ ] Each sync button visually reflects its synced/unsynced state on page load
- [ ] Clipboard copy behavior is preserved on sync button click

---

## Issue 5 — Patient Summary Email Sends to Patient

### Problem
The Patient Summary section on the visit detail page has an email input field and
a send icon button, but clicking send has no effect. There is no backend endpoint
to handle sending the summary to the patient's email.

### Expected Behavior
When the provider enters a patient's email address and clicks the send icon:
1. The patient summary text is sent to the provided email address via AWS SES
2. The provider sees a confirmation that the email was sent
3. If the email field is empty or the summary is empty, show a validation error
4. The email received by the patient is clearly formatted and patient-friendly

### Backend Instructions

#### 1. Add patient summary send endpoint
Add to `backend/app/api/notes.py` (or equivalent):

```python
class SendSummaryRequest(BaseModel):
    patient_email: EmailStr
    summary_text: str

@router.post("/visits/{visit_id}/notes/{note_id}/send-summary")
async def send_patient_summary(
    visit_id: str,
    note_id: str,
    payload: SendSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.summary_text.strip():
        raise HTTPException(status_code=400, detail="Summary text is empty.")

    note = db.query(Note).filter(
        Note.id == note_id,
        Note.visit_id == visit_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    success = send_patient_summary_email(
        patient_email=payload.patient_email,
        summary_text=payload.summary_text,
        provider_name=current_user.full_name,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send summary email.")
    return {"message": "Summary sent successfully."}
```

#### 2. Add patient summary email function to email service
In `backend/app/services/email.py` (created in BUGFIX_CLAUDE.md), add:

```python
def send_patient_summary_email(
    patient_email: str,
    summary_text: str,
    provider_name: str,
) -> bool:
    """Send a patient-friendly visit summary to the patient's email via SES."""
    client = boto3.client("ses", region_name=settings.AWS_SES_REGION)

    subject = f"Your Visit Summary from {provider_name}"
    body = (
        f"Dear Patient,\n\n"
        f"Here is a summary of your recent visit with {provider_name}:\n\n"
        f"{summary_text}\n\n"
        f"If you have any questions, please contact your provider directly.\n\n"
        f"— {provider_name} via Integrate Health"
    )

    try:
        client.send_email(
            Source=settings.AWS_SES_SENDER,
            Destination={"ToAddresses": [patient_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        return True
    except ClientError as e:
        print(f"Patient summary SES send failed: {e.response['Error']['Message']}")
        return False
```

### Frontend Instructions

1. Locate the Patient Summary section on the visit detail page
2. Find the email input field and the send icon button
3. On send button click:
   - Validate that the email field is not empty — show inline error if so
   - Validate that the summary textarea is not empty — show inline error if so
   - Call `POST /api/v1/visits/{visit_id}/notes/{note_id}/send-summary` with
     `{ patient_email, summary_text }`
   - Disable the send button while the request is in flight
   - On success: show a brief confirmation message "Summary sent to [email]"
   - On failure: show "Failed to send. Please try again."
4. Do not clear the email or summary fields after sending — the provider may
   want to review or resend

### Testing
```
Manual test:
1. Generate SOAP notes for a visit
2. Type content into the Patient Summary textarea
3. Leave email field blank, click send
4. Confirm: validation error appears ("Please enter a patient email address")
5. Enter a valid email address (use your own for testing), click send
6. Confirm: button shows loading state while request is in flight
7. Confirm: success message appears after send
8. Confirm: email is received with correct summary content and provider name
9. Leave summary textarea empty, enter email, click send
10. Confirm: validation error appears ("Summary is empty")
```

### Acceptance Criteria
- [ ] Clicking send with an empty email field shows a validation error
- [ ] Clicking send with an empty summary shows a validation error
- [ ] `POST /visits/{visit_id}/notes/{note_id}/send-summary` sends email via SES
- [ ] Patient receives a clearly formatted email with summary and provider name
- [ ] Send button is disabled during the request
- [ ] Success confirmation is shown after send
- [ ] Failure message is shown if SES call fails
- [ ] Email and summary fields are not cleared after a successful send

---

## Issue 6 — Forgot Password / Password Reset Flow

### Problem
The "forgot password?" link on the login page exists but has no functionality.
Clicking it does nothing. There is no password reset flow in the backend or frontend.

### Expected Behavior
1. User clicks "forgot password?" on the login page
2. User is shown a form to enter their email address
3. If the email exists in the system, a password reset email is sent via AWS SES
   containing a secure, time-limited reset link
4. User clicks the link, is taken to a reset password page, enters a new password
5. Password is updated; user is redirected to login with a success message
6. Reset links expire after 1 hour and cannot be reused

### Backend Instructions

#### 1. Add password reset token table
Create a new Alembic migration:
```bash
alembic revision --autogenerate -m "add password reset tokens"
```

```python
# In migration file
op.create_table(
    'password_reset_tokens',
    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
              server_default=sa.text('gen_random_uuid()')),
    sa.Column('user_id', postgresql.UUID(as_uuid=True),
              sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    sa.Column('token', sa.String(255), unique=True, nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used', sa.Boolean, default=False, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True),
              server_default=sa.text('NOW()')),
)
op.create_index('idx_reset_tokens_token', 'password_reset_tokens', ['token'])
```

Create `backend/app/models/password_reset_token.py`:
```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

#### 2. Add password reset endpoints
Add to `backend/app/api/auth.py`:

```python
import secrets
from datetime import datetime, timedelta, timezone
from app.models.password_reset_token import PasswordResetToken
from app.services.email import send_password_reset_email

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/auth/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    # Always return the same response to prevent email enumeration
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).delete()

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset_token)
        db.commit()

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
            user_name=user.full_name,
        )

    # Always return 200 regardless of whether email exists (security)
    return {"message": "If that email is registered, a reset link has been sent."}

@router.post("/auth/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == payload.token,
        PasswordResetToken.used == False,
    ).first()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired.")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    # Update password using existing password hashing utility
    from app.utils.security import hash_password
    user.hashed_password = hash_password(payload.new_password)

    reset_token.used = True
    db.commit()

    return {"message": "Password reset successfully. You can now log in."}
```

#### 3. Add password reset email function to email service
In `backend/app/services/email.py`, add:

```python
def send_password_reset_email(
    to_email: str,
    reset_url: str,
    user_name: str,
) -> bool:
    """Send a password reset link via AWS SES."""
    client = boto3.client("ses", region_name=settings.AWS_SES_REGION)

    body = (
        f"Hi {user_name},\n\n"
        f"We received a request to reset your Integrate Health password.\n\n"
        f"Click the link below to reset your password. "
        f"This link expires in 1 hour.\n\n"
        f"{reset_url}\n\n"
        f"If you did not request a password reset, you can safely ignore this email. "
        f"Your password will not change.\n\n"
        f"— The Integrate Health Team"
    )

    try:
        client.send_email(
            Source=settings.AWS_SES_SENDER,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Reset your Integrate Health password"},
                "Body": {"Text": {"Data": body}},
            },
        )
        return True
    except ClientError as e:
        print(f"Password reset SES send failed: {e.response['Error']['Message']}")
        return False
```

#### 4. Add FRONTEND_URL to config
Add to `.env` and `.env.example`:
```
FRONTEND_URL=https://app.integratehealth.ai
```
Add to `backend/app/config.py` Settings class:
```python
FRONTEND_URL: str = "https://app.integratehealth.ai"
```

### Frontend Instructions

#### 1. Forgot Password page
Create `frontend/src/pages/ForgotPassword.tsx`:
- A simple centered form matching the existing login page design language
- Single email input field with label "Enter your account email"
- A submit button "Send Reset Link"
- On submit: call `POST /api/v1/auth/forgot-password` with `{ email }`
- On response (always 200): show message
  "If that email is registered, a reset link has been sent. Check your inbox."
- Do not reveal whether the email exists or not (match backend behavior)
- "Back to login" link below the form

Add route in `frontend/src/App.tsx`:
```tsx
<Route path="/forgot-password" element={<ForgotPassword />} />
```

#### 2. Wire "forgot password?" link on login page
In `Login.tsx`, change the "forgot password?" link/button to navigate to
`/forgot-password` (React Router `<Link>` or `navigate()`).

#### 3. Reset Password page
Create `frontend/src/pages/ResetPassword.tsx`:
- On mount, read the `token` query parameter from the URL
  (`useSearchParams()` or equivalent)
- If no token is present, redirect to `/login`
- Show a form with:
  - "New password" input (type=password)
  - "Confirm new password" input (type=password)
  - Submit button "Reset Password"
- Validate that both fields match before submitting
- On submit: call `POST /api/v1/auth/reset-password` with
  `{ token, new_password }`
- On success (200): show "Password reset successfully." and redirect to
  `/login` after 2 seconds
- On failure (400): show the error message from the API response
  ("Invalid or expired reset link." or "Reset link has expired.")

Add route in `frontend/src/App.tsx`:
```tsx
<Route path="/reset-password" element={<ResetPassword />} />
```

Both new pages (`/forgot-password` and `/reset-password`) must be accessible
without authentication — add them as public routes outside the auth guard.

### Testing
```
Manual test — happy path:
1. Navigate to /login, click "forgot password?"
2. Confirm: navigates to /forgot-password
3. Enter your email address (burhankhan@integratehealth.ai), click Send Reset Link
4. Confirm: success message shown ("Check your inbox")
5. Confirm: reset email received with a working link
6. Click the link — confirm navigates to /reset-password with token in URL
7. Enter a new password and confirm it, click Reset Password
8. Confirm: success message shown, then redirect to /login after 2 seconds
9. Log in with the new password — confirm success
10. Confirm: old password no longer works

Manual test — edge cases:
11. Enter a non-existent email on /forgot-password
12. Confirm: same success message shown (no email enumeration)
13. Use an expired reset link (wait 1 hour, or manually expire in DB)
14. Confirm: "Reset link has expired." error shown
15. Use a reset link a second time after already resetting
16. Confirm: "Invalid or expired reset link." error shown
17. Enter mismatched passwords on /reset-password
18. Confirm: frontend validation error before API call is made
```

```bash
# Backend unit tests to add in backend/tests/test_auth.py
def test_forgot_password_known_email_sends_email():
    # Mock SES, confirm token created in DB

def test_forgot_password_unknown_email_returns_200():
    # Confirm 200 returned, no token created, no SES call

def test_reset_password_valid_token():
    # Create token, reset password, confirm hashed_password updated, token marked used

def test_reset_password_expired_token():
    # Create token with past expiry, confirm 400

def test_reset_password_already_used_token():
    # Mark token as used, confirm 400

def test_reset_password_invalid_token():
    # Random token string, confirm 400
```

### Acceptance Criteria
- [ ] "forgot password?" link navigates to `/forgot-password`
- [ ] `/forgot-password` and `/reset-password` are accessible without authentication
- [ ] `POST /auth/forgot-password` creates a token and sends reset email via SES
- [ ] Same response returned whether email exists or not (no enumeration)
- [ ] Reset email contains a working link to `/reset-password?token=...`
- [ ] `POST /auth/reset-password` updates the password on a valid, unexpired token
- [ ] Token is marked used after a successful reset and cannot be reused
- [ ] Expired tokens (> 1 hour) are rejected with a clear error
- [ ] Mismatched passwords on reset form are caught client-side before API call
- [ ] Successful reset redirects to `/login` after 2 seconds
- [ ] All new backend auth tests pass

---

## Final Checklist Before Deploying

- [ ] All 6 issues above have their acceptance criteria fully checked off
- [ ] `alembic upgrade head` has been run and all migrations applied cleanly
- [ ] Full backend test suite passes: `pytest --cov=app`
- [ ] Frontend builds without errors: `npm run build`
- [ ] Manual end-to-end test of the complete visit flow:
      login → new session → record → transcribe → generate notes →
      sync all sections → confirm blue dot clears → send patient summary
- [ ] No existing functionality has regressed (auth, visit creation,
      transcription, note generation, patient list)
- [ ] Sample transcript files confirmed absent from `backend/scripts/`
- [ ] AWS SES sender domain verified for all new email sending features
      (Issues 5 and 6 both send email — confirm SES is out of sandbox
      or recipient addresses are verified before testing in production)
