from __future__ import annotations

import io
import logging
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
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=0.0,
            verbose=False,
        )

    text = getattr(output, "text", output)
    text = text.strip() if isinstance(text, str) else str(text).strip()
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
