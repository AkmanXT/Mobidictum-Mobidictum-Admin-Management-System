#!/usr/bin/env python3
"""
Local development server with hot reload
Run this instead of deploying to Render for faster development
"""

import os
import subprocess
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found!")
        print("📝 Create .env file from env.example and fill in your credentials:")
        print("   cp env.example .env")
        print("   # Then edit .env with your actual values")
        return False
    
    # Check for required variables
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    missing_vars = []
    
    with open(env_path) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content or f"{var}=your-" in content:
                missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or placeholder values in .env: {missing_vars}")
        print("💡 Update these with your actual Supabase credentials")
        return False
    
    print("✅ .env file looks good!")
    return True

def install_dependencies():
    """Install Python dependencies if needed"""
    try:
        import fastapi, uvicorn, supabase
        print("✅ Python dependencies already installed")
    except ImportError:
        print("📦 Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

def start_server():
    """Start the development server"""
    print("🚀 Starting local development server...")
    print("📍 Backend will be available at: http://localhost:8000")
    print("📖 API docs at: http://localhost:8000/docs")
    print("🔄 Hot reload enabled - changes will restart the server automatically")
    print("\n💡 Update your frontend to use: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop\n")
    
    # Set environment for development
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['ENABLE_MONITORING'] = 'true'
    
    # Start uvicorn with hot reload
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "app.main:app", 
        "--reload", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--log-level", "info"
    ])

if __name__ == "__main__":
    print("🔧 Mobidictum Admin Management System - Local Development")
    print("=" * 50)
    
    if not check_env_file():
        sys.exit(1)
    
    install_dependencies()
    start_server()
