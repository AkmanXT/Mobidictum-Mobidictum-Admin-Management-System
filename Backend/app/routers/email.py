from fastapi import APIRouter, HTTPException, Depends, status
from supabase import Client
from app.deps import get_supabase_client
from app.models import EmailSendRequest, BatchJobCreate, APIResponse
from app.services.job_executor import JobExecutor
from app.routers.automation import get_job_executor
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/send", response_model=APIResponse)
async def send_email(
    request: EmailSendRequest,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """
    Send email using archived Gmail API scripts.
    Creates a background job to handle the email sending.
    """
    try:
        # Validate request
        if not request.to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one recipient (to) must be provided"
            )
        
        if not request.subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject is required"
            )
        
        if not request.body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Body is required"
            )
        
        # Create job record
        job_data = BatchJobCreate(
            job_type="email.send",
            args={
                "to": request.to,
                "cc": request.cc or [],
                "bcc": request.bcc or [],
                "subject": request.subject,
                "body": request.body,
                "html_body": request.html_body
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"Email send job started",
            data={
                "job_id": job_id,
                "job_type": "email.send",
                "recipients": len(request.to),
                "status": "pending"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting email send job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting email send job: {str(e)}"
        )


@router.get("/templates", response_model=APIResponse)
async def list_email_templates(
    limit: int = 50,
    offset: int = 0,
    supabase: Client = Depends(get_supabase_client)
):
    """List available email templates (if email_templates table exists)."""
    try:
        result = (
            supabase.table("email_templates")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} email templates",
            data={
                "templates": result.data,
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        # If table doesn't exist or other error, return empty list
        logger.warning(f"Could not retrieve email templates: {str(e)}")
        return APIResponse(
            success=True,
            message="No email templates available",
            data={
                "templates": [],
                "limit": limit,
                "offset": offset,
                "note": "email_templates table may not exist"
            }
        )


@router.get("/campaigns", response_model=APIResponse)
async def list_email_campaigns(
    limit: int = 50,
    offset: int = 0,
    supabase: Client = Depends(get_supabase_client)
):
    """List email campaigns (if email_campaigns table exists)."""
    try:
        result = (
            supabase.table("email_campaigns")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} email campaigns",
            data={
                "campaigns": result.data,
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        # If table doesn't exist or other error, return empty list
        logger.warning(f"Could not retrieve email campaigns: {str(e)}")
        return APIResponse(
            success=True,
            message="No email campaigns available",
            data={
                "campaigns": [],
                "limit": limit,
                "offset": offset,
                "note": "email_campaigns table may not exist"
            }
        )
