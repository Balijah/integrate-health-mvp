# Integrate Health — Dev Infrastructure Implementation

You are implementing a complete developer tooling and CI/CD infrastructure for the Integrate Health MVP. This is a HIPAA-compliant clinical documentation platform. Read this entire prompt before taking any action. Follow the phases in order and confirm with the user before proceeding past any checkpoint marked **[CONFIRM BEFORE CONTINUING]**.

---

## Project Context

**Stack:**
- Backend: FastAPI (Python 3.11) in a virtualenv (`venv`), running as a systemd service (`integrate-health.service`) on EC2
- Frontend: React + TypeScript + Vite, built to static files, served by nginx on EC2
- Database: AWS RDS PostgreSQL (managed, not on EC2)
- Migrations: Alembic
- No Docker in production

**Deployment pipeline (already exists — do not change it):**
- Local code → `deploy.sh` packages backend as tarball → uploads to S3 (`integrate-health-audio-317440775804`) → SSM sends command to EC2 to download, extract, run migrations, restart systemd service
- Frontend: `npm run build` locally → tarball → S3 → SSM extracts to `/var/www/html/` → nginx reload → CloudFront invalidation (`E3O39Z192PMEOR`)
- `deploy.sh` lives at the project root and must not be modified

**Existing `.claude/` structure:**
- `.claude/settings.local.json` already exists — do not modify or overwrite it
- No other files exist in `.claude/` yet

**GitHub:**
- Public repo, solo developer (Burhan)
- GitHub is source control only — it is NOT currently part of the deploy pipeline
- Goal: add GitHub Actions as a CI gate and optional CD trigger that calls `deploy.sh`

---

## What You Are Building

### Part 1 — Claude Code Slash Commands (`.claude/commands/`)
### Part 2 — Claude Code Hooks (`.claude/settings.json` + `.claude/hooks/`)
### Part 3 — Git Pre-commit Hook (`scripts/install_hooks.sh` + hook script)
### Part 4 — GitHub Actions Workflows (`.github/workflows/`)
### Part 5 — GitHub Supporting Files (PR template, Dependabot, settings doc)
### Part 6 — Version Infrastructure (if not already in place)

---

## PHASE 0 — Discovery (Do This First, No File Changes Yet)

Before creating anything, run the following checks and report findings:

```bash
# 1. Confirm .claude/ structure
ls -la .claude/

# 2. Check for existing tests
find . -type d -name "tests" | grep -v node_modules | grep -v .git
find . -name "test_*.py" -o -name "*_test.py" | grep -v node_modules | grep -v .git | head -20

# 3. Check for existing .github/ directory
ls -la .github/ 2>/dev/null || echo "No .github/ directory exists"

# 4. Find the version display in the frontend
grep -rn "version\|Version\|v1\.\|v0\." frontend/src/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".d.ts" | grep -iv "vite\|vitest\|package" | head -20

# 5. Confirm deploy.sh exists and is executable
ls -la deploy.sh

# 6. Check if version.json exists anywhere
find . -name "version.json" | grep -v node_modules | grep -v .git

# 7. Check current git branch and recent commits
git branch
git log --oneline -5

# 8. Check if CHANGELOG.md exists
ls -la CHANGELOG.md 2>/dev/null || echo "No CHANGELOG.md"

# 9. Check backend requirements for test dependencies
grep -iE "pytest|coverage|ruff|bandit" backend/requirements.txt || echo "No test deps found in requirements.txt"
```

Report all findings clearly. Then ask:

1. **Tests:** "I did not find an existing test suite. Before I create the CI workflow, should I scaffold a basic `backend/tests/` structure with a health check test and auth test stubs so CI has something to run? Or would you prefer CI skips the test step for now and just runs lint and type checks?"

2. **Version display:** Report exactly what you found for the version string in the frontend and ask: "I found the version displayed at [file:line] as [what you found]. Should I convert this to read from `frontend/public/version.json` so the version bump hook can update it automatically? This requires a small change to that component."

**[CONFIRM BEFORE CONTINUING]** — Wait for answers to both questions before proceeding to Phase 1.

---

## PHASE 1 — Claude Code Slash Commands

Create the following files. Each is a markdown prompt file that Claude Code executes with full codebase context when the `/command` is invoked.

### `.claude/commands/regression_test.md`

````markdown
# /regression_test

You are performing a full regression test for the Integrate Health MVP. Be thorough and systematic. Read actual files — do not rely on memory.

## Step 1: Run Automated Checks

```bash
# Python lint
cd backend && source venv/bin/activate && ruff check app/ 2>&1 || pip install ruff && ruff check app/
# TypeScript type check
cd frontend && npx tsc --noEmit 2>&1
# Backend tests (if tests/ exists)
cd backend && source venv/bin/activate && pytest tests/ -v --tb=short 2>&1 || echo "No test suite found"
```

## Step 2: API Endpoint Audit

Read all files in `backend/app/api/`. For every route, verify:
- Authentication dependency (`get_current_user`) is present on all protected routes
- User ownership validation exists (user_id scoping — no cross-user data access)
- Input validation via Pydantic schemas
- No unhandled exceptions that would return a 500 with a stack trace

Flag any endpoint missing any of the above.

## Step 3: Critical Path Walkthrough

Trace these flows through actual code files:

**Path A — Full visit workflow:**
Login → Create visit → Record audio → Upload audio → Deepgram transcription → Claude/Bedrock SOAP generation → Note stored in DB → Blue dot sync state initialized → Provider edits note → Sync state updated per section

**Path B — Returning provider:**
Login → JWT stored correctly → Sidebar patient list loads (scoped to user) → Click visit → Visit detail loads → Existing note loads with correct sync state

**Path C — Session isolation:**
Provider views Visit A → navigates to Visit B → confirm Visit A content does NOT persist in state → check `frontend/src/store/visitStore.ts` for stale state risk

## Step 4: State Management Audit

Read `frontend/src/store/authStore.ts` and `frontend/src/store/visitStore.ts`. Check:
- Auth state cleared on logout
- Visit/note state cleared on navigation away from a visit
- Sidebar patient list refreshes after new visit creation
- No stale state from previous visit bleeds into new visit

## Step 5: Database Integrity

Read `backend/app/models/`. Verify:
- Foreign keys have `ON DELETE CASCADE` where appropriate
- Indexes exist on `visits.user_id` and `notes.visit_id`
- `notes.content` JSONB partial updates preserve unmodified fields
- `sync_state` JSONB field exists and covers all four SOAP sections (S, O, A, P)

## Step 6: SOAP Note Quality

Read `backend/app/services/note_generation.py`. Verify:
- Prompt omits fields entirely rather than writing empty strings or "N/A"
- Uses "clinical rationale" framing, not "citations"
- JSON output parsed with error handling
- Empty/sample transcripts are blocked from triggering generation

## Output Format

