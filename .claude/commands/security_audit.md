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
