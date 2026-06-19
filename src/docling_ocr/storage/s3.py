from __future__ import annotations

import logging

from docling_ocr.exceptions import StorageError
from docling_ocr.storage.base import StorageBackend
from docling_ocr.storage.paths import quote_storage_key, sanitize_filename

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        region: str = "eu-central-1",
        prefix: str = "",
        endpoint_url: str | None = None,
        public_base_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        try:
            import boto3
        except ImportError as e:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install docling-ocr[s3]") from e

        self._bucket = bucket
        self._region = region
        self._prefix = prefix.rstrip("/")
        self._endpoint_url = endpoint_url
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None

        client_kwargs: dict = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key

        self._s3_client = boto3.client("s3", **client_kwargs)
        logger.info(
            "S3StorageBackend initialized (bucket=%s, region=%s, prefix=%s, endpoint=%s, public_base_url=%s)",
            bucket,
            region,
            prefix,
            endpoint_url,
            self._public_base_url,
        )

    @property
    def base_url(self) -> str:
        if self._public_base_url:
            return self._public_base_url
        if self._endpoint_url:
            return self._endpoint_url.rstrip("/")
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com"

    def upload(self, file_data: bytes, filename: str, content_type: str = "image/png") -> str:
        safe_filename = sanitize_filename(filename)
        key = f"{self._prefix}/{safe_filename}" if self._prefix else safe_filename
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

        url = f"{self.base_url}/{quote_storage_key(key)}"
        logger.info("File uploaded to S3: %s", url)
        return url

    def get_base_url(self) -> str:
        return self.base_url
