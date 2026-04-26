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
