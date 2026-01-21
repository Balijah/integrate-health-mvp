"""
Visit management API endpoints.

Handles CRUD operations for patient visits and audio upload.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models.visit import Visit
from app.schemas.visit import (
    AudioUploadResponse,
    VisitCreate,
    VisitListResponse,
    VisitResponse,
    VisitUpdate,
)
from app.utils.audio import (
    generate_audio_filename,
    get_audio_duration_estimate,
    validate_audio_file,
)

router = APIRouter()


@router.post(
    "",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new visit",
    description="Create a new patient visit record.",
)
async def create_visit(
    visit_data: VisitCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> VisitResponse:
    """
    Create a new visit.

    Args:
        visit_data: Visit creation data
        current_user: Authenticated user
        db: Database session

    Returns:
        VisitResponse: Created visit data
    """
    visit = Visit(
        user_id=current_user.id,
        patient_ref=visit_data.patient_ref,
        visit_date=visit_data.visit_date,
        chief_complaint=visit_data.chief_complaint,
    )

    db.add(visit)
    await db.flush()
    await db.refresh(visit)

    return VisitResponse.model_validate(visit)


@router.get(
    "",
    response_model=VisitListResponse,
    summary="List visits",
    description="Get paginated list of visits for the current user.",
)
async def list_visits(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100, description="Number of visits to return"),
    offset: int = Query(0, ge=0, description="Number of visits to skip"),
) -> VisitListResponse:
    """
    List visits for the current user.

    Args:
        current_user: Authenticated user
        db: Database session
        limit: Maximum number of visits to return
        offset: Number of visits to skip

    Returns:
        VisitListResponse: Paginated list of visits
    """
    # Get total count
    count_query = select(func.count()).select_from(Visit).where(
        Visit.user_id == current_user.id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get visits ordered by visit_date DESC
    visits_query = (
        select(Visit)
        .where(Visit.user_id == current_user.id)
        .order_by(Visit.visit_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(visits_query)
    visits = result.scalars().all()

    return VisitListResponse(
        items=[VisitResponse.model_validate(v) for v in visits],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{visit_id}",
    response_model=VisitResponse,
    summary="Get a visit",
    description="Get a single visit by ID.",
)
async def get_visit(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> VisitResponse:
    """
    Get a single visit by ID.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        VisitResponse: Visit data

    Raises:
        HTTPException: 404 if visit not found
    """
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

    return VisitResponse.model_validate(visit)


@router.patch(
    "/{visit_id}",
    response_model=VisitResponse,
    summary="Update a visit",
    description="Update a visit's details.",
)
async def update_visit(
    visit_id: uuid.UUID,
    visit_data: VisitUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> VisitResponse:
    """
    Update a visit.

    Args:
        visit_id: Visit UUID
        visit_data: Update data
        current_user: Authenticated user
        db: Database session

    Returns:
        VisitResponse: Updated visit data

    Raises:
        HTTPException: 404 if visit not found
    """
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

    # Update fields that are provided
    update_data = visit_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(visit, field, value)

    await db.flush()
    await db.refresh(visit)

    return VisitResponse.model_validate(visit)


@router.delete(
    "/{visit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a visit",
    description="Delete a visit and all associated data.",
)
async def delete_visit(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a visit.

    Args:
        visit_id: Visit UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if visit not found
    """
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

    await db.delete(visit)


@router.post(
    "/{visit_id}/audio",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio for a visit",
    description="Upload an audio recording for transcription.",
)
async def upload_audio(
    visit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="Audio file to upload"),
) -> AudioUploadResponse:
    """
    Upload audio file for a visit.

    Args:
        visit_id: Visit UUID
        file: Uploaded audio file
        current_user: Authenticated user
        db: Database session

    Returns:
        AudioUploadResponse: Upload confirmation with file details

    Raises:
        HTTPException: 404 if visit not found
        HTTPException: 400 if file validation fails
    """
    settings = get_settings()

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

    # Check if audio already uploaded
    if visit.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio already uploaded for this visit. Delete the visit to re-record.",
        )

    # Read file content
    content = await file.read()

    # Validate audio file
    mime_type = file.content_type or "audio/webm"
    is_valid, error_message = validate_audio_file(content, mime_type, file.filename)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Generate filename and save file
    filename = generate_audio_filename(str(visit_id), mime_type)
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    file_path = upload_path / filename
    file_path.write_bytes(content)

    # Estimate duration
    duration_estimate = get_audio_duration_estimate(content, mime_type)

    # Update visit record
    visit.audio_file_path = str(file_path)
    visit.audio_duration_seconds = duration_estimate
    visit.transcription_status = "pending"

    await db.flush()
    await db.refresh(visit)

    return AudioUploadResponse(
        visit_id=visit.id,
        audio_file_path=visit.audio_file_path,
        audio_duration_seconds=visit.audio_duration_seconds,
        file_size_bytes=len(content),
        mime_type=mime_type,
    )
