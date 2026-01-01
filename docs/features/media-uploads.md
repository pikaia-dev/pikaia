# Media Uploads

## Overview

Image uploads for user avatars and organization logos. Uses local filesystem in development and S3 in production.

## Upload Flow

```mermaid
sequenceDiagram
    participant Frontend
    participant Backend
    participant Storage

    Frontend->>Backend: POST /media/upload-request
    Backend-->>Frontend: upload_url + key

    alt Production (S3)
        Frontend->>Storage: PUT file to presigned URL
    else Development (Local)
        Frontend->>Backend: POST /media/direct-upload
        Backend->>Storage: Save to MEDIA_ROOT
    end

    Frontend->>Backend: POST /media/confirm
    Backend->>Backend: Update User.avatar_url / Org.logo_url
    Backend-->>Frontend: { url, width, height }
```

## Configuration

**Backend** (`config/settings/base.py`):
```python
MEDIA_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MEDIA_ALLOWED_IMAGE_TYPES = [
    "image/jpeg", "image/png", "image/webp",
    "image/svg+xml", "image/avif",
]
USE_S3_STORAGE = False  # Set True in production
```

**Frontend** (`lib/constants.ts`):
```typescript
export const MEDIA_UPLOAD = {
    MAX_SIZE_BYTES: 10 * 1024 * 1024,
    MAX_SIZE_MB: 10,
    ACCEPTED_TYPES: { ... }
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/media/upload-request` | POST | Get upload URL and storage key |
| `/api/v1/media/confirm` | POST | Confirm upload, update avatar/logo URL |
| `/api/v1/media/direct-upload` | POST | Direct upload (local dev only) |
| `/api/v1/media/{id}` | DELETE | Delete uploaded image |

## Frontend Usage

```tsx
import { ImageUploader } from '@/components/ui/image-uploader'

<ImageUploader
    type="avatar"  // or "logo"
    value={avatarUrl}
    onChange={(url) => setAvatarUrl(url)}
/>
```

The `ImageUploader` handles:
- Drag & drop with validation
- Image cropping (circular for avatars, square for logos)
- Progress indicator
- Delete with confirmation dialog

## Storage

| Environment | Storage | URL Pattern |
|-------------|---------|-------------|
| Development | `backend/media/` | `http://localhost:8000/media/avatars/{user_id}/{file}` |
| Production | S3 + CloudFront | `https://cdn.example.com/avatars/{user_id}/{file}` |

## Database Model

```python
# apps/media/models.py
class UploadedImage:
    storage_key     # S3 key or local path
    image_type      # "avatar" or "logo"
    content_type    # MIME type
    size_bytes
    user            # FK for avatars
    organization    # FK for logos
```

User avatars stored in `User.avatar_url`, org logos in `Organization.logo_url`.
