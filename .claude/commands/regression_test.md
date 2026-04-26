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
