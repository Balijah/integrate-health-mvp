"""
Support API endpoint.

Routes contact support submissions to founder emails.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORT_EMAILS = [
    "burhankhan@integratehealth.ai",
]


class SupportRequest(BaseModel):
    message: str


class SupportResponse(BaseModel):
    status: str
    message: str


@router.post(
    "/support",
    response_model=SupportResponse,
    summary="Submit a support request",
    description="Send a support message to the Integrate Health team.",
)
async def submit_support(
    request: SupportRequest,
    current_user: CurrentUser,
) -> SupportResponse:
    """
    Submit a contact support request.
    
    Logs the support request with user info. In production,
    this should send emails to the support team.
    """
    user_email = current_user.email
    user_name = current_user.full_name
    
    # Log the support request (always works)
    logger.info(
        f"Support request from {user_name} ({user_email}): {request.message}"
    )
    
    # Try to send via SES if available
    try:
        import boto3
        ses = boto3.client("ses", region_name="us-east-1")
        
        subject = f"Support Request from {user_name}"
        body = f"From: {user_name} ({user_email})\n\nMessage:\n{request.message}"
        
        ses.send_email(
            Source="burhankhan@integratehealth.ai",
            Destination={"ToAddresses": SUPPORT_EMAILS},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info(f"Support email sent to {SUPPORT_EMAILS}")
    except Exception as e:
        # SES not configured or unavailable — log only
        logger.warning(f"Could not send support email via SES: {e}")
    
    return SupportResponse(
        status="received",
        message="Your support request has been received. We will be in touch shortly.",
    )
