from pathlib import Path

from PIL import Image

from docling_ocr.models import AnnotationConfig
from docling_ocr.vlm_annotator import _resolve_repo_id, generate_vlm_annotations


def test_resolve_repo_id_uses_local_artifacts_path(tmp_path: Path):
    local_model = tmp_path / "mlx-community--Qwen2.5-VL-3B-Instruct-bf16"
    local_model.mkdir()

    repo_id = _resolve_repo_id("qwen25_vl_3b_mlx", str(tmp_path))

    assert repo_id == str(local_model)


def test_resolve_repo_id_falls_back_to_remote_identifier(tmp_path: Path):
    repo_id = _resolve_repo_id("qwen25_vl_3b_mlx", str(tmp_path))

    assert repo_id == "mlx-community/Qwen2.5-VL-3B-Instruct-bf16"


class _FakePicture:
    self_ref = "#/pictures/1"

    def get_image(self, document):
        return Image.new("RGB", (8, 8), color="white")


def test_generate_vlm_annotations_passes_document_and_artifacts_path(monkeypatch):
    calls = {}

    def fake_describe(image, config, artifacts_path):
        calls["image"] = image
        calls["config"] = config
        calls["artifacts_path"] = artifacts_path
        return "A concise diagram description."

    monkeypatch.setattr("docling_ocr.vlm_annotator.describe_image_with_mlx_vlm", fake_describe)

    config = AnnotationConfig(model="qwen25_vl_3b_mlx")
    annotations = generate_vlm_annotations([_FakePicture()], object(), config, "/models")

    assert annotations == {"#/pictures/1": "A concise diagram description."}
    assert isinstance(calls["image"], Image.Image)
    assert calls["config"] is config
    assert calls["artifacts_path"] == "/models"
