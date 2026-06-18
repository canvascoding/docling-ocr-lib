from __future__ import annotations


class DoclingOCRError(Exception):
    """Base exception for all docling-ocr errors."""


class ConversionError(DoclingOCRError):
    """Raised when document conversion fails."""


class StorageError(DoclingOCRError):
    """Raised when file storage (local or S3) fails."""
