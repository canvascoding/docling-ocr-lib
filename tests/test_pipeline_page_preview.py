from PIL import Image

from docling_ocr.pipeline import DoclingPipeline
from docling_ocr.storage.local import LocalStorageBackend


class _FakeImageRef:
    @property
    def pil_image(self):
        image = Image.new("RGB", (12, 8), color="white")
        image.format = "PNG"
        return image


class _FakePageItem:
    image = _FakeImageRef()


def test_extract_and_upload_page_preview(tmp_path):
    pipeline = DoclingPipeline(
        storage=LocalStorageBackend(output_dir=str(tmp_path / "output")),
        generate_page_previews=True,
    )

    preview = pipeline._extract_and_upload_page_preview(
        page_item=_FakePageItem(),
        page_index=2,
        source_file="EoI B.pdf",
        doc_stem="EoI B",
    )

    assert preview is not None
    assert preview.original_id == "#/pages/3"
    assert preview.image_kind == "page_preview"
    assert preview.content_image is True
    assert preview.low_value is False
    assert preview.content_type == "image/png"
    assert " " not in preview.file_name
    assert preview.file_name.startswith("EoI_B_")
    assert preview.hosted_url.endswith("_page2_preview.png")
