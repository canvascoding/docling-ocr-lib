from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_UNDERSCORES = re.compile(r"_+")


def sanitize_filename(filename: str, *, default: str = "file") -> str:
    """Return a URL-safe basename for stored image artifacts."""
    basename = Path(str(filename)).name.strip()
    ascii_name = unicodedata.normalize("NFKD", basename).encode("ascii", "ignore").decode("ascii")
    safe_name = _UNSAFE_FILENAME_CHARS.sub("_", ascii_name)
    safe_name = _REPEATED_UNDERSCORES.sub("_", safe_name).strip("._-")
    return safe_name or default


def quote_storage_key(key: str) -> str:
    """Percent-encode each object-key segment for public HTTP URLs."""
    return "/".join(quote(segment, safe="-._~") for segment in str(key).split("/"))
