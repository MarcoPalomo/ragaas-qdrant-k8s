"""MinIO storage service for document files."""

import io
import logging
import os
from typing import Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOStorage:
    """Service for storing and retrieving documents from MinIO."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: bool = False,
    ):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minio")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minio123")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "documents")
        self.secure = secure

        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        """Get or create MinIO client."""
        if self._client is None:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    async def ensure_bucket(self) -> None:
        """Ensure the bucket exists."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket: {e}")
            raise

    async def upload(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload content to MinIO.

        Args:
            content: File content
            path: Storage path (object name)
            content_type: MIME type

        Returns:
            Storage path
        """
        await self.ensure_bucket()

        try:
            self.client.put_object(
                self.bucket,
                path,
                io.BytesIO(content),
                length=len(content),
                content_type=content_type,
            )
            logger.info(f"Uploaded: {path}")
            return path
        except S3Error as e:
            logger.error(f"Upload error: {e}")
            raise

    async def download(self, path: str) -> Optional[bytes]:
        """
        Download content from MinIO.

        Args:
            path: Storage path (object name)

        Returns:
            File content or None if not found
        """
        try:
            response = self.client.get_object(self.bucket, path)
            content = response.read()
            response.close()
            response.release_conn()
            return content
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"Object not found: {path}")
                return None
            logger.error(f"Download error: {e}")
            raise

    async def delete(self, path: str) -> bool:
        """
        Delete object from MinIO.

        Args:
            path: Storage path

        Returns:
            True if deleted
        """
        try:
            self.client.remove_object(self.bucket, path)
            logger.info(f"Deleted: {path}")
            return True
        except S3Error as e:
            logger.error(f"Delete error: {e}")
            return False

    async def list_objects(self, prefix: str = "") -> list[str]:
        """
        List objects in bucket.

        Args:
            prefix: Path prefix filter

        Returns:
            List of object paths
        """
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=True,
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"List error: {e}")
            return []

    async def get_presigned_url(
        self,
        path: str,
        expires_seconds: int = 3600,
    ) -> str:
        """
        Get a presigned URL for downloading.

        Args:
            path: Storage path
            expires_seconds: URL validity in seconds

        Returns:
            Presigned URL
        """
        from datetime import timedelta

        try:
            url = self.client.presigned_get_object(
                self.bucket,
                path,
                expires=timedelta(seconds=expires_seconds),
            )
            return url
        except S3Error as e:
            logger.error(f"Presigned URL error: {e}")
            raise
