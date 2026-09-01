"""Media upload/download endpoints (encrypted, streamed)."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_current_user
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.message import Message, MessageType
from app.models.user import User
from app.schemas.message import MessageCreate, MessageOut
from app.services import conversations, media as media_service, messages, users

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/{conversation_id}", response_model=MessageOut, status_code=201)
async def upload_media(
    conversation_id: int,
    file: Annotated[UploadFile, File(description="Image, video, or file to upload")],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streamed encrypted upload. Returns the created message with attachment."""
    await conversations.ensure_member(db, conversation_id, current_user.id)
    mime = file.content_type or "application/octet-stream"
    message_type = _message_type_for_mime(mime)
    # Create the message row first so we have an id for the storage key.
    message = await messages.create_message(
        db, conversation_id, current_user.id,
        MessageCreate(content="", message_type=message_type),
    )
    attachment = await media_service.store_upload(conversation_id, message.id, file)
    db.add(attachment)
    await db.flush()
    message.attachment_id = attachment.id
    await db.commit()
    await db.refresh(message)
    await db.refresh(attachment)
    return await messages.to_out(db, message, current_user.id)


def _message_type_for_mime(mime: str) -> MessageType:
    if mime.startswith("image/"):
        return MessageType.IMAGE
    if mime.startswith("video/"):
        return MessageType.VIDEO
    return MessageType.FILE


@router.get("/{attachment_id}", response_class=StreamingResponse)
async def download_media(
    attachment_id: int,
    token: str | None = Query(default=None, description="Access token for in-browser media"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Streamed encrypted download (decrypted as it streams)."""
    # The user may authenticate via the Authorization header (dependency above)
    # or via ``?token=`` for in-browser <img>/<video> tags.
    if current_user is None and token:
        payload = decode_token(token, "access")
        if payload is None:
            raise UnauthorizedError("Invalid access token")
        current_user = await users.get_user_by_id(db, int(payload["sub"]))
    if current_user is None:
        raise UnauthorizedError("Not authenticated")

    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment not found")
    message = await db.get(Message, attachment.message_id)
    if message is None:
        raise NotFoundError("Attachment not found")
    await conversations.ensure_member(db, message.conversation_id, current_user.id)
    if await media_service.attachment_exists(attachment):
        return StreamingResponse(
            media_service.stream_download_response(attachment),
            media_type=attachment.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{attachment.original_filename}"',
                "Cache-Control": "private, no-store",
            },
        )
    raise NotFoundError("Attachment not found")