from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from docling_ocr.exceptions import DoclingOCRError
from docling_ocr.models import AnnotationConfig, ProcessedPage
from docling_ocr.pipeline import DoclingPipeline
from docling_ocr.storage.local import LocalStorageBackend
from docling_ocr.storage.s3 import S3StorageBackend

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".xhtml",
    ".epub",
    ".md",
    ".csv",
    ".latex",
    ".tex",
    ".png",
    ".jpeg",
    ".jpg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
}


def _get_storage(storage_type: str, output_dir: str, s3_bucket: str | None, s3_region: str) -> object:
    if storage_type == "s3":
        if not s3_bucket:
            raise click.UsageError("--s3-bucket is required when --storage=s3")
        return S3StorageBackend(bucket=s3_bucket, region=s3_region)
    return LocalStorageBackend(output_dir=output_dir)


def _save_results(pages: list[ProcessedPage], output_dir: str, doc_name: str) -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stem = Path(doc_name).stem

    all_markdown = "\n\n---\n\n".join(p.markdown for p in pages)
    md_file = out_path / f"{stem}.md"

    try:
        md_file.write_text(all_markdown, encoding="utf-8")
    except OSError as e:
        raise click.ClickException(f"Failed to write output file {md_file}: {e}") from e

    pages_meta = []
    for p in pages:
        page_entry: dict = {
            "page_index": p.page_index,
            "source_file": p.source_file,
            "images": [
                {
                    "original_id": img.original_id,
                    "file_name": img.file_name,
                    "hosted_url": img.hosted_url,
                    "content_type": img.content_type,
                    "image_annotation": img.image_annotation,
                }
                for img in p.images
            ],
        }
        if p.dimensions:
            page_entry["dimensions"] = {
                "dpi": p.dimensions.dpi,
                "height": p.dimensions.height,
                "width": p.dimensions.width,
            }
        pages_meta.append(page_entry)

    metadata = {
        "source_file": doc_name,
        "processed_at": datetime.now().isoformat(),
        "total_pages": len(pages),
        "pages": pages_meta,
    }

    meta_file = out_path / f"{stem}_metadata.json"
    try:
        meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        raise click.ClickException(f"Failed to write metadata file {meta_file}: {e}") from e

    click.echo(f"Saved {len(pages)} pages to {md_file}")
    click.echo(f"Saved metadata to {meta_file}")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    load_dotenv()
    _setup_logging(verbose)


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--storage", type=click.Choice(["local", "s3"]), default="local", help="Storage backend")
@click.option("--output-dir", default="./output", help="Output directory for local storage")
@click.option("--s3-bucket", envvar="S3_BUCKET", help="S3 bucket name")
@click.option("--s3-region", envvar="S3_REGION", default="eu-central-1", help="S3 region")
@click.option(
    "--pipeline",
    type=click.Choice(["standard", "vlm"]),
    default="standard",
    help="Docling pipeline: standard (Layout+EasyOCR) or vlm (GraniteDocling)",
)
@click.option(
    "--vlm-model",
    default="granite_docling_mlx",
    help="VLM model for --pipeline=vlm",
)
@click.option(
    "--picture-annotations",
    is_flag=True,
    help="Enable VLM picture descriptions (like Mistral image annotations)",
)
@click.option(
    "--annotation-model",
    default="qwen25_vl_3b_mlx",
    help="Model for picture annotations",
)
@click.option(
    "--annotation-prompt",
    default=AnnotationConfig().prompt,
    help="Prompt for picture annotations",
)
@click.option(
    "--artifacts-path", envvar="DOCLING_ARTIFACTS_PATH", default=None, help="Local model artifacts path for offline use"
)
@click.option("--no-ocr", is_flag=True, help="Disable OCR (text-layer only)")
@click.option("--max-pages", type=int, default=None, help="Max pages to process")
@click.option("--max-file-size", type=int, default=None, help="Max file size in bytes")
@click.option("--no-subfolder", is_flag=True, help="Disable per-doc subfolder in output")
def process(
    file: str,
    storage: str,
    output_dir: str,
    s3_bucket: str | None,
    s3_region: str,
    pipeline: str,
    vlm_model: str,
    picture_annotations: bool,
    annotation_model: str,
    annotation_prompt: str,
    artifacts_path: str | None,
    no_ocr: bool,
    max_pages: int | None,
    max_file_size: int | None,
    no_subfolder: bool,
) -> None:
    storage_backend = _get_storage(storage, output_dir, s3_bucket, s3_region)

    annotation_config = AnnotationConfig(
        prompt=annotation_prompt,
        model=annotation_model,
    )

    try:
        with DoclingPipeline(
            storage=storage_backend,
            pipeline=pipeline,
            vlm_model=vlm_model,
            picture_annotations=picture_annotations,
            annotation_config=annotation_config,
            artifacts_path=artifacts_path,
            do_ocr=not no_ocr,
            per_doc_subfolder=not no_subfolder,
            max_num_pages=max_pages,
            max_file_size=max_file_size,
        ) as pl:
            pages = pl.process(file)
            _save_results(pages, output_dir, file)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except DoclingOCRError as e:
        raise click.ClickException(f"Processing failed: {e}") from e


