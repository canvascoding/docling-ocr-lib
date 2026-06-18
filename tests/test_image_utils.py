from PIL import Image

from docling_ocr.image_utils import pil_image_to_bytes


class TestPilImageToBytes:
    def test_png_image(self):
        img = Image.new("RGB", (10, 10), color="red")
        img.format = "PNG"
        result = pil_image_to_bytes(img)
        assert result.extension == ".png"
        assert result.content_type == "image/png"
        assert len(result.data) > 0

    def test_jpeg_image(self):
        img = Image.new("RGB", (10, 10), color="blue")
        img.format = "JPEG"
        result = pil_image_to_bytes(img)
        assert result.extension == ".jpg"
        assert result.content_type == "image/jpeg"
        assert len(result.data) > 0

    def test_rgba_to_jpeg_converts_to_rgb(self):
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        img.format = "JPEG"
        result = pil_image_to_bytes(img)
        assert result.extension == ".jpg"
        assert result.content_type == "image/jpeg"

    def test_unknown_format_falls_back_to_png(self):
        img = Image.new("RGB", (10, 10), color="green")
        img.format = "UNKNOWN"
        result = pil_image_to_bytes(img)
        assert result.extension == ".png"
        assert result.content_type == "image/png"

    def test_no_format_defaults_to_png(self):
        img = Image.new("RGB", (10, 10), color="green")
        img.format = None
        result = pil_image_to_bytes(img)
        assert result.extension == ".png"
        assert result.content_type == "image/png"
