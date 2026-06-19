# docling-ocr-lib

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: 39](https://img.shields.io/badge/tests-39%20passed-brightgreen.svg)]()
[![Docling](https://img.shields.io/badge/powered%20by-Docling-8A2BE2.svg)](https://github.com/docling-project/docling)

Python library for **local** document processing using [Docling](https://github.com/docling-project/docling). Drop-in alternative to `mistral-ocr-lib` — same output structures (`ProcessedPage`, `ProcessedImage`), but runs entirely on your machine without API keys or cloud costs.

> **100% local • No API keys • All formats • Free • Private**

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI](#cli)
- [Pipeline Comparison](#pipeline-comparison-standard-vs-vlm)
- [Picture Annotations](#picture-annotations)
- [Output Format](#output)
- [Architecture](#architecture)
- [Comparison with mistral-ocr-lib](#comparison-mistral-ocr-lib-vs-docling-ocr-lib)
- [Error Handling](#error-handling)
- [Development](#development)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

## Features

- **100% local** — no API keys, no data leaves your machine
- **All Docling formats**: PDF, DOCX, PPTX, XLSX, HTML, EPUB, Markdown, LaTeX, CSV, images (PNG/JPEG/TIFF/BMP/WEBP)
- **Two pipelines** (switchable):
  - `standard` — Layout + EasyOCR (default, CPU-friendly, fast for digital PDFs)
  - `vlm` — GraniteDocling VLM on Apple Silicon MLX (best for scanned docs)
- **Picture annotations** (optional) — VLM-generated descriptions for each image, like Mistral's annotations. Default: Qwen2.5-VL-3B MLX
- Image extraction with PIL → storage (local or S3)
- Optional page previews — render each processed page/slide as a stored image for RAG and visual learning use cases
- `<!-- PAGE N -->` markers in markdown for page traceability
- Metadata JSON output per document with image mapping, page previews, image classification, and dimensions
- Configurable storage backends (local filesystem or S3)
- Per-document subfolder output to avoid file collisions
- Batch processing with configurable delay
- CLI for quick processing without writing code
- Offline mode via `artifacts_path` (pre-downloaded models)

## Installation

### Local development

```bash
git clone <repo-url>
cd docling-ocr-lib
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### With S3 support

```bash
pip install -e ".[s3]"
```

### VLM extras (for picture annotations or VLM pipeline)

```bash
pip install "docling[vlm]"
```

## Quick Start

### Python API

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

# Standard pipeline (default) — no API key needed
with DoclingPipeline(
    storage=LocalStorageBackend(output_dir="./output"),
) as pipeline:
    pages = pipeline.process("document.pdf")

for page in pages:
    print(f"Page {page.page_index} ({page.source_file}):")
    print(page.markdown)
    for img in page.images:
        print(f"  Image: {img.hosted_url} ({img.content_type})")
        if img.image_annotation:
            print(f"  Annotation: {img.image_annotation}")
```

### Page Previews for RAG

For slide decks or learning material, enable page previews so every processed PDF page is also stored as an image. This is useful when the original PDF page itself is the visual source, not only embedded pictures inside the page.

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    generate_page_previews=True,
) as pipeline:
    pages = pipeline.process("slides.pdf")

for page in pages:
    if page.page_preview:
        print(page.page_preview.hosted_url)
```

### VLM Pipeline (best for scanned documents)

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    pipeline="vlm",
    vlm_model="granite_docling_mlx",  # runs on Apple Silicon MPS
) as pipeline:
    pages = pipeline.process("scanned.pdf")
```

### With Picture Annotations (like Mistral)

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend, AnnotationConfig

annotation = AnnotationConfig(
    prompt="Beschreibe Diagramme, Tabellen und Frameworks in 2-3 kurzen Sätzen. Logos nur sehr kurz markieren.",
    model="qwen25_vl_3b_mlx",  # default, runs on MLX
    max_tokens=140,
    max_chars=650,
)

with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    picture_annotations=True,
    annotation_config=annotation,
) as pipeline:
    pages = pipeline.process("document.pdf")
    # Each ProcessedImage.image_annotation now contains a VLM description
```

### All Supported File Types

```python
# Not just PDF — all Docling formats work
pipeline.process("document.docx")
pipeline.process("presentation.pptx")
pipeline.process("spreadsheet.xlsx")
pipeline.process("page.html")
pipeline.process("book.epub")
pipeline.process("photo.png")
pipeline.process("data.csv")
```

### S3 Storage

```python
from docling_ocr import DoclingPipeline, S3StorageBackend

storage = S3StorageBackend(
    bucket="my-ocr-bucket",
    region="eu-central-1",
    prefix="ocr-images",
)

with DoclingPipeline(storage=storage) as pipeline:
    pages = pipeline.process("document.pdf")
```

### Batch Processing

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    batch_delay=0.0,  # local, no rate limit needed
) as pipeline:
    results = pipeline.process_batch(["doc1.pdf", "doc2.docx", "doc3.pptx"])

for path, pages in results.items():
    print(f"{path}: {len(pages)} pages processed")
```

### Offline Mode (pre-download models)

```bash
# Download models once
docling-tools models download

# Find the cache path
ls ~/.cache/docling/models
```

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    artifacts_path="/Users/you/.cache/docling/models",
) as pipeline:
    pages = pipeline.process("document.pdf")  # works offline
```

## CLI

```bash
# Process a single document (any supported format)
docling-ocr process document.pdf

# Process with VLM pipeline
docling-ocr process scanned.pdf --pipeline vlm

# Enable picture annotations
docling-ocr process document.pdf --picture-annotations

# Store one rendered image per page/slide
docling-ocr process slides.pdf --page-previews

# Custom annotation model
docling-ocr process document.pdf --picture-annotations --annotation-model granite_vision

# Process all supported documents in a directory
docling-ocr batch ./docs/

# Use S3 storage
docling-ocr process document.pdf --storage s3 --s3-bucket my-bucket

# Offline mode
docling-ocr process document.pdf --artifacts-path /path/to/models

# Disable OCR (text-layer only, faster for digital PDFs)
docling-ocr process document.pdf --no-ocr

# Enable debug logging
docling-ocr -v process document.pdf

# Disable per-doc subfolders
docling-ocr process document.pdf --no-subfolder

# Specify output directory
docling-ocr process document.pdf --output-dir ./results
```

## Output

For each document, two files are created in the output directory:

1. `{filename}.md` — Combined markdown from all pages (with `<!-- PAGE N -->` markers). Image annotations are written as `> **Bildbeschreibung:** ...` blockquotes so they stay visually separate from source text.
2. `{filename}_metadata.json` — Machine-readable metadata

Example metadata JSON:

```json
{
  "source_file": "document.pdf",
  "processed_at": "2025-06-18T12:00:00",
  "total_pages": 3,
  "pages": [
    {
      "page_index": 0,
      "source_file": "document.pdf",
      "dimensions": {
        "height": 2200,
        "width": 1700
      },
      "images": [
        {
          "original_id": "#/pictures/0",
          "file_name": "document_1718000000_#/pictures/0_page0.png",
          "hosted_url": "/path/to/output/document/document_1718000000_#/pictures/0_page0.png",
          "content_type": "image/png",
          "image_annotation": "A bar chart showing quarterly revenue",
          "image_kind": "chart",
          "content_image": true,
          "low_value": false
        }
      ],
      "page_preview": {
        "original_id": "#/pages/1",
        "file_name": "document_abc123_page0_preview.png",
        "hosted_url": "/path/to/output/document/document_abc123_page0_preview.png",
        "content_type": "image/png",
        "image_annotation": "Page preview for page 1.",
        "image_kind": "page_preview",
        "content_image": true,
        "low_value": false
      }
    }
  ]
}
```

## Pipeline Comparison: Standard vs. VLM

| Feature | `standard` | `vlm` |
|---|---|---|
| Engine | Layout model + EasyOCR | GraniteDocling-258M (MLX) |
| Best for | Digital PDFs, DOCX, PPTX | Scanned/handwritten PDFs |
| GPU needed | No (CPU works) | Recommended (MPS on Apple Silicon) |
| Speed | Fast | ~6s/page (M3 Max), slower on base M4 |
| Tables | Structured Markdown (TableFormer) | Good |
| Picture annotations | Optional (separate VLM) | Optional (separate VLM) |

## Picture Annotations

Annotations are **orthogonal** to the pipeline choice — you can combine:

| Pipeline | Annotations | Result |
|---|---|---|
| standard | off | Fastest, good for digital PDFs |
| standard | on | Digital PDFs + VLM image descriptions |
| vlm | off | Best OCR for scanned docs |
| vlm | on | Maximum quality, slowest |

The default annotation prompt writes German plain-text descriptions. It keeps simple photos short, gives charts/tables/diagrams enough structure for learning, and marks pure logos/decorative images briefly as low-value visual context.

**Annotation models (local, MLX):**
- `qwen25_vl_3b_mlx` (default) — 3B, ~23s/image, good general-purpose
- `granite_vision` — 2B, ~104s/image, strong on diagrams/charts
- `smolvlm` — 256M, fastest, lower quality

**Remote API (optional):**
```python
AnnotationConfig(
    model="gpt-4o",
    remote_api_url="https://api.openai.com/v1/chat/completions",
    remote_api_key="sk-...",
    prompt="Describe this image.",
)
```

## Architecture

```
src/docling_ocr/
├── __init__.py          # Public API exports
├── converter.py         # DoclingConverter — wraps DocumentConverter (standard/VLM)
├── pipeline.py          # DoclingPipeline — main orchestration
├── annotator.py         # PictureDescription enrichment + annotation extraction
├── models.py            # Pydantic models (ProcessedPage, DoclingConfig, etc.)
├── exceptions.py        # DoclingOCRError hierarchy
├── image_utils.py       # PIL Image → bytes conversion
├── markdown.py          # Image reference replacement in markdown
├── cli.py               # Click CLI interface
└── storage/
    ├── base.py          # StorageBackend ABC
    ├── local.py         # LocalStorageBackend (with subfolder support)
    └── s3.py            # S3StorageBackend
```

### Pipeline Flow

1. **Convert** document with Docling (`DocumentConverter.convert`)
   - Standard: Layout model + EasyOCR + TableFormer
   - VLM: GraniteDocling processes each page as image
   - Optional: PictureDescription enrichment runs VLM on each image
2. **Export** to markdown (`doc.export_to_markdown()`)
3. **Extract images** — for each `PictureItem`: `get_image()` → PIL → bytes
4. **Upload** to storage (local or S3) with correct format/extension
5. **Replace** local image references in markdown with hosted URLs + annotations
6. **Add** `<!-- PAGE N -->` markers
7. Return `list[ProcessedPage]` with markdown, images, dimensions

## Error Handling

All exceptions inherit from `DoclingOCRError`:

| Exception | When |
|---|---|
| `ConversionError` | Document conversion fails (unsupported format, corrupt file) |
| `StorageError` | File storage (local or S3) fails |

```python
from docling_ocr import DoclingPipeline, DoclingOCRError, ConversionError

try:
    pages = pipeline.process("document.pdf")
except ConversionError as e:
    print(f"Conversion failed: {e}")
except DoclingOCRError as e:
    print(f"Pipeline error: {e}")
```

## Comparison: mistral-ocr-lib vs. docling-ocr-lib

| Feature | mistral-ocr-lib | docling-ocr-lib |
|---|---|---|
| Compute | Cloud (Mistral API) | Local |
| API key | Required | Not needed |
| Cost | Per-page | Free |
| Privacy | Data sent to Mistral | 100% local |
| Formats | PDF only | PDF + DOCX + PPTX + XLSX + HTML + EPUB + images + ... |
| Tables | Image + annotation | Structured Markdown |
| Image annotations | Built-in | Optional VLM enrichment |
| Speed | Fast (cloud GPU) | Slower first run (model download), then depends on hardware |
| Output format | `list[ProcessedPage]` | `list[ProcessedPage]` (identical) |

## Environment Variables

Copy `.env.example` to `.env`:

```env
# Optional: pre-downloaded models for offline use
DOCLING_ARTIFACTS_PATH=/local/path/to/models

# S3 storage (optional)
S3_BUCKET=your-bucket
S3_REGION=eu-central-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
ruff format src/ tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR workflow.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and notable changes.

## License

MIT — see [LICENSE](LICENSE)
