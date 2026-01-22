"""
Pydantic schemas package.

Exports all request/response schemas for the API.
"""

from app.schemas.auth import LoginRequest, TokenPayload, TokenResponse
from app.schemas.user import UserCreate, UserInDB, UserResponse
from app.schemas.visit import VisitCreate, VisitListResponse, VisitResponse, VisitUpdate
from app.schemas.note import (
    GenerateNoteRequest,
    GenerateNoteResponse,
    NoteExportRequest,
    NoteExportResponse,
    NoteResponse,
    NoteUpdateRequest,
    SOAPContentSchema,
)

__all__ = [
    # User
    "UserCreate",
    "UserResponse",
    "UserInDB",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "TokenPayload",
    # Visit
    "VisitCreate",
    "VisitUpdate",
    "VisitResponse",
    "VisitListResponse",
    # Note
    "GenerateNoteRequest",
    "GenerateNoteResponse",
    "NoteExportRequest",
    "NoteExportResponse",
    "NoteResponse",
    "NoteUpdateRequest",
    "SOAPContentSchema",
]
