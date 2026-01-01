# Testing Guide

## Overview

The project uses **pytest** for backend testing with factory_boy for test data generation.

## Running Tests

### All Tests

```bash
cd backend
uv run pytest
```

### Specific App

```bash
uv run pytest tests/billing/
uv run pytest tests/accounts/
```

### Specific Test File

```bash
uv run pytest tests/billing/test_services.py
```

### Specific Test

```bash
uv run pytest tests/billing/test_services.py::TestGetOrCreateStripeCustomer::test_creates_new_customer
```

### With Coverage

```bash
uv run pytest --cov=apps --cov-report=html
open htmlcov/index.html  # View report
```

### Verbose Output

```bash
uv run pytest -v --tb=short
```

## Test Structure

```
backend/tests/
├── __init__.py
├── accounts/
│   ├── factories.py      # User, Member, Organization factories
│   ├── test_api.py       # API endpoint tests
│   ├── test_models.py    # Model unit tests
│   └── test_services.py  # Service function tests
├── billing/
│   ├── factories.py      # Subscription factory
│   ├── test_api.py       # Billing endpoint tests
│   ├── test_models.py    # Subscription model tests
│   └── test_services.py  # Stripe integration tests
└── core/
    └── test_middleware.py # Auth middleware tests
```

## Factories

Factories create test data using [factory_boy](https://factoryboy.readthedocs.io/).

### Usage

```python
from tests.accounts.factories import UserFactory, MemberFactory, OrganizationFactory
from tests.billing.factories import SubscriptionFactory

# Create a user
user = UserFactory(email="test@example.com", name="Test User")

# Create an org with members
org = OrganizationFactory()
member = MemberFactory(user=user, organization=org, role="admin")

# Create a subscription
subscription = SubscriptionFactory(
    organization=org,
    status=Subscription.Status.ACTIVE,
    quantity=5,
)
```

### Available Factories

| Factory | Model | Key Attributes |
|---------|-------|----------------|
| `UserFactory` | User | `email`, `name` |
| `OrganizationFactory` | Organization | `name`, `slug`, `stripe_customer_id` |
| `MemberFactory` | Member | `user`, `organization`, `role` |
| `SubscriptionFactory` | Subscription | `organization`, `status`, `quantity` |

## Mocking External Services

### Mocking Stripe

```python
from unittest.mock import MagicMock, patch

@pytest.mark.django_db
class TestCreateSubscriptionIntent:
    
    @patch("apps.billing.services.get_stripe")
    def test_creates_subscription(self, mock_get_stripe):
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        
        # Configure mock response
        mock_subscription = MagicMock()
        mock_subscription.id = "sub_test_123"
        mock_subscription.latest_invoice.confirmation_secret.client_secret = "pi_secret"
        mock_stripe.Subscription.create.return_value = mock_subscription
        
        # Test
        org = OrganizationFactory()
        client_secret, sub_id = create_subscription_intent(org, quantity=3)
        
        assert client_secret == "pi_secret"
        mock_stripe.Subscription.create.assert_called_once()
```

### Mocking Stytch

```python
from unittest.mock import patch

@patch("apps.accounts.api.get_stytch_client")
def test_send_magic_link(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Test sends email
    result = send_magic_link(request, payload)
    
    mock_client.magic_links.email.discovery.send.assert_called_once()
```

## Testing API Endpoints

### Unit Testing with RequestFactory

```python
from django.test import RequestFactory
from ninja.errors import HttpError

@pytest.mark.django_db
class TestGetSubscription:
    
    def test_returns_active_subscription(self, request_factory):
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE)
        
        request = request_factory.get("/api/v1/billing/subscription")
        request.auth_user = UserFactory()
        request.auth_member = MemberFactory(organization=sub.organization)
        request.auth_organization = sub.organization
        
        result = get_subscription(request)
        
        assert result.status == "active"
    
    def test_unauthenticated_returns_401(self, request_factory):
        request = request_factory.get("/api/v1/billing/subscription")
        
        with pytest.raises(HttpError) as exc_info:
            get_subscription(request)
        
        assert exc_info.value.status_code == 401
```

## Testing Patterns

### 1. Test Business Logic in Services

Services contain the core logic and are easy to test with mocked dependencies.

```python
def test_sync_subscription_from_stripe():
    with patch("apps.billing.services.get_stripe") as mock:
        mock.return_value.Subscription.retrieve.return_value = MagicMock(status="active")
        
        result = sync_subscription_from_stripe("sub_123")
        
        assert result is True
```

### 2. Test API for Request/Response

API tests verify request parsing, auth, and response format.

```python
def test_admin_can_create_checkout(mock_service, request_factory):
    request = _create_authenticated_request(role="admin")
    mock_service.return_value = "https://checkout.stripe.com"
    
    result = create_checkout(request, payload)
    
    assert "checkout_url" in result
```

### 3. Test Models for Invariants

Model tests verify properties, constraints, and methods.

```python
def test_is_active_when_trialing():
    sub = SubscriptionFactory(status=Subscription.Status.TRIALING)
    assert sub.is_active is True

def test_is_active_when_canceled():
    sub = SubscriptionFactory(status=Subscription.Status.CANCELED)
    assert sub.is_active is False
```

## Test Coverage Goals

| Area | Coverage Target |
|------|-----------------|
| Services | 90%+ |
| Models | 80%+ |
| API endpoints | 80%+ |

## CI/CD Integration

Tests run in CI on every push:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    cd backend
    uv sync
    uv run pytest --cov=apps --cov-fail-under=80
```
