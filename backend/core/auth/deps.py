from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import logging

from settings.config import get_settings

log = logging.getLogger("auth")

settings = get_settings()
SUPABASE_URL = settings.SUPABASE_URL.rstrip("/")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

security = HTTPBearer(auto_error=False)
_jwk_client = PyJWKClient(JWKS_URL)

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    token = creds.credentials

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token).key

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],          
            audience="authenticated",     
            options={"require": ["exp", "iat"]},
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")
    except jwt.PyJWTError as e:
        log.warning("JWT validation failed: %s", str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
