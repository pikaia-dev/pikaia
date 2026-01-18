# ADR 006: S3 Direct Upload with Presigned URLs

**Date:** January 18, 2026

## Context

We need a file upload solution for:
- User avatars and profile images
- Organization logos
- Document attachments (future)

Requirements:
- Handle files up to 50MB without backend timeout
- Scale without increasing backend compute
- Secure (no public write access to S3)
- Transform images on-the-fly (resize, crop, format)

Options considered:
1. **Backend file processing** - Upload to backend, process, store in S3
2. **Presigned URLs with direct upload** - Backend authorizes, frontend uploads directly to S3
3. **Third-party service** - Cloudinary, Uploadcare, etc.

## Decision

Use **S3 presigned URLs** for direct uploads with CloudFront + Lambda@Edge for image transformation.

## Rationale

### Backend Stays Thin

Backend only generates the presigned URL (~1ms), frontend handles the heavy lifting:
```python
# Backend: Generate presigned URL
@router.post("/upload-url", response=UploadUrlOut)
def generate_upload_url(request, payload: UploadRequest):
    key = f"uploads/{request.auth_organization.id}/{uuid4()}/{payload.filename}"
    presigned = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": payload.content_type},
        ExpiresIn=300,  # 5 minutes
    )
    return {"upload_url": presigned, "key": key}
```

```typescript
// Frontend: Upload directly to S3
const { upload_url, key } = await api.generateUploadUrl({ filename, content_type });
await fetch(upload_url, { method: "PUT", body: file, headers: { "Content-Type": content_type } });
// Save key to backend
await api.updateAvatar({ key });
```

### Cost Efficient

Direct upload avoids:
- Backend bandwidth costs (file never touches ECS)
- Backend compute for large file handling
- Memory pressure from buffering uploads
- Timeout issues on slow uploads

### Security Preserved

Presigned URLs provide controlled access:
- **Time-limited**: URLs expire in 5 minutes
- **Scoped**: Only for specific key and content type
- **Authenticated**: Backend validates user before generating URL
- **No public access**: Bucket blocks public writes

### Image Transformation via Lambda@Edge

CloudFront + Lambda@Edge enables on-the-fly transformation:
```
https://cdn.tango.app/uploads/org_123/avatar.jpg?w=100&h=100&fit=cover
```

Benefits:
- No pre-generation of multiple sizes
- Cache transformed images at edge
- Thumbor-compatible URL parameters
- Lazy transformation (only what's requested)

## Consequences

### Positive
- **Scalability** - Handle thousands of concurrent uploads without backend scaling
- **Performance** - No backend bottleneck, direct to S3 edge locations
- **Cost savings** - No compute/bandwidth costs for file handling
- **Flexibility** - Images transformed on-demand, cached at edge

### Negative
- **Client complexity** - Frontend handles upload logic
- **CORS configuration** - Must configure S3/CloudFront for cross-origin
- **Limited validation** - Can't validate file content server-side before upload
- **Two-step process** - Generate URL, then upload (vs. single POST)

### Mitigations
- Reusable upload hook in frontend abstracts complexity
- CDK configures CORS automatically
- Validate content-type in presigned URL; verify magic bytes post-upload if critical
- UX handles two-step as single user action

## Implementation Notes

### CDK Infrastructure
```python
# Media bucket with CORS
bucket = s3.Bucket(
    self, "MediaBucket",
    cors=[s3.CorsRule(
        allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
        allowed_origins=cors_origins,
        allowed_headers=["*"],
        max_age=3000,
    )],
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
)

# CloudFront with Lambda@Edge for transformation
distribution = cloudfront.Distribution(
    self, "MediaCDN",
    default_behavior=cloudfront.BehaviorOptions(
        origin=origins.S3Origin(bucket),
        edge_lambdas=[cloudfront.EdgeLambda(
            function_version=transform_fn.current_version,
            event_type=cloudfront.LambdaEdgeEventType.ORIGIN_REQUEST,
        )],
    ),
)
```

### Upload Flow
```
1. Frontend: Request upload URL from backend
2. Backend: Validate auth, generate presigned PUT URL, return URL + key
3. Frontend: PUT file directly to S3 via presigned URL
4. Frontend: Notify backend of completed upload (save key to model)
5. User: Access via CloudFront URL with optional transforms
```

### Transformation Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `w` | Width | `?w=200` |
| `h` | Height | `?h=200` |
| `fit` | Fit mode | `?fit=cover` |
| `q` | Quality | `?q=80` |
| `f` | Format | `?f=webp` |

### Security Checklist
- [ ] Presigned URLs expire in 5 minutes or less
- [ ] Content-Type specified in presigned URL params
- [ ] Bucket blocks all public access
- [ ] CORS origins explicitly configured (not `*` in production)
- [ ] CloudFront signed URLs for private content (if needed)
