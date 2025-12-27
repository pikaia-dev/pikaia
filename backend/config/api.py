"""
Django Ninja API configuration.
"""

from ninja import NinjaAPI

api = NinjaAPI(
    title="Tango API",
    version="1.0.0",
    description="B2B SaaS API built with Django Ninja",
)


@api.get("/health")
def health_check(request) -> dict:
    """Health check endpoint for load balancer."""
    return {"status": "ok"}
