"""
Monitoring API endpoints - Control and monitor the Fienta scraping system
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from supabase import Client
from typing import Dict, Any

from app.deps import get_supabase_client
from app.services.scheduler import get_scheduler, MonitoringScheduler
from app.services.fienta_monitor import FientaMonitorService

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@router.get("/status")
async def get_monitoring_status(
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Get comprehensive monitoring status"""
    try:
        scheduler = get_scheduler()
        monitor_service = FientaMonitorService()
        
        # Get scheduler status
        scheduler_status = scheduler.get_status()
        
        # Get monitoring service status
        monitor_status = await monitor_service.get_monitoring_status()
        
        return {
            "success": True,
            "data": {
                "scheduler": scheduler_status,
                "monitoring": monitor_status,
                "system": {
                    "status": "healthy" if scheduler_status['is_running'] else "stopped",
                    "interval_minutes": 15,
                    "description": "Fienta end-to-end monitoring system"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring status: {str(e)}")

@router.post("/start")
async def start_monitoring(
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Start the monitoring scheduler"""
    try:
        scheduler = get_scheduler()
        
        if scheduler.is_running:
            return {
                "success": True,
                "message": "Monitoring is already running",
                "data": scheduler.get_status()
            }
        
        # Start the scheduler in the background
        background_tasks.add_task(scheduler.start)
        
        return {
            "success": True,
            "message": "Monitoring scheduler started",
            "data": {
                "interval_minutes": 15,
                "next_run": "within 15 minutes"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@router.post("/stop")
async def stop_monitoring(
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Stop the monitoring scheduler"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler.is_running:
            return {
                "success": True,
                "message": "Monitoring is already stopped",
                "data": scheduler.get_status()
            }
        
        # Stop the scheduler in the background
        background_tasks.add_task(scheduler.stop)
        
        return {
            "success": True,
            "message": "Monitoring scheduler stopped",
            "data": scheduler.get_status()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")

@router.post("/run-now")
async def run_monitoring_now(
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Manually trigger a monitoring cycle"""
    try:
        scheduler = get_scheduler()
        
        # Run monitoring cycle in the background
        background_tasks.add_task(scheduler.run_manual_cycle)
        
        return {
            "success": True,
            "message": "Manual monitoring cycle started",
            "data": {
                "status": "running",
                "estimated_duration": "2-5 minutes"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start manual monitoring: {str(e)}")

@router.get("/jobs")
async def get_recent_jobs(
    limit: int = 20,
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Get recent monitoring job history"""
    try:
        result = supabase.table("batch_jobs")\
            .select("*")\
            .eq("job_type", "fienta_monitoring")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            "success": True,
            "data": {
                "jobs": result.data,
                "total": len(result.data)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job history: {str(e)}")

@router.get("/stats")
async def get_monitoring_stats(
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Get monitoring statistics and insights"""
    try:
        # Get code statistics
        codes_result = supabase.table("codes").select("status, metadata").execute()
        
        # Calculate code stats
        total_codes = len(codes_result.data)
        active_codes = len([c for c in codes_result.data if c['status'] == 'active'])
        used_codes = len([c for c in codes_result.data if c['status'] == 'used'])
        
        # Get order statistics
        orders_result = supabase.table("orders").select("status, total_amount, currency").execute()
        
        # Calculate order stats
        total_orders = len(orders_result.data)
        completed_orders = len([o for o in orders_result.data if o['status'] == 'completed'])
        
        # Calculate revenue
        total_revenue = sum(o['total_amount'] for o in orders_result.data if o['total_amount'])
        
        # Get recent job statistics
        jobs_result = supabase.table("batch_jobs")\
            .select("status, results")\
            .eq("job_type", "fienta_monitoring")\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        successful_jobs = len([j for j in jobs_result.data if j['status'] == 'completed'])
        failed_jobs = len([j for j in jobs_result.data if j['status'] == 'failed'])
        
        return {
            "success": True,
            "data": {
                "codes": {
                    "total": total_codes,
                    "active": active_codes,
                    "used": used_codes,
                    "usage_rate": round((used_codes / max(total_codes, 1)) * 100, 1)
                },
                "orders": {
                    "total": total_orders,
                    "completed": completed_orders,
                    "completion_rate": round((completed_orders / max(total_orders, 1)) * 100, 1),
                    "total_revenue": total_revenue
                },
                "jobs": {
                    "recent_runs": len(jobs_result.data),
                    "successful": successful_jobs,
                    "failed": failed_jobs,
                    "success_rate": round((successful_jobs / max(len(jobs_result.data), 1)) * 100, 1)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring stats: {str(e)}")

@router.get("/health")
async def monitoring_health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring system"""
    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()
        
        # Determine health status
        is_healthy = (
            status['is_running'] and 
            status['error_count'] < 5 and  # Less than 5 errors
            (status['last_run'] is None or 
             (datetime.now(timezone.utc) - datetime.fromisoformat(status['last_run'])).total_seconds() < 1800)  # Last run within 30 minutes
        )
        
        return {
            "success": True,
            "data": {
                "status": "healthy" if is_healthy else "unhealthy",
                "is_running": status['is_running'],
                "uptime_minutes": status['uptime_minutes'],
                "error_count": status['error_count'],
                "last_run": status['last_run']
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "data": {
                "status": "unhealthy",
                "error": str(e)
            }
        }

# Import required modules for health check
from datetime import datetime, timezone