```
## REGRESSION REPORT — [DATE]

### ✅ PASSING
- [list]

### ❌ FAILING
- [CRITICAL] description — file:line
- [HIGH] ...

### ⚠️ WARNINGS
- description + recommendation

### 📋 COVERAGE SUMMARY
- Backend coverage: X% (or "no test suite")
- Modules below 60%: [list]

### 🔁 REGRESSION RISK
- Based on recent git commits, highest-risk areas: [list]
```
````

---

### `.claude/commands/security_audit.md`

````markdown
# /security_audit

Comprehensive security audit for Integrate Health MVP. This is a HIPAA application. All findings must be ranked CRITICAL / HIGH / MEDIUM / LOW with specific file paths, line numbers, and remediation steps.

**CRITICAL** = PHI exposure, auth bypass, or breach vector. Fix before next deploy.
**HIGH** = Exploitable with moderate effort. Fix this sprint.
**MEDIUM** = Real weakness. Fix within 2 sprints.
**LOW** = Best-practice gap. Next hardening pass.

## Area 1: Authentication & Authorization
Read `backend/app/api/deps.py`, `backend/app/services/auth.py`, `backend/app/utils/security.py`.
- JWT secret loaded from env, never hardcoded?
- JWT algorithm explicitly validated on decode (algorithm confusion attack)?
- Token expiration enforced on every protected request?
- bcrypt with ≥12 rounds?
- Every protected route has `get_current_user` dependency?
- All data routes validate `user_id` ownership (cannot access another user's visits/notes)?
- Rate limiting on `/auth/login`?
- Forgot-password tokens are time-limited and single-use?

## Area 2: PHI Handling
Read all `backend/app/api/`, `backend/app/services/`, `backend/app/models/`.
- Transcripts never written to application logs?
- Patient names/identifiable info not stored beyond `patient_ref`?
- API responses not over-returning data?
- Audio files not accessible via unauthenticated direct URL?
- Note export endpoint not leaking system internals?

## Area 3: API Security
Read `backend/app/main.py` and all route files.
- CORS `allow_origins` is NOT `"*"`?
- Request size limiting for audio uploads?
- File types validated server-side (MIME type, not just extension)?
- Audio size cap enforced server-side from config?
- All queries use SQLAlchemy ORM (no raw SQL f-strings)?
- Production errors return no stack traces?
- `APP_DEBUG=false` in production?

## Area 4: Secrets & Environment
Read `backend/app/config.py`, `.env.example`.
- All secrets from environment variables?
- `.gitignore` includes `.env`, `uploads/`?
- No hardcoded keys anywhere in codebase?
- AWS credentials from IAM roles / Secrets Manager, not hardcoded?
- `.env.example` has only placeholder values?

## Area 5: Infrastructure
- HTTPS enforced with HTTP redirect?
- DB connections use SSL (`sslmode=require`)?
- Backend port (8000) not directly exposed to internet (behind ALB/nginx)?

## Area 6: Frontend
Read `frontend/src/store/authStore.ts`, `frontend/src/api/client.ts`.
- JWT NOT in localStorage (vulnerable to XSS)?
- No `dangerouslySetInnerHTML`?
- Auth state fully cleared on logout?
- No hardcoded API keys in frontend source?
- Axios client auto-attaches Authorization header?

## Area 7: HIPAA Technical Safeguards
- Every data access requires auth + ownership?
- PHI access events logged (who, what, when)?
- All PHI over HTTPS only?
- Audio/transcripts encrypted at rest (S3 SSE)?
- BAA confirmed for Deepgram and AWS Bedrock?
- Data deletion mechanism exists?

## Output
```
## SECURITY AUDIT REPORT — [DATE]

### CRITICAL FINDINGS
[#] [CRITICAL] Title
    File: path/to/file.py:line
    Issue: what is wrong
    Risk: what could happen
    Fix: exact remediation steps

### HIGH / MEDIUM / LOW FINDINGS
[same format]

### PASSED CHECKS ✅
[each check that passed with file verified]

### SUMMARY
Total: X (Critical: X, High: X, Medium: X, Low: X)
Highest risk area: ...
Recommended immediate action: ...
```
````

---

### `.claude/commands/financial_audit.md`

````markdown
# /financial_audit

Comprehensive cost analysis for Integrate Health MVP infrastructure.

## Context
Services in use: AWS EC2, ALB, RDS PostgreSQL, S3, SES, Bedrock (Claude), Deepgram Nova-2 Medical, CloudFront, GoDaddy.
Pilot client: Kare Health (single clinic).
Variable costs (Bedrock, Deepgram) are healthy COGS — they scale with revenue-generating visits.
Fixed costs (EC2, RDS, ALB) are overhead to minimize at current scale.

## Step 1: Gather Config
Read `backend/app/config.py`, `backend/app/services/transcription.py`, `backend/app/services/note_generation.py`, and `deploy.sh` to identify all external services and usage patterns.

## Step 2: Cost Analysis Per Service

**AWS Bedrock (Claude SOAP generation)**
- Identify model from `note_generation.py`
- Estimate input tokens: system prompt length + average transcript length
- Estimate output tokens: full SOAP JSON structure
- Calculate cost per visit at current Bedrock pricing
- Project monthly cost at 10 / 50 / 200 visits/day

**Deepgram (transcription)**
- Model: Nova-2 Medical (~$0.0043/minute pre-recorded)
- Estimate average functional medicine visit duration (20–45 min)
- Cost per visit
- Project monthly cost at 10 / 50 / 200 visits/day
- Flag: volume pricing available at scale?

**AWS EC2** — estimate based on visible instance usage patterns
**AWS RDS** — estimate based on config
**AWS ALB** — ~$16/month base + LCU costs
**AWS S3** — audio storage + tarball deploys + frontend static files
**CloudFront** — data transfer costs for frontend delivery
**AWS SES** — ~$0.10/1,000 emails (negligible at pilot scale)

## Step 3: Cost Table

| Service | 10 visits/day | 50 visits/day | 200 visits/day |
|---------|--------------|--------------|----------------|
| EC2 | $X/mo | $X/mo | $X/mo |
| RDS | $X/mo | $X/mo | $X/mo |
| ALB | $X/mo | $X/mo | $X/mo |
| S3 + CF | $X/mo | $X/mo | $X/mo |
| Bedrock | $X/mo | $X/mo | $X/mo |
| Deepgram | $X/mo | $X/mo | $X/mo |
| SES | $X/mo | $X/mo | $X/mo |
| **TOTAL** | **$X/mo** | **$X/mo** | **$X/mo** |
| **Per visit** | **$X.XX** | **$X.XX** | **$X.XX** |

## Step 4: Margin Analysis

At $99 / $149 / $199 per provider per month — what is gross margin at each scale tier?
How many providers needed to break even on infrastructure?

## Step 5: Optimization Opportunities (ranked by ROI)

**Immediate (zero risk):**
- Delete raw audio from S3 after transcript confirmed stored
- Confirm RDS Multi-AZ is OFF for pilot (not needed, saves ~$30-50/mo)
- CloudWatch log retention set (not infinite)

**Short-term:**
- EC2 + RDS Reserved Instances (1-year saves ~40%)
- Bedrock prompt optimization (shorter prompt = lower token cost)
- Deepgram enterprise/pre-pay pricing at volume

**Medium-term:**
- Audio compression before upload
- Cache repeated note generation for same transcript

## Step 6: Financial Risk Flags
- Is there a Deepgram spending cap?
- Is there an AWS budget alert configured?
- Is Bedrock token usage logged per visit (needed for accurate COGS)?
- Any zombie resources (unused EC2, unattached EBS, empty S3 buckets)?

## Output
```
## FINANCIAL AUDIT REPORT — [DATE]

### CURRENT ESTIMATED MONTHLY COSTS
[table]

### COST PER VISIT PROCESSED
[at each scale]

### MARGIN ANALYSIS
[table]

### TOP 3 COST DRIVERS
1. [service] — $X/mo — why

### OPTIMIZATION RECOMMENDATIONS
[ranked by ROI]

### FINANCIAL RISK FLAGS

### ASSUMPTIONS & DATA GAPS
```
````

---

### `.claude/commands/hipaa_audit.md`

````markdown
# /hipaa_audit

Thorough HIPAA Security Rule audit (45 CFR Part 164) for Integrate Health MVP. This application is a HIPAA Business Associate handling PHI on behalf of covered entities. Read actual files — do not summarize from memory.

## PHI in This Application
- Visit transcripts (patient speech with health information)
- SOAP note content (diagnoses, medications, symptoms, supplements)
- Audio recordings of patient visits
- `patient_ref` — verify this is truly non-PHI throughout all code paths

## Area 1: Access Controls (§164.312(a))
- Unique user identifiers (UUID)?
- No shared/generic accounts?
- JWT expiration enforced?
- Token invalidation on logout?
- Passwords hashed with bcrypt (not reversible)?
- Session timeout after inactivity?

## Area 2: Audit Controls (§164.312(b))
Read `backend/app/main.py` and any middleware.
- PHI access events logged (who accessed which record, when)?
- Login attempts (success + failure) logged?
- Note generation events logged (visit_id, user_id, timestamp — NOT transcript content)?
- Audit logs protected from modification?
- Log retention ≥6 years?

**CRITICAL FLAG:** If there is NO audit logging, flag as CRITICAL gap with recommendation to add an `audit_log` table to PostgreSQL.

## Area 3: Integrity Controls (§164.312(c))
- `updated_at` timestamp reliably updated on every note edit?
- DB transactions used for atomic visit + note writes?
- Mechanism to detect tampering with finalized notes?

## Area 4: Transmission Security (§164.312(e))
- HTTPS enforced on all endpoints?
- Deepgram API call over HTTPS?
- AWS Bedrock call over HTTPS?
- SES transmission encrypted?
- DB connection SSL (`sslmode=require`)?
- HTTP → HTTPS redirect in place?
- TLS 1.2 minimum?

## Area 5: Business Associate Agreements
Verify BAA status for each service:

| Service | Handles PHI? | BAA Required? | Status |
|---------|-------------|---------------|--------|
| AWS (EC2, RDS, S3, SES, Bedrock) | Yes | Yes | Verify |
| Deepgram | Yes — audio transcribed | Yes | BAA reportedly signed under Integrate Health LLC — confirm |
| CloudFront | Yes — serves frontend that displays PHI | Yes | Covered under AWS BAA |
| GoDaddy | No — DNS only | No | N/A |

## Area 6: Minimum Necessary (§164.502(b))
- Only minimum PHI collected?
- API endpoints not over-returning PHI?
- Patient summary email includes only necessary info, not full transcripts?
- `patient_ref` treated as non-PHI throughout — never converted to real patient name?
- Providers cannot access other providers' visits/notes?

## Area 7: Incident Response Readiness
- Alerts for unusual access patterns?
- RDS automated backups enabled?
- Documented incident response procedure?

## Output
```
## HIPAA COMPLIANCE AUDIT REPORT — [DATE]
## Framework: HIPAA Security Rule (45 CFR Part 164)

### EXECUTIVE SUMMARY
Overall posture: [Strong / Adequate / Needs Improvement / At Risk]
Critical gaps: X | Total findings: X

### CRITICAL GAPS (Must fix before handling real PHI at scale)
[#] [CRITICAL] Requirement: §164.XXX
    Finding: what is missing
    Risk: specific violation and consequence
    Remediation: exact steps
    Effort: [Hours / Days / Weeks]

### HIGH / MEDIUM / LOW GAPS
[same format]

### PHI DATA FLOW MAP
[where PHI enters, is stored, processed, transmitted, deleted]

### BAA STATUS TABLE

### PASSED CONTROLS ✅
[each control with file reference]

### RECOMMENDED NEXT STEPS
```
````

---

### `.claude/commands/onboard_patient_flow.md`

````markdown
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
````

---

### `.claude/commands/db_migration_check.md`

````markdown
# /db_migration_check

Review pending Alembic migrations before running in production. Run this BEFORE any `alembic upgrade head` on the live RDS instance.

If no specific migration provided, review all unapplied migrations in `backend/alembic/versions/`.

## Step 1: Read Migration File(s)
For each pending migration, identify: ID, description, all operations in `upgrade()`, all operations in `downgrade()`.

## Step 2: Classify Each Operation

🔴 **DESTRUCTIVE** (data loss — requires explicit confirmation):
- `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`

🟠 **BREAKING** (causes downtime or app errors if uncoordinated):
- `ADD COLUMN NOT NULL` without default on existing table
- Column type change (VARCHAR → INTEGER, etc.)
- Renaming a column still referenced by app code
- Unique constraint on column with existing duplicates
- Removing a column the app still reads/writes

🟡 **RISKY** (safe if done correctly):
- `ADD COLUMN NOT NULL WITH DEFAULT`
- Adding index on large table without `CONCURRENTLY`
- NULL → NOT NULL constraint change
- JSONB structure change (app must handle both old and new schemas)

🟢 **SAFE**:
- `ADD COLUMN NULL`
- `CREATE TABLE`
- `CREATE INDEX CONCURRENTLY`
- Adding nullable foreign key
- Dropping an index

## Step 3: Application Compatibility
For any non-green operation, read the relevant models and API code:
- Renamed column still referenced in `backend/app/models/` or `backend/app/api/`?
- Dropped column still queried anywhere?
- Type change compatible with existing app code?
- NOT NULL constraint — does app ever write NULL to this column?
- JSONB structure change on `notes.content` or `notes.sync_state` — does NoteEditor still work?

## Step 4: Rollback Safety
- Does `downgrade()` actually reverse the migration?
- Is any `downgrade()` a no-op or `NotImplementedError`? Flag this.
- After rollback, will app code still function?

## Step 5: Performance Impact
- Will any operation lock a table with existing rows?
- Recommend `CONCURRENTLY` for index operations on non-empty tables.

## Pre-Migration Checklist
- [ ] RDS snapshot exists (taken within 24 hours)
- [ ] Migration tested locally against a copy of the schema
- [ ] Downgrade tested
- [ ] App code for the new schema is already deployed (or deploying atomically)

## Output
```
## DB MIGRATION REVIEW — [DATE]
## Migration: [ID] — [description]

### OPERATIONS
[each operation with classification: 🔴/🟠/🟡/🟢]

### VERDICT: [✅ SAFE / ⚠️ CAUTION / 🚫 DO NOT RUN]

### Findings
### Required Actions Before Running
### Rollback Plan
### Post-Migration Verification
```
````

---

### `.claude/commands/context_refresh.md`

````markdown
# /context_refresh

Rebuild a complete picture of the current project state. Run this at the start of every Claude Code session. Read actual files — do not rely on memory.

## Step 1: Recent Git History
```bash
git log --oneline -20
git status
git diff --stat HEAD~1 2>/dev/null || true
```
What were the last 5–10 meaningful changes? Uncommitted files?

## Step 2: Current Version
```bash
cat frontend/public/version.json 2>/dev/null || \
grep -rn "version\|Version" frontend/src/ --include="*.tsx" --include="*.ts" | grep -iv "vite\|package\|node_modules" | head -5
```
What is the current version? When last bumped?

## Step 3: Service Health
```bash
# Check systemd service status (via SSM if needed, or note it's on EC2)
echo "Backend runs as systemd service: integrate-health.service"
echo "Frontend served by nginx from /var/www/html/"
echo "DB: AWS RDS PostgreSQL (managed)"

# Check local backend if running
curl -sf http://localhost:8000/health 2>/dev/null && echo "Local backend: UP" || echo "Local backend: not running locally"

# Check Alembic migration state
cd backend && source venv/bin/activate 2>/dev/null && alembic current 2>&1 || echo "Cannot check alembic locally"
```

## Step 4: Database Schema State
Read all files in `backend/app/models/`. Report:
- All tables with notable columns
- JSONB fields and their expected structures
- Recent additions (sync_state, clinic_id, etc.)
Cross-reference with latest migration in `backend/alembic/versions/`.

## Step 5: In-Progress Work
```bash
ls -la BUGFIX_*.md SPEC_*.md *.md 2>/dev/null | grep -v README | grep -v CHANGELOG
```
Summarize any active BUGFIX or SPEC files: what's being worked on and what's remaining.

## Step 6: Frontend State
Read `frontend/src/store/authStore.ts` and `frontend/src/store/visitStore.ts`. Report:
- State being managed
- TODOs or FIXMEs

Read `frontend/src/App.tsx` for current routing structure.

## Step 7: Open TODOs
```bash
grep -rn "TODO\|FIXME\|HACK\|XXX\|BUG" backend/app/ frontend/src/ \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  | grep -v node_modules | grep -v ".git" | head -30
```

## Step 8: Test Status
```bash
cd backend && source venv/bin/activate 2>/dev/null && \
  pytest tests/ --tb=no -q 2>&1 | tail -5 || echo "No test suite or venv not active locally"
```

## Output
```
## PROJECT CONTEXT REFRESH — [DATE/TIME]

### CURRENT VERSION: X.X.X

### INFRASTRUCTURE
- Backend: systemd (integrate-health.service) on EC2
- Frontend: nginx → /var/www/html/ on EC2
- Database: AWS RDS PostgreSQL
- Migrations: [up to date / X pending]

### RECENT CHANGES (last 10 commits)

### SCHEMA STATE
[tables and notable columns]

### IN-PROGRESS WORK
[active BUGFIX/SPEC files and status]

### OPEN TODOs
[file:line — description]

### TEST STATUS

### KEY REMINDERS FOR THIS SESSION
[fragile areas, recent breakage, pending decisions]
```
````

---

## PHASE 2 — Claude Code Hooks

### `.claude/settings.json`

Create this file. Do NOT modify or touch `.claude/settings.local.json`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/pre_deploy_guard.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/version_bump.sh"
          }
        ]
      }
    ]
  }
}
```

---

### `.claude/hooks/pre_deploy_guard.sh`

```bash
#!/bin/bash
# Pre-deploy regression guard for Integrate Health MVP
# Intercepts deploy commands and runs a gate before allowing them.
# Triggers on: ./deploy.sh, bash deploy.sh, any variant

