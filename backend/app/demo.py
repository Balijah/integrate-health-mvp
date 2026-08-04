"""Safety helpers for the isolated synthetic demo environment."""

from fastapi import HTTPException, status

from app.config import get_settings

DEMO_EXTERNAL_SERVICES_DISABLED = "External integrations are disabled in demo mode."


def ensure_external_services_enabled() -> None:
    """Block billable or externally visible actions while demo mode is active."""
    if get_settings().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DEMO_EXTERNAL_SERVICES_DISABLED,
        )
