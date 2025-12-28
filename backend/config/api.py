"""
Django Ninja API configuration.
"""

from django.http import HttpRequest
from ninja import NinjaAPI

from apps.accounts.api import router as auth_router

api = NinjaAPI(
    title="B2B SaaS Starter API",
    version="1.0.0",
    description="B2B SaaS API with Stytch authentication and Stripe billing.",
    openapi_extra={
        "info": {
            "contact": {"name": "API Support"},
        },
        "tags": [
            {
                "name": "auth",
                "description": "Magic link authentication and session management",
            },
            {
                "name": "health",
                "description": "Service health and readiness checks",
            },
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Stytch session JWT obtained from /auth/discovery/exchange or /auth/discovery/create-org. Include as: Authorization: Bearer <session_jwt>",
                }
            }
        },
    },
)

# Register routers
api.add_router("/auth", auth_router)


@api.get("/health", tags=["health"], operation_id="healthCheck", summary="Health check")
def health_check(request: HttpRequest) -> dict:
    """Health check endpoint for load balancer."""
    return {"status": "ok"}
