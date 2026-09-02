from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MediaMetadata:
    media_type: str
    file_id: str | None = None
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


def photo_metadata(message: Any) -> MediaMetadata:
    photo = message.photo[-1]

    return MediaMetadata(
        media_type="photo",
        file_id=photo.file_id,
        file_unique_id=photo.file_unique_id,
        file_size=getattr(photo, "file_size", None),
        width=photo.width,
        height=photo.height,
    )


def document_metadata(message: Any) -> MediaMetadata:
    document = message.document

    return MediaMetadata(
        media_type="document",
        file_id=document.file_id,
        file_unique_id=document.file_unique_id,
        file_name=document.file_name,
        mime_type=document.mime_type,
        file_size=document.file_size,
    )


def sticker_metadata(message: Any) -> MediaMetadata:
    sticker = message.sticker

    return MediaMetadata(
        media_type="sticker",
        file_id=sticker.file_id,
        file_unique_id=sticker.file_unique_id,
        width=sticker.width,
        height=sticker.height,
    )


def animation_metadata(message: Any) -> MediaMetadata:
    animation = message.animation

    return MediaMetadata(
        media_type="animation",
        file_id=animation.file_id,
        file_unique_id=animation.file_unique_id,
        file_name=animation.file_name,
        mime_type=animation.mime_type,
        file_size=animation.file_size,
        width=animation.width,
        height=animation.height,
        duration=animation.duration,
    )


def metadata_to_dict(metadata: MediaMetadata) -> dict[str, Any]:
    return {
        "media_type": metadata.media_type,
        "file_id": metadata.file_id,
        "file_unique_id": metadata.file_unique_id,
        "file_name": metadata.file_name,
        "mime_type": metadata.mime_type,
        "file_size": metadata.file_size,
        "width": metadata.width,
        "height": metadata.height,
        "duration": metadata.duration,
  }
