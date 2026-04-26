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
