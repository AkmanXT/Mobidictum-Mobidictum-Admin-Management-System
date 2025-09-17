"""
Scheduler Service - Runs Fienta monitoring every 15 minutes
Uses asyncio for non-blocking scheduling with proper error handling
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.services.fienta_monitor import FientaMonitorService
from app.services.action_processor import ActionProcessor

logger = logging.getLogger(__name__)

class MonitoringScheduler:
    def __init__(self):
        self.monitor_service = FientaMonitorService()
        self.action_processor = ActionProcessor()
        self.is_running = False
        self.current_task: Optional[asyncio.Task] = None
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.last_action_check: Optional[datetime] = None
        
    async def start(self):
        """Start the monitoring scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
            
        self.is_running = True
        logger.info("🚀 Starting Fienta monitoring scheduler (15-minute intervals)")
        
        # Start the scheduling loop
        self.current_task = asyncio.create_task(self._schedule_loop())
        
    async def stop(self):
        """Stop the monitoring scheduler"""
        if not self.is_running:
            return
            
        self.is_running = False
        logger.info("🛑 Stopping Fienta monitoring scheduler")
        
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
    
    async def _schedule_loop(self):
        """Main scheduling loop - runs monitoring every 15 minutes and actions every 30 seconds"""
        # Run immediately on startup
        await self._run_monitoring_cycle()
        
        while self.is_running:
            try:
                # Two-tier monitoring: fast checks every minute + full monitoring every 15 minutes
                for i in range(15):  # 15 iterations of 1 minute = 15 minutes
                    if not self.is_running:
                        break
                    
                    # Process pending actions every 30 seconds (2x per minute)
                    for j in range(2):
                        if not self.is_running:
                            break
                        await self._process_pending_actions()
                        await asyncio.sleep(30)
                    
                    # Fast code existence check every minute (except first minute)
                    if i > 0 and self.is_running:
                        await self._run_fast_monitoring()
                
                # Run full monitoring cycle after 15 minutes
                if self.is_running:
                    await self._run_monitoring_cycle()
                    
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                self.error_count += 1
                
                # Wait a bit before retrying on error
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _run_monitoring_cycle(self):
        """Run a single monitoring cycle with error handling"""
        cycle_start = datetime.now(timezone.utc)
        self.next_run = None  # Clear next run time during execution
        
        try:
            logger.info(f"🔄 Starting monitoring cycle #{self.run_count + 1}")
            
            # Run the monitoring cycle
            result = await self.monitor_service.run_monitoring_cycle()
            
            self.run_count += 1
            self.last_run = cycle_start
            
            if result['success']:
                logger.info(f"✅ Monitoring cycle completed successfully")
                logger.info(f"   📊 Codes synced: {result['codes_synced']}")
                logger.info(f"   📝 Orders synced: {result['orders_synced']}")
                logger.info(f"   ⏱️  Duration: {result['duration']:.1f}s")
            else:
                logger.error(f"❌ Monitoring cycle failed: {result['error']}")
                self.error_count += 1
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in monitoring cycle: {e}")
            self.error_count += 1
        
        # Calculate next run time
        if self.is_running:
            self.next_run = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            # Add 15 minutes
            import datetime as dt
            self.next_run += dt.timedelta(minutes=15)
            
            logger.info(f"⏭️  Next monitoring cycle: {self.next_run.strftime('%H:%M:%S')}")
    
    async def _run_fast_monitoring(self):
        """Run lightweight code existence check"""
        try:
            logger.debug("⚡ Running fast code existence check...")
            
            result = await self.monitor_service.run_fast_check()
            
            if result['success']:
                codes_checked = result.get('codes_checked', 0)
                codes_cleaned = result.get('codes_cleaned', 0)
                metadata_updated = result.get('metadata_updated', 0)
                duration = result.get('duration', 0)
                
                if codes_cleaned > 0 or metadata_updated > 0:
                    logger.info(f"⚡ Fast check completed: {codes_checked} codes, {codes_cleaned} cleaned, {metadata_updated} metadata updated, {duration:.1f}s")
                else:
                    logger.debug(f"⚡ Fast check completed: {codes_checked} codes verified, {duration:.1f}s")
            else:
                logger.warning(f"⚠️ Fast monitoring failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Error in fast monitoring: {e}")
    
    async def _process_pending_actions(self):
        """Process pending actions using the action processor"""
        try:
            result = await self.action_processor.process_pending_actions()
            self.last_action_check = datetime.now(timezone.utc)
            
            if result['success']:
                # Only sum the numeric processing results, not timestamp/duration
                results_dict = result.get('results', {})
                total_processed = sum([
                    results_dict.get('codes_processed', 0),
                    results_dict.get('orders_processed', 0), 
                    results_dict.get('links_processed', 0),
                    results_dict.get('organizations_processed', 0)
                ])
                if total_processed > 0:
                    logger.info(f"🔧 Processed {total_processed} pending actions")
            else:
                logger.error(f"❌ Action processing failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Error in action processing: {e}")
    
    async def run_manual_cycle(self) -> Dict[str, Any]:
        """Manually trigger a monitoring cycle (for API endpoints)"""
        logger.info("🔧 Manual monitoring cycle triggered")
        
        try:
            result = await self.monitor_service.run_monitoring_cycle()
            
            if result['success']:
                logger.info("✅ Manual monitoring cycle completed")
            else:
                logger.error(f"❌ Manual monitoring cycle failed: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Manual monitoring cycle error: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'is_running': self.is_running,
            'run_count': self.run_count,
            'error_count': self.error_count,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'last_action_check': self.last_action_check.isoformat() if self.last_action_check else None,
            'uptime_minutes': (datetime.now(timezone.utc) - self.last_run).total_seconds() / 60 if self.last_run else 0,
            'action_processor': self.action_processor.get_status()
        }

# Global scheduler instance
monitoring_scheduler = MonitoringScheduler()

async def start_monitoring():
    """Start the global monitoring scheduler"""
    await monitoring_scheduler.start()

async def stop_monitoring():
    """Stop the global monitoring scheduler"""
    await monitoring_scheduler.stop()

def get_scheduler() -> MonitoringScheduler:
    """Get the global scheduler instance"""
    return monitoring_scheduler
