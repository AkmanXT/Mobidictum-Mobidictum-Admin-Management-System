from fastapi import APIRouter, HTTPException, Header, Depends, status
from supabase import Client
from app.deps import get_supabase_client
from app.config import settings
from app.models import OrderCreate, WebhookCreate, APIResponse
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def verify_make_token(x_make_token: Optional[str] = Header(None)) -> bool:
    """Verify the Make.com webhook token."""
    if not x_make_token or x_make_token != settings.make_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token"
        )
    return True


@router.post("/make/webhook", response_model=APIResponse)
async def receive_make_webhook(
    payload: Dict[str, Any],
    supabase: Client = Depends(get_supabase_client),
    _: bool = Depends(verify_make_token)
):
    """
    Receive webhook from Make.com (Fienta → Make → backend).
    
    Enforces idempotency via processed_webhooks table.
    Creates orders but does NOT auto-consume codes.
    """
    try:
        # Extract event metadata
        event_id = payload.get("event_id") or payload.get("id") or payload.get("order_id")
        event_type = payload.get("event_type", "unknown")
        
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing event_id in payload"
            )
        
        # Check for duplicate processing
        existing = supabase.table("processed_webhooks").select("id").eq("event_id", event_id).execute()
        if existing.data:
            logger.info(f"Webhook {event_id} already processed, skipping")
            return APIResponse(
                success=True,
                message=f"Webhook {event_id} already processed",
                data={"event_id": event_id, "skipped": True}
            )
        
        # Insert webhook record for idempotency
        webhook_data = WebhookCreate(
            event_id=event_id,
            event_type=event_type,
            source="make.com",
            raw_payload=payload
        )
        
        supabase.table("processed_webhooks").insert(webhook_data.model_dump()).execute()
        
        # Process based on event type
        result_data = {"event_id": event_id, "processed": True}
        
        if event_type in ["order.created", "order.completed", "order_created", "order_completed"]:
            order_result = await process_order_webhook(payload, supabase)
            result_data.update(order_result)
        
        logger.info(f"Successfully processed webhook {event_id}")
        return APIResponse(
            success=True,
            message=f"Webhook {event_id} processed successfully",
            data=result_data
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


async def process_order_webhook(payload: Dict[str, Any], supabase: Client) -> Dict[str, Any]:
    """Process order-related webhook payload."""
    try:
        # Extract order data from payload
        order_data = payload.get("order", payload)
        
        # Map Fienta fields to our order model
        external_id = str(order_data.get("id") or order_data.get("order_id", ""))
        
        if not external_id:
            raise ValueError("Missing order ID in webhook payload")
        
        # Check if order already exists
        existing_order = supabase.table("orders").select("id").eq("external_id", external_id).execute()
        if existing_order.data:
            logger.info(f"Order {external_id} already exists, updating")
            # Could update existing order here if needed
            return {"order_id": external_id, "action": "updated"}
        
        # Create new order
        order = OrderCreate(
            external_id=external_id,
            customer_email=order_data.get("buyer_email") or order_data.get("email") or "",
            customer_name=order_data.get("buyer_name") or order_data.get("name"),
            status="completed" if payload.get("event_type") == "order.completed" else "pending",
            total_amount=float(order_data.get("total", 0)) if order_data.get("total") else None,
            currency=order_data.get("currency", "USD"),
            order_date=datetime.fromisoformat(order_data.get("created_at", datetime.utcnow().isoformat())),
            items=order_data.get("items", []),
            metadata={
                "fienta_data": order_data,
                "webhook_source": "make.com",
                "processed_at": datetime.utcnow().isoformat()
            }
        )
        
        result = supabase.table("orders").insert(order.model_dump()).execute()
        
        logger.info(f"Created order {external_id}")
        return {
            "order_id": external_id,
            "action": "created",
            "supabase_id": result.data[0]["id"] if result.data else None
        }
        
    except Exception as e:
        logger.error(f"Error processing order webhook: {str(e)}")
        raise


@router.get("/webhooks/processed", response_model=APIResponse)
async def list_processed_webhooks(
    limit: int = 50,
    offset: int = 0,
    supabase: Client = Depends(get_supabase_client)
):
    """List processed webhooks for debugging."""
    try:
        result = (
            supabase.table("processed_webhooks")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(result.data)} processed webhooks",
            data={
                "webhooks": result.data,
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing processed webhooks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing processed webhooks: {str(e)}"
        )
