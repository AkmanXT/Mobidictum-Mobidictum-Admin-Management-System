#!/usr/bin/env python3
import httpx
import asyncio
import json

async def check_status():
    client = httpx.AsyncClient(timeout=5.0)
    
    try:
        print("🔍 Checking action status...")
        response = await client.get("http://127.0.0.1:8000/api/actions/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Pending actions: {data.get('data', {}).get('pending_actions', {})}")
            print(f"🔢 Total pending: {data.get('data', {}).get('total_pending', 0)}")
            
            failed = data.get('data', {}).get('failed_actions', [])
            if failed:
                print(f"❌ Failed actions: {len(failed)}")
                for f in failed[:3]:
                    print(f"   • {f.get('code', 'unknown')}: {f.get('metadata', {}).get('action_error', 'unknown')}")
        else:
            print(f"❌ Error: {response.status_code}")
        
        print("\n📋 Recent codes with status...")
        codes_response = await client.get("http://127.0.0.1:8000/api/codes?limit=10")
        if codes_response.status_code == 200:
            codes_data = codes_response.json()
            codes = codes_data.get('data', [])
            
            if isinstance(codes, list):
                for code in codes[:8]:
                    status = code.get('status', 'unknown')
                    code_name = code.get('code', 'unknown')
                
                    emoji = {
                        'active': '✅',
                        'deleting': '🗑️',
                        'deleted': '❌',
                        'creating': '🆕',
                        'updating': '✏️'
                    }.get(status, '❓')
                    
                    print(f"   {emoji} {code_name:<25} {status}")
            elif isinstance(codes, dict):
                print(f"   Unexpected dict format. Keys: {list(codes.keys())}")
                print(f"   Raw data: {codes}")
            else:
                print(f"   No codes found or unexpected format: {type(codes)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(check_status())