COMMAND="${CLAUDE_TOOL_INPUT_COMMAND:-}"
IS_DEPLOY=false

if echo "$COMMAND" | grep -qE "(deploy\.sh|git push (origin )?(main|production|master))"; then
  IS_DEPLOY=true
fi

if [ "$IS_DEPLOY" = false ]; then
  exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚦 PRE-DEPLOY REGRESSION GATE — Integrate Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Detected: $COMMAND"
echo ""

FAILURES=0

# Check 1: TypeScript type check
echo "▶ [1/3] TypeScript type check..."
if cd frontend && npx tsc --noEmit 2>&1; then
  echo "  ✅ TypeScript passed"
  cd ..
else
  echo "  ❌ TypeScript errors found"
  cd ..
  FAILURES=$((FAILURES + 1))
fi

# Check 2: Python lint
echo ""
echo "▶ [2/3] Python lint (ruff)..."
if cd backend && source venv/bin/activate 2>/dev/null && ruff check app/ 2>&1; then
  echo "  ✅ Python lint passed"
  cd ..
else
  echo "  ⚠️  Ruff issues found (review above) — non-blocking"
  cd ..
fi

# Check 3: Backend tests (if test suite exists)
echo ""
echo "▶ [3/3] Backend tests..."
if [ -d "backend/tests" ] && [ "$(find backend/tests -name 'test_*.py' | wc -l)" -gt 0 ]; then
  if cd backend && source venv/bin/activate 2>/dev/null && pytest tests/ -q --tb=short 2>&1; then
    echo "  ✅ Tests passed"
    cd ..
  else
    echo "  ❌ Tests FAILED"
    cd ..
    FAILURES=$((FAILURES + 1))
  fi
