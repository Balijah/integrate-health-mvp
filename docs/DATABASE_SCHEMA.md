# Database Schema - Integrate Health MVP

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │     visits      │       │     notes       │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │──┐    │ id (PK)         │──┐    │ id (PK)         │
│ email           │  │    │ user_id (FK)    │  │    │ visit_id (FK)   │
│ hashed_password │  └───▶│ patient_ref     │  └───▶│ content         │
│ full_name       │       │ visit_date      │       │ note_type       │
│ is_active       │       │ chief_complaint │       │ status          │
│ created_at      │       │ audio_file_path │       │ created_at      │
│ updated_at      │       │ audio_duration  │       │ updated_at      │
└─────────────────┘       │ transcript      │       └─────────────────┘
                          │ trans_status    │
                          │ created_at      │
                          │ updated_at      │
                          └─────────────────┘
```

---

## Table Definitions

### users

**Purpose:** Store provider accounts (functional medicine practitioners)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;
```

**Columns:**
- `id`: Unique identifier (UUID v4)
- `email`: Login email, must be unique
- `hashed_password`: Bcrypt hash (12 rounds), never store plain text
- `full_name`: Provider's full name (e.g., "Dr. Jane Smith")
- `is_active`: Soft delete flag, disabled users can't log in
- `created_at`: Account creation timestamp
- `updated_at`: Last modification timestamp

**Constraints:**
- Email must be unique and valid format
- Password hash must be bcrypt format
- is_active defaults to TRUE

**Sample Data:**
```sql
INSERT INTO users (email, hashed_password, full_name)
VALUES (
    'provider@karehealth.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lZJpVV1HbXCm',
    'Dr. Jane Smith'
);
```

---

### visits

**Purpose:** Store patient visit records with audio and transcripts

```sql
CREATE TABLE visits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    patient_ref VARCHAR(255) NOT NULL,
    visit_date TIMESTAMP WITH TIME ZONE NOT NULL,
    chief_complaint TEXT,
    audio_file_path VARCHAR(500),
    audio_duration_seconds INTEGER,
    transcript TEXT,
    transcription_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_visits_user_id ON visits(user_id);
CREATE INDEX idx_visits_status ON visits(transcription_status);
CREATE INDEX idx_visits_date ON visits(visit_date DESC);
CREATE INDEX idx_visits_patient_ref ON visits(patient_ref);
```

**Columns:**
- `id`: Unique identifier
- `user_id`: Foreign key to users (provider who created visit)
- `patient_ref`: Non-PHI patient identifier (e.g., "PT-001", "PATIENT-ABC")
- `visit_date`: Date and time of visit
- `chief_complaint`: Main reason for visit (optional)
- `audio_file_path`: Relative path to stored audio file
- `audio_duration_seconds`: Length of audio recording
- `transcript`: Full text transcript from Deepgram
- `transcription_status`: Current status of transcription
- `created_at`: Record creation timestamp
- `updated_at`: Last modification timestamp

**Transcription Status Values:**
- `pending`: Visit created, no audio uploaded yet
- `recording`: Audio is being recorded (optional state)
- `transcribing`: Audio uploaded, transcription in progress
- `completed`: Transcription successful
- `failed`: Transcription failed, check logs

**Constraints:**
- user_id must reference valid user
- patient_ref is required (non-empty string)
- visit_date is required
- ON DELETE CASCADE: Deleting user deletes all their visits

**Sample Data:**
```sql
INSERT INTO visits (user_id, patient_ref, visit_date, chief_complaint, transcription_status)
VALUES (
    'user-uuid-here',
    'PT-001',
    '2024-01-15 14:00:00+00',
    'Fatigue and brain fog for 3 months',
    'pending'
);
```

---

### notes

**Purpose:** Store generated SOAP notes in structured format

```sql
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id UUID NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    content JSONB NOT NULL,
    note_type VARCHAR(50) DEFAULT 'soap',
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_notes_visit_id ON notes(visit_id);
CREATE INDEX idx_notes_status ON notes(status);

-- JSONB indexes for querying note content
CREATE INDEX idx_notes_content_gin ON notes USING GIN (content);
```

