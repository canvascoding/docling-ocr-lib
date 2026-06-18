from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from docling_ocr.models import AnnotationConfig

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert assistant describing images from university lecture slides. "
    "Describe each image accurately in 2-4 sentences. Focus on the main message, "
    "any diagrams, charts, formulas, tables, graphs, or key text visible. "
    "Be concise but informative."
)

DEFAULT_USER_PROMPT = "Describe this image from a university lecture slide."


def _resolve_repo_id(model_name: str) -> str:
    if model_name == "qwen25_vl_3b_mlx":
        return "mlx-community/Qwen2.5-VL-3B-Instruct-bf16"
    if model_name == "qwen25_vl_7b_mlx":
        return "mlx-community/Qwen2.5-VL-7B-Instruct-bf16"
    if model_name == "pixtral_12b_mlx":
        return "mlx-community/pixtral-12b-bf16"
    if model_name.startswith("mlx-community/") or "/" in model_name:
        return model_name
    return model_name


def describe_image_with_mlx_vlm(
    image: Image.Image,
    config: AnnotationConfig,
    artifacts_path: str | None = None,
) -> str:
    """Describe an image using a local MLX-VLM model via mlx_vlm."""
    try:
        from mlx_vlm import generate, load
    except ImportError as e:
        raise ImportError("mlx-vlm is required for local image annotation") from e

    repo_id = _resolve_repo_id(config.model)
    system_prompt = config.prompt or DEFAULT_SYSTEM_PROMPT
    user_prompt = DEFAULT_USER_PROMPT

    logger.info("Loading MLX-VLM annotation model: %s", repo_id)
    model, processor = load(repo_id)

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    buf.seek(0)

    logger.debug("Generating annotation for image")
    output = generate(
        model,
        processor,
        image=buf,
        prompt=user_prompt,
        system=system_prompt,
        verbose=False,
    )

    text = output.strip() if isinstance(output, str) else str(output).strip()
    logger.debug("Generated annotation: %s", text[:200])
    return text


def generate_vlm_annotations(
    pictures: list,
    document: object,
    config: AnnotationConfig,
    artifacts_path: str | None = None,
) -> dict[str, str]:
    """Generate annotations for Docling picture objects using a local MLX-VLM.

    Args:
        pictures: List of Docling picture objects.
        document: The DoclingDocument containing the pictures.
        config: AnnotationConfig with model and prompt.
        artifacts_path: Optional local model artifacts path.

    Returns:
        Mapping of picture self_ref -> annotation text.
    """
    annotations: dict[str, str] = {}
    if not pictures:
        return annotations

    for i, picture in enumerate(pictures):
        ref = getattr(picture, "self_ref", "") or f"pic_{i}"
        try:
            if hasattr(picture, "get_image"):
                image = picture.get_image(document)
            elif hasattr(picture, "image"):
                image = picture.image
            else:
                image = None

            if image is None:
                logger.warning("No image data for picture %s, skipping annotation", ref)
                continue

            logger.info("Annotating picture %s with model %s", ref, config.model)
            text = describe_image_with_mlx_vlm(image, config, artifacts_path)
            if text:
                annotations[ref] = text
        except Exception as e:
            logger.warning("Failed to annotate picture %s: %s", ref, e)

    logger.info("Generated %d VLM annotations", len(annotations))
    return annotations
