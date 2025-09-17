"""
Actions API Router - Handle pending action requests
Frontend sends direct database updates, backend processes them via actions
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from supabase import Client
from app.deps import get_supabase_client
from app.models import APIResponse
from app.services.scheduler import get_scheduler
from app.auth import verify_api_key

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/actions", tags=["actions"])

@router.post("/codes/create")
async def request_code_creation(
    code_data: Dict[str, Any],
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Request creation of a new discount code in Fienta"""
    try:
        code = code_data.get('code')
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code is required"
            )
        
        # Check if code already exists
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{code}' already exists"
            )
        
        # Create code record with 'creating' status
        code_record = {
            'code': code,
            'type': code_data.get('type', 'discount'),
            'status': 'creating',
            'organization_id': code_data.get('organization_id'),
            'metadata': {
                'action': 'create',
                'requested_at': datetime.now(timezone.utc).isoformat(),
                'request_method': 'api',
                **{k: v for k, v in code_data.items() if k not in ['code', 'type', 'organization_id']}
            }
        }
        
        result = supabase.table("codes").insert(code_record).execute()
        
        return APIResponse(
            success=True,
            message=f"Code creation requested for '{code}'. Processing will begin shortly.",
            data={
                'code': code,
                'status': 'creating',
                'estimated_completion': '1-2 minutes'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting code creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting code creation: {str(e)}"
        )

@router.post("/codes/{code}/update")
async def request_code_update(
    code: str,
    update_data: Dict[str, Any],
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Request update of an existing discount code in Fienta"""
    try:
        # Check if code exists
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        current_data = existing.data[0]
        current_metadata = current_data.get('metadata', {})
        
        # Update metadata with new values (prefixed with 'new_')
        updated_metadata = {**current_metadata}
        for key, value in update_data.items():
            if key != 'code':  # Don't allow code changes via update
                updated_metadata[f'new_{key}'] = value
        
        updated_metadata.update({
            'action': 'update',
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'request_method': 'api'
        })
        
        # Set status to 'updating'
        supabase.table("codes").update({
            'status': 'updating',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': updated_metadata
        }).eq("code", code).execute()
        
        return APIResponse(
            success=True,
            message=f"Code update requested for '{code}'. Processing will begin shortly.",
            data={
                'code': code,
                'status': 'updating',
                'updates': update_data,
                'estimated_completion': '1-2 minutes'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting code update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting code update: {str(e)}"
        )

@router.post("/codes/{code}/delete")
async def request_code_deletion(
    code: str,
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Request deletion of a discount code from Fienta"""
    try:
        # Check if code exists
        existing = supabase.table("codes").select("*").eq("code", code).execute()
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{code}' not found"
            )
        
        current_data = existing.data[0]
        current_metadata = current_data.get('metadata', {})
        
        # Check if code is already being processed
        current_status = current_data.get('status', 'active')
        if current_status in ['deleting', 'creating', 'updating', 'renaming']:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{code}' is already being processed (status: {current_status})"
            )
        
        # Update status to 'deleting' with action metadata
        # Hydrate with any existing Fienta identifiers so the processor can run without resolving
        updated_metadata = {
            **current_metadata,
            'action': 'delete',
            'deletion_source': 'user_request',
            'deletion_method': 'api_request',
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'request_method': 'api',
            'previous_status': current_status,
            'coordination_lock': datetime.now(timezone.utc).isoformat()
        }
        # Copy identifiers if present on the current row
        if isinstance(current_metadata, dict):
            if current_metadata.get('fienta_discount_id'):
                updated_metadata['fienta_discount_id'] = current_metadata.get('fienta_discount_id')
            if current_metadata.get('fienta_edit_url'):
                updated_metadata['fienta_edit_url'] = current_metadata.get('fienta_edit_url')
        
        supabase.table("codes").update({
            'status': 'deleting',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': updated_metadata
        }).eq("code", code).execute()
        
        return APIResponse(
            success=True,
            message=f"Code deletion requested for '{code}'. Processing will begin shortly.",
            data={
                'code': code,
                'status': 'deleting',
                'estimated_completion': '1-2 minutes'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting code deletion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting code deletion: {str(e)}"
        )

@router.post("/codes/{old_code}/rename")
async def request_code_rename(
    old_code: str,
    rename_data: Dict[str, str],
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Request renaming of a discount code in Fienta"""
    try:
        new_code = rename_data.get('new_code')
        if not new_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_code is required"
            )
        
        # Check if old code exists
        existing = supabase.table("codes").select("*").eq("code", old_code).execute()
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Code '{old_code}' not found"
            )
        
        # Check if new code already exists
        new_existing = supabase.table("codes").select("*").eq("code", new_code).execute()
        if new_existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Code '{new_code}' already exists"
            )
        
        current_data = existing.data[0]
        current_metadata = current_data.get('metadata', {})
        
        # Update status to 'renaming' with action metadata
        updated_metadata = {
            **current_metadata,
            'action': 'rename',
            'new_code': new_code,
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'request_method': 'api',
            'previous_status': current_data.get('status', 'active')
        }
        
        supabase.table("codes").update({
            'status': 'renaming',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': updated_metadata
        }).eq("code", old_code).execute()
        
        return APIResponse(
            success=True,
            message=f"Code rename requested from '{old_code}' to '{new_code}'. Processing will begin shortly.",
            data={
                'old_code': old_code,
                'new_code': new_code,
                'status': 'renaming',
                'estimated_completion': '1-2 minutes'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting code rename: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting code rename: {str(e)}"
        )

@router.get("/status")
async def get_actions_status(
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Get status of pending actions"""
    try:
        # Get counts of pending actions by type
        pending_codes = supabase.table("codes")\
            .select("status")\
            .in_("status", ["creating", "updating", "deleting", "renaming"])\
            .execute()
        
        status_counts = {}
        for code in pending_codes.data or []:
            status = code['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get recent failed actions
        failed_codes = supabase.table("codes")\
            .select("code, metadata")\
            .contains("metadata", {"action_failed": True})\
            .order("updated_at", desc=True)\
            .limit(10)\
            .execute()
        
        # Get action processor status from scheduler
        scheduler = get_scheduler()
        processor_status = scheduler.action_processor.get_status()
        
        return APIResponse(
            success=True,
            message="Action status retrieved successfully",
            data={
                'pending_actions': status_counts,
                'failed_actions': failed_codes.data or [],
                'processor_status': processor_status,
                'total_pending': sum(status_counts.values())
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting actions status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting actions status: {str(e)}"
        )

@router.post("/process-now")
async def trigger_action_processing(
    auth: bool = Depends(verify_api_key)
):
    """Manually trigger action processing (for testing/debugging)"""
    try:
        scheduler = get_scheduler()
        result = await scheduler.action_processor.process_pending_actions()
        
        return APIResponse(
            success=result['success'],
            message="Action processing completed" if result['success'] else f"Action processing failed: {result.get('error')}",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error triggering action processing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering action processing: {str(e)}"
        )

@router.get("/history")
async def get_action_history(
    limit: int = 50,
    action_type: Optional[str] = None,
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Get history of completed actions"""
    try:
        query = supabase.table("codes").select("code, status, metadata, created_at, updated_at")
        
        if action_type:
            query = query.contains("metadata", {"action": action_type})
        
        # Get codes that have completed actions
        query = query.or_("status.eq.active,status.eq.deleted")\
                    .order("updated_at", desc=True)\
                    .limit(limit)
        
        result = query.execute()
        
        # Filter to only show codes with action history
        action_history = []
        for code in result.data or []:
            metadata = code.get('metadata', {})
            if any(key.endswith('_at') and 'fienta' in key for key in metadata.keys()):
                action_history.append({
                    'code': code['code'],
                    'status': code['status'],
                    'last_action': metadata.get('action', 'unknown'),
                    'completed_at': code['updated_at'],
                    'metadata': metadata
                })
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(action_history)} action history records",
            data=action_history
        )
        
    except Exception as e:
        logger.error(f"Error getting action history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting action history: {str(e)}"
        )


@router.post("/process")
async def process_pending_actions(
    supabase: Client = Depends(get_supabase_client),
    auth: bool = Depends(verify_api_key)
):
    """Manually trigger action processing for pending actions"""
    try:
        from app.services.action_processor import ActionProcessor
        
        logger.info("🔄 Manual action processing triggered via API")
        
        # Create action processor instance (no arguments needed)
        processor = ActionProcessor()
        
        # Process all pending actions
        result = await processor.process_pending_actions()
        
        logger.info(f"✅ Manual action processing completed: {result}")
        
        return APIResponse(
            success=True,
            message="Action processing completed successfully",
            data={
                'processed': result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Manual action processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Action processing failed: {str(e)}"
        )
