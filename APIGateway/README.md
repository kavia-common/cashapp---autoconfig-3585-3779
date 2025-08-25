# CashApp API Gateway

FastAPI-based API Gateway that acts as the central entry point for clients. It handles:
- OAuth2 (JWT Bearer) authentication
- Basic in-memory rate limiting
- Proxy routing to APIGateway_backend
- API composition endpoints
- CORS configuration
- OpenAPI documentation

## Run locally

1) Create a `.env` using `.env.example` and set values.
2) Install dependencies:
   pip install -r requirements.txt
3) Start server:
   uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload

## Endpoints

- GET /           -> Health
- POST /auth/token -> Obtain JWT token (demo password flow)
- GET /me         -> Get current subject and claims
- ANY /proxy/*    -> Generic proxy to backend (APIGateway_backend)
- GET /compose/overview -> Example composition from multiple backend resources

OpenAPI docs at /docs and /openapi.json

## Environment variables

See `.env.example` for all supported configuration. Do not hardcode secrets in code.