**Columns:**
- `id`: Unique identifier
- `visit_id`: Foreign key to visits (one-to-one relationship)
- `content`: JSONB structured SOAP note (see structure below)
- `note_type`: Type of note (default 'soap', future: 'progress', 'discharge')
- `status`: Current status of note
- `created_at`: Note creation timestamp
- `updated_at`: Last modification timestamp

**Note Status Values:**
- `draft`: AI-generated, not yet reviewed
- `reviewed`: Provider has reviewed and may have edited
- `finalized`: Provider has approved and finalized

**Constraints:**
- visit_id must reference valid visit
- content must be valid JSONB
- ON DELETE CASCADE: Deleting visit deletes associated notes

**Content Structure (JSONB):**
See "SOAP Note Structure" section below.

---

## SOAP Note Structure

### Full JSONB Schema

```json
{
  "subjective": {
    "chief_complaint": "string",
    "history_of_present_illness": "string",
    "review_of_systems": "string",
    "past_medical_history": "string",
    "medications": ["string"],
    "supplements": ["string"],
    "allergies": ["string"],
    "social_history": "string",
    "family_history": "string"
  },
  "objective": {
    "vitals": {
      "blood_pressure": "string",
      "heart_rate": "string",
      "temperature": "string",
      "weight": "string"
    },
    "physical_exam": "string",
    "lab_results": "string"
  },
  "assessment": {
    "diagnoses": ["string"],
    "clinical_reasoning": "string"
  },
  "plan": {
    "treatment_plan": "string",
    "medications_prescribed": ["string"],
    "supplements_recommended": ["string"],
    "lifestyle_recommendations": "string",
    "lab_orders": ["string"],
    "follow_up": "string",
    "patient_education": "string"
  },
  "metadata": {
    "generated_at": "ISO timestamp",
    "model_version": "string",
    "confidence_score": 0.95
  }
}
```

### Example Note

```json
{
  "subjective": {
    "chief_complaint": "Persistent fatigue and difficulty concentrating for 3 months",
    "history_of_present_illness": "Patient reports gradual onset of fatigue starting approximately 3 months ago. Describes feeling exhausted by mid-afternoon despite adequate sleep (7-8 hours nightly). Also notes brain fog and difficulty focusing on tasks at work.",
    "review_of_systems": "Denies fever, weight changes, night sweats. Reports occasional headaches.",
    "past_medical_history": "Hypothyroidism diagnosed 2015, managed with levothyroxine",
    "medications": ["Levothyroxine 100mcg daily"],
    "supplements": ["Vitamin D 2000 IU daily"],
    "allergies": ["Penicillin - rash"],
    "social_history": "Non-smoker, occasional alcohol use (1-2 drinks/week), sedentary lifestyle",
    "family_history": "Mother has Hashimoto's thyroiditis, father has type 2 diabetes"
  },
  "objective": {
    "vitals": {
      "blood_pressure": "118/76",
      "heart_rate": "72",
      "temperature": "98.4°F",
      "weight": "165 lbs"
    },
    "physical_exam": "Alert and oriented. Thyroid: no nodules palpated, mildly enlarged. Cardiovascular: regular rate and rhythm. Respiratory: clear to auscultation bilaterally.",
    "lab_results": "Pending - ordered comprehensive thyroid panel and ferritin"
  },
  "assessment": {
    "diagnoses": [
      "Chronic fatigue, likely multifactorial",
      "Rule out suboptimal thyroid function",
      "Rule out iron deficiency"
    ],
    "clinical_reasoning": "Given patient's history of hypothyroidism and family history of autoimmune thyroid disease, suboptimal thyroid function is a strong consideration. Iron deficiency is also common cause of fatigue in this demographic. Brain fog may be related to either condition."
  },
  "plan": {
    "treatment_plan": "Comprehensive lab work to assess thyroid function and iron status. Will review results and adjust treatment accordingly.",
    "medications_prescribed": [],
    "supplements_recommended": [
      "Methylated B-complex (B-Right) - 1 capsule daily with food",
      "Continue Vitamin D 2000 IU"
    ],
    "lifestyle_recommendations": "Begin gentle exercise program (walking 20 minutes daily). Focus on sleep hygiene - maintain consistent sleep/wake schedule. Consider stress management techniques (meditation, yoga).",
    "lab_orders": [
      "TSH, Free T3, Free T4, Reverse T3",
      "TPO antibodies, Thyroglobulin antibodies",
      "Ferritin",
      "Complete metabolic panel",
      "Vitamin B12, Folate"
    ],
    "follow_up": "Return visit in 2 weeks to review lab results and adjust treatment plan",
    "patient_education": "Discussed thyroid function and its role in energy metabolism. Explained importance of comprehensive thyroid testing beyond TSH. Reviewed symptoms to monitor."
  },
  "metadata": {
    "generated_at": "2024-01-15T15:30:00Z",
    "model_version": "claude-sonnet-4-20250514",
    "confidence_score": 0.92
  }
}
```

