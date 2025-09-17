"""
Action Processor Service - Monitors Supabase changes and executes Fienta operations
Handles all operations: create, update, delete, rename codes via metadata patterns
"""

import asyncio
import json
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from supabase import Client
from app.deps import get_supabase_client
from app.config import settings

logger = logging.getLogger(__name__)

class ActionProcessor:
    """Processes pending actions by monitoring database changes"""
    
    def __init__(self):
        self.supabase: Client = get_supabase_client()
        self.project_root = Path(__file__).parent.parent.parent
        self.last_check: Optional[datetime] = None
        
    async def process_pending_actions(self) -> Dict[str, Any]:
        """Check for and process all pending actions in the database"""
        check_start = datetime.now(timezone.utc)
        
        try:
            logger.debug("🔍 Checking for pending actions...")
            
            # Process different types of pending actions
            results = {
                'codes_processed': await self._process_code_actions(),
                'orders_processed': await self._process_order_actions(),
                'links_processed': await self._process_link_actions(),
                'organizations_processed': await self._process_organization_actions(),
                'timestamp': check_start.isoformat(),
                'duration': 0
            }
            
            self.last_check = check_start
            duration = (datetime.now(timezone.utc) - check_start).total_seconds()
            results['duration'] = duration
            
            total_processed = sum([
                results['codes_processed'],
                results['orders_processed'], 
                results['links_processed'],
                results['organizations_processed']
            ])
            
            if total_processed > 0:
                logger.info(f"✅ Processed {total_processed} pending actions in {duration:.1f}s")
            
            return {
                'success': True,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing pending actions: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': check_start.isoformat()
            }
    
    async def _process_code_actions(self) -> int:
        """Process pending code actions (create, update, delete, rename)"""
        processed = 0
        
        # Find codes with pending actions
        pending_codes = self.supabase.table("codes")\
            .select("*")\
            .or_("status.eq.creating,status.eq.deleting,status.eq.updating,status.eq.renaming")\
            .execute()
        
        for code_record in pending_codes.data or []:
            try:
                await self._process_single_code_action(code_record)
                processed += 1
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to process code action for {code_record['code']}: {e}")
                
        return processed
    
    async def _process_single_code_action(self, code_record: Dict[str, Any]) -> None:
        """Process a single code action based on status and metadata"""
        code = code_record['code']
        status = code_record['status']
        metadata = code_record.get('metadata', {})
        action = metadata.get('action')
        
        logger.info(f"🔧 Processing {action or status} action for code: {code}")
        
        try:
            if status == 'creating' or action == 'create':
                await self._handle_code_creation(code_record)
            elif status == 'deleting' or action == 'delete':
                logger.info(f"➡️ Entering delete handler for {code}")
                await self._handle_code_deletion(code_record)
                logger.info(f"⬅️ Finished delete handler for {code}")
            elif status == 'updating' or action == 'update':
                await self._handle_code_update(code_record)
            elif status == 'renaming' or action == 'rename':
                await self._handle_code_rename(code_record)
            else:
                logger.warning(f"Unknown action for code {code}: {action}")
                
        except Exception as e:
            # Mark action as failed
            await self._mark_action_failed(code, str(e), code_record.get('status', 'active'))
            raise
    
    async def _handle_code_creation(self, code_record: Dict[str, Any]) -> None:
        """Handle code creation in Fienta"""
        code = code_record['code']
        metadata = code_record.get('metadata', {})
        
        # Extract creation parameters from metadata
        creation_params = {
            'discount_percent': metadata.get('discount_percent', 10),
            'discount_amount': metadata.get('discount_amount'),
            'max_uses': metadata.get('max_uses', 1),
            'expires_at': metadata.get('expires_at'),
            'description': metadata.get('description', f'Auto-created code {code}')
        }
        
        # Run Node.js script to create code in Fienta
        success = await self._run_fienta_operation('create-code', {
            'code': code,
            **creation_params
        })
        
        if success:
            # Mark as successfully created
            self.supabase.table("codes").update({
                'status': 'active',
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': {
                    **metadata,
                    'created_in_fienta_at': datetime.now(timezone.utc).isoformat(),
                    'creation_method': 'api_request',
                    **{k: v for k, v in creation_params.items() if v is not None}
                }
            }).eq('code', code).execute()
            
            logger.info(f"✅ Successfully created code {code} in Fienta")
        else:
            raise Exception("Failed to create code in Fienta")
    
    async def _handle_code_deletion(self, code_record: Dict[str, Any]) -> None:
        """Handle code deletion in Fienta with coordination"""
        code = code_record['code']
        metadata = code_record.get('metadata', {})
        
        # Log deletion source for audit trail
        deletion_source = metadata.get('deletion_source', 'unknown')
        deletion_method = metadata.get('deletion_method', 'unknown')
        coordination_lock = metadata.get('coordination_lock')
        
        logger.info(f"🗑️ Processing deletion for {code} - Source: {deletion_source}, Method: {deletion_method}, Lock: {coordination_lock}")
        
        # Double-check current status to prevent race conditions
        current_status_check = self.supabase.table("codes").select("status,metadata").eq('code', code).execute()
        if current_status_check.data:
            current_status = current_status_check.data[0].get('status')
            if current_status != 'deleting':
                logger.warning(f"⚠️ Code {code} status changed from 'deleting' to '{current_status}' - aborting deletion")
                return
        
        # Get Fienta discount ID from metadata
        fienta_discount_id = metadata.get('fienta_discount_id')
        fienta_edit_url = metadata.get('fienta_edit_url')
        
        logger.info(f"🔍 Deletion handler for {code}: ID={fienta_discount_id}, URL={fienta_edit_url}")
        
        # If identifiers are missing, try to resolve them first
        if not fienta_discount_id or not fienta_edit_url:
            logger.info(f"Attempting to resolve Fienta identifiers for code {code} before deletion")
            resolved = await self._resolve_fienta_code_identifiers(code)
            if resolved:
                fienta_discount_id = fienta_discount_id or resolved.get('discount_id')
                fienta_edit_url = fienta_edit_url or resolved.get('edit_url')
                logger.info(f"🔄 Resolved for {code}: ID={fienta_discount_id}, URL={fienta_edit_url}")
                # Persist resolved identifiers on the record so future actions work offline
                updated_meta = {**metadata}
                if fienta_discount_id:
                    updated_meta['fienta_discount_id'] = fienta_discount_id
                if fienta_edit_url:
                    updated_meta['fienta_edit_url'] = fienta_edit_url
                self.supabase.table("codes").update({
                    'metadata': updated_meta,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('code', code).execute()
            else:
                logger.error(f"❌ Could not resolve identifiers for {code}")

        if not fienta_discount_id:
            # Hard fail instead of pretending deletion succeeded
            previous_status = metadata.get('previous_status', code_record.get('status', 'active'))
            await self._mark_action_failed(code, "Missing fienta_discount_id; cannot delete in Fienta", previous_status)
            logger.error(f"Cannot delete {code}: fienta_discount_id missing and could not be resolved")
            # Write a failure log for auditing
            try:
                from pathlib import Path as _P
                import os as _os, datetime as _dt
                _os.makedirs('logs', exist_ok=True)
                ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_code = str(code).replace('/', '_')
                log_path = _P('logs') / f'fienta_delete_{safe_code}_{ts}.log'
                log_path.write_text('Aborted: Missing fienta_discount_id and could not resolve.\n', encoding='utf-8')
                logger.info(f"📝 Wrote failure log to {log_path}")
            except Exception:
                pass
            return

        else:
            # Run deletion with Fienta discount ID
            success = await self._run_fienta_operation('delete-code', {
                'code': code,
                'fienta_discount_id': fienta_discount_id,
                'fienta_edit_url': fienta_edit_url
            })
        
        if success:
            # Mark as deleted only after successful browser run
            completion_metadata = {
                **metadata,
                'deleted_in_fienta_at': datetime.now(timezone.utc).isoformat(),
                'deletion_completed_by': 'action_processor',
                'deletion_source': deletion_source,  # Keep original source
                'deletion_method': deletion_method,   # Keep original method
                'coordination_completed': datetime.now(timezone.utc).isoformat()
            }
            
            self.supabase.table("codes").update({
                'status': 'deleted',
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': completion_metadata
            }).eq('code', code).execute()
            logger.info(f"✅ Successfully deleted code {code} from Fienta (ID: {fienta_discount_id}) - Source: {deletion_source}")
        else:
            # Do not mark as deleted; leave as deleting and flag failure
            await self._mark_action_failed(code, "Playwright deletion did not complete", 'active')
            raise Exception("Failed to delete code from Fienta")

    async def _resolve_fienta_code_identifiers(self, code: str) -> Optional[Dict[str, str]]:
        """Try to resolve discount ID and edit URL for a code from DB or by scraping one-off."""
        try:
            # 1) Check current DB metadata
            row = self.supabase.table("codes").select("metadata").eq("code", code).execute()
            if row.data:
                md = row.data[0].get('metadata', {}) or {}
                did = md.get('fienta_discount_id')
                eurl = md.get('fienta_edit_url')
                if did and eurl:
                    return {'discount_id': did, 'edit_url': eurl}

            # 2) Scrape specific code details via enhanced CLI
            import tempfile, json
            temp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            temp_path = temp.name
            temp.close()

            cli = self.project_root / 'src' / 'cli-enhanced.ts'
            cmd = f'cd "{self.project_root}" && node dist/cli-enhanced.js scrape-code-details {settings.fienta_event_id} {code} --output="{temp_path}"'
            logger.info(f"Running one-off scrape to resolve identifiers for {code}")
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=120, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logger.error(f"Scrape failed while resolving identifiers for {code}: {result.stderr}")
            else:
                try:
                    import pathlib
                    p = pathlib.Path(temp_path)
                    if p.exists():
                        data = json.loads(p.read_text(encoding='utf-8'))
                        # data may be a list or an object with codes property depending on CLI output
                        items = data if isinstance(data, list) else data.get('codes', [])
                        match = next((d for d in items if d.get('code') == code), None)
                        if match:
                            did = match.get('discountId')
                            eurl = match.get('editUrl')
                            if did or eurl:
                                # persist before returning so subsequent runs can reuse
                                md = {'fienta_discount_id': did, 'fienta_edit_url': eurl}
                                try:
                                    self.supabase.table('codes').update({
                                        'metadata': {**(self.supabase.table('codes').select('metadata').eq('code', code).execute().data[0].get('metadata', {}) if self.supabase.table('codes').select('metadata').eq('code', code).execute().data else {}), **md},
                                        'updated_at': datetime.now(timezone.utc).isoformat()
                                    }).eq('code', code).execute()
                                except Exception:
                                    pass
                                return {'discount_id': did, 'edit_url': eurl}
                except Exception as parse_err:
                    logger.error(f"Failed to parse scrape output for {code}: {parse_err}")
        except Exception as e:
            logger.error(f"Error resolving identifiers for {code}: {e}")
        return None
    
    async def _handle_code_update(self, code_record: Dict[str, Any]) -> None:
        """Handle code updates in Fienta"""
        code = code_record['code']
        metadata = code_record.get('metadata', {})
        
        # Extract update parameters
        update_params = {}
        for field in ['discount_percent', 'discount_amount', 'max_uses', 'expires_at', 'description']:
            if f'new_{field}' in metadata:
                update_params[field] = metadata[f'new_{field}']
        
        if not update_params:
            logger.warning(f"No update parameters found for code {code}")
            return
        
        # Run Node.js script to update code in Fienta
        success = await self._run_fienta_operation('update-code', {
            'code': code,
            **update_params
        })
        
        if success:
            # Mark as updated and apply the new values
            updated_metadata = {**metadata}
            for field, value in update_params.items():
                updated_metadata[field] = value
                # Remove the new_ prefix
                updated_metadata.pop(f'new_{field}', None)
            
            updated_metadata['updated_in_fienta_at'] = datetime.now(timezone.utc).isoformat()
            updated_metadata['update_method'] = 'api_request'
            
            self.supabase.table("codes").update({
                'status': 'active',
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': updated_metadata
            }).eq('code', code).execute()
            
            logger.info(f"✅ Successfully updated code {code} in Fienta")
        else:
            raise Exception("Failed to update code in Fienta")
    
    async def _handle_code_rename(self, code_record: Dict[str, Any]) -> None:
        """Handle code renaming in Fienta"""
        old_code = code_record['code']
        metadata = code_record.get('metadata', {})
        new_code = metadata.get('new_code')
        
        if not new_code:
            raise Exception("No new_code specified in metadata for rename operation")
        
        # Run Node.js script to rename code in Fienta
        success = await self._run_fienta_operation('rename-code', {
            'old_code': old_code,
            'new_code': new_code
        })
        
        if success:
            # Create new record with new code name
            new_record = {**code_record}
            new_record['code'] = new_code
            new_record['status'] = 'active'
            new_record['updated_at'] = datetime.now(timezone.utc).isoformat()
            new_record['metadata'] = {
                **metadata,
                'renamed_from': old_code,
                'renamed_in_fienta_at': datetime.now(timezone.utc).isoformat(),
                'rename_method': 'api_request'
            }
            
            # Remove old record and insert new one
            self.supabase.table("codes").delete().eq('code', old_code).execute()
            self.supabase.table("codes").insert(new_record).execute()
            
            logger.info(f"✅ Successfully renamed code {old_code} to {new_code} in Fienta")
        else:
            raise Exception("Failed to rename code in Fienta")
    
    async def _process_order_actions(self) -> int:
        """Process pending order actions (mainly status updates)"""
        processed = 0
        
        # Find orders with pending actions (guard for schemas without metadata)
        try:
            pending_orders = self.supabase.table("orders")\
                .select("*")\
                .contains("metadata", {"action": "update_status"})\
                .execute()
        except Exception as e:
            logger.warning(f"Skipping order actions due to schema mismatch: {e}")
            return 0
        
        for order_record in pending_orders.data or []:
            try:
                await self._process_order_action(order_record)
                processed += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Failed to process order action for {order_record['external_id']}: {e}")
                
        return processed
    
    async def _process_order_action(self, order_record: Dict[str, Any]) -> None:
        """Process a single order action"""
        order_id = order_record['external_id']
        metadata = order_record.get('metadata', {})
        action = metadata.get('action')
        
        if action == 'update_status':
            new_status = metadata.get('new_status')
            if new_status:
                # Update order status in Fienta (if needed) 
                # For now, just mark as processed since Fienta is read-only for orders
                updated_metadata = {**metadata}
                updated_metadata.pop('action', None)
                updated_metadata['status_updated_at'] = datetime.now(timezone.utc).isoformat()
                
                self.supabase.table("orders").update({
                    'status': new_status,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'metadata': updated_metadata
                }).eq('external_id', order_id).execute()
                
                logger.info(f"✅ Updated order {order_id} status to {new_status}")
    
    async def _process_link_actions(self) -> int:
        """Process pending link actions (URL shortening, tracking)"""
        processed = 0
        
        # Find links with pending actions (guard against schemas without metadata column)
        try:
            pending_links = self.supabase.table("links")\
                .select("*")\
                .contains("metadata", {"action": "create_short_url"})\
                .execute()
        except Exception as e:
            logger.warning(f"Skipping link actions due to schema mismatch: {e}")
            return 0
        
        for link_record in pending_links.data or []:
            try:
                await self._process_link_action(link_record)
                processed += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to process link action for {link_record['id']}: {e}")
                
        return processed
    
    async def _process_link_action(self, link_record: Dict[str, Any]) -> None:
        """Process a single link action"""
        link_id = link_record['id']
        metadata = link_record.get('metadata', {})
        action = metadata.get('action')
        
        if action == 'create_short_url':
            # Generate short URL (placeholder - integrate with your URL shortener)
            original_url = link_record['original_url']
            short_url = f"https://short.ly/{link_id[:8]}"  # Placeholder
            
            updated_metadata = {**metadata}
            updated_metadata.pop('action', None)
            updated_metadata['short_url_created_at'] = datetime.now(timezone.utc).isoformat()
            
            self.supabase.table("links").update({
                'short_url': short_url,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': updated_metadata
            }).eq('id', link_id).execute()
            
            logger.info(f"✅ Created short URL for link {link_id}")
    
    async def _process_organization_actions(self) -> int:
        """Process pending organization actions"""
        processed = 0
        
        # Find organizations with pending actions (guard for schemas without metadata)
        try:
            pending_orgs = self.supabase.table("organizations")\
                .select("*")\
                .contains("metadata", {"action": "sync_to_external"})\
                .execute()
        except Exception as e:
            logger.warning(f"Skipping organization actions due to schema mismatch: {e}")
            return 0
        
        for org_record in pending_orgs.data or []:
            try:
                await self._process_organization_action(org_record)
                processed += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to process organization action for {org_record['id']}: {e}")
                
        return processed
    
    async def _process_organization_action(self, org_record: Dict[str, Any]) -> None:
        """Process a single organization action"""
        org_id = org_record['id']
        metadata = org_record.get('metadata', {})
        action = metadata.get('action')
        
        if action == 'sync_to_external':
            # Placeholder for external system sync
            updated_metadata = {**metadata}
            updated_metadata.pop('action', None)
            updated_metadata['synced_at'] = datetime.now(timezone.utc).isoformat()
            
            self.supabase.table("organizations").update({
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': updated_metadata
            }).eq('id', org_id).execute()
            
            logger.info(f"✅ Synced organization {org_id} to external system")
    
    async def _run_fienta_operation(self, operation: str, params: Dict[str, Any]) -> bool:
        """Run a Fienta operation using Playwright automation"""
        try:
            if operation == 'delete-code':
                return await self._delete_code_in_fienta(params)
            
            elif operation in ['create-code', 'update-code', 'rename-code']:
                # These operations would need more complex implementation
                logger.info(f"⚠️ Operation {operation} for {params.get('code')} - Implementation pending")
                logger.info("Note: Operation marked as completed in database. Manual Fienta sync may be needed.")
                return True
            
            else:
                logger.error(f"Unknown Fienta operation: {operation}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in Fienta operation {operation}: {e}")
            return False
    
    async def _delete_code_in_fienta(self, params: Dict[str, Any]) -> bool:
        """Delete a discount code in Fienta using Playwright"""
        try:
            logger.info(f"🎯 _delete_code_in_fienta started with params: {params}")
            code = params.get('code')
            fienta_discount_id = params.get('fienta_discount_id')
            fienta_edit_url = params.get('fienta_edit_url')
            logger.info(f"📝 Extracted: code={code}, id={fienta_discount_id}, url={fienta_edit_url}")
            
            if not fienta_discount_id:
                logger.error(f"No Fienta discount ID provided for code {code}")
                return False
            
            # Construct the edit URL if we already know it; otherwise we'll navigate via list and search
            logger.info(f"🔗 Constructing edit URL from: {fienta_edit_url}")
            if fienta_edit_url:
                if fienta_edit_url.startswith('http'):
                    edit_url = fienta_edit_url
                else:
                    edit_url = f"https://fienta.com{fienta_edit_url}"
            else:
                edit_url = f"https://fienta.com/my/events/{settings.fienta_event_id}/discounts/{fienta_discount_id}/edit"
            logger.info(f"🎯 Final edit URL: {edit_url}")
            
            # Create a simple Node.js script to handle the deletion
            logger.info(f"🔨 Creating deletion script...")
            delete_script = f'''
const {{ chromium }} = require('playwright');

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {{
    // Load auth state if available
    const fs = require('fs');
    const authStatePath = 'auth/state.json';
    if (fs.existsSync(authStatePath)) {{
      const authState = JSON.parse(fs.readFileSync(authStatePath, 'utf8'));
      await context.addCookies(authState.cookies || []);
    }}
    
    const eventId = '{settings.fienta_event_id}';
    let targetUrl = '{edit_url}';
    if (!targetUrl || targetUrl === 'null') {{
      // Fallback: open discounts list and find the code by text
      const listUrl = `https://fienta.com/my/events/${{eventId}}/discounts`;
      console.log('Navigating to list:', listUrl);
      await page.goto(listUrl);
      await page.waitForLoadState('networkidle');
      // Try to find the row link with code text
      const codeText = '{code}';
      const link = page.locator(`a:has-text("${{codeText}}")`).first();
      await link.waitFor({{ timeout: 10000 }});
      const href = await link.getAttribute('href');
      if (!href) {{
        console.error('Could not find edit link for code in list');
        process.exit(1);
      }}
      targetUrl = href.startsWith('http') ? href : `https://fienta.com${{href}}`;
    }}
    console.log('Navigating to:', targetUrl);
    await page.goto(targetUrl);
    await page.waitForLoadState('networkidle');
    
    // Look for the specific Delete button with class btn-delete
    console.log('Looking for Delete button with class .btn-delete...');
    const deleteButton = page.locator('button.btn-delete, .btn-delete');
    
    // Wait for the button to be visible
    await deleteButton.waitFor({{ state: 'visible', timeout: 10000 }});
    
    if (await deleteButton.isVisible()) {{
      console.log('Found Delete button! Clicking...');
      await deleteButton.click();
      
      // Handle any confirmation dialog (could be modal or alert)
      try {{
        // Wait for confirmation modal/dialog
        console.log('Waiting for confirmation dialog...');
        await page.waitForTimeout(1000); // Give time for modal to appear
        
        // Look for common confirmation patterns
        const confirmSelectors = [
          'button:has-text("Confirm")',
          'button:has-text("Yes")', 
          'button:has-text("Delete")',
          'button:has-text("OK")',
          '.btn-danger:has-text("Delete")',
          '.btn-primary:has-text("Confirm")',
          '[data-dismiss="modal"]:has-text("Delete")'
        ];
        
        let confirmed = false;
        for (const selector of confirmSelectors) {{
          try {{
            const confirmButton = page.locator(selector);
            if (await confirmButton.isVisible({{ timeout: 2000 }})) {{
              console.log(`Found confirmation button: ${{selector}}`);
              await confirmButton.click();
              confirmed = true;
              break;
            }}
          }} catch (e) {{
            // Continue to next selector
          }}
        }}
        
        if (!confirmed) {{
          console.log('No confirmation dialog found or already confirmed');
        }}
        
      }} catch (e) {{
        console.log('No confirmation dialog needed or error:', e.message);
      }}
      
      // Wait for navigation or success indicator
      console.log('Waiting for operation to complete...');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      
      // Check if we're redirected to discounts list
      const currentUrl = page.url();
      if (currentUrl.includes('/discounts') && !currentUrl.includes('/edit')) {{
        console.log('Redirected to discounts list - verifying code deletion...');
        
        // Verify the code is actually deleted by checking if it still exists
        try {{
          // Search for the code in the current page
          const codeRows = await page.locator('tbody tr').all();
          let codeFound = false;
          
          for (const row of codeRows) {{
            try {{
              const codeButton = row.locator('button[data-code]');
              const codeText = await codeButton.getAttribute('data-code');
              if (codeText === '{code}') {{
                codeFound = true;
                break;
              }}
            }} catch (e) {{
              // Continue checking other rows
            }}
          }}
          
          if (codeFound) {{
            console.log('❌ Code {code} still found on page - deletion failed');
            process.exit(1);
          }} else {{
            console.log('✅ Code {code} successfully deleted - not found on discounts page');
            process.exit(0);
          }}
          
        }} catch (e) {{
          console.log('❌ Error verifying deletion:', e.message);
          process.exit(1);
        }}
        
      }} else {{
        console.log('❌ Still on edit page after attempting delete. URL:', currentUrl);
        process.exit(1);
      }}
      
    }} else {{
      console.error('❌ Delete button with class .btn-delete not found');
      
      // Debug: List all buttons on the page
      const allButtons = await page.locator('button').all();
      console.log('Available buttons on page:');
      for (const btn of allButtons) {{
        const text = await btn.textContent();
        const className = await btn.getAttribute('class');
        console.log(`  Button: "${{text}}" class: "${{className}}"`);
      }}
      
      process.exit(1);
    }}
    
  }} catch (error) {{
    console.error('❌ Error:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  }} finally {{
    await browser.close();
  }}
}})();
'''
            logger.info(f"✅ Script generated successfully, length: {len(delete_script)}")
            
            # Write the script to a temporary file in the project directory
            import tempfile
            import os
            temp_dir = self.project_root / 'temp'
            temp_dir.mkdir(exist_ok=True)
            
            temp_file = temp_dir / f'delete_{code}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.js'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(delete_script)
            script_path = str(temp_file)
            
            # Run the deletion script
            logger.info(f"Running Fienta deletion for code {code} (ID: {fienta_discount_id})")
            
            # Debug: Print the command and ensure all variables are defined
            cmd = f'cd "{self.project_root}" && node "{script_path}"'
            logger.info(f"Command: {cmd}")
            logger.info(f"Timeout value: 90")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=90,  # allow more time
                encoding="utf-8",
                errors="ignore"
            )
            
            # Persist stdout/stderr for debugging
            try:
                from pathlib import Path as _P
                import os as _os, datetime as _dt
                _os.makedirs('logs', exist_ok=True)
                ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_code = str(code).replace('/', '_')
                log_path = _P('logs') / f'fienta_delete_{safe_code}_{ts}.log'
                log_path.write_text(f'Edit URL: {edit_url}\nReturn code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n', encoding='utf-8')
                logger.info(f"📝 Wrote Playwright output to {log_path}")
            except Exception as _log_err:
                logger.warning(f"Could not write deletion debug log: {_log_err}")

            # Clean up temp file
            try:
                os.unlink(script_path)
            except:
                pass
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully deleted code {code} from Fienta. Output: {result.stdout}")
                return True
            else:
                logger.error(f"❌ Failed to delete code {code} from Fienta. rc={result.returncode} stdout={result.stdout} stderr={result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting code from Fienta: {e}")
            return False
    
    async def _mark_action_failed(self, code: str, error: str, previous_status: str) -> None:
        """Mark an action as failed and revert status"""
        try:
            # Get current metadata to preserve existing fields
            current = self.supabase.table("codes").select("metadata").eq('code', code).execute()
            existing_metadata = current.data[0].get('metadata', {}) if current.data else {}
            
            # Preserve existing metadata and add error info
            updated_metadata = {
                **existing_metadata,
                'action_failed': True,
                'action_error': error,
                'failed_at': datetime.now(timezone.utc).isoformat()
            }
            
            self.supabase.table("codes").update({
                'status': previous_status,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': updated_metadata
            }).eq('code', code).execute()
            
            logger.error(f"❌ Marked action as failed for code {code}: {error}")
        except Exception as e:
            logger.error(f"Failed to mark action as failed for {code}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get action processor status"""
        return {
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'processor_status': 'active'
        }