else
  echo "  ⚠️  No test suite found — skipping"
fi

# Check 4: No uncommitted changes to critical files
echo ""
echo "▶ Checking for uncommitted critical changes..."
DIRTY=$(git diff --name-only 2>/dev/null | grep -E "(migration|models|auth|security)" | head -5)
if [ -n "$DIRTY" ]; then
  echo "  ⚠️  Uncommitted changes to critical files:"
  echo "$DIRTY"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAILURES -gt 0 ]; then
  echo ""
  echo "  🚫 DEPLOY BLOCKED — $FAILURES check(s) failed."
  echo "  Fix failures above, then re-run deploy."
  echo "  Emergency override: SKIP_DEPLOY_GATE=1 ./deploy.sh"
  echo ""
  if [ "${SKIP_DEPLOY_GATE:-0}" = "1" ]; then
    echo "  ⚠️  Override active — proceeding despite failures."
    exit 0
  fi
  exit 1
else
  echo ""
  echo "  ✅ All checks passed — deploy cleared."
  echo ""
  exit 0
fi
```

---

### `.claude/hooks/version_bump.sh`

```bash
#!/bin/bash
# Version bump hook — runs after git commits to main
# Bumps frontend/public/version.json and appends to CHANGELOG.md
#
# Commit message conventions:
#   feat: ...     → bumps MINOR (1.0.0 → 1.1.0)
#   breaking: ... → bumps MAJOR (1.0.0 → 2.0.0)
#   anything else → bumps PATCH (1.0.0 → 1.0.1)

