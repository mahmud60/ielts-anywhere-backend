import boto3
import uuid
import mimetypes
from app.core.config import settings


def get_r2_client():
    """
    Cloudflare R2 is S3-compatible — we use boto3 with a custom endpoint.
    """
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_audio(file_bytes: bytes, original_filename: str) -> str:
    """
    Uploads an audio file to R2 and returns the public URL.
    Files are stored under audio/<uuid>.<ext> to avoid name collisions.
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "mp3"
    key = f"audio/{uuid.uuid4()}.{ext}"
    content_type = mimetypes.guess_type(original_filename)[0] or "audio/mpeg"

    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"{settings.R2_PUBLIC_URL}/{key}"


def delete_audio(url: str) -> None:
    """Deletes a file from R2 given its public URL."""
    if not url or not settings.R2_PUBLIC_URL:
        return
    key = url.replace(f"{settings.R2_PUBLIC_URL}/", "")
    client = get_r2_client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except Exception:
        pass  # Best-effort deletion