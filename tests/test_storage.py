import sys
from pathlib import Path
from types import SimpleNamespace

from docling_ocr.storage.s3 import S3StorageBackend
from docling_ocr.storage.local import LocalStorageBackend
from docling_ocr.storage.paths import quote_storage_key, sanitize_filename


def test_sanitize_filename_returns_url_safe_basename():
    assert sanitize_filename("../EoI B ä chart.png") == "EoI_B_a_chart.png"
    assert sanitize_filename("   ###.png") == "png"


def test_quote_storage_key_encodes_segments_not_slashes():
    assert quote_storage_key("RAG Docs/EoI B_page 1.png") == "RAG%20Docs/EoI%20B_page%201.png"


class TestLocalStorageBackend:
    def test_upload_creates_file(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"))
        result = storage.upload(b"hello", "test.png")
        assert result.endswith("test.png")
        assert Path(result).exists()
        assert Path(result).read_bytes() == b"hello"

    def test_get_base_url(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"))
        base = storage.get_base_url()
        assert "output" in base

    def test_subfolder(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"), subfolder="mydoc")
        result = storage.upload(b"hello", "test.png")
        assert "mydoc" in result
        assert Path(result).exists()

    def test_effective_output_dir_with_subfolder(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"), subfolder="mydoc")
        assert storage.effective_output_dir == Path(tmp_path / "output" / "mydoc")

    def test_effective_output_dir_without_subfolder(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"))
        assert storage.effective_output_dir == Path(tmp_path / "output")

    def test_output_dir_setter(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"))
        assert storage._output_dir == Path(tmp_path / "output")
        new_dir = tmp_path / "new_output"
        storage._output_dir = new_dir
        assert storage._output_dir == new_dir

    def test_upload_sanitizes_filename(self, tmp_path):
        storage = LocalStorageBackend(output_dir=str(tmp_path / "output"))
        result = storage.upload(b"hello", "EoI B ä chart.png")
        assert result.endswith("EoI_B_a_chart.png")
        assert Path(result).exists()


class TestS3StorageBackend:
    def test_upload_sanitizes_filename_and_quotes_public_url(self, monkeypatch):
        calls = []

        class FakeClient:
            def put_object(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: FakeClient()))

        storage = S3StorageBackend(
            bucket="bucket",
            prefix="RAG Docs",
            public_base_url="https://r2.example.com",
        )

        result = storage.upload(b"hello", "EoI B ä chart.png")

        assert calls[0]["Key"] == "RAG Docs/EoI_B_a_chart.png"
        assert result == "https://r2.example.com/RAG%20Docs/EoI_B_a_chart.png"