COMMAND="${CLAUDE_TOOL_INPUT_COMMAND:-}"
EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-1}"

# Only run after successful git commit
if ! echo "$COMMAND" | grep -qE "git commit"; then
  exit 0
fi
if [ "$EXIT_CODE" != "0" ]; then
  exit 0
fi

# Only on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ "$BRANCH" != "main" && "$BRANCH" != "production" ]]; then
  exit 0
fi

VERSION_FILE="frontend/public/version.json"

# Create if missing
if [ ! -f "$VERSION_FILE" ]; then
  mkdir -p "$(dirname "$VERSION_FILE")"
  echo '{"major":1,"minor":0,"patch":0,"version":"1.0.0","built_at":"","git_hash":"","branch":"main"}' > "$VERSION_FILE"
fi

MAJOR=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('major',1))")
MINOR=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('minor',0))")
PATCH=$(python3 -c "import json; d=json.load(open('$VERSION_FILE')); print(d.get('patch',0))")
OLD="$MAJOR.$MINOR.$PATCH"

LAST_MSG=$(git log -1 --format="%s" 2>/dev/null)

if echo "$LAST_MSG" | grep -qiE "^(feat|feature):"; then
  MINOR=$((MINOR + 1)); PATCH=0; TYPE="minor"
elif echo "$LAST_MSG" | grep -qiE "^(break|breaking|major):"; then
  MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0; TYPE="major"
else
  PATCH=$((PATCH + 1)); TYPE="patch"
fi

NEW="$MAJOR.$MINOR.$PATCH"
BUILT_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

cat > "$VERSION_FILE" << EOF
{
  "major": $MAJOR,
  "minor": $MINOR,
  "patch": $PATCH,
  "version": "$NEW",
  "built_at": "$BUILT_AT",
  "git_hash": "$GIT_HASH",
  "branch": "$BRANCH"
}
EOF

# Update CHANGELOG.md
CHANGELOG="CHANGELOG.md"
if [ ! -f "$CHANGELOG" ]; then
  printf "# Changelog — Integrate Health MVP\n\n---\n\n" > "$CHANGELOG"
fi

ENTRY="## [$NEW] — $(date -u +"%Y-%m-%d") — $GIT_HASH\n- $LAST_MSG\n"
TEMP=$(mktemp)
head -4 "$CHANGELOG" > "$TEMP"
printf "\n$ENTRY" >> "$TEMP"
tail -n +5 "$CHANGELOG" >> "$TEMP"
mv "$TEMP" "$CHANGELOG"

git add "$VERSION_FILE" "$CHANGELOG" 2>/dev/null

echo ""
echo "  📦 Version: $OLD → $NEW ($TYPE bump)"
echo "  📝 CHANGELOG.md updated"
echo ""
```

Make both hook scripts executable:
```bash
chmod +x .claude/hooks/pre_deploy_guard.sh
chmod +x .claude/hooks/version_bump.sh
```

---

## PHASE 3 — Git Pre-commit Hook

### `scripts/install_hooks.sh`

This is a one-time setup script the developer runs after cloning.

```bash
#!/bin/bash
# One-time dev setup for Integrate Health
# Run: bash scripts/install_hooks.sh

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔧 Installing Integrate Health dev hooks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Git pre-commit hook
echo "▶ Installing git pre-commit hook..."
cp scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "  ✅ .git/hooks/pre-commit installed"

# Claude Code hook permissions
echo "▶ Setting Claude Code hook permissions..."
chmod +x .claude/hooks/pre_deploy_guard.sh
chmod +x .claude/hooks/version_bump.sh
echo "  ✅ Claude Code hooks executable"

# Initialize version.json
VERSION_FILE="frontend/public/version.json"
echo "▶ Checking version.json..."
if [ ! -f "$VERSION_FILE" ]; then
  mkdir -p "$(dirname "$VERSION_FILE")"
  GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "initial")
  cat > "$VERSION_FILE" << EOF
{
  "major": 1,
  "minor": 0,
  "patch": 0,
  "version": "1.0.0",
  "built_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "git_hash": "$GIT_HASH",
  "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"
}
EOF
  echo "  ✅ Created version.json (v1.0.0)"
else
  V=$(python3 -c "import json; print(json.load(open('$VERSION_FILE')).get('version','unknown'))" 2>/dev/null || echo "unknown")
  echo "  ✅ version.json exists — current version: $V"
fi

# CHANGELOG
echo "▶ Checking CHANGELOG.md..."
if [ ! -f "CHANGELOG.md" ]; then
  cat > CHANGELOG.md << 'EOF'
# Changelog — Integrate Health MVP

All notable changes documented here automatically on commits to main.

---

## [1.0.0] — Initial release
- MVP: audio recording, Deepgram transcription, Claude SOAP note generation
- Pilot client: Kare Health

EOF
  echo "  ✅ CHANGELOG.md created"
else
  echo "  ✅ CHANGELOG.md already exists"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Setup complete!"
echo ""
echo "  Slash commands available in Claude Code:"
echo "  /regression_test      — Full regression check"
echo "  /security_audit       — Security vulnerability scan"
echo "  /financial_audit      — Cost analysis"
echo "  /hipaa_audit          — HIPAA compliance assessment"
echo "  /onboard_patient_flow — First-visit flow verification"
echo "  /db_migration_check   — Safe migration review"
echo "  /context_refresh      — Project state for new sessions"
echo ""
echo "  Commit conventions for version bumping:"
echo "  feat: ...     → MINOR bump"
echo "  breaking: ... → MAJOR bump"
echo "  fix: ...      → PATCH bump (default)"
echo ""
```

### `scripts/pre-commit.sh`

```bash
#!/bin/bash
# Git pre-commit hook for Integrate Health
# Runs on every commit: lint, type check, secret scan

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔍 Pre-commit — Integrate Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FAILURES=0

# Python lint on staged .py files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$" || true)
if [ -n "$STAGED_PY" ]; then
  echo "▶ Python lint (ruff)..."
  if cd backend && source venv/bin/activate 2>/dev/null && \
     echo "$STAGED_PY" | sed 's|backend/||g' | xargs ruff check 2>&1; then
    echo "  ✅ Python lint passed"
    cd ..
  else
    echo "  ❌ Ruff errors found"
    cd ..
    FAILURES=$((FAILURES + 1))
  fi
fi

