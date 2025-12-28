"""
Factories for accounts app models.

Used in tests to create test data.
"""

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Member, User
from apps.organizations.models import Organization


class UserFactory(DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Faker("name")
    is_active = True
    is_staff = False


class OrganizationFactory(DjangoModelFactory):
    """Factory for Organization model."""

    class Meta:
        model = Organization

    stytch_org_id = factory.Sequence(lambda n: f"org-test-{n}")
    name = factory.Faker("company")
    slug = factory.Sequence(lambda n: f"org-{n}")


class MemberFactory(DjangoModelFactory):
    """Factory for Member model."""

    class Meta:
        model = Member

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    stytch_member_id = factory.Sequence(lambda n: f"member-test-{n}")
    role = "member"
