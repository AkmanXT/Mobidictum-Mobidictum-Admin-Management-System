#!/usr/bin/env python3
"""
Action System Dashboard - Monitor pending actions and system status
Shows real-time status of the action processing system
"""

import httpx
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000"

class ActionDashboard:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        
    async def get_action_status(self) -> Dict[str, Any]:
        """Get current action status"""
        try:
            response = await self.client.get(f"{BASE_URL}/api/actions/status")
            if response.status_code == 200:
                return response.json().get('data', {})
            else:
                return {'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'error': str(e)}
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring system status"""
        try:
            response = await self.client.get(f"{BASE_URL}/api/monitoring/status")
            if response.status_code == 200:
                return response.json().get('data', {})
            else:
                return {'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'error': str(e)}
    
    async def get_recent_codes(self) -> list:
        """Get recent codes with their statuses"""
        try:
            response = await self.client.get(f"{BASE_URL}/api/codes?limit=10")
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                return []
        except Exception as e:
            return []
    
    def print_dashboard(self, action_status: Dict, monitoring_status: Dict, recent_codes: list):
        """Print the dashboard to console"""
        # Clear screen (works on most terminals)
        print("\033[2J\033[H")
        
        print("🎛️  FIENTA ACTION SYSTEM DASHBOARD")
        print("=" * 60)
        print(f"⏰ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Action Status Section
        print("📊 ACTION STATUS")
        print("-" * 30)
        
        if 'error' in action_status:
            print(f"❌ Error: {action_status['error']}")
        else:
            pending = action_status.get('pending_actions', {})
            total_pending = action_status.get('total_pending', 0)
            
            print(f"🔄 Total Pending Actions: {total_pending}")
            
            if pending:
                for status, count in pending.items():
                    emoji = {
                        'creating': '🆕',
                        'updating': '✏️',
                        'deleting': '🗑️',
                        'renaming': '📝'
                    }.get(status, '❓')
                    print(f"   {emoji} {status.title()}: {count}")
            else:
                print("   ✅ No pending actions")
            
            failed_actions = action_status.get('failed_actions', [])
            if failed_actions:
                print(f"❌ Failed Actions: {len(failed_actions)}")
                for failed in failed_actions[:3]:  # Show first 3
                    code = failed.get('code', 'unknown')
                    error = failed.get('metadata', {}).get('action_error', 'unknown error')
                    print(f"   • {code}: {error[:50]}...")
            
        print()
        
        # Monitoring Status Section
        print("🤖 MONITORING SYSTEM")
        print("-" * 30)
        
        if 'error' in monitoring_status:
            print(f"❌ Error: {monitoring_status['error']}")
        else:
            is_running = monitoring_status.get('is_running', False)
            status_icon = "🟢" if is_running else "🔴"
            print(f"{status_icon} Scheduler Running: {is_running}")
            
            last_run = monitoring_status.get('last_run')
            if last_run:
                last_run_time = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                minutes_ago = (datetime.now() - last_run_time.replace(tzinfo=None)).total_seconds() / 60
                print(f"🕐 Last Full Sync: {minutes_ago:.1f} minutes ago")
            
            last_action_check = monitoring_status.get('last_action_check')
            if last_action_check:
                last_check_time = datetime.fromisoformat(last_action_check.replace('Z', '+00:00'))
                seconds_ago = (datetime.now() - last_check_time.replace(tzinfo=None)).total_seconds()
                print(f"⚡ Last Action Check: {seconds_ago:.0f} seconds ago")
            
            run_count = monitoring_status.get('run_count', 0)
            error_count = monitoring_status.get('error_count', 0)
            print(f"📈 Runs: {run_count} | Errors: {error_count}")
            
            # Action processor specific info
            action_processor = monitoring_status.get('action_processor', {})
            processor_status = action_processor.get('processor_status', 'unknown')
            print(f"🔧 Action Processor: {processor_status}")
        
        print()
        
        # Recent Codes Section
        print("📋 RECENT CODES")
        print("-" * 30)
        
        if recent_codes:
            for code in recent_codes[:8]:  # Show top 8
                code_name = code.get('code', 'unknown')
                status = code.get('status', 'unknown')
                
                status_emoji = {
                    'active': '✅',
                    'used': '🎫',
                    'expired': '⏰',
                    'creating': '🆕',
                    'updating': '✏️',
                    'deleting': '🗑️',
                    'renaming': '📝',
                    'deleted': '❌'
                }.get(status, '❓')
                
                # Show usage info if available
                metadata = code.get('metadata', {})
                usage_info = ""
                if 'orders_used' in metadata and 'order_limit' in metadata:
                    used = metadata['orders_used']
                    limit = metadata['order_limit']
                    usage_info = f" ({used}/{limit})"
                
                print(f"   {status_emoji} {code_name:<20} {status}{usage_info}")
        else:
            print("   No codes found")
        
        print()
        print("🔄 Auto-refreshing every 5 seconds... (Ctrl+C to exit)")
    
    async def run_dashboard(self):
        """Run the dashboard with auto-refresh"""
        print("🚀 Starting Action System Dashboard...")
        print("Connecting to API server...")
        
        try:
            while True:
                # Fetch all data
                action_status = await self.get_action_status()
                monitoring_status = await self.get_monitoring_status()
                recent_codes = await self.get_recent_codes()
                
                # Display dashboard
                self.print_dashboard(action_status, monitoring_status, recent_codes)
                
                # Wait before next refresh
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Dashboard stopped by user")
        except Exception as e:
            print(f"\n\n❌ Dashboard error: {e}")
        finally:
            await self.client.aclose()

async def main():
    """Main dashboard runner"""
    dashboard = ActionDashboard()
    await dashboard.run_dashboard()

if __name__ == "__main__":
    print("🎛️  Fienta Action System Dashboard")
    print("Make sure your FastAPI server is running on http://127.0.0.1:8000")
    print("Press Ctrl+C to exit...")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Dashboard closed.")
    except Exception as e:
        print(f"Error: {e}")
