from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, Request, Header, Body, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.responses import JSONResponse

from src.api.config import get_settings
from src.api.security import TokenRequest, TokenResponse, issue_access_token, decode_and_verify_jwt
from src.api.rate_limiter import enforce_rate_limit
from src.api.proxy import get_backend_json

settings = get_settings()

# Configure OAuth2 scheme for FastAPI docs (tokenUrl exposed by this gateway)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=settings.oauth2_token_url)

openapi_tags = [
    {"name": "health", "description": "Health and diagnostics"},
    {"name": "auth", "description": "OAuth2 token issuance and user verification"},
    {"name": "proxy", "description": "Pass-through routes to backend"},
    {"name": "compose", "description": "API composition endpoints"},
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    openapi_tags=openapi_tags,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health check", description="Returns gateway health status.")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"message": "Healthy", "service": settings.app_name}


async def get_current_subject(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """
    Resolve the subject (user id) from bearer token if provided; return None for anonymous.

    This dependency also enforces rate limiting per client and subject.
    """
    subject: Optional[str] = None
    if token:
        payload = decode_and_verify_jwt(
            token=token,
            secret=settings.oauth2_secret_key,
            audience=settings.oauth2_audience,
            issuer=settings.oauth2_issuer,
        )
        subject = payload.get("sub")
    await enforce_rate_limit(request, subject)
    return subject


# PUBLIC_INTERFACE
@app.post(
    settings.oauth2_token_url,
    tags=["auth"],
    summary="Obtain OAuth2 access token",
    description="Issues a JWT bearer token for a valid credential pair. In production, replace with IdP integration.",
    response_model=TokenResponse,
)
async def token_endpoint(credentials: TokenRequest = Body(..., embed=False)) -> TokenResponse:
    """
    OAuth2 Token endpoint (Password flow for demo).

    Parameters:
    - username: user login
    - password: user password

    Returns:
    - access_token: JWT token signed by the gateway
    - token_type: 'bearer'
    - expires_in: seconds until expiry
    """
    # Demo-only authentication check. Replace with real identity provider lookup.
    if not credentials.username or not credentials.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    # Any username/password pair is accepted in this demo, in real application validate securely.
    return issue_access_token(sub=credentials.username)


# PUBLIC_INTERFACE
@app.get(
    "/me",
    tags=["auth"],
    summary="Get current user info",
    description="Returns subject and scopes extracted from the bearer token.",
)
async def me(subject: Optional[str] = Depends(get_current_subject), token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Returns the current authenticated subject and token claims extracted from the access token.
    """
    payload = decode_and_verify_jwt(
        token=token,
        secret=settings.oauth2_secret_key,
        audience=settings.oauth2_audience,
        issuer=settings.oauth2_issuer,
    )
    return {"subject": subject, "claims": payload}


# PUBLIC_INTERFACE
@app.api_route(
    "/proxy/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["proxy"],
    summary="Generic proxy to backend",
    description="Proxies any request under /proxy/* to the APIGateway_backend service.",
)
async def generic_proxy(
    request: Request,
    full_path: str,
    subject: Optional[str] = Depends(get_current_subject),
    authorization: Optional[str] = Header(default=None),
):
    """
    Proxy endpoint that forwards the request to the APIGateway_backend.

    Parameters:
    - full_path: The backend path after the base URL
    - Authorization header is forwarded (if present)
    """
    method = request.method
    # Extract JSON body if applicable
    body = None
    if method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = None

    # Forward headers and include X-Subject for backend context
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    if subject:
        headers["X-Subject"] = subject

    params = dict(request.query_params)
    data = await get_backend_json(method, full_path, headers=headers, params=params, json_body=body)
    return JSONResponse(content=data)


# PUBLIC_INTERFACE
@app.get(
    "/compose/overview",
    tags=["compose"],
    summary="Composed overview",
    description="Demonstrates API composition by aggregating data from multiple backend endpoints.",
)
async def composed_overview(subject: Optional[str] = Depends(get_current_subject)) -> Dict[str, Any]:
    """
    Fetches account and recent transactions from backend and composes a single response.

    Backend assumptions (APIGateway_backend):
    - GET /accounts/me -> {'id': 'u123', 'balance': 100.0, ...}
    - GET /transactions/recent?limit=5 -> [{'id': 't1', 'amount': 10.0, ...}, ...]
    """
    headers = {}
    if subject:
        headers["X-Subject"] = subject

    account = await get_backend_json("GET", "/accounts/me", headers=headers)
    txns = await get_backend_json("GET", "/transactions/recent", headers=headers, params={"limit": 5})

    return {
        "account": account,
        "recent_transactions": txns,
        "subject": subject,
    }
