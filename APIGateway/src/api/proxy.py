from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from src.api.config import get_settings


async def proxy_request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    timeout_seconds: float = 15.0,
) -> httpx.Response:
    """
    Forward a request to the backend service.

    Parameters:
    - method: HTTP method to use
    - path: path to append to backend base URL
    - headers: headers to forward to backend
    - params: query parameters
    - json_body: JSON body for POST/PUT/PATCH
    - timeout_seconds: request timeout

    Returns:
    - httpx.Response from backend

    Raises:
    - HTTPException 503 if backend is unavailable
    - HTTPException 504 if backend times out
    """
    settings = get_settings()
    url = f"{settings.backend_base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
            )
            return resp
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend unavailable",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Backend timeout",
        )


async def get_backend_json(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    timeout_seconds: float = 15.0,
) -> Any:
    """
    Helper that proxies to backend and returns JSON with error handling.

    If the backend response is not JSON, wraps it as {'message': '<text>'}.
    Propagates backend HTTP status codes.
    """
    resp = await proxy_request(
        method=method,
        path=path,
        headers=headers,
        params=params,
        json_body=json_body,
        timeout_seconds=timeout_seconds,
    )
    # Pass through status codes, but normalize error payload if not JSON
    content_type = (resp.headers.get("content-type") or "").lower()
    data: Any
    if "application/json" in content_type:
        try:
            data = resp.json()
        except ValueError:
            data = {"message": resp.text}
    else:
        data = {"message": resp.text}

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data)
    return data
