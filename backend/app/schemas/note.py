"""
Note Pydantic schemas for request/response validation.

Defines schemas for SOAP note content, creation, and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# SOAP Note Content Schemas

class VitalsSchema(BaseModel):
    """Vitals section of objective data."""

    blood_pressure: str | None = None
    heart_rate: str | None = None
    temperature: str | None = None
    weight: str | None = None


class SubjectiveSchema(BaseModel):
    """Subjective section of SOAP note."""

    chief_complaint: str = ""
    history_of_present_illness: str = ""
    review_of_systems: str = ""
    past_medical_history: str = ""
    medications: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    social_history: str = ""
    family_history: str = ""


class ObjectiveSchema(BaseModel):
    """Objective section of SOAP note."""

    vitals: VitalsSchema = Field(default_factory=VitalsSchema)
    physical_exam: str = ""
    lab_results: str = ""


class AssessmentSchema(BaseModel):
    """Assessment section of SOAP note."""

    diagnoses: list[str] = Field(default_factory=list)
    clinical_reasoning: str = ""


class PlanSchema(BaseModel):
    """Plan section of SOAP note."""

    treatment_plan: str = ""
    medications_prescribed: list[str] = Field(default_factory=list)
    supplements_recommended: list[str] = Field(default_factory=list)
    lifestyle_recommendations: str = ""
    lab_orders: list[str] = Field(default_factory=list)
    follow_up: str = ""
    patient_education: str = ""


class NoteMetadataSchema(BaseModel):
    """Metadata for generated note."""

    generated_at: str = ""
    model_version: str = ""
    confidence_score: float | None = None


class SOAPContentSchema(BaseModel):
    """Full SOAP note content structure."""

    subjective: SubjectiveSchema = Field(default_factory=SubjectiveSchema)
    objective: ObjectiveSchema = Field(default_factory=ObjectiveSchema)
    assessment: AssessmentSchema = Field(default_factory=AssessmentSchema)
    plan: PlanSchema = Field(default_factory=PlanSchema)
    metadata: NoteMetadataSchema = Field(default_factory=NoteMetadataSchema)


# Request/Response Schemas

class GenerateNoteRequest(BaseModel):
    """Request schema for generating a SOAP note."""

    additional_context: str | None = Field(
        None,
        max_length=2000,
        description="Additional context for note generation (e.g., patient history)",
    )


class NoteUpdateRequest(BaseModel):
    """Request schema for updating a note."""

    content: dict[str, Any] | None = Field(
        None,
        description="Updated SOAP note content",
    )
    status: str | None = Field(
        None,
        pattern="^(draft|reviewed|finalized)$",
        description="Note status",
    )


class NoteExportRequest(BaseModel):
    """Request schema for exporting a note."""

    format: str = Field(
        "markdown",
        pattern="^(markdown|text|json)$",
        description="Export format",
    )


class NoteResponse(BaseModel):
    """Response schema for note data."""

    id: uuid.UUID
    visit_id: uuid.UUID
    content: dict[str, Any]
    note_type: str
    status: str
    synced_sections: dict = Field(default_factory=dict)
    all_synced: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_all_synced(self) -> "NoteResponse":
        sections = {"subjective", "objective", "assessment", "plan"}
        self.all_synced = all(self.synced_sections.get(s) for s in sections)
        return self


class NoteExportResponse(BaseModel):
    """Response schema for exported note."""

    visit_id: uuid.UUID
    note_id: uuid.UUID
    format: str
    content: str


class GenerateNoteResponse(BaseModel):
    """Response schema for note generation."""

    note_id: uuid.UUID
    visit_id: uuid.UUID
    status: str
    message: str


class SyncSectionRequest(BaseModel):
    """Request schema for syncing a SOAP section."""

    section: str = Field(
        ...,
        pattern="^(subjective|objective|assessment|plan)$",
        description="SOAP section to mark as synced",
    )


class SyncSectionResponse(BaseModel):
    """Response schema for sync-section endpoint."""

    synced_sections: dict
    all_synced: bool
