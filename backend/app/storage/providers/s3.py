"""S3-compatible providers — MinIO (self-hosted) and Cloudflare R2 (cloud).

These are wired by class but **not activated by default**. To switch:

* MinIO:
    STORAGE_PROVIDER=minio
    MINIO_ENDPOINT=https://minio.example.com
    MINIO_ACCESS_KEY=...
    MINIO_SECRET_KEY=...
    MINIO_BUCKET=eco-files
    MINIO_REGION=us-east-1   (optional)

* Cloudflare R2:
    STORAGE_PROVIDER=r2
    R2_ACCOUNT_ID=...
    R2_ACCESS_KEY_ID=...
    R2_SECRET_ACCESS_KEY=...
    R2_BUCKET=eco-files

Migration is a key-by-key copy from LocalStorage; the rest of the system
uses ``storage_key`` only, never filesystem paths, so callers do not
change.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from .base import StorageProvider, StoredObject, guess_mime, safe_name, sha256_hex


class _S3LikeProvider(StorageProvider):
    name = "s3"

    def __init__(self, *, endpoint_url: Optional[str], access_key: str, secret_key: str,
                 bucket: str, region: Optional[str] = None) -> None:
        try:
            import boto3  # type: ignore
            from botocore.client import Config  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required for S3-compatible storage providers "
                "(install it or fall back to STORAGE_PROVIDER=local)"
            ) from e
        if not bucket:
            raise ValueError("bucket name is required")
        if not access_key or not secret_key:
            raise ValueError("access_key / secret_key are required")
        self.bucket = bucket
        self._client = boto3.client(  # type: ignore[attr-defined]
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "auto",
            config=Config(signature_version="s3v4"),
        )

    # ----- API ---------------------------------------------------------
    def put_bytes(self, data: bytes, *, filename: str, mime: Optional[str] = None, prefix: str = "uploads") -> StoredObject:
        if not data:
            raise ValueError("Файл порожній")
        mime = guess_mime(filename, mime)
        prefix = (prefix or "uploads").strip("/") or "uploads"
        sname = safe_name(filename)
        key = f"{prefix}/{uuid.uuid4().hex}__{sname}"
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime)
        return StoredObject(
            storage_key=key,
            size=len(data),
            sha256=sha256_hex(data),
            mime=mime,
            filename=filename,
            provider=self.name,
        )

    def get_bytes(self, storage_key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=storage_key)
            return resp["Body"].read()
        except Exception as e:  # noqa: BLE001
            raise FileNotFoundError(storage_key) from e

    def delete(self, storage_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=storage_key)
        except Exception:
            pass

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False


class MinioProvider(_S3LikeProvider):
    name = "minio"

    @classmethod
    def from_env(cls) -> "MinioProvider":
        return cls(
            endpoint_url=os.environ.get("MINIO_ENDPOINT"),
            access_key=os.environ.get("MINIO_ACCESS_KEY", ""),
            secret_key=os.environ.get("MINIO_SECRET_KEY", ""),
            bucket=os.environ.get("MINIO_BUCKET", ""),
            region=os.environ.get("MINIO_REGION"),
        )


class R2Provider(_S3LikeProvider):
    name = "r2"

    @classmethod
    def from_env(cls) -> "R2Provider":
        account = os.environ.get("R2_ACCOUNT_ID", "").strip()
        endpoint = f"https://{account}.r2.cloudflarestorage.com" if account else None
        return cls(
            endpoint_url=endpoint,
            access_key=os.environ.get("R2_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            bucket=os.environ.get("R2_BUCKET", ""),
            region="auto",
        )
