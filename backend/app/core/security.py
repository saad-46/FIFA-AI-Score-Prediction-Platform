from typing import Optional
from urllib.parse import urlparse
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

# Supabase projects on the newer signing-key system issue asymmetric
# (ES256/RS256) JWTs verified via the project's public JWKS, rather than a
# static HS256 shared secret. Key fetches are cached in-process.
_parsed_supabase_url = urlparse(settings.SUPABASE_URL)
_JWKS_URL = f"{_parsed_supabase_url.scheme}://{_parsed_supabase_url.netloc}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)


def decode_supabase_jwt(token: str) -> dict:
    """
    Decode and verify a Supabase-issued JWT.

    Dispatches on the token's own `alg` header: ES256/RS256 tokens are
    verified against the project's public JWKS, HS256 tokens (older
    Supabase projects on the shared-secret system) fall back to the static
    SUPABASE_JWT_SECRET.
    """
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Dependency: require authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_supabase_jwt(credentials.credentials)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Dependency: optionally authenticate user (public endpoints)."""
    if not credentials:
        return None
    try:
        return decode_supabase_jwt(credentials.credentials)
    except HTTPException:
        return None


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin role."""
    role = user.get("user_metadata", {}).get("role", "user")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
