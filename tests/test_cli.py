from __future__ import annotations

import json

from docling_ocr.cli import _save_results
from docling_ocr.models import ProcessedImage, ProcessedPage


def test_save_results_writes_image_classification_and_page_preview(tmp_path):
    image = ProcessedImage(
        original_id="#/pictures/0",
        file_name="chart.png",
        hosted_url="https://r2.example/chart.png",
        content_type="image/png",
        image_annotation="A chart.",
        image_kind="chart",
        content_image=True,
        low_value=False,
    )
    preview = ProcessedImage(
        original_id="#/pages/1",
        file_name="page.png",
        hosted_url="https://r2.example/page.png",
        content_type="image/png",
        image_annotation="Page preview for page 1.",
        image_kind="page_preview",
        content_image=True,
        low_value=False,
    )
    page = ProcessedPage(
        page_index=0,
        markdown="# Page",
        images=[image],
        source_file="slides.pdf",
        page_preview=preview,
    )

    _save_results([page], str(tmp_path), "slides.pdf")

    metadata = json.loads((tmp_path / "slides_metadata.json").read_text(encoding="utf-8"))
    first_page = metadata["pages"][0]
    assert first_page["images"][0]["image_kind"] == "chart"
    assert first_page["images"][0]["content_image"] is True
    assert first_page["images"][0]["low_value"] is False
    assert first_page["page_preview"]["hosted_url"] == "https://r2.example/page.png"
    assert first_page["page_preview"]["image_kind"] == "page_preview"
