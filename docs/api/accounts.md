# Accounts API Reference

Base URL: `/api/v1/auth`

## Public Endpoints

These endpoints don't require authentication.

### Send Magic Link

```
POST /magic-link/send
```

Send a magic link email for passwordless login.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "Magic link sent. Check your email."
}
```

**Errors:**
- `400` — Invalid email format
- `429` — Rate limit exceeded

---

### Authenticate Magic Link

```
POST /magic-link/authenticate
```

Validate the magic link token from the email.

**Request:**
```json
{
  "token": "magic_link_token_from_url"
}
```

**Response:**
```json
{
  "intermediate_session_token": "ist_xxx",
  "email": "user@example.com",
  "discovered_organizations": [
    {
      "organization_id": "organization-xxx",
      "organization_name": "Acme Corp",
      "organization_slug": "acme"
    }
  ]
}
```

**Errors:**
- `401` — Invalid or expired token

---

### Create Organization

```
POST /discovery/create-org
```

Create a new organization and authenticate as admin.

**Request:**
```json
{
  "intermediate_session_token": "ist_xxx",
  "organization_name": "New Corp",
  "organization_slug": "new-corp"
}
```

**Response:**
```json
{
  "session_token": "session_xxx",
  "session_jwt": "jwt_xxx",
  "member_id": "member-xxx",
  "organization_id": "organization-xxx"
}
```

**Errors:**
- `400` — Invalid token or parameters
- `409` — Slug already in use

---

### Exchange Session

```
POST /discovery/exchange
```

Exchange intermediate session token for a full session by selecting an organization.

**Request:**
```json
{
  "intermediate_session_token": "ist_xxx",
  "organization_id": "organization-xxx"
}
```

**Response:**
```json
{
  "session_token": "session_xxx",
  "session_jwt": "jwt_xxx",
  "member_id": "member-xxx",
  "organization_id": "organization-xxx"
}
```

---

## Authenticated Endpoints

These endpoints require a valid `Authorization: Bearer <session_jwt>` header.

### Get Current User

```
GET /me
```

Get the authenticated user, member, and organization info.

**Response:**
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  },
  "member": {
    "id": 1,
    "stytch_member_id": "member-xxx",
    "role": "admin",
    "is_admin": true
  },
  "organization": {
    "id": 1,
    "stytch_org_id": "organization-xxx",
    "name": "Acme Corp",
    "slug": "acme-corp"
  }
}
```

---

### Update Profile

```
PATCH /me/profile
```

Update the current user's profile.

**Request:**
```json
{
  "name": "New Name"
}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "New Name"
}
```

---

### Logout

```
POST /logout
```

Revoke the current session.

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

---

### Get Organization

```
GET /organization
```

Get the current organization with billing info.

**Response:**
```json
{
  "id": 1,
  "stytch_org_id": "organization-xxx",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "billing": {
    "billing_email": "billing@acme.com",
    "billing_name": "Acme Corporation Inc.",
    "address": {
      "line1": "123 Main St",
      "line2": "",
      "city": "San Francisco",
      "state": "CA",
      "postal_code": "94102",
      "country": "US"
    },
    "vat_id": ""
  }
}
```

---

### Update Organization (Admin)

```
PATCH /organization
```

Update the organization name.

**Requires:** Admin role

**Request:**
```json
{
  "name": "New Organization Name"
}
```

---

### Update Billing (Admin)

```
PATCH /organization/billing
```

Update billing address and VAT info.

**Requires:** Admin role

**Request:**
```json
{
  "billing_email": "invoices@acme.com",
  "billing_name": "Acme Corp Inc.",
  "address": {
    "line1": "456 Oak Ave",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "US"
  },
  "vat_id": "DE123456789"
}
```

---

### List Members

```
GET /organization/members
```

List all members of the current organization.

**Response:**
```json
{
  "members": [
    {
      "id": 1,
      "stytch_member_id": "member-xxx",
      "email": "admin@acme.com",
      "name": "Admin User",
      "role": "admin",
      "is_admin": true
    },
    {
      "id": 2,
      "stytch_member_id": "member-yyy",
      "email": "member@acme.com",
      "name": "Team Member",
      "role": "member",
      "is_admin": false
    }
  ]
}
```

---

### Invite Member (Admin)

```
POST /organization/members
```

Send an invitation email to join the organization.

**Requires:** Admin role

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "member"
}
```

---

### Update Member Role (Admin)

```
PATCH /organization/members/{member_id}
```

Change a member's role.

**Requires:** Admin role

**Request:**
```json
{
  "role": "admin"
}
```

---

### Delete Member (Admin)

```
DELETE /organization/members/{member_id}
```

Remove a member from the organization.

**Requires:** Admin role

**Response:** `204 No Content`
