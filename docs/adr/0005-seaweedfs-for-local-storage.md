# 0005: SeaweedFS as the local S3 stand-in

Accepted. Public MinIO images could not be pulled during the build. SeaweedFS exposes the same S3 API including presigned URLs.
Production uses Cloudflare R2 by changing `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT` and `MEDIA_PUBLIC_BASE`. The app code does not change.
