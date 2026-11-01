"""Creates the local buckets. In production the R2 buckets come from Terraform."""
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.storage import internal

for bucket in (settings.s3_raw_bucket, settings.s3_public_bucket):
    try:
        internal().create_bucket(Bucket=bucket)
        print("created", bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
