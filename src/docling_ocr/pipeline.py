from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from docling_ocr.annotator import extract_annotations
from docling_ocr.converter import DoclingConverter
from docling_ocr.exceptions import ConversionError, DoclingOCRError, StorageError
from docling_ocr.image_utils import extract_image_bytes
from docling_ocr.markdown import replace_image_references
from docling_ocr.models import (
    AnnotationConfig,
    DoclingConfig,
    PageDimensions,
    ProcessedDocument,
    ProcessedImage,
    ProcessedPage,
)
from docling_ocr.storage.base import StorageBackend
from docling_ocr.storage.local import LocalStorageBackend
from docling_ocr.vlm_annotator import generate_vlm_annotations

logger = logging.getLogger(__name__)


class DoclingPipeline:
    """Local document processing pipeline using Docling.

    Drop-in alternative to mistral_ocr.OCRPipeline. Returns the same
    ProcessedPage/ProcessedImage structures, but runs entirely locally
    without any API keys.

    Supports all Docling input formats: PDF, DOCX, PPTX, XLSX, HTML,
    EPUB, Markdown, LaTeX, CSV, images (PNG/JPEG/TIFF/BMP/WEBP).
    """

    def __init__(
        self,
        storage: StorageBackend | None = None,
        pipeline: str = "standard",
        vlm_model: str = "granite_docling_mlx",
        picture_annotations: bool = False,
        annotation_config: AnnotationConfig | None = None,
        artifacts_path: str | None = None,
        do_table_structure: bool = True,
        table_structure_mode: str = "accurate",
        generate_picture_images: bool = True,
        do_ocr: bool = True,
        ocr_languages: list[str] | None = None,
        per_doc_subfolder: bool = True,
        batch_delay: float = 0.0,
        max_num_pages: int | None = None,
        max_file_size: int | None = None,
        images_scale: float = 2.0,
        image_format: str = "png",
    ) -> None:
        self._storage = storage or LocalStorageBackend()
        self._batch_delay = batch_delay
        self._per_doc_subfolder = per_doc_subfolder

        self._config = DoclingConfig(
            pipeline=pipeline,
            vlm_model=vlm_model,
            picture_annotations=picture_annotations,
            annotation_config=annotation_config or AnnotationConfig(),
            artifacts_path=artifacts_path,
            do_table_structure=do_table_structure,
            table_structure_mode=table_structure_mode,
            generate_picture_images=generate_picture_images,
            do_ocr=do_ocr,
            ocr_languages=ocr_languages or ["en", "de"],
            per_doc_subfolder=per_doc_subfolder,
            batch_delay=batch_delay,
            max_num_pages=max_num_pages,
            max_file_size=max_file_size,
            images_scale=images_scale,
            image_format=image_format,
        )

        self._converter = DoclingConverter(self._config)
        logger.info(
            "DoclingPipeline initialized (pipeline=%s, storage=%s, "
            "picture_annotations=%s, per_doc_subfolder=%s, batch_delay=%.1fs, "
            "images_scale=%s, image_format=%s)",
            pipeline,
            type(self._storage).__name__,
            picture_annotations,
            per_doc_subfolder,
            batch_delay,
            images_scale,
            image_format,
        )

    def process(self, file_path: str | Path) -> list[ProcessedPage]:
        return self.process_with_document(file_path).pages

    def process_with_document(self, file_path: str | Path) -> ProcessedDocument:
        """Process a document and return both Docling's native document and exported pages.

        This is useful for downstream RAG pipelines that want to use Docling's
        native chunkers and provenance metadata while still reusing this
        pipeline's image extraction, annotations, and storage backends.
        """
        path = Path(file_path)
        source_file = path.name
        doc_stem = path.stem
        logger.info("Starting processing for: %s", path)

        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {path}")

        original_storage_dir = None
        if self._per_doc_subfolder and isinstance(self._storage, LocalStorageBackend):
            original_storage_dir = self._storage._output_dir
            self._storage._output_dir = original_storage_dir / doc_stem
            self._storage._output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Per-doc subfolder: %s", self._storage._output_dir)

        try:
            try:
                logger.debug("Step 1/2: Converting document with Docling")
                conversion_result = self._converter.convert(path)
            except ConversionError:
                raise
            except Exception as e:
                logger.error("Failed to convert %s: %s", path, e)
                raise ConversionError(f"Conversion failed for {path}: {e}") from e

            document = conversion_result.document
            logger.info("Step 2/2: Extracting pages, images, and annotations")

            annotations_map: dict[str, str] = {}
            if self._config.picture_annotations:
                if self._config.pipeline == "vlm":
                    logger.info("Generating VLM annotations for %d pictures", len(document.pictures))
                    annotations_map = generate_vlm_annotations(
                        document.pictures,
                        document,
                        self._config.annotation_config,
                        self._config.artifacts_path,
                    )
                else:
                    annotations_map = extract_annotations(document)

            result = self._process_document(document, source_file, doc_stem, annotations_map)
            return ProcessedDocument(document=document, pages=result, source_file=source_file)
        finally:
            if original_storage_dir is not None and isinstance(self._storage, LocalStorageBackend):
                self._storage._output_dir = original_storage_dir
                logger.debug("Restored original output dir: %s", original_storage_dir)

    def process_batch(self, file_paths: list[str | Path]) -> dict[str, list[ProcessedPage]]:
        logger.info("Starting batch processing for %d files", len(file_paths))
        results: dict[str, list[ProcessedPage]] = {}
        for i, file_path in enumerate(file_paths):
            path_str = str(file_path)
            logger.info("Processing file %d/%d: %s", i + 1, len(file_paths), path_str)
            if i > 0 and self._batch_delay > 0:
                logger.debug("Batch delay: sleeping %.1fs before next file", self._batch_delay)
                time.sleep(self._batch_delay)
            try:
                results[path_str] = self.process(file_path)
            except DoclingOCRError as e:
                logger.error("Failed to process %s: %s", path_str, e)
                results[path_str] = []
        logger.info(
            "Batch processing complete: %d/%d files succeeded",
            sum(1 for v in results.values() if v),
            len(file_paths),
        )
        return results

    def _process_document(
        self,
        document: Any,
        source_file: str,
        doc_stem: str,
        annotations_map: dict[str, str],
    ) -> list[ProcessedPage]:
        page_count = document.num_pages()
        pages_data = self._build_page_index(document)
        processed: list[ProcessedPage] = []

        pictures_by_ref: dict[str, Any] = {}
        for pic in document.pictures:
            ref = pic.self_ref or ""
            pictures_by_ref[ref] = pic

        for page_idx in range(page_count):
            logger.debug("Processing page %d", page_idx)
            page_info = pages_data.get(page_idx, {})
            page_markdown = page_info.get("markdown", "")
            page_pictures = page_info.get("pictures", [])

            processed_images: list[ProcessedImage] = []
            for pic_ref in page_pictures:
                picture = pictures_by_ref.get(pic_ref)
                if picture is None:
                    continue
                processed_img = self._extract_and_upload_image(
                    picture, pic_ref, page_idx, source_file, doc_stem, annotations_map, document
                )
                if processed_img:
                    processed_images.append(processed_img)

            if processed_images:
                page_markdown = replace_image_references(page_markdown, processed_images)

            page_marker = f"\n\n<!-- PAGE {page_idx} -->\n\n"
            page_markdown = page_marker + page_markdown

            dimensions = page_info.get("dimensions")

            processed.append(
                ProcessedPage(
                    markdown=page_markdown,
                    images=processed_images,
                    page_index=page_idx,
                    source_file=source_file,
                    dimensions=dimensions,
                    metadata={
                        "original_page_index": page_idx,
                        "source_file": source_file,
                    },
                )
            )

        return processed

    def _build_page_index(self, document: Any) -> dict[int, dict]:
        """Build a per-page index of markdown segments, pictures, and dimensions.

        Uses Docling's iterate_items() to split content by page provenance.
        Falls back to full markdown on page 0 for single-page docs or when
        page attribution is not available.
        """
        pages: dict[int, dict] = {}
        page_count = document.num_pages()

        for page_no in range(page_count):
            pages[page_no] = {
                "markdown": "",
                "pictures": [],
                "dimensions": None,
            }

        for page_no, page_item in (document.pages or {}).items():
            idx = page_no - 1 if page_no >= 1 else page_no
            if idx not in pages:
                pages[idx] = {"markdown": "", "pictures": [], "dimensions": None}

            size = getattr(page_item, "size", None)
            if size:
                pages[idx]["dimensions"] = PageDimensions(
                    width=getattr(size, "width", None),
                    height=getattr(size, "height", None),
                )

        for picture in document.pictures:
            page_no = 0
            if picture.prov:
                page_no = picture.prov[0].page_no - 1 if picture.prov[0].page_no >= 1 else 0
            if page_no not in pages:
                page_no = 0
            ref = picture.self_ref or ""
            if ref:
                pages[page_no]["pictures"].append(ref)

        if page_count <= 1:
            pages[0]["markdown"] = document.export_to_markdown()
            return pages

        per_page_md: dict[int, list[str]] = {idx: [] for idx in pages}
        for item, _level in document.iterate_items():
            prov = getattr(item, "prov", None)
            if not prov:
                continue
            page_no = prov[0].page_no
            idx = page_no - 1 if page_no >= 1 else 0
            if idx not in per_page_md:
                idx = 0

            item_md = self._item_to_markdown(item, document)
            if item_md:
                per_page_md[idx].append(item_md)

        for idx, segments in per_page_md.items():
            pages[idx]["markdown"] = "\n\n".join(segments)

        return pages

    def _item_to_markdown(self, item: Any, document: Any) -> str:
        """Convert a single Docling item to its markdown representation."""
        from docling_core.types.doc import ImageRefMode

        try:
            if hasattr(item, "export_to_markdown"):
                try:
                    return item.export_to_markdown(doc=document, image_mode=ImageRefMode.PLACEHOLDER)
                except TypeError:
                    return item.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)
        except Exception:
            pass

        text = getattr(item, "text", None)
        if text:
            return text

        return ""

    def _extract_and_upload_image(
        self,
        picture: Any,
        pic_ref: str,
        page_index: int,
        source_file: str,
        doc_stem: str,
        annotations_map: dict[str, str],
        document: Any = None,
    ) -> ProcessedImage | None:
        try:
            cleaned = extract_image_bytes(picture, document)
        except Exception as e:
            logger.warning("Failed to extract image %s on page %d: %s", pic_ref, page_index, e)
            return None

        import hashlib

        unique_hash = hashlib.sha256(f"{source_file}_{page_index}_{pic_ref}".encode()).hexdigest()[:12]
        file_name = f"{doc_stem}_{unique_hash}_page{page_index}{cleaned.extension}"

        try:
            hosted_url = self._storage.upload(
                file_data=cleaned.data,
                filename=file_name,
                content_type=cleaned.content_type,
            )
        except StorageError as e:
            logger.error("Failed to upload image %s on page %d: %s", pic_ref, page_index, e)
            return None

        annotation = annotations_map.get(pic_ref, "")

        logger.debug("Uploaded image %s -> %s (%s)", pic_ref, hosted_url, cleaned.content_type)
        return ProcessedImage(
            original_id=pic_ref,
            file_name=file_name,
            image_annotation=annotation,
            hosted_url=hosted_url,
            content_type=cleaned.content_type,
        )

    def close(self) -> None:
        logger.debug("Closing DoclingPipeline")
        self._converter.close()

    def __enter__(self) -> DoclingPipeline:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
