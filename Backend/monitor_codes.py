#!/usr/bin/env python3
"""Monitor codes in real-time to see when new ones are created."""

import requests
import time
from datetime import datetime

API_URL = "http://127.0.0.1:8000/api/codes"

def get_codes():
    """Get current codes from API."""
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            return data["data"]["codes"]
        else:
            print(f"❌ Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return []

def monitor_codes():
    """Monitor for new codes."""
    print("🔍 Monitoring codes...")
    print("📋 Current codes:")
    
    # Get initial codes
    codes = get_codes()
    known_codes = {code["id"]: code for code in codes}
    
    # Display initial codes
    for code in codes:
        print(f"  - {code['code']} ({code['status']}) - Created: {code['created_at'][:10]}")
    
    print(f"\n✅ Found {len(codes)} existing codes")
    print("👀 Watching for new codes... (Press Ctrl+C to stop)\n")
    
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        current_codes = get_codes()
        current_ids = {code["id"] for code in current_codes}
        known_ids = set(known_codes.keys())
        
        # Check for new codes
        new_ids = current_ids - known_ids
        if new_ids:
            print(f"\n🎉 NEW CODE DETECTED at {datetime.now().strftime('%H:%M:%S')}!")
            for code in current_codes:
                if code["id"] in new_ids:
                    print(f"  📌 Code: {code['code']}")
                    print(f"     Type: {code['type']}")
                    print(f"     Status: {code['status']}")
                    print(f"     Organization: {code.get('organization_id', 'N/A')}")
                    print(f"     Created: {code['created_at']}")
                    if code.get('metadata'):
                        print(f"     Metadata: {code['metadata']}")
                    known_codes[code["id"]] = code
            print()
        
        # Check for deleted codes
        deleted_ids = known_ids - current_ids
        if deleted_ids:
            print(f"\n🗑️  CODE DELETED at {datetime.now().strftime('%H:%M:%S')}:")
            for code_id in deleted_ids:
                code = known_codes[code_id]
                print(f"  - {code['code']}")
                del known_codes[code_id]
            print()

if __name__ == "__main__":
    try:
        monitor_codes()
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped.")
