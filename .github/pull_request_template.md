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