@main.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--storage", type=click.Choice(["local", "s3"]), default="local", help="Storage backend")
@click.option("--output-dir", default="./output", help="Output directory for local storage")
@click.option("--s3-bucket", envvar="S3_BUCKET", help="S3 bucket name")
@click.option("--s3-region", envvar="S3_REGION", default="eu-central-1", help="S3 region")
@click.option(
    "--pipeline",
    type=click.Choice(["standard", "vlm"]),
    default="standard",
    help="Docling pipeline: standard or vlm",
)
@click.option("--vlm-model", default="granite_docling_mlx", help="VLM model for --pipeline=vlm")
@click.option("--picture-annotations", is_flag=True, help="Enable VLM picture descriptions")
@click.option("--annotation-model", default="qwen25_vl_3b_mlx", help="Model for picture annotations")
@click.option("--artifacts-path", envvar="DOCLING_ARTIFACTS_PATH", default=None, help="Local model artifacts path")
@click.option("--no-ocr", is_flag=True, help="Disable OCR (text-layer only)")
@click.option("--batch-delay", default=0.0, help="Delay between files in seconds")
@click.option("--no-subfolder", is_flag=True, help="Disable per-doc subfolder in output")
def batch(
    directory: str,
    storage: str,
    output_dir: str,
    s3_bucket: str | None,
    s3_region: str,
    pipeline: str,
    vlm_model: str,
    picture_annotations: bool,
    annotation_model: str,
    artifacts_path: str | None,
    no_ocr: bool,
    batch_delay: float,
    no_subfolder: bool,
) -> None:
    doc_dir = Path(directory)
    doc_files = sorted(f for f in doc_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)

    if not doc_files:
        click.echo("No supported document files found in directory.")
        return

    click.echo(f"Found {len(doc_files)} document(s) to process.")

    storage_backend = _get_storage(storage, output_dir, s3_bucket, s3_region)

    annotation_config = AnnotationConfig(model=annotation_model)

    with DoclingPipeline(
        storage=storage_backend,
        pipeline=pipeline,
        vlm_model=vlm_model,
        picture_annotations=picture_annotations,
        annotation_config=annotation_config,
        artifacts_path=artifacts_path,
        do_ocr=not no_ocr,
        batch_delay=batch_delay,
        per_doc_subfolder=not no_subfolder,
    ) as pl:
        for doc_path in doc_files:
            click.echo(f"Processing {doc_path.name}...")
            try:
                pages = pl.process(str(doc_path))
                _save_results(pages, output_dir, str(doc_path))
            except DoclingOCRError as e:
                click.echo(f"Error processing {doc_path.name}: {e}", err=True)
                logger.error("Failed to process %s: %s", doc_path, e)