# TypeScript check on staged .ts/.tsx files
STAGED_TS=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.(ts|tsx)$" || true)
if [ -n "$STAGED_TS" ]; then
  echo "▶ TypeScript check..."
  if cd frontend && npx tsc --noEmit 2>&1 | grep -c "error TS" | grep -q "^0$"; then
    echo "  ✅ TypeScript passed"
    cd ..
  else
    echo "  ❌ TypeScript errors found"
    cd ..
    FAILURES=$((FAILURES + 1))
  fi
fi

# Secret scan on all staged files
echo "▶ Secret scan..."
STAGED_ALL=$(git diff --cached --name-only --diff-filter=ACM || true)
FOUND_SECRET=false
PATTERNS=("sk-ant-" "AKIA[A-Z0-9]{16}" "dg_" "postgres://.*:.*@.*@")
for file in $STAGED_ALL; do
  if [ -f "$file" ]; then
    for pat in "${PATTERNS[@]}"; do
      if git diff --cached "$file" | grep -qE "$pat"; then
        echo "  ❌ Possible secret in $file — pattern: $pat"
        FOUND_SECRET=true
        FAILURES=$((FAILURES + 1))
      fi
    done
  fi
done
if [ "$FOUND_SECRET" = false ]; then
  echo "  ✅ No secrets detected"
fi

# Block .env commit
if git diff --cached --name-only | grep -qE "^\.env$"; then
  echo "  ❌ BLOCKED: .env file staged for commit — add to .gitignore"
  FAILURES=$((FAILURES + 1))
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILURES -gt 0 ]; then
  echo ""
  echo "  🚫 $FAILURES check(s) failed — commit blocked."
  echo "  Bypass (emergency): git commit --no-verify"
  echo ""
  exit 1
else
  echo ""
  echo "  ✅ All checks passed."
  echo ""
  exit 0
fi
```

---

## PHASE 4 — GitHub Actions Workflows

### `.github/workflows/ci.yml`

This runs on every push and PR. It validates the code without deploying.

```yaml
name: CI — Test & Lint

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  backend:
    name: Backend (Python)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: integrate_health_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/integrate_health_test
      APP_ENV: test
      APP_SECRET_KEY: test-secret-key-not-real-32-chars-min
      JWT_SECRET_KEY: test-jwt-secret-key-not-real-32-chars
      JWT_ALGORITHM: HS256
      JWT_EXPIRATION_HOURS: 24
      DEEPGRAM_API_KEY: test-key
      ANTHROPIC_API_KEY: test-key
      UPLOAD_DIR: /tmp/test-uploads
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        working-directory: backend
        run: pip install -r requirements.txt
      - name: Run migrations
        working-directory: backend
        run: alembic upgrade head
      - name: Lint (ruff)
        working-directory: backend
        run: |
          pip install ruff
          ruff check app/ --output-format=github
      - name: Tests
        working-directory: backend
        run: |
          if [ -d "tests" ] && [ "$(find tests -name 'test_*.py' | wc -l)" -gt 0 ]; then
            pip install pytest pytest-cov
            pytest tests/ -v --tb=short --cov=app --cov-report=xml --cov-fail-under=50
          else
            echo "No test suite found — skipping. Add tests to backend/tests/ to enable coverage gating."
          fi
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: backend-coverage
          path: backend/coverage.xml
          retention-days: 7

  frontend:
    name: Frontend (TypeScript + Build)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      - name: TypeScript check
        working-directory: frontend
        run: npx tsc --noEmit
      - name: Build verification
        working-directory: frontend
        env:
          VITE_API_URL: https://app.integratehealth.ai/api/v1
        run: npm run build
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: frontend-build
          path: frontend/dist/
          retention-days: 3

  secret-scan:
    name: Secret Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

### `.github/workflows/cd.yml`

This workflow deploys to production by calling the existing `deploy.sh`. It requires:
- AWS credentials with permissions to call SSM, S3, and CloudFront (already working locally)
- GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

The workflow does NOT replace `deploy.sh` — it calls it exactly as you would locally.

```yaml
name: CD — Deploy to Production

on:
  workflow_dispatch:
    inputs:
      deploy_target:
        description: "What to deploy"
        required: true
        default: "both"
        type: choice
        options:
          - both
          - backend-only
          - frontend-only

# Prevent concurrent deploys
concurrency:
  group: production-deploy
  cancel-in-progress: false

jobs:
  ci-gate:
    name: CI Must Pass First
    uses: ./.github/workflows/ci.yml

  deploy:
    name: Deploy via deploy.sh
    runs-on: ubuntu-latest
    needs: ci-gate
    environment: production
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Make deploy.sh executable
        run: chmod +x deploy.sh

      - name: Deploy — both
        if: ${{ github.event.inputs.deploy_target == 'both' }}
        run: ./deploy.sh

      - name: Deploy — backend only
        if: ${{ github.event.inputs.deploy_target == 'backend-only' }}
        run: ./deploy.sh --backend-only

      - name: Deploy — frontend only
        if: ${{ github.event.inputs.deploy_target == 'frontend-only' }}
        run: ./deploy.sh --frontend-only

      - name: Deploy success notice
        if: success()
        run: echo "::notice title=Deploy Successful::Integrate Health deployed. Commit ${{ github.sha }}"

      - name: Deploy failure notice
        if: failure()
        run: echo "::error title=Deploy Failed::Deploy failed for commit ${{ github.sha }}. Check logs."

  smoke-test:
    name: Post-Deploy Smoke Test
    runs-on: ubuntu-latest
    needs: deploy
    steps:
      - name: Backend health check
        run: |
          RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" \
            https://app.integratehealth.ai/health || echo "000")
          if [ "$RESPONSE" = "200" ]; then
            echo "✅ Backend health check passed"
          else
            echo "❌ Backend returned HTTP $RESPONSE"
            exit 1
          fi

      - name: Frontend check
        run: |
          RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" \
            https://app.integratehealth.ai || echo "000")
          if [ "$RESPONSE" = "200" ]; then
            echo "✅ Frontend check passed"
          else
            echo "❌ Frontend returned HTTP $RESPONSE"
            exit 1
          fi

      - name: Auth endpoint sanity check
        run: |
          RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" \
            -X POST https://app.integratehealth.ai/api/v1/auth/login \
            -H "Content-Type: application/json" \
            -d '{"email":"smoke@test.invalid","password":"invalid"}' \
            || echo "000")
          # Expect 401 (wrong creds) or 422 (validation error) — NOT 500 or 000
          if [ "$RESPONSE" = "401" ] || [ "$RESPONSE" = "422" ]; then
            echo "✅ Auth endpoint responding correctly (HTTP $RESPONSE)"
          else
            echo "❌ Auth endpoint returned unexpected HTTP $RESPONSE"
            exit 1
          fi
```

