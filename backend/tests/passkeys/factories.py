"""
Factory for Passkey model.
"""

import factory
from factory.django import DjangoModelFactory

from apps.passkeys.models import Passkey
from tests.accounts.factories import UserFactory


class PasskeyFactory(DjangoModelFactory[Passkey]):
    """Factory for creating Passkey instances."""

    class Meta:
        model = Passkey

    user = factory.SubFactory(UserFactory)
    credential_id = factory.Sequence(lambda n: f"credential_{n}".encode())
    public_key = factory.Sequence(lambda n: f"public_key_{n}".encode())
    sign_count = 0
    name = factory.Sequence(lambda n: f"Test Passkey {n}")
    aaguid = ""
    is_discoverable = True
    backup_eligible = False
    backup_state = False
    transports = factory.LazyFunction(list)
