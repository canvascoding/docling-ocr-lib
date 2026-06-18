from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from docling_ocr.exceptions import ConversionError
from docling_ocr.models import DoclingConfig

logger = logging.getLogger(__name__)


VLM_MODEL_MAP: dict[str, str] = {
    "granite_docling_mlx": "GRANITEDOCLING_MLX",
    "granite_docling_transformers": "GRANITEDOCLING_TRANSFORMERS",
    "smoldocling_mlx": "SMOLDOCLING_MLX",
    "smoldocling_transformers": "SMOLDOCLING_TRANSFORMERS",
    "qwen25_vl_3b_mlx": "QWEN25_VL_3B_MLX",
}


class DoclingConverter:
    """Wraps Docling's DocumentConverter with standard or VLM pipeline.

    Handles all Docling-supported formats: PDF, DOCX, PPTX, XLSX, HTML,
    EPUB, Markdown, LaTeX, CSV, images (PNG/JPEG/TIFF/BMP/WEBP), and more.
    """

    def __init__(self, config: DoclingConfig) -> None:
        self._config = config
        self._converter = self._build_converter()
        logger.info(
            "DoclingConverter initialized (pipeline=%s, vlm_model=%s, picture_annotations=%s, artifacts_path=%s)",
            config.pipeline,
            config.vlm_model,
            config.picture_annotations,
            config.artifacts_path,
        )

    def _build_converter(self):
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter

        if self._config.pipeline == "vlm":
            pdf_format_option = self._build_vlm_format_option()
        else:
            pdf_format_option = self._build_standard_format_option()

        format_options: dict = {
            InputFormat.PDF: pdf_format_option,
        }

        return DocumentConverter(format_options=format_options)

    def _build_standard_format_option(self):
        from docling.datamodel.pipeline_options import (
            OcrOptions,
            PdfPipelineOptions,
            RapidOcrOptions,
            TableFormerMode,
            TableStructureOptions,
        )

        try:
            ocr_options: OcrOptions = RapidOcrOptions()
            ocr_engine = "rapidocr"
        except Exception:
            from docling.datamodel.pipeline_options import EasyOcrOptions

            ocr_options = EasyOcrOptions(lang=self._config.ocr_languages)
            ocr_engine = "easyocr"

        logger.info("Using OCR engine: %s", ocr_engine)
        table_mode = (
            TableFormerMode.ACCURATE if self._config.table_structure_mode == "accurate" else TableFormerMode.FAST
        )

        pipeline_options = PdfPipelineOptions(
            artifacts_path=self._config.artifacts_path,
            do_ocr=self._config.do_ocr,
            ocr_options=ocr_options,
            do_table_structure=self._config.do_table_structure,
            table_structure_options=TableStructureOptions(do_cell_matching=True, mode=table_mode),
            generate_picture_images=self._config.generate_picture_images,
            images_scale=self._config.images_scale,
        )

        if self._config.picture_annotations:
            self._apply_picture_description(pipeline_options)
            if hasattr(pipeline_options, "images_scale") and pipeline_options.images_scale is None:
                pipeline_options.images_scale = 2.0

    def convert(self, file_path: str | Path) -> Any:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {path}")

        logger.info("Converting document: %s", path)

        kwargs: dict = {}
        if self._config.max_num_pages is not None:
            kwargs["max_num_pages"] = self._config.max_num_pages
        if self._config.max_file_size is not None:
            kwargs["max_file_size"] = self._config.max_file_size

        try:
            result = self._converter.convert(str(path), **kwargs)
        except Exception as e:
            logger.error("Docling conversion failed for %s: %s", path, e)
            raise ConversionError(f"Failed to convert {path}: {e}") from e

        logger.info("Conversion complete: %d pages", result.document.num_pages())
        return result

    def close(self) -> None:
        pass

    def __enter__(self) -> DoclingConverter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
