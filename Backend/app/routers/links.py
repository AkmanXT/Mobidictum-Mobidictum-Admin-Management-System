from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from supabase import Client
from app.deps import get_supabase_client
from app.models import Link, LinkCreate, LinkStatus, APIResponse
from typing import Optional
import logging
import uuid
import hashlib
from urllib.parse import urlencode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/links", tags=["links"])


def generate_short_id(target_url: str, utm_params: dict) -> str:
    """Generate a short ID for the link."""
    # Create a hash of the URL + UTM params for uniqueness
    content = f"{target_url}_{utm_params}"
    hash_obj = hashlib.md5(content.encode())
    return hash_obj.hexdigest()[:8]


def build_utm_url(target_url: str, utm_params: dict) -> str:
    """Build URL with UTM parameters."""
    if not any(utm_params.values()):
        return target_url
    
    # Filter out None values
    params = {k: v for k, v in utm_params.items() if v is not None}
    
    if not params:
        return target_url
    
    # Add UTM parameters to URL
    separator = "&" if "?" in target_url else "?"
    return f"{target_url}{separator}{urlencode(params)}"


@router.post("", response_model=APIResponse)
async def create_link(
    link_data: LinkCreate,
    supabase: Client = Depends(get_supabase_client)
):
    """Create a new short link with UTM parameters."""
    try:
        # Validate target URL
        if not link_data.target_url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target URL must start with http:// or https://"
            )
        
        # Prepare UTM parameters
        utm_params = {
            "utm_source": link_data.utm_source,
            "utm_medium": link_data.utm_medium,
            "utm_campaign": link_data.utm_campaign,
            "utm_term": link_data.utm_term,
            "utm_content": link_data.utm_content
        }
        
        # Generate short ID
        short_id = generate_short_id(link_data.target_url, utm_params)
        
        # Check if link already exists
        existing = supabase.table("links").select("*").eq("short_url", short_id).execute()
        if existing.data:
            return APIResponse(
                success=True,
                message="Link already exists",
                data=existing.data[0]
            )
        
        # Create link record
        link = Link(
            short_url=short_id,
            target_url=link_data.target_url,
            utm_source=link_data.utm_source,
            utm_medium=link_data.utm_medium,
            utm_campaign=link_data.utm_campaign,
            utm_term=link_data.utm_term,
            utm_content=link_data.utm_content,
            organization_id=link_data.organization_id
        )
        
        result = supabase.table("links").insert(link.model_dump()).execute()
        
        return APIResponse(
            success=True,
            message=f"Short link created successfully",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating link: {str(e)}"
        )


@router.get("", response_model=APIResponse)
async def list_links(
    status_filter: Optional[LinkStatus] = Query(None, alias="status"),
    utm_campaign: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0),
    supabase: Client = Depends(get_supabase_client)
):
    """List links with optional filters."""
    try:
        query = supabase.table("links").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter.value)
        if utm_campaign:
            query = query.eq("utm_campaign", utm_campaign)
        if organization_id:
            query = query.eq("organization_id", organization_id)
            
        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} links",
            data={
                "links": result.data,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status_filter.value if status_filter else None,
                    "utm_campaign": utm_campaign,
                    "organization_id": organization_id
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing links: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing links: {str(e)}"
        )


@router.get("/{short_id}", response_model=APIResponse)
async def get_link_details(
    short_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get details of a specific link."""
    try:
        result = supabase.table("links").select("*").eq("short_url", short_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link {short_id} not found"
            )
        
        return APIResponse(
            success=True,
            message=f"Link {short_id} retrieved successfully",
            data=result.data[0]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting link: {str(e)}"
        )


@router.get("/{short_id}/redirect")
async def redirect_link(
    short_id: str,
    request: Request,
    supabase: Client = Depends(get_supabase_client)
):
    """Redirect to target URL and track the click."""
    try:
        # Get link details
        result = supabase.table("links").select("*").eq("short_url", short_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link {short_id} not found"
            )
        
        link = result.data[0]
        
        # Check if link is active
        if link["status"] != LinkStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=f"Link {short_id} is disabled"
            )
        
        # Increment click count
        supabase.table("links").update({
            "clicks": link["clicks"] + 1,
            "updated_at": "now()"
        }).eq("short_url", short_id).execute()
        
        # Build final URL with UTM parameters
        utm_params = {
            "utm_source": link.get("utm_source"),
            "utm_medium": link.get("utm_medium"),
            "utm_campaign": link.get("utm_campaign"),
            "utm_term": link.get("utm_term"),
            "utm_content": link.get("utm_content")
        }
        
        final_url = build_utm_url(link["target_url"], utm_params)
        
        logger.info(f"Redirecting {short_id} to {final_url} (click #{link['clicks'] + 1})")
        
        return RedirectResponse(url=final_url, status_code=status.HTTP_302_FOUND)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redirecting link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error redirecting link: {str(e)}"
        )


@router.post("/{short_id}/disable", response_model=APIResponse)
async def disable_link(
    short_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Disable a link (set status to disabled)."""
    try:
        # Check if link exists
        existing = supabase.table("links").select("*").eq("short_url", short_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link {short_id} not found"
            )
        
        # Update link status
        result = (
            supabase.table("links")
            .update({
                "status": LinkStatus.disabled.value,
                "updated_at": "now()"
            })
            .eq("short_url", short_id)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Link {short_id} disabled",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disabling link: {str(e)}"
        )


@router.post("/{short_id}/enable", response_model=APIResponse)
async def enable_link(
    short_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Enable a link (set status to active)."""
    try:
        # Check if link exists
        existing = supabase.table("links").select("*").eq("short_url", short_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link {short_id} not found"
            )
        
        # Update link status
        result = (
            supabase.table("links")
            .update({
                "status": LinkStatus.active.value,
                "updated_at": "now()"
            })
            .eq("short_url", short_id)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Link {short_id} enabled",
            data=result.data[0] if result.data else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enabling link: {str(e)}"
        )
