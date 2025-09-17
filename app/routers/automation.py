from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from supabase import Client
from app.deps import get_supabase_client
from app.models import (
    BatchJobCreate, APIResponse, FientaCreateCodesRequest, 
    FientaRenameCodesRequest, CSVDiffRequest, JobStatus
)
from app.services.job_executor import JobExecutor
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/automation", tags=["automation"])

# Global job executor instance
job_executor: Optional[JobExecutor] = None


def get_job_executor(supabase: Client = Depends(get_supabase_client)) -> JobExecutor:
    """Get or create job executor instance."""
    global job_executor
    if job_executor is None:
        job_executor = JobExecutor(supabase)
    return job_executor


@router.post("/fienta/create-codes", response_model=APIResponse)
async def create_fienta_codes(
    request: FientaCreateCodesRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """
    Create Fienta discount codes from CSV/XLSX using existing Node.js automation.
    Wraps the existing npm run dev script as a background job.
    """
    try:
        # Validate request
        if not request.csv_path and not request.xlsx_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either csv_path or xlsx_path must be provided"
            )
        
        # Create job record
        job_data = BatchJobCreate(
            job_type="fienta.create_codes",
            args={
                "csv_path": request.csv_path,
                "xlsx_path": request.xlsx_path,
                "dry_run": request.dry_run,
                "headless": request.headless
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"Fienta code creation job started",
            data={
                "job_id": job_id,
                "job_type": "fienta.create_codes",
                "status": "pending"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Fienta create codes job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(e)}"
        )


@router.post("/fienta/rename-codes", response_model=APIResponse)
async def rename_fienta_codes(
    request: FientaRenameCodesRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """
    Rename Fienta discount codes using existing Node.js automation.
    Supports both prefix-based renaming and pairs CSV mapping.
    """
    try:
        # Validate request
        has_pairs = bool(request.pairs_csv_path)
        has_prefix = bool(request.csv_path and request.rename_prefix)
        
        if not has_pairs and not has_prefix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either pairs_csv_path or (csv_path + rename_prefix) must be provided"
            )
        
        # Create job record
        job_data = BatchJobCreate(
            job_type="fienta.rename_codes",
            args={
                "pairs_csv_path": request.pairs_csv_path,
                "csv_path": request.csv_path,
                "rename_prefix": request.rename_prefix,
                "rename_pad_length": request.rename_pad_length,
                "rename_start": request.rename_start,
                "rename_limit": request.rename_limit,
                "dry_run": request.dry_run,
                "headless": request.headless
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"Fienta code rename job started",
            data={
                "job_id": job_id,
                "job_type": "fienta.rename_codes",
                "status": "pending"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Fienta rename codes job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(e)}"
        )


@router.post("/fienta/update-discount", response_model=APIResponse)
async def update_fienta_discount(
    csv_path: str,
    discount_percent: int,
    dry_run: bool = False,
    headless: bool = True,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """Update discount percentage for existing Fienta codes."""
    try:
        # Create job record
        job_data = BatchJobCreate(
            job_type="fienta.update_discount",
            args={
                "csv_path": csv_path,
                "discount_percent": discount_percent,
                "dry_run": dry_run,
                "headless": headless
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"Fienta discount update job started",
            data={
                "job_id": job_id,
                "job_type": "fienta.update_discount",
                "status": "pending"
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting Fienta update discount job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(e)}"
        )


@router.post("/csv/diff", response_model=APIResponse)
async def csv_diff(
    request: CSVDiffRequest,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """Generate applied-diff report between two XLSX files."""
    try:
        # Create job record
        job_data = BatchJobCreate(
            job_type="fienta.csv_diff",
            args={
                "old_xlsx_path": request.old_xlsx_path,
                "new_xlsx_path": request.new_xlsx_path
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"CSV diff job started",
            data={
                "job_id": job_id,
                "job_type": "fienta.csv_diff",
                "status": "pending"
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting CSV diff job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(e)}"
        )


@router.post("/xlsx-to-csv", response_model=APIResponse)
async def xlsx_to_csv(
    input_path: str,
    output_path: Optional[str] = None,
    supabase: Client = Depends(get_supabase_client),
    executor: JobExecutor = Depends(get_job_executor)
):
    """Convert XLSX to CSV using existing TypeScript tool."""
    try:
        # Create job record
        job_data = BatchJobCreate(
            job_type="csv.xlsx_to_csv",
            args={
                "input_path": input_path,
                "output_path": output_path
            }
        )
        
        result = supabase.table("batch_jobs").insert(job_data.model_dump()).execute()
        job_id = result.data[0]["id"]
        
        # Start job in background
        await executor.start_job(job_id)
        
        return APIResponse(
            success=True,
            message=f"XLSX to CSV conversion job started",
            data={
                "job_id": job_id,
                "job_type": "csv.xlsx_to_csv",
                "status": "pending"
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting XLSX to CSV job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(e)}"
        )
