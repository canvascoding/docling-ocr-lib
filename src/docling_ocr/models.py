from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class PageDimensions(BaseModel):
    dpi: float | None = None
    height: float | None = None
    width: float | None = None


class ProcessedImage(BaseModel):
    original_id: str
    file_name: str
    image_annotation: str = ""
    hosted_url: str
    content_type: str = "image/jpeg"
    image_kind: str = "picture"
    content_image: bool = True
    low_value: bool = False


class ProcessedPage(BaseModel):
    markdown: str = ""
    images: list[ProcessedImage] = Field(default_factory=list)
    page_preview: ProcessedImage | None = None
    page_index: int = 0
    source_file: str = ""
    dimensions: PageDimensions | None = None
    metadata: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class ProcessedDocument:
    document: Any
    pages: list[ProcessedPage]
    source_file: str


class AnnotationConfig(BaseModel):
    prompt: str = (
        "Beschreibe dieses visuelle Element aus Uni-Unterlagen präzise auf Deutsch. "
        "Bei Diagrammen, Tabellen, Frameworks, Modellen, Formeln oder Foliengrafiken: "
        "schreibe 2-3 kurze Sätze mit Bildtyp, sichtbaren Achsen/Kategorien/Beziehungen, "
        "zentraler Aussage und wichtigen sichtbaren Fachbegriffen. Bei einfachen Fotos oder "
        "Produktbildern reicht ein klarer Satz. Wenn es nur ein Logo, Icon, Wasserzeichen "
        "oder dekoratives Bild ist, antworte sehr kurz und beginne mit "
        "'Logo/dekoratives Bild:'. Erfinde keine Zahlen oder Aussagen, die nicht sichtbar sind. "
        "Gib nur reinen Text ohne Markdown zurück."
    )
    model: str = "qwen25_vl_3b_mlx"
    remote_api_url: str | None = None
    remote_api_key: str | None = None
    max_tokens: int = 140
    max_chars: int = 650
    skip_small_images: bool = True
    min_area_ratio: float = 0.015


class DoclingConfig(BaseModel):
    pipeline: str = "standard"
    vlm_model: str = "granite_docling_mlx"
    picture_annotations: bool = False
    annotation_config: AnnotationConfig = Field(default_factory=AnnotationConfig)
    artifacts_path: str | None = None
    do_table_structure: bool = True
    table_structure_mode: str = "accurate"
    generate_picture_images: bool = True
    generate_page_previews: bool = False
    do_ocr: bool = True
    ocr_languages: list[str] = Field(default_factory=lambda: ["en", "de"])
    per_doc_subfolder: bool = True
    batch_delay: float = 0.0
    max_num_pages: int | None = None
    max_file_size: int | None = None
    images_scale: float = 2.0
    image_format: str = "png"