**Important note about the CD workflow:** It is set to `workflow_dispatch` only (manual trigger from the GitHub Actions UI). This means it will never deploy automatically — you choose when to trigger it and what to deploy. This is intentional for a HIPAA app at the pilot stage. You can change it to trigger automatically on push to `main` later if desired by replacing `workflow_dispatch` with `push: branches: [main]`.

---

### `.github/workflows/scheduled-audits.yml`

```yaml
name: Scheduled Audits

on:
  schedule:
    - cron: "0 14 * * 1"  # Every Monday 9am CST (14:00 UTC)
  workflow_dispatch:
    inputs:
      audit_type:
        description: "Which audit to run"
        required: false
        default: "all"
        type: choice
        options: [all, dependencies, security, hipaa]

jobs:
  dependency-audit:
    name: Dependency Vulnerability Scan
    runs-on: ubuntu-latest
    if: ${{ github.event.inputs.audit_type == 'all' || github.event.inputs.audit_type == 'dependencies' || github.event_name == 'schedule' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Python dependency scan
        working-directory: backend
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt --format=markdown \
            --output=../python-vulnerabilities.md || true
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: npm audit
        working-directory: frontend
        run: |
          npm ci --prefer-offline
          npm audit > ../npm-audit.txt || true
      - uses: actions/upload-artifact@v4
        with:
          name: dependency-audit-${{ github.run_id }}
          path: |
            python-vulnerabilities.md
            npm-audit.txt
          retention-days: 30

  security-scan:
    name: Static Security Analysis
    runs-on: ubuntu-latest
    if: ${{ github.event.inputs.audit_type == 'all' || github.event.inputs.audit_type == 'security' || github.event_name == 'schedule' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Bandit scan
        working-directory: backend
        run: |
          pip install bandit
          bandit -r app/ -f markdown -o ../bandit-report.md \
            --severity-level medium || true
      - name: Semgrep scan
        uses: semgrep/semgrep-action@v1
        with:
          config: "p/python p/jwt p/secrets p/owasp-top-ten"
        continue-on-error: true
      - uses: actions/upload-artifact@v4
        with:
          name: security-scan-${{ github.run_id }}
          path: bandit-report.md
          retention-days: 30
      - name: Write summary
        run: |
          echo "## Security Scan — $(date +%Y-%m-%d)" >> $GITHUB_STEP_SUMMARY
          [ -f bandit-report.md ] && cat bandit-report.md >> $GITHUB_STEP_SUMMARY || true

  hipaa-snapshot:
    name: HIPAA Compliance Snapshot
    runs-on: ubuntu-latest
    if: ${{ github.event.inputs.audit_type == 'all' || github.event.inputs.audit_type == 'hipaa' || github.event_name == 'schedule' }}
    steps:
      - uses: actions/checkout@v4
      - name: Run automated HIPAA checks
        run: |
          PASS=0; FAIL=0; WARN=0
          OUT="hipaa-snapshot.md"
          echo "# HIPAA Snapshot — $(date +%Y-%m-%d)" > $OUT
          echo "**Commit:** ${{ github.sha }}" >> $OUT

          echo "" >> $OUT; echo "## Transmission Security" >> $OUT
          if grep -r "http://" backend/app/ --include="*.py" | \
             grep -v "localhost\|127.0.0.1\|test\|#" | \
             grep -q "deepgram\|anthropic\|bedrock"; then
            echo "- ❌ FAIL: Non-HTTPS external API call" >> $OUT; FAIL=$((FAIL+1))
          else
            echo "- ✅ PASS: No non-HTTPS external calls" >> $OUT; PASS=$((PASS+1))
          fi

          echo "" >> $OUT; echo "## PHI Protection" >> $OUT
          if grep -rn "logger\.\(info\|debug\)\|print(" backend/app/ --include="*.py" | \
             grep -iE "transcript|patient|diagnosis" | grep -v "#\|test" | grep -q .; then
            echo "- ⚠️  WARN: Possible PHI in log statements — review manually" >> $OUT; WARN=$((WARN+1))
          else
            echo "- ✅ PASS: No obvious PHI in logs" >> $OUT; PASS=$((PASS+1))
          fi

          echo "" >> $OUT; echo "## Secrets" >> $OUT
          if git log --all --name-only --format="" | grep -q "^\.env$"; then
            echo "- ❌ FAIL: .env in git history" >> $OUT; FAIL=$((FAIL+1))
          else
            echo "- ✅ PASS: .env not in history" >> $OUT; PASS=$((PASS+1))
          fi

          echo "" >> $OUT; echo "## Authentication" >> $OUT
          if grep -r "bcrypt\|passlib" backend/app/ --include="*.py" | grep -q "bcrypt"; then
            echo "- ✅ PASS: bcrypt detected" >> $OUT; PASS=$((PASS+1))
          else
            echo "- ❌ FAIL: bcrypt not detected" >> $OUT; FAIL=$((FAIL+1))
          fi

          if grep -r "expires_delta\|JWT_EXPIRATION\|exp" backend/app/ --include="*.py" | grep -q "expires"; then
            echo "- ✅ PASS: JWT expiration detected" >> $OUT; PASS=$((PASS+1))
          else
            echo "- ⚠️  WARN: JWT expiration unclear" >> $OUT; WARN=$((WARN+1))
          fi

          echo "" >> $OUT; echo "## Access Controls" >> $OUT
          if grep -r "user_id\|current_user" backend/app/api/ --include="*.py" | grep -q "user_id"; then
            echo "- ✅ PASS: Ownership checks detected" >> $OUT; PASS=$((PASS+1))
          else
            echo "- ❌ FAIL: Ownership checks not detected" >> $OUT; FAIL=$((FAIL+1))
          fi

          echo "" >> $OUT; echo "---" >> $OUT
          echo "## Summary: ✅ $PASS passing | ❌ $FAIL failing | ⚠️ $WARN warnings" >> $OUT
          echo "> Run \`/hipaa_audit\` in Claude Code for full manual review." >> $OUT

          cat $OUT >> $GITHUB_STEP_SUMMARY

          if [ $FAIL -gt 0 ]; then
            echo "❌ $FAIL HIPAA check(s) failed"
            exit 1
          fi
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: hipaa-snapshot-${{ github.run_id }}
          path: hipaa-snapshot.md
          retention-days: 90
```

---

## PHASE 5 — GitHub Supporting Files

### `.github/pull_request_template.md`

