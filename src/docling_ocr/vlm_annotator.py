from __future__ import annotations

import io
import logging
import re
import tempfile
from typing import TYPE_CHECKING

from docling_ocr.models import AnnotationConfig

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert assistant describing images from university lecture slides. "
    "Describe each image accurately in one concise sentence. Focus only on the "
    "main chart, diagram, table, formula, graph, or visible key message. Do not speculate."
)

DEFAULT_USER_PROMPT = "Describe this image from a university lecture slide."
DEFAULT_MAX_TOKENS = 80
_MODEL_CACHE: dict[str, tuple[object, object]] = {}
_WHITESPACE_RE = re.compile(r"\s+")


def _resolve_repo_id(model_name: str, artifacts_path: str | None = None) -> str:
    """Resolve model identifier to a path/loadable identifier.

    For mlx-vlm, passing a local directory path works offline.
    If the model cache has the model under a docling-style directory
    (namespace--repo), use that directly.
    """
    repo_id = None
    if model_name == "qwen25_vl_3b_mlx":
        repo_id = "mlx-community/Qwen2.5-VL-3B-Instruct-bf16"
    elif model_name == "qwen25_vl_7b_mlx":
        repo_id = "mlx-community/Qwen2.5-VL-7B-Instruct-bf16"
    elif model_name == "pixtral_12b_mlx":
        repo_id = "mlx-community/pixtral-12b-bf16"
    elif model_name.startswith("mlx-community/") or "/" in model_name:
        repo_id = model_name
    else:
        repo_id = model_name

    if artifacts_path:
        from pathlib import Path

        sanitized = repo_id.replace("/", "--")
        local_dir = Path(artifacts_path) / sanitized
        if local_dir.exists():
            logger.info("Using local model directory: %s", local_dir)
            return str(local_dir)

    return repo_id


def _load_mlx_model(repo_id: str):
    try:
        from mlx_vlm import load
    except ImportError as e:
        raise ImportError("mlx-vlm is required for local image annotation") from e

    if repo_id not in _MODEL_CACHE:
        logger.info("Loading MLX-VLM annotation model: %s", repo_id)
        _MODEL_CACHE[repo_id] = load(repo_id)
    return _MODEL_CACHE[repo_id]


def _trim_annotation(text: str, max_chars: int) -> str:
    normalized = _WHITESPACE_RE.sub(" ", text).strip()
    if max_chars <= 0 or len(normalized) <= max_chars:
        return normalized

    sentence_cut = max(
        normalized.rfind(".", 0, max_chars), normalized.rfind("!", 0, max_chars), normalized.rfind("?", 0, max_chars)
    )
    if sentence_cut >= max_chars // 2:
        return normalized[: sentence_cut + 1].strip()

    word_cut = normalized.rfind(" ", 0, max_chars - 3)
    if word_cut <= 0:
        word_cut = max_chars - 3
    return normalized[:word_cut].rstrip(" ,;:") + "..."


def _get_page_dimensions(document: object, page_no: int) -> tuple[float, float] | None:
    pages = getattr(document, "pages", None)
    page = None
    if isinstance(pages, dict):
        page = pages.get(page_no) or pages.get(page_no - 1)
    elif isinstance(pages, list | tuple):
        index = page_no - 1 if page_no > 0 else page_no
        if isinstance(index, int) and 0 <= index < len(pages):
            page = pages[index]

    size = getattr(page, "size", None)
    width = getattr(size, "width", None)
    height = getattr(size, "height", None)
    try:
        width_f = float(width)
        height_f = float(height)
    except (TypeError, ValueError):
        return None
    if width_f <= 0 or height_f <= 0:
        return None
    return width_f, height_f


def _picture_area_ratio(picture: object, document: object) -> float | None:
    for prov in getattr(picture, "prov", None) or []:
        bbox = getattr(prov, "bbox", None)
        page_no = getattr(prov, "page_no", None)
        if bbox is None or not isinstance(page_no, int):
            continue

        dims = _get_page_dimensions(document, page_no)
        if dims is None:
            continue

        try:
            left = float(getattr(bbox, "l"))
            right = float(getattr(bbox, "r"))
            top = float(getattr(bbox, "t"))
            bottom = float(getattr(bbox, "b"))
        except (AttributeError, TypeError, ValueError):
            continue

        area = abs(right - left) * abs(bottom - top)
        page_area = dims[0] * dims[1]
        if page_area > 0:
            return area / page_area
    return None


def _should_annotate_picture(picture: object, document: object, config: AnnotationConfig) -> bool:
    if not config.skip_small_images:
        return True

    ratio = _picture_area_ratio(picture, document)
    if ratio is None:
        return True
    return ratio >= config.min_area_ratio


def describe_image_with_mlx_vlm(
    image: Image.Image,
    config: AnnotationConfig,
    artifacts_path: str | None = None,
) -> str:
    """Describe an image using a local MLX-VLM model via mlx_vlm."""
    try:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
    except ImportError as e:
        raise ImportError("mlx-vlm is required for local image annotation") from e

    repo_id = _resolve_repo_id(config.model, artifacts_path)
    system_prompt = config.prompt or DEFAULT_SYSTEM_PROMPT
    user_prompt = DEFAULT_USER_PROMPT

    model, processor = _load_mlx_model(repo_id)

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    buf.seek(0)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    prompt = apply_chat_template(processor, model.config, messages, num_images=1)

    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(buf.getvalue())
        tmp.flush()

        logger.debug("Generating annotation for image")
        output = generate(
            model,
            processor,
            prompt=prompt,
            image=[tmp.name],
            max_tokens=config.max_tokens or DEFAULT_MAX_TOKENS,
            temperature=0.0,
            verbose=False,
        )

    text = getattr(output, "text", output)
    text = text.strip() if isinstance(text, str) else str(text).strip()
    text = _trim_annotation(text, config.max_chars)
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
            if not _should_annotate_picture(picture, document, config):
                logger.info(
                    "Skipping small picture %s below annotation area threshold %.4f",
                    ref,
                    config.min_area_ratio,
                )
                continue

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
