"""
API Authentication and Security
"""

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Verify API key for protected endpoints
    
    Usage: add `auth: bool = Depends(verify_api_key)` to any endpoint
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check against configured API key
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server"
        )
    
    if credentials.credentials != settings.api_key:
        logger.warning(f"Invalid API key attempt: {credentials.credentials[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True

# Optional: IP whitelist function
def verify_ip_whitelist(request) -> bool:
    """
    Verify request comes from whitelisted IP
    Only use if you have fixed IP addresses
    """
    # Example implementation
    allowed_ips = getattr(settings, 'allowed_ips', [])
    if not allowed_ips:
        return True  # No restrictions
    
    client_ip = request.client.host
    return client_ip in allowed_ips
