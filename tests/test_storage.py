from pathlib import Path

from docling_ocr.storage.local import LocalStorageBackend


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
