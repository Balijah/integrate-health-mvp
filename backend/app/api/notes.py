"""
Note API endpoints.

Handles SOAP note generation, retrieval, and export.
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.note import Note
from app.models.visit import Visit
from app.schemas.note import (
    GenerateNoteRequest,
    GenerateNoteResponse,
    NoteExportRequest,
    NoteExportResponse,
    NoteResponse,
    NoteUpdateRequest,
    SyncSectionRequest,
    SyncSectionResponse,
)
from app.services.note_generation import (
    NoteGenerationError,
    generate_soap_note,
    format_note_as_markdown,
    format_note_as_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{visit_id}/notes/generate",
    response_model=GenerateNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate SOAP note",
    description="Generate a SOAP note from the visit transcript using AI.",
)
async def generate_note(
    visit_id: uuid.UUID,
    request: GenerateNoteRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> GenerateNoteResponse:
    """
    Generate a SOAP note for a visit.

    Args:
        visit_id: Visit UUID
        request: Generation request with optional context
        current_user: Authenticated user
        db: Database session

    Returns:
        GenerateNoteResponse: Confirmation with note ID

    Raises:
        HTTPException: 404 if visit not found
        HTTPException: 400 if transcript not available or note exists
    """
    # Verify visit exists and belongs to user
    result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Check if transcript exists
    if not visit.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript not available. Complete transcription first.",
        )

    # Check if note already exists
    existing_note = await db.execute(
        select(Note).where(Note.visit_id == visit_id)
    )
    if existing_note.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note already exists for this visit. Delete it first to regenerate.",
        )

    try:
        # Generate SOAP note
        logger.info(f"Generating SOAP note for visit {visit_id}")
        content = generate_soap_note(
            transcript=visit.transcript,
            additional_context=request.additional_context,
        )

        # Create note record
        note = Note(
            visit_id=visit_id,
            content=content,
            note_type="soap",
            status="draft",
        )

        db.add(note)
        await db.flush()
        await db.refresh(note)

        logger.info(f"SOAP note created: {note.id}")

        return GenerateNoteResponse(
            note_id=note.id,
            visit_id=visit_id,
            status="draft",
            message="SOAP note generated successfully",
        )

    except NoteGenerationError as e:
        logger.error(f"Note generation failed for visit {visit_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{visit_id}/notes",
    response_model=NoteResponse | None,
    summary="Get note for visit",
    description="Get the SOAP note for a visit.",
)
async def get_note(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> NoteResponse | None:
    """
    Get the note for a visit.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        NoteResponse: Note data or None if not exists

    Raises:
        HTTPException: 404 if visit not found
    """
    # Verify visit exists and belongs to user
    visit_result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    if visit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Get note
    result = await db.execute(
        select(Note).where(Note.visit_id == visit_id)
    )
    note = result.scalar_one_or_none()

    if note is None:
        return None

    return NoteResponse.model_validate(note)


@router.put(
    "/{visit_id}/notes/{note_id}",
    response_model=NoteResponse,
    summary="Update note",
    description="Update a SOAP note's content or status.",
)
async def update_note(
    visit_id: uuid.UUID,
    note_id: uuid.UUID,
    request: NoteUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> NoteResponse:
    """
    Update a note.

    Args:
        visit_id: Visit UUID
        note_id: Note UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        NoteResponse: Updated note data

    Raises:
        HTTPException: 404 if note not found
    """
    # Verify visit exists and belongs to user
    visit_result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    if visit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Get note
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.visit_id == visit_id,
        )
    )
    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    # Update fields
    if request.content is not None:
        note.content = request.content

    if request.status is not None:
        note.status = request.status

    await db.flush()
    await db.refresh(note)

    return NoteResponse.model_validate(note)


@router.delete(
    "/{visit_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Delete a SOAP note.",
)
async def delete_note(
    visit_id: uuid.UUID,
    note_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a note.

    Args:
        visit_id: Visit UUID
        note_id: Note UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if note not found
    """
    # Verify visit exists and belongs to user
    visit_result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    if visit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Get note
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.visit_id == visit_id,
        )
    )
    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    await db.delete(note)


@router.post(
    "/{visit_id}/notes/{note_id}/export",
    response_model=NoteExportResponse,
    summary="Export note",
    description="Export a SOAP note in the specified format.",
)
async def export_note(
    visit_id: uuid.UUID,
    note_id: uuid.UUID,
    request: NoteExportRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> NoteExportResponse:
    """
    Export a note in the specified format.

    Args:
        visit_id: Visit UUID
        note_id: Note UUID
        request: Export request with format
        current_user: Authenticated user
        db: Database session

    Returns:
        NoteExportResponse: Exported note content

    Raises:
        HTTPException: 404 if note not found
    """
    # Verify visit exists and belongs to user
    visit_result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    if visit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Get note
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.visit_id == visit_id,
        )
    )
    note = result.scalar_one_or_none()

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    # Format based on requested format
    if request.format == "markdown":
        content = format_note_as_markdown(note.content)
    elif request.format == "text":
        content = format_note_as_text(note.content)
    elif request.format == "json":
        content = json.dumps(note.content, indent=2)
    else:
        content = format_note_as_markdown(note.content)

    return NoteExportResponse(
        visit_id=visit_id,
        note_id=note_id,
        format=request.format,
        content=content,
    )


_SOAP_SECTIONS = {"subjective", "objective", "assessment", "plan"}


@router.post(
    "/{visit_id}/notes/{note_id}/sync-section",
    response_model=SyncSectionResponse,
    summary="Mark a SOAP section as synced",
    description="Persist that a provider has copied a SOAP section to their EHR.",
)
async def sync_section(
    visit_id: uuid.UUID,
    note_id: uuid.UUID,
    request: SyncSectionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SyncSectionResponse:
    """Mark a SOAP section as synced and return overall sync status."""
    # Verify visit ownership
    visit_result = await db.execute(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.user_id == current_user.id,
        )
    )
    if visit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    # Get note
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.visit_id == visit_id,
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    updated = dict(note.synced_sections or {})
    updated[request.section] = True
    note.synced_sections = updated

    await db.flush()
    await db.refresh(note)

    all_synced = all(note.synced_sections.get(s) for s in _SOAP_SECTIONS)
    return SyncSectionResponse(synced_sections=note.synced_sections, all_synced=all_synced)
