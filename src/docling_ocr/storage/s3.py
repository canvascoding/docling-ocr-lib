from __future__ import annotations

import logging

from docling_ocr.exceptions import StorageError
from docling_ocr.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        region: str = "eu-central-1",
        prefix: str = "",
    ) -> None:
        try:
            import boto3
        except ImportError as e:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install docling-ocr[s3]") from e

        self._bucket = bucket
        self._region = region
        self._prefix = prefix.rstrip("/")
        self._s3_client = boto3.client("s3", region_name=region)
        logger.info("S3StorageBackend initialized (bucket=%s, region=%s, prefix=%s)", bucket, region, prefix)

    @property
    def base_url(self) -> str:
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com"

    def upload(self, file_data: bytes, filename: str, content_type: str = "image/png") -> str:
        key = f"{self._prefix}/{filename}" if self._prefix else filename
        logger.debug("Uploading to S3: bucket=%s key=%s (%d bytes)", self._bucket, key, len(file_data))
        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=file_data,
                ContentType=content_type,
            )
        except Exception as e:
            logger.error("S3 upload failed: bucket=%s key=%s error=%s", self._bucket, key, e)
            raise StorageError(f"Failed to upload to S3 (bucket={self._bucket}, key={key}): {e}") from e

        url = f"{self.base_url}/{key}"
        logger.info("File uploaded to S3: %s", url)
        return url

    def get_base_url(self) -> str:
        return self.base_url
