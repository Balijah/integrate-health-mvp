"""
Visit management API endpoints.

Handles CRUD operations for patient visits and audio upload.
Supports both local storage and S3 storage modes.
"""

import logging
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models.note import Note
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

logger = logging.getLogger(__name__)

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

    # Bulk-fetch notes to compute all_synced per visit
    visit_ids = [v.id for v in visits]
    _SOAP_SECTIONS = {"subjective", "objective", "assessment", "plan"}
    synced_map: dict = {}
    if visit_ids:
        notes_result = await db.execute(
            select(Note.visit_id, Note.synced_sections).where(Note.visit_id.in_(visit_ids))
        )
        for row in notes_result:
            synced_map[row[0]] = row[1] or {}

    items = []
    for v in visits:
        vr = VisitResponse.model_validate(v)
        synced = synced_map.get(v.id, {})
        all_synced = all(synced.get(s) for s in _SOAP_SECTIONS)
        items.append(vr.model_copy(update={"all_synced": all_synced}))

    return VisitListResponse(
        items=items,
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

    _SOAP_SECTIONS = {"subjective", "objective", "assessment", "plan"}
    note_result = await db.execute(
        select(Note.synced_sections).where(Note.visit_id == visit_id)
    )
    synced = note_result.scalar_one_or_none() or {}
    all_synced = all(synced.get(s) for s in _SOAP_SECTIONS)

    return VisitResponse.model_validate(visit).model_copy(update={"all_synced": all_synced})


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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio file to upload"),
) -> AudioUploadResponse:
    """
    Upload audio file for a visit.

    Supports both local storage and S3 storage based on configuration.

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

    # Estimate duration
    duration_estimate = get_audio_duration_estimate(content, mime_type)

    # Store file based on storage mode
    if settings.storage_mode == "s3" and settings.s3_bucket_name:
        # S3 Storage mode
        try:
            from app.services.s3_storage import upload_audio as s3_upload

            s3_key = s3_upload(content, str(visit_id), mime_type)
            file_path = s3_key  # Store S3 key in database
            logger.info(f"Audio uploaded to S3: {s3_key}")

        except Exception as e:
            logger.error(f"S3 upload failed: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload audio file. Please try again.",
            )
    else:
        # Local storage mode (default)
        filename = generate_audio_filename(str(visit_id), mime_type)
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)

        local_file_path = upload_path / filename
        local_file_path.write_bytes(content)
        file_path = str(local_file_path)
        logger.info(f"Audio saved locally: {file_path}")

    # Update visit record
    visit.audio_file_path = file_path
    visit.audio_duration_seconds = duration_estimate
    visit.transcription_status = "pending"

    await db.flush()
    await db.refresh(visit)

    # Automatically trigger transcription in the background
    from app.api.transcription import process_transcription

    background_tasks.add_task(process_transcription, visit_id, settings.database_url)

    return AudioUploadResponse(
        visit_id=visit.id,
        audio_file_path=visit.audio_file_path,
        audio_duration_seconds=visit.audio_duration_seconds,
        file_size_bytes=len(content),
        mime_type=mime_type,
    )


class SendSummaryRequest(BaseModel):
    """Request schema for sending a patient summary email."""

    email: EmailStr
    summary: str


@router.post(
    "/{visit_id}/summary/send",
    summary="Send patient summary email",
    description="Send the patient-friendly summary to the provided email address via SES.",
)
async def send_summary(
    visit_id: uuid.UUID,
    request: SendSummaryRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Send a patient summary email.

    Args:
        visit_id: Visit UUID
        request: Email address and summary text
        current_user: Authenticated user
        db: Database session

    Returns:
        dict: Confirmation message
    """
    if not request.summary.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Summary cannot be empty.",
        )

    # Verify visit belongs to user
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

    try:
        ses_client = boto3.client("ses", region_name="us-east-1")
        ses_client.send_email(
            Source="burhankhan@integratehealth.ai",
            Destination={"ToAddresses": [str(request.email)]},
            Message={
                "Subject": {"Data": f"Your Visit Summary — {visit.patient_ref}"},
                "Body": {
                    "Text": {"Data": request.summary},
                },
            },
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "MessageRejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is not verified. Please contact support.",
            )
        logger.error(f"SES send failed for visit {visit_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        )
    except (BotoCoreError, Exception) as e:
        logger.error(f"SES error for visit {visit_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        )

    return {"message": "Summary sent successfully"}
