# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-18

### Added
- Initial release of `docling-ocr-lib`
- `DoclingPipeline` — drop-in alternative to `mistral_ocr.OCRPipeline`
- Two switchable pipelines:
  - `standard` — Layout model + RapidOCR + TableFormer (default, CPU-friendly)
  - `vlm` — GraniteDocling-258M via MLX on Apple Silicon MPS
- Optional picture annotations via VLM (Qwen2.5-VL-3B MLX default), independent of pipeline choice
- Support for all Docling input formats: PDF, DOCX, PPTX, XLSX, HTML, EPUB, Markdown, LaTeX, CSV, images (PNG/JPEG/TIFF/BMP/WEBP)
- Image extraction via `PictureItem.get_image()` → PIL → bytes → storage upload
- Per-page markdown splitting via item provenance
- `<!-- PAGE N -->` markers for page traceability
- Metadata JSON output per document
- Configurable storage backends: `LocalStorageBackend` (with per-doc subfolders) and `S3StorageBackend`
- CLI: `docling-ocr process <file>` and `docling-ocr batch <dir>`
- Offline mode via `artifacts_path` (pre-downloaded models)
- 26 unit tests covering markdown replacement, image utils, storage, models, exceptions
- README with usage examples and pipeline comparison
- Architecture plan document

### Security
- No API keys required — runs 100% locally
- No data sent to external services (unless remote annotation API explicitly configured)