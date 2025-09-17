"""
Authentication and Session Management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
import subprocess
import logging
import os
from app.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/refresh-fienta-session")
async def refresh_fienta_session(
    auth: bool = Depends(verify_api_key)
):
    """
    Refresh Fienta authentication session by performing fresh login
    This will overwrite the existing auth/state.json with fresh session data
    """
    try:
        logger.info("🔐 Starting fresh Fienta login process...")
        
        # Check if credentials are available
        if not os.getenv('FIENTA_EMAIL') or not os.getenv('FIENTA_PASSWORD'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fienta credentials not configured on server"
            )
        
        # Run the login script
        result = subprocess.run([
            'node', 'scripts/fienta_login.js'
        ], 
        capture_output=True, 
        text=True, 
        timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("✅ Fienta login successful")
            logger.info(f"Login output: {result.stdout}")
            
            return {
                "success": True,
                "message": "Fienta session refreshed successfully",
                "details": "Fresh authentication state saved to auth/state.json",
                "output": result.stdout.split('\n')[-10:]  # Last 10 lines
            }
        else:
            logger.error(f"❌ Fienta login failed: {result.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Login failed: {result.stderr}"
            )
            
    except subprocess.TimeoutExpired:
        logger.error("⏰ Fienta login timed out")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login process timed out after 2 minutes"
        )
    except Exception as e:
        logger.error(f"💥 Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )

@router.get("/check-fienta-session")
async def check_fienta_session(
    auth: bool = Depends(verify_api_key)
):
    """
    Check if Fienta authentication state exists and get basic info
    """
    try:
        auth_file = "auth/state.json"
        
        if not os.path.exists(auth_file):
            return {
                "success": False,
                "message": "No authentication state found",
                "has_auth_file": False,
                "file_size": 0
            }
        
        # Get file stats
        stat = os.stat(auth_file)
        
        # Try to read and parse the file
        try:
            import json
            with open(auth_file, 'r') as f:
                auth_data = json.load(f)
                
            return {
                "success": True,
                "message": "Authentication state found",
                "has_auth_file": True,
                "file_size": stat.st_size,
                "last_modified": stat.st_mtime,
                "cookies_count": len(auth_data.get('cookies', [])),
                "origins_count": len(auth_data.get('origins', []))
            }
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "Authentication file is corrupted",
                "has_auth_file": True,
                "file_size": stat.st_size,
                "error": "Invalid JSON format"
            }
            
    except Exception as e:
        logger.error(f"Error checking auth session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check session: {str(e)}"
        )