```markdown
## Summary
<!-- One or two sentences: what does this change do? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Refactor / code cleanup
- [ ] Infrastructure / config
- [ ] Dependency update

## Spec or Bug File
<!-- Link the BUGFIX_CLAUDE.md or SPEC file this implements, if applicable -->

---

## What Could This Break?
<!-- Most important section — think carefully before checking boxes -->

Existing flows this change touches:
- [ ] Authentication / login / forgot password
- [ ] Visit creation and management
- [ ] Audio recording and upload
- [ ] Deepgram transcription pipeline
- [ ] SOAP note generation (Claude / Bedrock)
- [ ] Blue dot sync state tracking
- [ ] Session isolation between visits
- [ ] Patient summary email (SES)
- [ ] Sidebar patient list
- [ ] Database schema (Alembic migration included?)
- [ ] None of the above

**Specific regression risk:**
<!-- e.g., "Changes note generation service — verify sync state still updates correctly" -->

---

## Testing Done
- [ ] TypeScript check passes (`npx tsc --noEmit`)
- [ ] Python lint passes (`ruff check app/`)
- [ ] Manually tested the complete affected user flow end-to-end
- [ ] Ran `/regression_test` in Claude Code and reviewed output
- [ ] If schema changed: ran `/db_migration_check` and confirmed safe

**What you manually tested:**

---

## HIPAA / Security Checklist
*(Complete if this touches auth, data storage, API endpoints, or external services)*
- [ ] No PHI added to logs
- [ ] No new endpoints missing auth dependency
- [ ] No secrets committed
- [ ] User ownership validation on any new data access

---

## Deploy Notes
- [ ] New environment variables required (list below)
- [ ] Manual step required before/after deploy (describe below)
- [ ] Database migration included (runs automatically via deploy.sh)

Notes:
```

---

### `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /backend
    schedule:
      interval: weekly
      day: monday
      time: "09:00"
      timezone: America/Chicago
    open-pull-requests-limit: 5
    labels: [dependencies, python]
    commit-message:
      prefix: "chore(deps)"
    groups:
      python-minor-patch:
        update-types: [minor, patch]

  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: weekly
      day: monday
      time: "09:00"
      timezone: America/Chicago
    open-pull-requests-limit: 5
    labels: [dependencies, javascript]
    commit-message:
      prefix: "chore(deps)"
    groups:
      npm-minor-patch:
        update-types: [minor, patch]

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    labels: [dependencies, github-actions]
    commit-message:
      prefix: "chore(actions)"
```

---

### `.github/GITHUB_SETTINGS.md`

```markdown
# GitHub Repository Settings — Integrate Health

Manual settings to configure in GitHub UI (Settings tab on the repo).
These cannot be set via files.

---

## Branch Protection — `main`
Settings → Branches → Add rule → Branch name pattern: `main`

- [x] Require status checks to pass before merging
- [x] Require branches to be up to date before merging
- Status checks to require (appear after first CI run):
  - `Backend (Python)`
  - `Frontend (TypeScript + Build)`
  - `Secret Scan`
- [x] Do not allow force pushes
- [x] Do not allow deletions
- [x] Require conversation resolution before merging

---

## Secrets — for CD Workflow
Settings → Secrets and variables → Actions → New repository secret

| Secret Name           | Value |
|-----------------------|-------|
| AWS_ACCESS_KEY_ID     | AWS access key that has SSM, S3, and CloudFront permissions |
| AWS_SECRET_ACCESS_KEY | Corresponding secret key |
| AWS_REGION            | e.g., us-east-1 |

These are the same AWS credentials you use locally for deploy.sh.
Consider creating a dedicated IAM user for GitHub Actions with only the
permissions deploy.sh needs: SSM SendCommand, S3 PutObject/GetObject,
CloudFront CreateInvalidation.

---

## Environments — Production Gate
Settings → Environments → New environment: `production`

- [x] Required reviewers: add yourself (Burhan)
  This pauses the CD workflow for manual approval before deploying.
  You get an email — click Approve in GitHub to proceed.
- [x] Deployment branches: Selected branches → `main` only

---

## General Settings
Settings → General → Pull Requests:
- [x] Allow squash merging
- [ ] Allow merge commits (disable)
- [x] Allow rebase merging
- [x] Automatically delete head branches

---

## Dependabot Alerts
Settings → Security → Enable:
- [x] Dependency graph
- [x] Dependabot alerts
- [x] Dependabot security updates
```

---

## PHASE 6 — Version Infrastructure

**[CONFIRM BEFORE CONTINUING]** — At this point you should have the answers from Phase 0 about where the version string lives. Based on those answers:

**If version is a hardcoded string in a component:**
1. Create `frontend/public/version.json` using the template from Phase 2
2. In the component where the version string is hardcoded, replace it with a `fetch('/version.json')` call. Use a `useEffect` + `useState` pattern:

```typescript
const [version, setVersion] = useState<string>('');

useEffect(() => {
  fetch('/version.json')
    .then(r => r.json())
    .then(v => setVersion(v.version))
    .catch(() => setVersion(''));
}, []);
```

3. Replace the hardcoded version display with `{version}`.

**If version.json already exists:** confirm the structure matches the shape the version_bump hook writes and adjust if needed.

---

## PHASE 7 — Final Wiring and Verification

After all files are created, run:

```bash
# 1. Run the install script
bash scripts/install_hooks.sh

# 2. Verify directory structure
find .claude/ -type f | sort
find .github/ -type f | sort
find scripts/ -name "*.sh" | sort

# 3. Confirm hook scripts are executable
ls -la .claude/hooks/
ls -la .git/hooks/pre-commit

# 4. Verify settings.json is valid JSON (does not touch settings.local.json)
python3 -c "import json; json.load(open('.claude/settings.json')); print('settings.json valid')"
python3 -c "import json; json.load(open('.claude/settings.local.json')); print('settings.local.json still intact')"

# 5. Verify version.json exists and is valid
python3 -c "import json; d=json.load(open('frontend/public/version.json')); print(f'Version: {d[\"version\"]}')"

# 6. Dry-run the pre-deploy guard (should exit 0 for non-deploy commands)
CLAUDE_TOOL_INPUT_COMMAND="git status" bash .claude/hooks/pre_deploy_guard.sh
echo "Exit code: $?"
```

Report results of all verification steps. Flag anything that did not pass.

---

## Final Deliverable Summary

When complete, confirm the following files exist:

**Claude Code commands (7 files):**
- `.claude/commands/regression_test.md`
- `.claude/commands/security_audit.md`
- `.claude/commands/financial_audit.md`
- `.claude/commands/hipaa_audit.md`
- `.claude/commands/onboard_patient_flow.md`
- `.claude/commands/db_migration_check.md`
- `.claude/commands/context_refresh.md`

**Claude Code hooks (3 files):**
- `.claude/settings.json` ← new file, does NOT replace settings.local.json
- `.claude/hooks/pre_deploy_guard.sh` ← executable
- `.claude/hooks/version_bump.sh` ← executable

**Git hooks (2 files):**
- `scripts/pre-commit.sh`
- `scripts/install_hooks.sh`
- `.git/hooks/pre-commit` ← installed by install_hooks.sh, not committed

**GitHub Actions (3 workflows):**
- `.github/workflows/ci.yml`
- `.github/workflows/cd.yml`
- `.github/workflows/scheduled-audits.yml`

**GitHub supporting files (3 files):**
- `.github/pull_request_template.md`
- `.github/dependabot.yml`
- `.github/GITHUB_SETTINGS.md`

**Version infrastructure (2 files):**
- `frontend/public/version.json`
- `CHANGELOG.md`
