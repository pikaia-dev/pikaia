# ADR 009: Trusted Auth for Passkeys and Phone OTP

**Date:** January 18, 2026

## Context

We use Stytch B2B for authentication (see ADR 001), which provides:
- Magic links
- OAuth (Google, Microsoft)
- SSO/SAML
- Organization and member management

However, Stytch B2B **does not natively support**:
- **Passkeys/WebAuthn** - Only available in Stytch Consumer product
- **Phone number OTP** - SMS verification not included in B2B

We need these capabilities for:
- **Passkeys**: Passwordless, phishing-resistant authentication for returning users
- **Phone OTP**: Identity verification, 2FA, compliance requirements

Options considered:
1. **Wait for Stytch B2B support** - Unknown timeline, blocks feature delivery
2. **Use separate auth system** - Complexity, two sources of truth
3. **Trusted Auth bridge** - Verify locally, exchange for Stytch session
4. **Custom session management** - Bypass Stytch entirely for these flows

## Decision

Use **Stytch Trusted Auth** to bridge locally-verified credentials into the Stytch session system.

```
User → Local Verification → Trusted Auth JWT → Stytch Session
         (WebAuthn/OTP)      (our signature)    (full access)
```

## Rationale

### Unified Session Management

All auth methods result in the same Stytch session:
- Magic link → Stytch session
- OAuth → Stytch session
- SSO → Stytch session
- **Passkey → Local verify → Trusted Auth → Stytch session**
- **Phone OTP → Local verify → Trusted Auth → Stytch session**

Frontend and backend only deal with Stytch sessions. No special handling for different auth methods.

### Security Model

Trusted Auth uses a cryptographic handshake:
1. We verify the credential locally (WebAuthn signature or OTP code)
2. We sign a short-lived JWT (5 minutes) with our private key
3. Stytch verifies our signature using registered public key
4. Stytch issues a full session token

```python
# We sign the JWT with RS256
trusted_auth_jwt = jwt.encode(
    {
        "sub": member.stytch_member_id,
        "aud": stytch_project_id,
        "scope": "full_access",
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "token_id": str(uuid4()),
    },
    private_key,
    algorithm="RS256",
)

# Stytch verifies and issues session
session = stytch.sessions.authenticate_jwt_local(trusted_auth_jwt)
```

The private key never leaves our backend. Stytch trusts our verification.

### Passkey Implementation

WebAuthn verification happens entirely in our backend:

```
1. Frontend: navigator.credentials.get() → signed assertion
2. Backend: Verify assertion against stored public key
3. Backend: Generate Trusted Auth JWT for verified member
4. Frontend: Exchange JWT for Stytch session
5. User: Fully authenticated with Stytch session
```

Benefits:
- Full control over WebAuthn registration and verification
- No dependency on Stytch's passkey roadmap
- Works with any WebAuthn-compatible authenticator

### Phone OTP Implementation

SMS verification uses AWS End User Messaging:

```
1. User: Requests OTP for phone number
2. Backend: Generate code, send via AWS SMS, store hash
3. User: Enters received code
4. Backend: Verify code, update user.phone_verified_at
5. Backend: Generate Trusted Auth JWT (if used for login)
6. User: Authenticated or phone verified
```

Phone OTP serves dual purposes:
- **Verification**: Prove phone ownership (doesn't create session)
- **Authentication**: Login via phone (creates session via Trusted Auth)

## Consequences

### Positive
- **Feature availability** - Passkeys and phone OTP without waiting for Stytch
- **Unified sessions** - Single session type regardless of auth method
- **Full control** - Can customize WebAuthn and OTP flows
- **Standards-based** - WebAuthn is W3C standard, portable implementation

### Negative
- **Operational burden** - We manage WebAuthn credentials and OTP codes
- **Key management** - Must secure Trusted Auth private key
- **Two verification paths** - Some auth in Stytch, some in our backend
- **Migration complexity** - If Stytch adds native support, need migration path

### Mitigations
- Trusted Auth private key in AWS Secrets Manager, rotated periodically
- Comprehensive test coverage for local verification paths
- Clear separation: Stytch owns identity, we own additional credentials
- WebAuthn credentials stored with standard format for portability

## Implementation Notes

### Credential Storage

```python
class PasskeyCredential(models.Model):
    """WebAuthn credential for passkey authentication."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveIntegerField(default=0)
    transports = models.JSONField(default=list)  # usb, nfc, ble, internal
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True)
    device_name = models.CharField(max_length=255, blank=True)
```

### Auth Flow Selection

```typescript
// Frontend: Detect available auth methods
const authMethods = await api.getAuthMethods(email);

if (authMethods.has_passkey) {
  // Offer passkey-first for returning users
  await authenticateWithPasskey();
} else if (authMethods.has_sso) {
  // Redirect to SSO
  await stytch.sso.start({ connection_id });
} else {
  // Fall back to magic link
  await stytch.magicLinks.email.send({ email });
}
```

### Trusted Auth Key Setup

```bash
# Generate RSA key pair
openssl genrsa -out trusted_auth_private.pem 2048
openssl rsa -in trusted_auth_private.pem -pubout -out trusted_auth_public.pem

# Register public key with Stytch (one-time setup)
# Store private key in AWS Secrets Manager
```

### Rate Limiting

Both passkey and OTP flows have rate limiting:

| Flow | Limit | Scope |
|------|-------|-------|
| OTP send | 3/hour | Per phone number |
| OTP verify | 5 attempts | Per OTP |
| Passkey auth | 10/min | Per user |
| Trusted Auth exchange | 5/min | Per member |

### Coexistence Matrix

| Auth Method | Handled By | Session Via |
|-------------|------------|-------------|
| Magic link | Stytch | Stytch direct |
| OAuth | Stytch | Stytch direct |
| SSO/SAML | Stytch | Stytch direct |
| Passkey | Our backend | Trusted Auth → Stytch |
| Phone OTP (login) | Our backend | Trusted Auth → Stytch |
| Phone OTP (verify) | Our backend | No session (verification only) |
