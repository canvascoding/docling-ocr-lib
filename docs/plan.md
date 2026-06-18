# Docling OCR Lib – Architektur & Plan

## Ziel

Python-Library zur **lokalen** Dokumentenverarbeitung mit [Docling](https://github.com/docling-project/docling). Drop-in-Alternative zu `mistral-ocr-lib` — identisches Output-Interface (`ProcessedPage`, `ProcessedImage`), aber ohne API-Keys, ohne Cloud-Kosten, mit Unterstützung für alle Docling-Formate.

## Motivation

- **Privacy**: Dokumente verlassen nie die Maschine
- **Kosten**: Keine Per-Page-API-Kosten
- **Formate**: Nicht nur PDF, sondern DOCX, PPTX, XLSX, HTML, EPUB, Bilder, etc.
- **Flexibilität**: Wählbare Pipeline (Standard vs. VLM) + optionale Bild-Annotationen
- **Offline**: Modelle können vorgeladen werden (air-gapped möglich)

## Architektur

```
docling-ocr-lib/
├── .gitignore
├── .env.example
├── pyproject.toml                    # Hatch Build-System, deps: docling, pydantic, click, Pillow
├── docs/
│   └── plan.md                       # Dieser Plan
├── src/
│   └── docling_ocr/
│       ├── __init__.py               # Public API exports
│       ├── converter.py              # DoclingConverter: wrappt DocumentConverter (standard/VLM)
│       ├── pipeline.py               # DoclingPipeline: single doc + batch
│       ├── annotator.py              # PictureDescription enrichment + annotation extraction
│       ├── models.py                 # Pydantic-Modelle (ProcessedPage, DoclingConfig, etc.)
│       ├── exceptions.py             # DoclingOCRError-Hierarchie
│       ├── image_utils.py            # PIL Image → bytes conversion
│       ├── markdown.py               # Bild-Referenzen im Markdown ersetzen
│       ├── cli.py                    # CLI: docling-ocr process <file>
│       └── storage/
│           ├── __init__.py
│           ├── base.py               # StorageBackend ABC (1:1 von mistral-ocr-lib)
│           ├── local.py              # LocalStorageBackend (1:1)
│           └── s3.py                 # S3StorageBackend (1:1)
└── tests/
    ├── __init__.py
    ├── test_markdown.py
    ├── test_storage.py
    ├── test_image_utils.py
    └── test_models.py
```

## Module-Detail

### converter.py – `DoclingConverter`

- Wrappt Doclings `DocumentConverter`
- Zwei Pipeline-Modi:
  - `standard`: `PdfPipelineOptions` mit EasyOCR + TableFormer + Layout-Modell
  - `vlm`: `VlmPipeline` mit `VlmPipelineOptions` + `vlm_model_specs.GRANITEDOCLING_MLX`
- Optional: `do_picture_description=True` mit `PictureDescriptionVlmOptions` (im Standard-Modus)
- `convert(file_path) → ConversionResult`
- Unterstützt alle Docling-Formate: PDF, DOCX, PPTX, XLSX, HTML, EPUB, MD, CSV, LaTeX, Bilder
- `max_num_pages` und `max_file_size` Limits konfigurierbar

### pipeline.py – `DoclingPipeline`

- Konstruktor-Parameter (alle optional außer storage):
  - `storage: StorageBackend | None`
  - `pipeline: "standard" | "vlm"` (default: `"standard"`)
  - `vlm_model: str` (default: `"granite_docling_mlx"`)
  - `picture_annotations: bool` (default: `False`) — **unabhängig von pipeline**
  - `annotation_config: AnnotationConfig | None`
  - `artifacts_path: str | None` — für Offline-Modelle
  - `do_table_structure`, `table_structure_mode`, `generate_picture_images`
  - `do_ocr`, `ocr_languages`
  - `per_doc_subfolder`, `batch_delay`, `max_num_pages`, `max_file_size`
- `process(file_path: str | Path) → list[ProcessedPage]`
- `process_batch(file_paths: list[str | Path]) → dict[str, list[ProcessedPage]]`
- Pipeline-Schritte:
  1. Dokument konvertieren (`converter.convert`)
  2. Markdown exportieren (`doc.export_to_markdown()`)
  3. Annotationen extrahieren (falls `picture_annotations=True`)
  4. Pro PictureItem: PIL-Image → Bytes → Storage-Upload → `ProcessedImage`
  5. Bild-Referenzen im Markdown ersetzen
  6. `<!-- PAGE N -->`-Marker hinzufügen
  7. `list[ProcessedPage]` zurückgeben

### annotator.py – Picture-Annotationen

- `build_picture_description_options(config) → PictureDescriptionVlmOptions | PictureDescriptionApiOptions`
  - Preset-basiert: `from_preset("qwen2_5_vl_3b")` (default), `"granite_vision"`, `"smolvlm"`
  - Custom: `repo_id` für beliebige HuggingFace-Modelle
  - Remote: `PictureDescriptionApiOptions` für OpenAI-kompatible APIs
- `extract_annotations(document) → dict[str, str]` — Mapping `picture.self_ref → annotation_text`

### models.py – Pydantic-Modelle

- `ProcessedImage(original_id, file_name, image_annotation, hosted_url, content_type)` — **identisch zu mistral-ocr-lib**
- `ProcessedPage(markdown, images, page_index, source_file, dimensions, metadata)` — **identisch**
- `PageDimensions(dpi, height, width)` — **identisch**
- `AnnotationConfig(prompt, model, remote_api_url, remote_api_key)` — angepasst für Docling
- `DoclingConfig` — interne Pipeline-Konfiguration

### image_utils.py – Bild-Extraktion

- `pil_image_to_bytes(pil_image) → ImageProcessingResult` — PIL → Bytes mit Format-Detection
- `extract_image_bytes(picture_item) → ImageProcessingResult` — Docling PictureItem → Bytes
- Format-Map: JPEG, PNG, GIF, WebP, BMP, TIFF
- Fallback auf PNG bei unbekanntem Format
- RGBA→RGB Konvertierung für JPEG

### markdown.py – Bild-Referenzen-Ersetzung

- `replace_image_references(markdown, images) → str` — gleiche Logik wie mistral-ocr-lib
- Ersetzt: `![id](id)`, `![id]()`, `![image](id)`, `![](id)` (Docling-Styles)

### storage/ – 1:1 von mistral-ocr-lib übernommen

- `StorageBackend` ABC, `LocalStorageBackend`, `S3StorageBackend`
- Keine Änderungen notwendig

### cli.py – Click CLI

- `docling-ocr process <file>` — Einzelnes Dokument
- `docling-ocr batch <dir>` — Alle unterstützten Dateien in Verzeichnis
- Optionen: `--pipeline`, `--vlm-model`, `--picture-annotations`, `--annotation-model`, `--annotation-prompt`, `--artifacts-path`, `--no-ocr`, `--max-pages`, `--storage`, `--output-dir`, `--s3-bucket`, `--s3-region`, `--no-subfolder`, `--batch-delay`

### exceptions.py

- `DoclingOCRError` – Basis-Exception
- `ConversionError(DoclingOCRError)` – Konvertierung fehlgeschlagen
- `StorageError(DoclingOCRError)` – Speicher-Fehler

## Design-Entscheidungen

| Entscheidung | Wahl | Begründung |
|---|---|---|
| Interface | Identisch zu mistral-ocr-lib | Drop-in Replacement, einfacher Wechsel |
| Pipeline-Schalter | `standard` vs `vlm` | Standard=CPU-freundlich Default, VLM für gescannte Docs |
| Annotationen | Unabhängig von Pipeline | Flexibilität: 4 Kombinationen möglich |
| Default-Annotation-Modell | Qwen2.5-VL-3B MLX | Ausgewogen Speed/Qualität auf Apple Silicon |
| VLM-Default | GraniteDocling MLX | 258M, MLX auf MPS, gut für Apple Silicon |
| Storage | 1:1 von mistral-ocr-lib übernommen | Bewährt, keine Änderung nötig |
| Bild-Extraktion | PIL via PictureItem.get_image() | Docling-nativ, kein Base64-Prefix-Problem |
| Formate | Alle Docling-Formate | Mehrwert gegenüber Mistral (nur PDF) |
| Offline | `artifacts_path` Parameter | Air-gapped-Umgebungen unterstützt |
| Sync vs Async | Synchron | Konsistent mit mistral-ocr-lib |

## Pipeline-Vergleich

| Pipeline | Engine | Best for | GPU? | Speed |
|---|---|---|---|---|
| `standard` | Layout + EasyOCR + TableFormer | Digitale PDFs, DOCX, etc. | Nein (CPU) | Schnell |
| `vlm` | GraniteDocling-258M (MLX) | Gescannte/handgeschriebene PDFs | Empfohlen (MPS) | ~6s/Seite (M3 Max) |

## Annotation-Kombinationen

| Pipeline | Annotations | Result |
|---|---|---|
| standard | off | Schnellster Default, digitale PDFs |
| standard | on | Digitale PDFs + VLM-Bildbeschreibungen |
| vlm | off | Beste OCR für gescannte Docs |
| vlm | on | Maximale Qualität, langsamste Variante |

## Usage-Beispiel

```python
from docling_ocr import DoclingPipeline, LocalStorageBackend

# Standard (Default) — lokal, keine API-Keys
with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
) as pipeline:
    pages = pipeline.process("document.pdf")
    # Auch: .docx, .pptx, .xlsx, .html, .epub, .png, ...

# VLM + Annotationen (Premium-Modus)
from docling_ocr import AnnotationConfig
with DoclingPipeline(
    storage=LocalStorageBackend("./output"),
    pipeline="vlm",
    picture_annotations=True,
    annotation_config=AnnotationConfig(prompt="Beschreibe jedes Bild..."),
) as pipeline:
    pages = pipeline.process("scanned.pdf")
```

## Integration in Hausarbeits-KI-Agent

```python
# pdf_ingest/content_processor.py
class ContentProcessor:
    def __init__(self, backend: Literal["mistral", "docling"] = "mistral"):
        if backend == "docling":
            from docling_ocr import DoclingPipeline
            self._pipeline = DoclingPipeline(storage=LocalStorageBackend("./output"))
        else:
            from mistral_ocr import OCRPipeline
            self._pipeline = OCRPipeline(api_key=..., storage=LocalStorageBackend("./output"))
```

`.env`: `OCR_BACKEND=docling` oder `OCR_BACKEND=mistral`

## Environment-Variablen (.env)

```
# Optional: Offline-Modelle
DOCLING_ARTIFACTS_PATH=/local/path/to/models

# S3 storage (optional)
S3_BUCKET=
S3_REGION=eu-central-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

## Dependencies

**Core:**
- `docling>=2.0`
- `pydantic>=2.0`
- `click>=8.0`
- `python-dotenv>=1.0`
- `Pillow>=10.0`

**Optional (s3):**
- `boto3>=1.34`

**Optional (vlm):**
- `docling[vlm]` (für VLM-Pipeline und Picture-Annotationen)

**Dev:**
- `pytest>=8.0`
- `pytest-mock>=3.12`
- `ruff>=0.4`

## Hardware-Empfehlung (Mac Mini M4 Base 16GB)

- **Default**: `pipeline="standard"`, `picture_annotations=False` — läuft problemlos auf CPU
- **VLM-Modus**: Für einzelne gescannte PDFs nutzbar (~6-10s/Seite auf M4 Base MPS)
- **Annotationen**: Nur bei Bedarf aktivieren — bei vielen Bildern langsam (sekundenpro-Bild)
- **Offline**: `docling-tools models download` einmalig ausführen, dann `--artifacts-path` setzen