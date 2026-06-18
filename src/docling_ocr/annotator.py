from __future__ import annotations

import logging
from typing import Any

from docling_ocr.models import AnnotationConfig

logger = logging.getLogger(__name__)


PRESET_MAP: dict[str, str] = {
    "qwen25_vl_3b_mlx": "qwen2_5_vl_3b",
    "qwen25_vl_3b": "qwen2_5_vl_3b",
    "granite_vision": "granite_vision",
    "granite_vision_2b": "granite_vision",
    "smolvlm": "smolvlm",
    "smolvlm_256m": "smolvlm",
}


def build_picture_description_options(config: AnnotationConfig) -> Any:
    """Build Docling PictureDescriptionVlmOptions from our AnnotationConfig.

    Supports:
    - Local MLX models via presets (default: qwen2_5_vl_3b)
    - Local Transformers models via repo_id
    - Remote API (OpenAI-compatible) via remote_api_url
    """
    from docling.datamodel.pipeline_options import PictureDescriptionVlmOptions

    if config.remote_api_url:
        from docling.datamodel.pipeline_options import PictureDescriptionApiOptions

        logger.info("Using remote API for picture description: %s", config.remote_api_url)
        return PictureDescriptionApiOptions(
            url=config.remote_api_url,
            params={
                "model": config.model,
                "temperature": 0.0,
            },
            prompt=config.prompt,
        )

    preset = PRESET_MAP.get(config.model)
    if preset:
        logger.info("Using picture description preset: %s (model=%s)", preset, config.model)
        try:
            options = PictureDescriptionVlmOptions.from_preset(preset)
        except Exception as e:
            logger.warning("Preset '%s' not available, falling back to repo_id: %s", preset, e)
            options = PictureDescriptionVlmOptions(
                repo_id="mlx-community/Qwen2.5-VL-3B-Instruct-bf16",
                prompt=config.prompt,
            )
        options.prompt = config.prompt
        return options

    logger.info("Using custom repo_id for picture description: %s", config.model)
    return PictureDescriptionVlmOptions(
        repo_id=config.model,
        prompt=config.prompt,
    )


def extract_annotations(document) -> dict[str, str]:
    """Extract picture annotations from a converted DoclingDocument.

    Returns a mapping of picture self_ref -> annotation text.
    """
    annotations: dict[str, str] = {}

    for picture in document.pictures:
        ref = picture.self_ref or ""
        ann_text = ""

        if picture.annotations:
            for ann in picture.annotations:
                if hasattr(ann, "text") and ann.text:
                    ann_text = ann.text
                    break
                if hasattr(ann, "data") and isinstance(ann.data, dict):
                    ann_text = str(ann.data.get("description", ann.data))
                    break

        if ann_text:
            annotations[ref] = ann_text

    logger.debug("Extracted %d picture annotations", len(annotations))
    return annotations