---

## Database Migrations

### Initial Migration (001_initial_schema)

```python
# alembic/versions/001_initial_schema.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for users
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_active', 'users', ['is_active'], postgresql_where=sa.text('is_active = true'))
    
    # Create visits table
    op.create_table(
        'visits',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_ref', sa.String(255), nullable=False),
        sa.Column('visit_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('chief_complaint', sa.Text()),
        sa.Column('audio_file_path', sa.String(500)),
        sa.Column('audio_duration_seconds', sa.Integer()),
        sa.Column('transcript', sa.Text()),
        sa.Column('transcription_status', sa.String(50), server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for visits
    op.create_index('idx_visits_user_id', 'visits', ['user_id'])
    op.create_index('idx_visits_status', 'visits', ['transcription_status'])
    op.create_index('idx_visits_date', 'visits', ['visit_date'], postgresql_ops={'visit_date': 'DESC'})
    op.create_index('idx_visits_patient_ref', 'visits', ['patient_ref'])
    
    # Create notes table
    op.create_table(
        'notes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('visit_id', UUID(as_uuid=True), sa.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', JSONB, nullable=False),
        sa.Column('note_type', sa.String(50), server_default='soap'),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for notes
    op.create_index('idx_notes_visit_id', 'notes', ['visit_id'])
    op.create_index('idx_notes_status', 'notes', ['status'])
    op.create_index('idx_notes_content_gin', 'notes', ['content'], postgresql_using='gin')

def downgrade():
    op.drop_table('notes')
    op.drop_table('visits')
    op.drop_table('users')
```

---

## Database Queries

### Common Queries

**Get user's recent visits:**
```sql
SELECT 
    v.id,
    v.patient_ref,
    v.visit_date,
    v.chief_complaint,
    v.transcription_status,
    EXISTS(SELECT 1 FROM notes n WHERE n.visit_id = v.id) as has_note
FROM visits v
WHERE v.user_id = :user_id
ORDER BY v.visit_date DESC
LIMIT 20 OFFSET :offset;
```

**Get visit with note:**
```sql
SELECT 
    v.*,
    n.content as note_content,
    n.status as note_status,
    n.id as note_id
FROM visits v
LEFT JOIN notes n ON n.visit_id = v.id
WHERE v.id = :visit_id AND v.user_id = :user_id;
```

**Search notes by content:**
```sql
SELECT 
    n.id,
    n.visit_id,
    v.patient_ref,
    v.visit_date,
    n.content->'subjective'->>'chief_complaint' as chief_complaint
FROM notes n
JOIN visits v ON v.id = n.visit_id
WHERE v.user_id = :user_id
    AND n.content @> '{"assessment": {"diagnoses": ["fatigue"]}}'::jsonb
ORDER BY v.visit_date DESC;
```

---

## Performance Considerations

### Index Strategy
- All foreign keys have indexes
- Common query patterns covered (user_id, status, date)
- JSONB GIN index for content searches
- Composite indexes if queries become complex

### Query Optimization
- Use EXPLAIN ANALYZE for slow queries
- Limit result sets with pagination
- Avoid SELECT * (specify needed columns)
- Use connection pooling

### Future Optimizations
- Partitioning visits table by date (when > 1M rows)
- Read replicas for reporting queries
- Materialized views for dashboards
- Archive old visits to cold storage

---

This schema supports the MVP requirements and provides a foundation for future enhancements.