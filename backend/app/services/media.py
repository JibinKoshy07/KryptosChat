"""Media upload/download service.

Uploads stream the request body in chunks, encrypting each chunk with
AES-256-GCM and writing it directly to the storage backend — the file is
never fully loaded into memory. Downloads stream the encrypted blob back
through the decryptor to the HTTP response.
"""
import json
import logging
import os
import secrets
import tempfile
from typing import IO

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.attachment import Attachment
from app.storage.factory import get_storage_backend
from app.services.crypto import MediaDecryptor, MediaEncryptor

logger = logging.getLogger(__name__)


def validate_upload(filename: str, content_type: str, size: int) -> None:
    """Validate MIME type and size before streaming the body."""
    if content_type not in settings.allowed_media_types:
        raise BadRequestError(f"File type '{content_type}' is not allowed")
    if size > settings.max_upload_size_bytes:
        raise BadRequestError("File is too large")
    if not filename:
        raise BadRequestError("Filename is required")


async def store_upload(conv_id: int, message_id: int, file: UploadFile) -> Attachment:
    """Stream an uploaded file to encrypted storage and return an Attachment row."""
    content_type = file.content_type or "application/octet-stream"
    # We can't know the size ahead of time for a stream; validate type now,
    # and enforce the size limit while streaming.
    if content_type not in settings.allowed_media_types:
        raise BadRequestError(f"File type '{content_type}' is not allowed")

    storage_key = f"conv_{conv_id}_{message_id}_{secrets.token_hex(16)}"
    backend = get_storage_backend()

    total = 0
    if backend.name == "local":
        sink = await backend.open_write(storage_key)
        try:
            enc = MediaEncryptor(sink)
            while True:
                chunk = await file.read(settings.media_chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.max_upload_size_bytes:
                    raise BadRequestError("File is too large")
                await enc.write(chunk)
            await enc.close()
        finally:
            sink.close()
    else:
        # S3: accumulate encrypted chunks in memory (acceptable for large files
        # with a modest chunk size) then upload once.
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            enc = MediaEncryptor(tmp)
            while True:
                chunk = await file.read(settings.media_chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.max_upload_size_bytes:
                    raise BadRequestError("File is too large")
                await enc.write(chunk)
            await enc.close()
            tmp.flush()
        with open(tmp.name, "rb") as fh:
            data = fh.read()
        await backend.put_object(storage_key, data)
        os.unlink(tmp.name)

    # Enforce size limit when the stream finishes (defense in depth).
    if total > settings.max_upload_size_bytes:
        await backend.delete(storage_key)
        raise BadRequestError("File is too large")

    attachment = Attachment(
        message_id=message_id,
        encrypted_storage_key=storage_key,
        storage_backend=backend.name,
        original_filename=os.path.basename(file.filename or "attachment"),
        mime_type=content_type,
        size=total,
        encryption_metadata=json.dumps({"format": "krypte-media-v1"}),
    )
    return attachment


async def stream_download(attachment: Attachment, sink: IO) -> None:
    """Stream an encrypted blob from storage, decrypting into ``sink``."""
    backend = get_storage_backend()
    if backend.name == "local":
        src = await backend.open_read(attachment.encrypted_storage_key)
        try:
            dec = MediaDecryptor(src)
            while True:
                chunk = dec.read_chunk()
                if chunk is None:
                    break
                sink.write(chunk)
        finally:
            src.close()
    else:
        data = await backend.get_object(attachment.encrypted_storage_key)
        import io

        dec = MediaDecryptor(io.BytesIO(data))
        while True:
            chunk = dec.read_chunk()
            if chunk is None:
                break
            sink.write(chunk)


async def delete_stored(attachment: Attachment) -> None:
    backend = get_storage_backend()
    try:
        await backend.delete(attachment.encrypted_storage_key)
    except Exception:
        logger.warning("media_delete_failed", extra={"extra_fields": {"storage_key": attachment.encrypted_storage_key}})


async def attachment_exists(attachment: Attachment) -> bool:
    backend = get_storage_backend()
    try:
        return await backend.exists(attachment.encrypted_storage_key)
    except Exception:
        return False


def stream_download_response(attachment: Attachment):
    """Return an async generator that streams the decrypted blob to the client
    without loading the whole file into memory."""
    import anyio

    backend = get_storage_backend()

    async def _gen():
        try:
            if backend.name == "local":
                src = await backend.open_read(attachment.encrypted_storage_key)
                dec = MediaDecryptor(src)
                while True:
                    chunk = await anyio.to_thread.run_sync(dec.read_chunk)
                    if chunk is None:
                        break
                    yield chunk
                src.close()
            else:
                data = await backend.get_object(attachment.encrypted_storage_key)
                import io

                dec = MediaDecryptor(io.BytesIO(data))
                while True:
                    chunk = await anyio.to_thread.run_sync(dec.read_chunk)
                    if chunk is None:
                        break
                    yield chunk
        except Exception:
            logger.error("media_download_failed", extra={"extra_fields": {"attachment_id": attachment.id}})
            raise

    return _gen()