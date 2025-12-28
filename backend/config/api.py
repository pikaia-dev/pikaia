"""
Django Ninja API configuration.
"""

from django.http import HttpRequest
from ninja import NinjaAPI

from apps.accounts.api import router as auth_router

api = NinjaAPI(
    title="Tango API",
    version="1.0.0",
    description="B2B SaaS API built with Django Ninja",
)

# Register routers
api.add_router("/auth", auth_router)


@api.get("/health")
def health_check(request: HttpRequest) -> dict:
    """Health check endpoint for load balancer."""
    return {"status": "ok"}
