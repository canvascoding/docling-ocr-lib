import sys
from pathlib import Path
from types import ModuleType

from PIL import Image

from docling_ocr import vlm_annotator
from docling_ocr.models import AnnotationConfig
from docling_ocr.vlm_annotator import (
    _picture_area_ratio,
    _resolve_repo_id,
    _should_annotate_picture,
    _trim_annotation,
    describe_image_with_mlx_vlm,
    generate_vlm_annotations,
)


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


class _FakeBBox:
    t = 0
    r = 10
    b = 10

    def __init__(self):
        setattr(self, "l", 0)


class _FakeProv:
    page_no = 1
    bbox = _FakeBBox()


class _FakeSize:
    width = 100
    height = 100


class _FakePage:
    size = _FakeSize()


class _FakeDocument:
    pages = {1: _FakePage()}


class _FakePictureWithProv(_FakePicture):
    prov = [_FakeProv()]


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


def test_generate_vlm_annotations_skips_small_images(monkeypatch):
    calls = {"describe_count": 0}

    def fake_describe(image, config, artifacts_path):
        calls["describe_count"] += 1
        return "A concise diagram description."

    monkeypatch.setattr("docling_ocr.vlm_annotator.describe_image_with_mlx_vlm", fake_describe)

    config = AnnotationConfig(min_area_ratio=0.02)
    annotations = generate_vlm_annotations([_FakePictureWithProv()], _FakeDocument(), config)

    assert annotations == {}
    assert calls["describe_count"] == 0


def test_picture_area_ratio_from_docling_provenance():
    assert _picture_area_ratio(_FakePictureWithProv(), _FakeDocument()) == 0.01


def test_should_annotate_picture_respects_small_image_config():
    picture = _FakePictureWithProv()
    document = _FakeDocument()

    assert _should_annotate_picture(picture, document, AnnotationConfig(min_area_ratio=0.02)) is False
    assert _should_annotate_picture(picture, document, AnnotationConfig(skip_small_images=False)) is True


def test_trim_annotation_prefers_sentence_boundary():
    text = "First short sentence. " + "Second sentence with many details. " * 20

    assert _trim_annotation(text, max_chars=40) == "First short sentence."


def test_trim_annotation_truncates_at_word_boundary():
    text = "This annotation has no early sentence boundary and should be shortened cleanly"

    assert _trim_annotation(text, max_chars=35) == "This annotation has no early..."


def test_describe_image_with_mlx_vlm_uses_temp_image_path_and_chat_template(monkeypatch):
    calls = {}
    vlm_annotator._MODEL_CACHE.clear()

    class FakeModel:
        config = {"model_type": "qwen2_5_vl"}

    class FakeOutput:
        text = "A concise chart description."

    def fake_load(repo_id):
        calls["load_count"] = calls.get("load_count", 0) + 1
        calls["repo_id"] = repo_id
        return FakeModel(), object()

    def fake_apply_chat_template(processor, config, messages, num_images):
        calls["messages"] = messages
        calls["num_images"] = num_images
        return "formatted prompt"

    def fake_generate(model, processor, prompt, image, max_tokens, temperature, verbose):
        calls["prompt"] = prompt
        calls["image"] = image
        calls["max_tokens"] = max_tokens
        calls["temperature"] = temperature
        calls["verbose"] = verbose
        assert isinstance(image, list)
        assert len(image) == 1
        assert Path(image[0]).exists()
        return FakeOutput()

    fake_mlx_vlm = ModuleType("mlx_vlm")
    fake_mlx_vlm.load = fake_load
    fake_mlx_vlm.generate = fake_generate
    fake_prompt_utils = ModuleType("mlx_vlm.prompt_utils")
    fake_prompt_utils.apply_chat_template = fake_apply_chat_template
    monkeypatch.setitem(sys.modules, "mlx_vlm", fake_mlx_vlm)
    monkeypatch.setitem(sys.modules, "mlx_vlm.prompt_utils", fake_prompt_utils)

    text = describe_image_with_mlx_vlm(Image.new("RGB", (8, 8), color="white"), AnnotationConfig())
    text_again = describe_image_with_mlx_vlm(Image.new("RGB", (8, 8), color="white"), AnnotationConfig())

    assert text == "A concise chart description."
    assert text_again == "A concise chart description."
    assert calls["load_count"] == 1
    assert calls["repo_id"] == "mlx-community/Qwen2.5-VL-3B-Instruct-bf16"
    assert calls["num_images"] == 1
    assert calls["prompt"] == "formatted prompt"
    assert calls["max_tokens"] == 80
    assert calls["temperature"] == 0.0
    assert calls["verbose"] is False
    assert calls["messages"][0]["role"] == "system"
    assert calls["messages"][1]["role"] == "user"
