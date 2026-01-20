# ADR 004: Django Ninja for REST API

**Date:** January 18, 2026

## Context

We need a REST API framework for our Django backend that:
- Provides automatic OpenAPI/Swagger documentation
- Has strong typing and validation
- Offers good developer experience (DX)
- Performs well under load
- Integrates naturally with Django's ecosystem

Options considered:
1. **Django REST Framework (DRF)** - Industry standard, feature-rich, verbose
2. **Django Ninja** - FastAPI-inspired, Pydantic-based, async support
3. **FastAPI + Django ORM** - Mixing frameworks, complex setup
4. **Graphene/Strawberry (GraphQL)** - Different paradigm, overkill for our needs

## Decision

Use **Django Ninja** as the REST API framework.

## Rationale

### Best of Both Worlds

Django Ninja combines:
- **FastAPI's elegance**: Pydantic schemas, type hints, auto-docs
- **Django's maturity**: ORM, admin, migrations, middleware, auth

```python
# FastAPI-like syntax with full Django underneath
@router.post("/members", response=MemberOut)
def create_member(request, payload: MemberCreate) -> Member:
    return MemberService.create(
        organization=request.auth_organization,
        email=payload.email,
        role=payload.role,
    )
```

### Type-Safe by Design

Pydantic schemas provide:
- Runtime validation with clear error messages
- IDE autocompletion and type checking
- Automatic request/response serialization
- Self-documenting API contracts

```python
class MemberCreate(Schema):
    email: EmailStr
    role: Literal["admin", "member", "viewer"]

class MemberOut(Schema):
    id: str
    email: str
    role: str
    created_at: datetime
```

### Automatic OpenAPI Documentation

Zero-config interactive documentation:
- Swagger UI at `/api/docs`
- ReDoc at `/api/redoc`
- OpenAPI schema export for client generation

Frontend can generate TypeScript types directly from the schema.

### Performance

Django Ninja is significantly faster than DRF:
- Pydantic v2 is compiled with Rust
- No serializer overhead for simple cases
- Async view support for I/O-bound operations
- Benchmarks show 2-5x throughput improvement

### Escape from DRF Complexity

DRF issues we avoid:
- **Serializer proliferation**: Separate serializers for read/write/list/detail
- **ViewSet magic**: Implicit routing and action names
- **Nested serializer pain**: Complex validation across relationships
- **Performance gotchas**: N+1 queries from nested serializers

Django Ninja is explicit:
```python
# Clear, explicit, no magic
@router.get("/members/{member_id}", response=MemberDetailOut)
def get_member(request, member_id: str) -> Member:
    return get_object_or_404(Member, id=member_id, organization=request.auth_organization)
```

### Django Ecosystem Preserved

Full access to Django features:
- ORM with all its query capabilities
- Admin panel for internal tooling
- Migrations for schema management
- Middleware for cross-cutting concerns
- Management commands
- Django Debug Toolbar
- Existing Django packages (django-filter, django-cors-headers, etc.)

## Consequences

### Positive
- **Developer velocity** - Less boilerplate than DRF, faster iteration
- **Type safety** - Catch errors at development time, not runtime
- **Auto-documentation** - Always up-to-date API docs
- **Performance** - Lower latency, higher throughput
- **Simplicity** - Explicit routing, no ViewSet magic to debug

### Negative
- **Smaller ecosystem** - Fewer third-party packages than DRF
- **Less industry adoption** - Team members may need onboarding
- **Different patterns** - DRF experience doesn't directly transfer
- **Async limitations** - Django ORM is still sync (use sync_to_async)

### Mitigations
- Most Django packages work unchanged (filtering, permissions)
- Clear documentation and examples in codebase
- Pydantic/FastAPI knowledge transfers directly
- Service layer abstracts ORM details from API layer

## Implementation Notes

### Project Structure
```
backend/
  apps/
    members/
      api.py          # Router definition
      schemas.py      # Pydantic schemas
      services.py     # Business logic
      models.py       # Django models
```

### Router Organization
```python
# apps/members/api.py
from ninja import Router

router = Router(tags=["Members"])

@router.get("/", response=list[MemberOut])
def list_members(request):
    ...

# config/api.py
from ninja import NinjaAPI
from apps.members.api import router as members_router

api = NinjaAPI(
    title="Pikaia API",
    version="1.0.0",
)

api.add_router("/members", members_router)
```

### Authentication Pattern
```python
from ninja.security import HttpBearer

class StytchAuth(HttpBearer):
    def authenticate(self, request, token: str):
        # Validate JWT, set request.auth_user, request.auth_organization
        ...

api = NinjaAPI(auth=StytchAuth())
```

### Error Handling
```python
from ninja.errors import HttpError

@router.post("/members")
def create_member(request, payload: MemberCreate):
    if Member.objects.filter(email=payload.email).exists():
        raise HttpError(409, "Member already exists")
    ...
```
