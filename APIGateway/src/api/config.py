import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseModel, Field, AnyHttpUrl, ValidationError
from dotenv import load_dotenv

# Load environment variables from .env at startup (without reading the file directly outside standard practice)
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    app_name: str = Field(default="CashApp API Gateway", description="Application name.")
    app_version: str = Field(default="1.0.0", description="Application version.")
    app_description: str = Field(
        default="Central API Gateway for CashApp. Handles routing, OAuth2 authentication, rate limiting, and API composition.",
        description="App description.",
    )

    # CORS allowed origins
    cors_allow_origins: List[str] = Field(
        default_factory=lambda: ["*"], description="List of allowed CORS origins."
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials.")
    cors_allow_methods: List[str] = Field(
        default_factory=lambda: ["*"], description="Allowed HTTP methods."
    )
    cors_allow_headers: List[str] = Field(
        default_factory=lambda: ["*"], description="Allowed headers."
    )

    # Backend service base URL (APIGateway_backend)
    backend_base_url: AnyHttpUrl = Field(
        default="http://apigateway-backend:8000",
        description="Base URL for the APIGateway_backend service.",
    )

    # OAuth2 configuration (Password flow for example; token generation handled by Gateway or external IdP)
    oauth2_secret_key: str = Field(
        default="CHANGE_ME_DEV_ONLY",
        description="Secret key for signing JWT tokens issued by the gateway.",
    )
    oauth2_algorithm: str = Field(default="HS256", description="JWT signing algorithm.")
    oauth2_access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes."
    )
    oauth2_token_url: str = Field(
        default="/auth/token",
        description="Local OAuth2 token endpoint path exposed by the gateway.",
    )
    oauth2_issuer: str = Field(
        default="cashapp-gateway", description="JWT issuer (iss) claim."
    )
    oauth2_audience: str = Field(
        default="cashapp-clients", description="JWT audience (aud) claim."
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100, description="Number of requests allowed in window per client."
    )
    rate_limit_window_seconds: int = Field(
        default=60, description="Rate limiting window in seconds."
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, etc.)")

    # Site URL for redirects (e.g., with Supabase or OAuth2 redirect hints)
    site_url: Optional[str] = Field(
        default=None, description="Public site URL for redirect flows."
    )

    class Config:
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Load settings from environment variables and cache the result."""
    env_map = {
        "APP_NAME": "app_name",
        "APP_VERSION": "app_version",
        "APP_DESCRIPTION": "app_description",
        "CORS_ALLOW_ORIGINS": "cors_allow_origins",
        "BACKEND_BASE_URL": "backend_base_url",
        "OAUTH2_SECRET_KEY": "oauth2_secret_key",
        "OAUTH2_ALGORITHM": "oauth2_algorithm",
        "OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES": "oauth2_access_token_expire_minutes",
        "OAUTH2_TOKEN_URL": "oauth2_token_url",
        "OAUTH2_ISSUER": "oauth2_issuer",
        "OAUTH2_AUDIENCE": "oauth2_audience",
        "RATE_LIMIT_REQUESTS": "rate_limit_requests",
        "RATE_LIMIT_WINDOW_SECONDS": "rate_limit_window_seconds",
        "LOG_LEVEL": "log_level",
        "SITE_URL": "site_url",
    }
    data = {}
    for env_key, field_name in env_map.items():
        value = os.getenv(env_key)
        if value is not None:
            # Special handling for lists
            if field_name == "cors_allow_origins":
                data[field_name] = [v.strip() for v in value.split(",") if v.strip()]
            elif field_name in {"rate_limit_requests", "rate_limit_window_seconds", "oauth2_access_token_expire_minutes"}:
                try:
                    data[field_name] = int(value)
                except ValueError:
                    pass
            else:
                data[field_name] = value
    try:
        return Settings(**data)
    except ValidationError as e:
        # Fallback to defaults while printing validation error for visibility in logs
        print("Settings validation error:", e)
        return Settings()
