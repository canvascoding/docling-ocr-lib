from __future__ import annotations

import logging
import re

from docling_ocr.models import ProcessedImage

logger = logging.getLogger(__name__)


def _format_image_annotation(annotation: str) -> str:
    cleaned = re.sub(r"\s+", " ", annotation).strip()
    if not cleaned:
        return ""
    return f"> **Bildbeschreibung:** {cleaned}"


def replace_image_references(
    markdown: str,
    images: list[ProcessedImage],
) -> str:
    if not images:
        return markdown

    logger.debug("Replacing %d image references in markdown", len(images))

    for image in images:
        local_patterns = [
            re.compile(rf"!\[{re.escape(image.original_id)}\]\({re.escape(image.original_id)}\)"),
            re.compile(rf"!\[{re.escape(image.original_id)}\]\(\)"),
            re.compile(rf"!\[image\]\({re.escape(image.original_id)}\)"),
            re.compile(rf"!\[\]\({re.escape(image.original_id)}\)"),
            re.compile(r"<!--\s*image\s*-->"),
        ]

        hosted_replacement = f"![{image.original_id}]({image.hosted_url})"
        if image.image_annotation:
            hosted_replacement += f"\n\n{_format_image_annotation(image.image_annotation)}"

        for pattern in local_patterns:
            new_markdown = pattern.sub(lambda _match: hosted_replacement, markdown, count=1)
            if new_markdown != markdown:
                logger.debug("Replaced image reference for '%s' -> %s", image.original_id, image.hosted_url)
            markdown = new_markdown

    return markdown
