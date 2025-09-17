from fastapi import APIRouter, HTTPException, Depends, Query, status
from supabase import Client
from app.deps import get_supabase_client
from app.models import BatchJob, JobStatus, APIResponse
from app.services.job_executor import JobExecutor
from app.routers.automation import get_job_executor
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=APIResponse)
async def list_jobs(
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    job_type: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0),
    supabase: Client = Depends(get_supabase_client)
):
    """List batch jobs with optional filters."""
    try:
        query = supabase.table("batch_jobs").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter.value)
        if job_type:
            query = query.eq("job_type", job_type)
        if organization_id:
            query = query.eq("organization_id", organization_id)
            
        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} jobs",
            data={
                "jobs": result.data,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status_filter.value if status_filter else None,
                    "job_type": job_type,
                    "organization_id": organization_id
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing jobs: {str(e)}"
        )


@router.get("/{job_id}", response_model=APIResponse)
async def get_job(
    job_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get details of a specific job."""
    try:
        result = supabase.table("batch_jobs").select("*").eq("id", job_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        return APIResponse(
            success=True,
            message=f"Job {job_id} retrieved successfully",
            data=result.data[0]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting job: {str(e)}"
        )


@router.post("/{job_id}/cancel", response_model=APIResponse)
async def cancel_job(
    job_id: str,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """Cancel a running job."""
    try:
        # Check if job exists and is cancellable
        result = supabase.table("batch_jobs").select("*").eq("id", job_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = result.data[0]
        current_status = job["status"]
        
        if current_status in [JobStatus.completed.value, JobStatus.failed.value, JobStatus.cancelled.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {job_id} is already {current_status} and cannot be cancelled"
            )
        
        # Try to cancel the job
        cancelled = await executor.cancel_job(job_id)
        
        if not cancelled and current_status == JobStatus.pending.value:
            # Job is pending but not running yet, update status directly
            supabase.table("batch_jobs").update({
                "status": JobStatus.cancelled.value,
                "completed_at": "now()",
                "updated_at": "now()"
            }).eq("id", job_id).execute()
            cancelled = True
        
        return APIResponse(
            success=True,
            message=f"Job {job_id} {'cancelled' if cancelled else 'cancellation requested'}",
            data={"job_id": job_id, "cancelled": cancelled}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling job: {str(e)}"
        )


@router.get("/{job_id}/logs", response_model=APIResponse)
async def get_job_logs(
    job_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get logs for a specific job."""
    try:
        result = supabase.table("batch_jobs").select("results, error_log").eq("id", job_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = result.data[0]
        logs = {
            "job_id": job_id,
            "results": job.get("results"),
            "error_log": job.get("error_log")
        }
        
        # If results contain a log file path, try to read it
        results = job.get("results", {})
        if isinstance(results, dict) and results.get("log_file"):
            try:
                import os
                log_file = results["log_file"]
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as f:
                        logs["file_contents"] = f.read()
                else:
                    logs["file_contents"] = f"Log file not found: {log_file}"
            except Exception as e:
                logs["file_read_error"] = str(e)
        
        return APIResponse(
            success=True,
            message=f"Logs for job {job_id} retrieved successfully",
            data=logs
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting job logs: {str(e)}"
        )


@router.get("/running/status", response_model=APIResponse)
async def get_running_jobs_status(
    executor: JobExecutor = Depends(get_job_executor)
):
    """Get status of currently running jobs."""
    try:
        running_job_ids = executor.get_running_jobs()
        
        return APIResponse(
            success=True,
            message=f"Retrieved status of {len(running_job_ids)} running jobs",
            data={
                "running_jobs": running_job_ids,
                "count": len(running_job_ids)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting running jobs status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting running jobs status: {str(e)}"
        )


@router.get("/stats/summary", response_model=APIResponse)
async def get_job_stats(
    supabase: Client = Depends(get_supabase_client)
):
    """Get job statistics summary."""
    try:
        # Get job counts by status
        result = supabase.table("batch_jobs").select("status").execute()
        
        if not result.data:
            stats = {status.value: 0 for status in JobStatus}
        else:
            from collections import Counter
            status_counts = Counter(job["status"] for job in result.data)
            stats = {status.value: status_counts.get(status.value, 0) for status in JobStatus}
        
        # Get recent job activity (last 24 hours)
        recent_result = supabase.table("batch_jobs").select("*").gte(
            "created_at", "now() - interval '24 hours'"
        ).execute()
        
        return APIResponse(
            success=True,
            message="Job statistics retrieved successfully",
            data={
                "total_jobs": len(result.data) if result.data else 0,
                "status_counts": stats,
                "recent_24h": len(recent_result.data) if recent_result.data else 0,
                "recent_jobs": recent_result.data if recent_result.data else []
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting job stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting job stats: {str(e)}"
        )
