"""S3 compatible object storage: Cloudflare R2 in production, SeaweedFS locally."""
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import settings


def _client(endpoint: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache
def internal() -> Any:
    return _client(settings.s3_endpoint)


def presign_put(key: str, content_type: str, size: int, origin: str) -> str:
    """Content type and exact length are signed, so the browser cannot upload anything else."""
    endpoint = settings.s3_public_endpoint or origin or settings.s3_endpoint
    url: str = _client(endpoint).generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_raw_bucket, "Key": key, "ContentType": content_type, "ContentLength": size},
        ExpiresIn=900,
    )
    return url


def public_url(key: str | None) -> str | None:
    return f"{settings.media_public_base}/{key}" if key else None
