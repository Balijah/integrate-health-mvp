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
