from fastapi import APIRouter, HTTPException, Depends, Query, status
from supabase import Client
from app.deps import get_supabase_client
from app.models import (
    Code, CodeCreate, CodeUpdate, CodeStatus, CodeType, 
    CodeAllocateResponse, APIResponse
)
from typing import Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/codes", tags=["codes"])


@router.post("", response_model=APIResponse)
async def create_code(
    code_data: CodeCreate,
    supabase: Client = Depends(get_supabase_client)
):
    """Create a new discount code."""
    try:
        # Check if code already exists
        existing = supabase.table("codes").select("id").eq("code", code_data.code).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{code_data.code}' already exists"
            )
        
        result = supabase.table("codes").insert(code_data.model_dump()).execute()
        
        return APIResponse(
            success=True,
            message=f"Code '{code_data.code}' created successfully",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating code: {str(e)}"
        )


@router.get("", response_model=APIResponse)
async def list_codes(
    status_filter: Optional[CodeStatus] = Query(None, alias="status"),
    type_filter: Optional[CodeType] = Query(None, alias="type"),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0),
    supabase: Client = Depends(get_supabase_client)
):
    """List codes with optional filters."""
    try:
        query = supabase.table("codes").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter.value)
        if type_filter:
            query = query.eq("type", type_filter.value)
        if organization_id:
            query = query.eq("organization_id", organization_id)
            
        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} codes",
            data={
                "codes": result.data,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status_filter.value if status_filter else None,
                    "type": type_filter.value if type_filter else None,
                    "organization_id": organization_id
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing codes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing codes: {str(e)}"
        )


@router.get("/{code}", response_model=APIResponse)
async def get_code(
    code: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get a specific code by its code value."""
    try:
        result = supabase.table("codes").select("*").eq("code", code).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        return APIResponse(
            success=True,
            message=f"Code '{code}' retrieved successfully",
            data=result.data[0]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting code: {str(e)}"
        )


@router.post("/allocate", response_model=CodeAllocateResponse)
async def allocate_code(
    code_type: Optional[CodeType] = Query(CodeType.discount),
    organization_id: Optional[str] = Query(None),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Atomically allocate one active, unused code and mark it as used.
    Uses the allocate_code Postgres function for race-safety.
    """
    try:
        # Call the Postgres function for atomic allocation
        result = supabase.rpc(
            "allocate_code",
            {
                "p_code_type": code_type.value,
                "p_organization_id": organization_id
            }
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No available {code_type.value} codes found"
            )
        
        allocated_code = result.data[0]
        
        return CodeAllocateResponse(
            code=allocated_code["code"],
            id=allocated_code["id"],
            allocated_at=datetime.fromisoformat(allocated_code["used_at"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error allocating code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error allocating code: {str(e)}"
        )


@router.post("/{code}/mark-used", response_model=APIResponse)
async def mark_code_used(
    code: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Explicitly mark a code as used."""
    try:
        # Check if code exists and is not already used
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        current_code = existing.data[0]
        
        if current_code["status"] == CodeStatus.used.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{code}' is already used"
            )
        
        if current_code["status"] in [CodeStatus.expired.value, CodeStatus.revoked.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{code}' is {current_code['status']} and cannot be used"
            )
        
        # Update code status
        update_data = {
            "status": CodeStatus.used.value,
            "used_at": datetime.utcnow().isoformat(),
            "current_uses": (current_code.get("current_uses", 0) + 1),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = (
            supabase.table("codes")
            .update(update_data)
            .eq("code", code)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Code '{code}' marked as used",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking code as used: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking code as used: {str(e)}"
        )


@router.post("/{code}/revoke", response_model=APIResponse)
async def revoke_code(
    code: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Revoke a code (set status to revoked)."""
    try:
        # Check if code exists
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        # Update code status
        update_data = {
            "status": CodeStatus.revoked.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = (
            supabase.table("codes")
            .update(update_data)
            .eq("code", code)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Code '{code}' revoked",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error revoking code: {str(e)}"
        )


@router.put("/{code}", response_model=APIResponse)
async def update_code(
    code: str,
    update_data: CodeUpdate,
    supabase: Client = Depends(get_supabase_client)
):
    """Update code properties."""
    try:
        # Check if code exists
        existing = supabase.table("codes").select("id").eq("code", code).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        # Prepare update data
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow().isoformat()
        
        result = (
            supabase.table("codes")
            .update(update_dict)
            .eq("code", code)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Code '{code}' updated successfully",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating code: {str(e)}"
        )


@router.delete("/{code}")
async def delete_code(
    code: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Delete a discount code from both database and Fienta."""
    try:
        # Check if code exists and get current data
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        code_data = existing.data[0]
        
        # Update code status to deleted in Supabase
        update_result = supabase.table("codes").update({
            "status": "deleted",
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": {
                **code_data.get("metadata", {}),
                "deleted_at": datetime.utcnow().isoformat(),
                "deletion_method": "api_request",
                "previous_status": code_data.get("status", "unknown")
            }
        }).eq("code", code).execute()
        
        # TODO: Integrate with Fienta automation to actually delete from Fienta
        # This would call your Node.js/Playwright scripts to delete from Fienta admin
        
        return APIResponse(
            success=True,
            message=f"Code '{code}' marked as deleted successfully",
            data={
                "code": code,
                "status": "deleted",
                "deleted_at": datetime.utcnow().isoformat(),
                "note": "Code marked as deleted in database. Fienta deletion will be handled by automation."
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting code: {str(e)}"
        )
