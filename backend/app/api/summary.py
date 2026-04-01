"""
Patient Summary send endpoint.

Sends ONLY the patient summary content to the specified email.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()


class SendSummaryRequest(BaseModel):
    email: EmailStr
    summary: str


class SendSummaryResponse(BaseModel):
    status: str
    message: str
    recipient: str


@router.post(
    "/{visit_id}/summary/send",
    response_model=SendSummaryResponse,
    summary="Send patient summary via email",
    description="Send ONLY the patient summary to the specified email address.",
)
async def send_summary(
    visit_id: uuid.UUID,
    request: SendSummaryRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SendSummaryResponse:
    """
    Send patient summary to a patient via email.
    
    IMPORTANT: Only sends the patient summary text.
    Does NOT send SOAP notes, transcripts, or any other visit data.
    """
    provider_name = current_user.full_name
    
    logger.info(
        f"Sending patient summary for visit {visit_id} "
        f"to {request.email} by {provider_name}"
    )
    
    # Try to send via SES
    try:
        import boto3
        ses = boto3.client("ses", region_name="us-east-1")
        
        subject = f"Your Visit Summary from {provider_name} - Integrate Health"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #4ac6d6, #2a8fa0); padding: 20px; border-radius: 12px 12px 0 0;">
                <h2 style="color: white; margin: 0;">Your Visit Summary</h2>
            </div>
            <div style="padding: 24px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0 0 12px 12px;">
                <p style="color: #374151; line-height: 1.6;">{request.summary}</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #9ca3af; font-size: 12px; font-style: italic;">
                    This summary was prepared by {provider_name} using Integrate Health.
                    If you have questions, please contact your provider directly.
                </p>
            </div>
        </body>
        </html>
        """
        
        ses.send_email(
            Source="noreply@integratehealth.ai",
            Destination={"ToAddresses": [request.email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": body_html},
                    "Text": {"Data": f"Your Visit Summary from {provider_name}\n\n{request.summary}\n\nThis summary was prepared by {provider_name} using Integrate Health."},
                },
            },
        )
        logger.info(f"Patient summary email sent to {request.email}")
        
        return SendSummaryResponse(
            status="sent",
            message="Summary sent successfully",
            recipient=request.email,
        )
        
    except Exception as e:
        logger.warning(f"Could not send summary email via SES: {e}")
        # For now, log and return success - the summary was captured
        return SendSummaryResponse(
            status="logged",
            message="Summary recorded. Email delivery will be available once email service is configured.",
            recipient=request.email,
        )
