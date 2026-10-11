"""Файлы — в MinIO; ключи с UUID (ASCII) — в PostgreSQL."""
import logging
import json
from urllib.parse import quote
from functools import lru_cache
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error
from starlette.concurrency import run_in_threadpool
from urllib3 import PoolManager
from urllib3.exceptions import HTTPError
from core.config import settings

logger = logging.getLogger(__name__)

class MediaStorage:
    def __init__(self):
        self.client = Minio(settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY,
                            secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE,
                            region="us-east-1", http_client=PoolManager(timeout=10, retries=1))

    def ensure_public_bucket(self):
        if not self.client.bucket_exists(settings.MINIO_BUCKET):
            try:
                self.client.make_bucket(settings.MINIO_BUCKET)
            except S3Error as exc:
                if exc.code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    raise
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"],
            }],
        }
        self.client.set_bucket_policy(settings.MINIO_BUCKET, json.dumps(policy))

    def _put(self, upload, key, size):
        self.ensure_public_bucket()
        self.client.put_object(settings.MINIO_BUCKET, key, upload.file, size,
                               content_type=upload.content_type)

    async def save(self, upload: UploadFile, kind: str) -> str:
        extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"} if kind == "image" else {
            "video/mp4": ".mp4", "video/webm": ".webm"}
        extension = extensions.get(upload.content_type)
        if extension is None:
            raise HTTPException(404)
        limit = settings.MAX_IMAGE_BYTES if kind == "image" else settings.MAX_VIDEO_BYTES
        size = upload.size
        if size is None or size <= 0 or size > limit:
            raise HTTPException(404)
        head = await upload.read(16)
        await upload.seek(0)
        signatures = {
            "image/jpeg": head.startswith(bytes.fromhex("ffd8ff")),
            "image/png": head.startswith(bytes.fromhex("89504e470d0a1a0a")),
            "image/webp": head.startswith(b"RIFF") and head[8:12] == b"WEBP",
            "video/mp4": head[4:8] == b"ftyp",
            "video/webm": head.startswith(bytes.fromhex("1a45dfa3")),
        }
        if not signatures[upload.content_type]:
            raise HTTPException(404)
        key = f"{kind}/{uuid4().hex}{extension}"
        try:
            await run_in_threadpool(self._put, upload, key, size)
        except (S3Error, HTTPError, OSError) as exc:
            raise HTTPException(404) from exc
        return key

    async def remove(self, key):
        try:
            await run_in_threadpool(self.client.remove_object, settings.MINIO_BUCKET, key)
        except (S3Error, HTTPError, OSError):
            logger.exception("Не удалось очистить объект %s после ошибки создания", key)

    def url(self, key):
        if not key:
            return None
        scheme = "https" if settings.MINIO_SECURE else "http"
        return f"{scheme}://{settings.MINIO_ENDPOINT}/{quote(settings.MINIO_BUCKET, safe='')}/{quote(key, safe='/')}"

@lru_cache(maxsize=1)
def get_storage():
    return MediaStorage()
