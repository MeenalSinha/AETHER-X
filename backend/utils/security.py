import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger("aether-x.security")

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# In production, this would be in .env or Secrets Manager
MASTER_API_KEY = os.getenv("AETHER_API_KEY", "aether_secret_2026")

async def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key:
        # For this prototype, we require an API key for ALL mutation endpoints.
        # GET endpoints are unprotected in this design for dashboard visibility.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key missing",
        )
    if api_key != MASTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate API Key",
        )
    return api_key
