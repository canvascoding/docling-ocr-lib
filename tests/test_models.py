from docling_ocr.exceptions import ConversionError, DoclingOCRError, StorageError
from docling_ocr.models import (
    AnnotationConfig,
    DoclingConfig,
    PageDimensions,
    ProcessedDocument,
    ProcessedImage,
    ProcessedPage,
)


class TestExceptions:
    def test_base_exception(self):
        assert issubclass(ConversionError, DoclingOCRError)
        assert issubclass(StorageError, DoclingOCRError)

    def test_exception_messages(self):
        err = ConversionError("test error")
        assert str(err) == "test error"
        err2 = StorageError("storage failed")
        assert str(err2) == "storage failed"


class TestModels:
    def test_processed_page_defaults(self):
        page = ProcessedPage()
        assert page.markdown == ""
        assert page.images == []
        assert page.page_preview is None
        assert page.page_index == 0
        assert page.source_file == ""
        assert page.metadata == {}

    def test_processed_document(self):
        page = ProcessedPage(markdown="hello", source_file="lecture.pdf")
        processed = ProcessedDocument(document={"raw": "docling-document"}, pages=[page], source_file="lecture.pdf")

        assert processed.document == {"raw": "docling-document"}
        assert processed.pages == [page]
        assert processed.source_file == "lecture.pdf"

    def test_processed_image_defaults(self):
        img = ProcessedImage(original_id="img-0", file_name="a.png", hosted_url="http://example.com/a.png")
        assert img.image_annotation == ""
        assert img.content_type == "image/jpeg"
        assert img.image_kind == "picture"
        assert img.content_image is True
        assert img.low_value is False

    def test_page_dimensions(self):
        dims = PageDimensions(dpi=72, height=800, width=600)
        assert dims.dpi == 72
        assert dims.height == 800
        assert dims.width == 600

    def test_annotation_config_defaults(self):
        config = AnnotationConfig()
        assert config.model == "qwen25_vl_3b_mlx"
        assert "visuelle element" in config.prompt.lower()
        assert config.max_tokens == 140
        assert config.max_chars == 650

    def test_docling_config_defaults(self):
        config = DoclingConfig()
        assert config.pipeline == "standard"
        assert config.vlm_model == "granite_docling_mlx"
        assert config.picture_annotations is False
        assert config.do_table_structure is True
        assert config.table_structure_mode == "accurate"
        assert config.generate_picture_images is True
        assert config.generate_page_previews is False
        assert config.do_ocr is True
        assert config.per_doc_subfolder is True
        assert config.batch_delay == 0.0

    def test_docling_config_custom(self):
        config = DoclingConfig(
            pipeline="vlm",
            picture_annotations=True,
            ocr_languages=["en", "de", "fr"],
        )
        assert config.pipeline == "vlm"
        assert config.picture_annotations is True
        assert config.ocr_languages == ["en", "de", "fr"]
