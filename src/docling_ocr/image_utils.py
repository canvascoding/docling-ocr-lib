from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PIL_FORMAT_MAP: dict[str, tuple[str, str]] = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "GIF": (".gif", "image/gif"),
    "WEBP": (".webp", "image/webp"),
    "BMP": (".bmp", "image/bmp"),
    "TIFF": (".tiff", "image/tiff"),
}


@dataclass
class ImageProcessingResult:
    data: bytes
    extension: str
    content_type: str


def pil_image_to_bytes(pil_image) -> ImageProcessingResult:
    """Convert a PIL Image to bytes, detecting the format.

    Docling's PictureItem.get_image() returns a PIL Image. We save it to
    a byte buffer in its original format (or PNG as fallback) and return
    the bytes together with extension and MIME type.
    """
    img_format = pil_image.format or "PNG"
    if img_format not in PIL_FORMAT_MAP:
        img_format = "PNG"

    extension, content_type = PIL_FORMAT_MAP[img_format]

    buf = io.BytesIO()
    try:
        if img_format == "JPEG" and pil_image.mode in ("RGBA", "P"):
            pil_image = pil_image.convert("RGB")
        pil_image.save(buf, format=img_format)
        data = buf.getvalue()
    except Exception as e:
        logger.warning("Failed to save PIL image as %s, falling back to PNG: %s", img_format, e)
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        data = buf.getvalue()
        extension, content_type = ".png", "image/png"

    logger.debug("PIL image converted: format=%s, %d bytes, %s", img_format, len(data), content_type)
    return ImageProcessingResult(data=data, extension=extension, content_type=content_type)


def extract_image_bytes(picture_item, document=None) -> ImageProcessingResult:
    """Extract image bytes from a Docling PictureItem.

    Uses get_image(doc) which returns a PIL Image (via ImageRef).
    The document argument is required by Docling's newer API.
    """
    try:
        if document is not None:
            pil_image = picture_item.get_image(doc=document)
        else:
            pil_image = picture_item.get_image()
    except TypeError:
        try:
            pil_image = picture_item.get_image()
        except Exception as e:
            logger.warning("Failed to get PIL image from PictureItem: %s", e)
            raise
    except Exception as e:
        logger.warning("Failed to get PIL image from PictureItem: %s", e)
        raise

    if pil_image is None:
        raise ValueError("PictureItem.get_image() returned None")

    return pil_image_to_bytes(pil_image)
