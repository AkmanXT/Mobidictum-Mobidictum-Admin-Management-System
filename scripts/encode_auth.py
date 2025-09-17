#!/usr/bin/env python3
"""
Script to encode auth/state.json for production deployment
Usage: python scripts/encode_auth.py
"""

import base64
import json
import os

def encode_auth_state():
    auth_file = "auth/state.json"
    
    if not os.path.exists(auth_file):
        print(f"❌ {auth_file} not found!")
        print("Make sure you have logged into Fienta locally first.")
        return None
    
    try:
        with open(auth_file, 'r', encoding='utf-8') as f:
            auth_data = f.read()
        
        # Encode to base64
        encoded = base64.b64encode(auth_data.encode('utf-8')).decode('utf-8')
        
        print("✅ Auth state encoded successfully!")
        print("\n📋 Add this as FIENTA_AUTH_STATE environment variable in Render:")
        print("-" * 60)
        print(encoded)
        print("-" * 60)
        print("\n🔒 This contains your login session - keep it secure!")
        
        return encoded
        
    except Exception as e:
        print(f"❌ Error encoding auth state: {e}")
        return None

if __name__ == "__main__":
    encode_auth_state()
