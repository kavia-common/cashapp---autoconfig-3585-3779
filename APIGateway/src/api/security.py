from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import base64
import hmac
import hashlib
import json

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from src.api.config import get_settings

# Note: We implement a small JWT HS256 encoder/decoder to avoid extra dependencies beyond provided requirements.
# This is sufficient for demo purposes; in production, use python-jose or authlib with careful key management.

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(signature)


def create_jwt(payload: Dict[str, Any], secret: str, algorithm: str = "HS256") -> str:
    if algorithm != "HS256":
        raise ValueError("Unsupported algorithm")
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    message = f"{header_b64}.{payload_b64}".encode("ascii")
    signature_b64 = _sign(message, secret)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_and_verify_jwt(token: str, secret: str, audience: Optional[str] = None, issuer: Optional[str] = None) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    message = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = _sign(message, secret)
    if not hmac.compare_digest(signature_b64, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    now = int(datetime.now(tz=timezone.utc).timestamp())
    if "exp" in payload and now >= int(payload["exp"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    if audience and "aud" in payload and payload["aud"] != audience:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid audience")
    if issuer and "iss" in payload and payload["iss"] != issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid issuer")

    return payload


class TokenRequest(BaseModel):
    """Token request for password flow."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time in seconds")


def issue_access_token(sub: str, scopes: Optional[list[str]] = None) -> TokenResponse:
    """Issue a signed JWT access token."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.oauth2_access_token_expire_minutes)
    expire = datetime.now(tz=timezone.utc) + expires_delta
    payload = {
        "sub": sub,
        "scopes": scopes or [],
        "iss": settings.oauth2_issuer,
        "aud": settings.oauth2_audience,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(tz=timezone.utc).timestamp()),
    }
    token = create_jwt(payload, secret=settings.oauth2_secret_key, algorithm=settings.oauth2_algorithm)
    return TokenResponse(access_token=token, expires_in=int(expires_delta.total_seconds()))
