"""
Fienta Monitoring Service - End-to-End Code and Order Tracking
Syncs data from Fienta to Supabase every 15 minutes with rate limiting
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from supabase import Client
from app.deps import get_supabase_client
from app.config import settings
from app.models import CodeCreate, OrderCreate, BatchJobCreate, BatchJobUpdate

import logging

logger = logging.getLogger(__name__)

class FientaMonitorService:
    def __init__(self):
        self.supabase: Client = get_supabase_client()
        self.event_id = settings.fienta_event_id or "118714"  # Default to your event
        self.project_root = Path(__file__).parent.parent.parent
        self.last_sync_time: Optional[datetime] = None
        
    async def run_monitoring_cycle(self) -> Dict[str, Any]:
        """Run a complete monitoring cycle with rate limiting"""
        cycle_start = datetime.now(timezone.utc)
        
        try:
            # Try to create batch job record (optional - system works without it)
            batch_job = None
            try:
                batch_job = await self._create_batch_job("fienta_monitoring", "Full Fienta monitoring cycle")
                logger.info(f"🚀 Starting Fienta monitoring cycle - Job ID: {batch_job['id']}")
            except Exception as e:
                logger.warning(f"Failed to create batch job record (continuing anyway): {e}")
                logger.info("🚀 Starting Fienta monitoring cycle")
            
            # Step 1: Scrape basic usage data (fast)
            logger.info("📊 Step 1: Scraping basic code usage...")
            basic_data = await self._scrape_basic_usage()
            await asyncio.sleep(2)  # Rate limiting delay
            
            # Step 2: Sync codes to Supabase
            logger.info("💾 Step 2: Syncing codes to Supabase...")
            codes_synced = await self._sync_codes_to_supabase(basic_data)
            await asyncio.sleep(2)
            
            # Step 2.5: Clean up codes deleted from Fienta
            logger.info("🧹 Step 2.5: Cleaning up deleted codes...")
            deleted_count = await self._cleanup_deleted_codes(basic_data)
            if deleted_count > 0:
                logger.info(f"🗑️ Marked {deleted_count} codes as deleted")
            await asyncio.sleep(1)
            
            # Step 3: Scrape detailed order data for used codes only
            logger.info("🎫 Step 3: Scraping detailed order data...")
            used_codes = [code for code in basic_data if code.get('ordersUsed', 0) > 0]
            detailed_data = await self._scrape_detailed_orders(used_codes)
            await asyncio.sleep(3)
            
            # Step 4: Sync orders to Supabase
            logger.info("📝 Step 4: Syncing orders to Supabase...")
            orders_synced = await self._sync_orders_to_supabase(detailed_data)
            await asyncio.sleep(2)
            
            # Step 5: Update batch job as completed (if job was created)
            cycle_end = datetime.now(timezone.utc)
            duration = (cycle_end - cycle_start).total_seconds()
            
            if batch_job:
                try:
                    await self._update_batch_job(batch_job['id'], {
                        'status': 'completed',
                        'processed_items': codes_synced + orders_synced,
                        'completed_at': cycle_end.isoformat(),
                        'results': {
                            'codes_processed': len(basic_data),
                            'codes_synced': codes_synced,
                            'orders_synced': orders_synced,
                            'used_codes': len(used_codes),
                            'duration_seconds': duration,
                            'cycle_type': 'full_monitoring'
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to update batch job (continuing anyway): {e}")
            
            self.last_sync_time = cycle_end
            
            logger.info(f"✅ Monitoring cycle completed in {duration:.1f}s - Codes: {codes_synced}, Orders: {orders_synced}")
            
            return {
                'success': True,
                'job_id': batch_job['id'] if batch_job else None,
                'duration': duration,
                'codes_synced': codes_synced,
                'orders_synced': orders_synced,
                'timestamp': cycle_end.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Monitoring cycle failed: {e}")
            
            # Update batch job as failed (if job was created)
            if 'batch_job' in locals() and batch_job:
                try:
                    await self._update_batch_job(batch_job['id'], {
                        'status': 'failed',
                        'error_log': [str(e)],
                        'completed_at': datetime.now(timezone.utc).isoformat()
                    })
                except Exception as update_error:
                    logger.warning(f"Failed to update failed batch job: {update_error}")
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def _scrape_basic_usage(self) -> List[Dict[str, Any]]:
        """Scrape basic code usage data using the enhanced CLI"""
        output_file = self.project_root / f"monitoring_basic_{int(time.time())}.json"
        
        try:
            # Run the enhanced scraping command (Windows-compatible with absolute paths)
            cli_path = self.project_root / "src" / "cli-enhanced.ts"
            cmd = f'cd "{self.project_root}" && node dist/cli-enhanced.js scrape-usage {self.event_id} --with-orders --output="{output_file}"'
            
            logger.info(f"Running command: {cmd}")
            logger.info(f"Working directory: {self.project_root}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,  # Use shell on Windows
                timeout=180,  # 3 minute timeout for detailed scraping
                encoding="utf-8",
                errors="ignore"
            )
            
            if result.returncode != 0:
                raise Exception(f"Scraping failed: {result.stderr}")
            
            # Read the generated JSON file
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Clean up the file
                output_file.unlink()
                
                return data
            else:
                raise Exception("Output file not created")
                
        except subprocess.TimeoutExpired:
            raise Exception("Scraping timed out after 2 minutes")
        except Exception as e:
            # Clean up on error
            if output_file.exists():
                output_file.unlink()
            raise e
    
    async def _scrape_detailed_orders(self, used_codes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scrape detailed order data for codes that have been used"""
        if not used_codes:
            return []
            
        output_file = self.project_root / f"monitoring_detailed_{int(time.time())}.json"
        
        try:
            # Run detailed scraping with orders (Windows-compatible with absolute paths)
            cli_path = self.project_root / "src" / "cli-enhanced.ts"
            cmd = f'cd "{self.project_root}" && node dist/cli-enhanced.js scrape-usage {self.event_id} --with-orders --output="{output_file}"'
            
            logger.info(f"Running detailed scraping for {len(used_codes)} used codes...")
            logger.info(f"Working directory: {self.project_root}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,  # Use shell on Windows
                timeout=300,  # 5 minute timeout for detailed scraping
                encoding="utf-8",
                errors="ignore"
            )
            
            if result.returncode != 0:
                raise Exception(f"Detailed scraping failed: {result.stderr}")
            
            # Read the generated JSON file
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Clean up the file
                output_file.unlink()
                
                # Filter to only return codes that have orders
                return [code for code in data if code.get('orders', [])]
            else:
                raise Exception("Detailed output file not created")
                
        except subprocess.TimeoutExpired:
            raise Exception("Detailed scraping timed out after 5 minutes")
        except Exception as e:
            # Clean up on error
            if output_file.exists():
                output_file.unlink()
            raise e
    
    async def _sync_codes_to_supabase(self, codes_data: List[Dict[str, Any]]) -> int:
        """Sync code data to Supabase codes table"""
        synced_count = 0
        
        logger.info(f"💾 Syncing {len(codes_data)} codes to database...")
        
        for code_data in codes_data:
            try:
                # Check if code already exists
                existing = self.supabase.table("codes").select("*").eq("code", code_data['code']).execute()
                
                code_record = {
                    'code': code_data['code'],
                    'type': 'discount',  # All scraped codes are discount codes
                    'status': 'active' if code_data.get('ordersUsed', 0) < code_data.get('orderLimit', 1) else 'used',
                    'metadata': {
                        'orders_used': code_data.get('ordersUsed', 0),
                        'order_limit': code_data.get('orderLimit', 0),
                        'tickets_used': code_data.get('ticketsUsed', 0),
                        'ticket_limit': code_data.get('ticketLimit', 0),
                        'usage_percentage': round((code_data.get('ordersUsed', 0) / max(code_data.get('orderLimit', 1), 1)) * 100, 1),
                        'last_scraped': datetime.now(timezone.utc).isoformat(),
                        'fienta_event_id': self.event_id,
                        'fienta_discount_id': code_data.get('discountId'),  # Store Fienta internal ID
                        'fienta_edit_url': code_data.get('editUrl')  # Store edit URL for easy access
                    }
                }
                
                if existing.data:
                    # Update existing code
                    self.supabase.table("codes").update(code_record).eq("code", code_data['code']).execute()
                else:
                    # Insert new code
                    self.supabase.table("codes").insert(code_record).execute()
                
                synced_count += 1
                
                # Rate limiting - small delay between operations
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to sync code {code_data['code']}: {e}")
        
        return synced_count
    
    async def _sync_orders_to_supabase(self, detailed_data: List[Dict[str, Any]]) -> int:
        """Sync order data to Supabase orders table"""
        synced_count = 0
        
        for code_data in detailed_data:
            for order in code_data.get('orders', []):
                try:
                    # Check if order already exists
                    existing = self.supabase.table("orders").select("*").eq("external_id", order['orderId']).execute()
                    
                    order_record = {
                        'external_id': order['orderId'],
                        'customer_email': order['customerEmail'],
                        'customer_name': order.get('customerName', ''),
                        'total_amount': float(order['totalAmount'].replace(',', '.')) if order['totalAmount'] else 0.0,
                        'currency': order.get('currency', 'EUR'),
                        'status': order['status'],
                        'order_date': self._parse_order_date(order['orderDate']),
                        'metadata': {
                            'customer_phone': order.get('customerPhone', ''),
                            'discount_code': order.get('discountCode', ''),
                            'ticket_count': order.get('ticketCount', 0),
                            'ticket_details': order.get('ticketDetails', []),
                            'fienta_event_id': self.event_id,
                            'last_scraped': datetime.now(timezone.utc).isoformat()
                        }
                    }
                    
                    if existing.data:
                        # Update existing order
                        self.supabase.table("orders").update(order_record).eq("external_id", order['orderId']).execute()
                    else:
                        # Insert new order
                        self.supabase.table("orders").insert(order_record).execute()
                    
                    synced_count += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to sync order {order['orderId']}: {e}")
        
        return synced_count
    
    async def _create_batch_job(self, job_type: str, description: str) -> Dict[str, Any]:
        """Create a new batch job record"""
        job_data = {
            'name': f"Fienta Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'job_type': job_type,
            'status': 'running',
            'total_items': 0,  # Will be updated later
            'processed_items': 0,
            'failed_items': 0,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'results': {
                'description': description,
                'event_id': self.event_id,
                'monitor_version': '1.0'
            }
        }
        
        result = self.supabase.table("batch_jobs").insert(job_data).execute()
        return result.data[0]
    
    async def _update_batch_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update a batch job record"""
        self.supabase.table("batch_jobs").update(updates).eq("id", job_id).execute()
    
    def _parse_order_date(self, date_str: str) -> str:
        """Parse Fienta date format to ISO format"""
        try:
            # Fienta format: "12.09.2025 10:45"
            from datetime import datetime
            dt = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")
            # Convert to timezone-aware datetime
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return datetime.now(timezone.utc).isoformat()

    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status and recent activity"""
        try:
            # Get recent batch jobs
            recent_jobs = self.supabase.table("batch_jobs")\
                .select("*")\
                .eq("type", "fienta_monitoring")\
                .order("created_at", desc=True)\
                .limit(10)\
                .execute()
            
            # Get code statistics
            codes_stats = self.supabase.table("codes")\
                .select("status")\
                .execute()
            
            status_counts = {}
            for code in codes_stats.data:
                status = code['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Get recent orders
            recent_orders = self.supabase.table("orders")\
                .select("*")\
                .order("created_at", desc=True)\
                .limit(5)\
                .execute()
            
            return {
                'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None,
                'recent_jobs': recent_jobs.data,
                'code_statistics': status_counts,
                'recent_orders': recent_orders.data,
                'event_id': self.event_id,
                'status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Failed to get monitoring status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _cleanup_deleted_codes(self, current_codes_data: List[Dict[str, Any]]) -> int:
        """Mark codes as deleted if they exist in database but not in Fienta"""
        try:
            # Get current code names from Fienta scrape
            fienta_codes = set(code['code'] for code in current_codes_data)
            
            # Only consider active codes for cleanup. Do not touch creating/deleting/updating/renaming.
            all_db_codes = self.supabase.table("codes").select("code,status").eq("status", "active").execute()
            
            deleted_count = 0
            for db_code in all_db_codes.data:
                code_name = db_code['code']
                current_status = db_code['status']
                
                # If active in DB but missing in Fienta → mark deleted
                if code_name not in fienta_codes and current_status == 'active':
                    logger.info(f"🗑️ Code {code_name} missing from Fienta - marking as deleted")
                    
                    # Get existing metadata
                    existing_metadata = self._get_existing_metadata(code_name)
                    
                    # Update code status to deleted
                    cleanup_metadata = {
                        **existing_metadata,
                        'deleted_at': datetime.now(timezone.utc).isoformat(),
                        'deletion_source': 'monitoring_cleanup',
                        'deletion_method': 'monitoring_cleanup',
                        'deletion_reason': 'missing_from_fienta',
                        'deletion_completed_by': 'fienta_monitor',
                        'previous_status': current_status
                    }
                    
                    self.supabase.table("codes").update({
                        'status': 'deleted',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                        'metadata': cleanup_metadata
                    }).eq("code", code_name).execute()
                    
                    deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup of deleted codes: {e}")
            return 0
    
    def _get_existing_metadata(self, code_name: str) -> Dict[str, Any]:
        """Get existing metadata for a code"""
        try:
            result = self.supabase.table("codes").select("metadata").eq("code", code_name).execute()
            if result.data:
                return result.data[0].get('metadata', {})
            return {}
        except Exception as e:
            logger.warning(f"Could not get existing metadata for {code_name}: {e}")
            return {}
    
    async def run_fast_check(self) -> Dict[str, Any]:
        """Run lightweight code existence check"""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Use the new lightweight CLI command
            timestamp = int(start_time.timestamp())
            output_file = f"fast_check_{timestamp}.json"
            
            command = [
                'node', 'dist/cli-enhanced.js',
                'list-codes', '118714',
                f'--output={output_file}'
            ]
            
            logger.info(f"Running fast check command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30  # Much shorter timeout for fast check
            )
            
            if result.returncode != 0:
                logger.error(f"Fast check command failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f"Command failed: {result.stderr}",
                    'timestamp': start_time.isoformat()
                }
            
            # Read the results
            output_path = self.project_root / output_file
            if not output_path.exists():
                logger.error(f"Fast check output file not found: {output_path}")
                return {
                    'success': False,
                    'error': 'Output file not found',
                    'timestamp': start_time.isoformat()
                }
            
            with open(output_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            
            # Clean up the output file
            output_path.unlink()
            
            # Extract codes and metadata
            fienta_codes = result_data.get('codes', [])
            metadata_captured = result_data.get('metadata', {})
            
            # Update database with captured metadata
            updated_count = await self._update_codes_metadata(metadata_captured)
            
            # Compare with database and cleanup deleted codes
            cleaned_count = await self._fast_cleanup_deleted_codes(fienta_codes)
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return {
                'success': True,
                'codes_checked': len(fienta_codes),
                'codes_cleaned': cleaned_count,
                'metadata_updated': updated_count,
                'duration': duration,
                'timestamp': start_time.isoformat()
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Fast check command timed out")
            return {
                'success': False,
                'error': 'Command timed out',
                'timestamp': start_time.isoformat()
            }
        except Exception as e:
            logger.error(f"Fast check failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': start_time.isoformat()
            }
    
    async def _fast_cleanup_deleted_codes(self, fienta_codes: List[str]) -> int:
        """Fast cleanup - mark codes as deleted if they're missing from Fienta"""
        try:
            fienta_codes_set = set(fienta_codes)
            
            # Only consider active codes for cleanup
            all_db_codes = self.supabase.table("codes").select("code,status").eq("status", "active").execute()
            
            deleted_count = 0
            for db_code in all_db_codes.data:
                code_name = db_code['code']
                
                # If active in DB but missing in Fienta → mark deleted
                if code_name not in fienta_codes_set:
                    logger.info(f"⚡ Code {code_name} missing from Fienta - marking as deleted (fast check)")
                    
                    # Get existing metadata
                    existing_metadata = self._get_existing_metadata(code_name)
                    
                    # Update code status to deleted
                    cleanup_metadata = {
                        **existing_metadata,
                        'deleted_at': datetime.now(timezone.utc).isoformat(),
                        'deletion_source': 'fast_monitoring',
                        'deletion_method': 'fast_monitoring',
                        'deletion_reason': 'missing_from_fienta_fast_check',
                        'deletion_completed_by': 'fienta_monitor',
                        'previous_status': 'active'
                    }
                    
                    self.supabase.table("codes").update({
                        'status': 'deleted',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                        'metadata': cleanup_metadata
                    }).eq("code", code_name).execute()
                    
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"⚡ Fast cleanup: marked {deleted_count} codes as deleted")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Fast cleanup failed: {e}")
            return 0
    
    async def _update_codes_metadata(self, metadata_captured: Dict[str, Dict[str, str]]) -> int:
        """Update database with metadata captured during fast check"""
        updated_count = 0
        
        try:
            for code, code_metadata in metadata_captured.items():
                # Get current record
                current = self.supabase.table("codes").select("metadata").eq('code', code).execute()
                
                if current.data:
                    existing_metadata = current.data[0].get('metadata', {})
                    
                    # Only update if we have new information
                    needs_update = False
                    updated_metadata = {**existing_metadata}
                    
                    if 'discountId' in code_metadata and not existing_metadata.get('fienta_discount_id'):
                        updated_metadata['fienta_discount_id'] = code_metadata['discountId']
                        needs_update = True
                    
                    if 'editUrl' in code_metadata and not existing_metadata.get('fienta_edit_url'):
                        updated_metadata['fienta_edit_url'] = code_metadata['editUrl']
                        needs_update = True
                    
                    if needs_update:
                        updated_metadata['metadata_updated_at'] = datetime.now(timezone.utc).isoformat()
                        updated_metadata['metadata_source'] = 'fast_monitoring'
                        
                        self.supabase.table("codes").update({
                            'metadata': updated_metadata,
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }).eq('code', code).execute()
                        
                        updated_count += 1
                        logger.debug(f"⚡ Updated metadata for {code}: ID={code_metadata.get('discountId')}")
            
            if updated_count > 0:
                logger.info(f"⚡ Fast monitoring: updated metadata for {updated_count} codes")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating codes metadata: {e}")
            return updated_count
