from docling_ocr.markdown import replace_image_references
from docling_ocr.models import ProcessedImage


class TestReplaceImageReferences:
    def test_no_images(self):
        md = "# Hello\n\nSome text"
        result = replace_image_references(md, [])
        assert result == "# Hello\n\nSome text"

    def test_single_image_replacement(self):
        md = "![img-0](img-0)"
        images = [
            ProcessedImage(
                original_id="img-0",
                file_name="123_img-0.png",
                image_annotation="A chart showing sales data",
                hosted_url="https://bucket.s3.eu-central-1.amazonaws.com/123_img-0.png",
            )
        ]
        result = replace_image_references(md, images)
        assert "https://bucket.s3.eu-central-1.amazonaws.com/123_img-0.png" in result
        assert "A chart showing sales data" in result

    def test_image_empty_parens(self):
        md = "![img-0]()"
        images = [
            ProcessedImage(
                original_id="img-0",
                file_name="123_img-0.png",
                image_annotation="",
                hosted_url="https://example.com/123_img-0.png",
            )
        ]
        result = replace_image_references(md, images)
        assert "![img-0](https://example.com/123_img-0.png)" in result

    def test_multiple_images(self):
        md = "![img-0](img-0)\n\nText\n\n![img-1](img-1)"
        images = [
            ProcessedImage(
                original_id="img-0",
                file_name="a.png",
                image_annotation="Chart",
                hosted_url="https://example.com/a.png",
            ),
            ProcessedImage(
                original_id="img-1",
                file_name="b.png",
                image_annotation="Table",
                hosted_url="https://example.com/b.png",
            ),
        ]
        result = replace_image_references(md, images)
        assert "![img-0](https://example.com/a.png)" in result
        assert "![img-1](https://example.com/b.png)" in result
        assert "Chart" in result
        assert "Table" in result

    def test_image_without_annotation(self):
        md = "![img-0](img-0)"
        images = [
            ProcessedImage(
                original_id="img-0",
                file_name="a.png",
                image_annotation="",
                hosted_url="https://example.com/a.png",
            )
        ]
        result = replace_image_references(md, images)
        assert "![img-0](https://example.com/a.png)" in result

    def test_image_label_placeholder(self):
        md = "![image](pic_ref_0)"
        images = [
            ProcessedImage(
                original_id="pic_ref_0",
                file_name="a.png",
                image_annotation="",
                hosted_url="https://example.com/a.png",
            )
        ]
        result = replace_image_references(md, images)
        assert "https://example.com/a.png" in result

    def test_empty_label_placeholder(self):
        md = "![](pic_ref_0)"
        images = [
            ProcessedImage(
                original_id="pic_ref_0",
                file_name="a.png",
                image_annotation="",
                hosted_url="https://example.com/a.png",
            )
        ]
        result = replace_image_references(md, images)
        assert "https://example.com/a.png" in result
