# -*- coding: utf-8 -*-
"""Read-only checks for one already selected school-config row."""
import hashlib
from pathlib import Path

from PIL import Image, UnidentifiedImageError


REQUIRED_FIELDS = ("school_code", "SCHOOLNAME", "template", "CARD", "CARD_TYPE")


def normalize_cell(value):
    """Empty, None and NaN are blank. Whitespace is blank. Other text stays."""
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:
            return ""
        if value.is_integer():
            return str(int(value))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value).replace("\xa0", " ").strip()
    return text


def header_positions(header_row):
    """Map a stripped header to every original 1-based column. Blank headers stay out of the map."""
    positions = {}
    blanks = []
    for index, raw in enumerate(header_row, start=1):
        name = normalize_cell(raw)
        if not name:
            blanks.append(index)
            continue
        positions.setdefault(name, []).append(index)
    return positions, blanks


def resolve_header(row, columns):
    """Return one value only when every duplicate cell normalizes to the same text."""
    found = []
    for column in columns:
        raw = row[column - 1] if column - 1 < len(row) else None
        found.append({"column": column, "raw": raw, "normalized": normalize_cell(raw)})
    values = [item["normalized"] for item in found]
    ambiguous = len(set(values)) > 1
    resolved = "" if ambiguous else (values[0] if values else "")
    return {"columns": found, "resolved": resolved, "ambiguous": ambiguous}


def validate_template(template_path):
    """Open only the selected row's file. No fallback path is tried."""
    text = normalize_cell(template_path)
    if not text:
        return {"ok": False, "error": "template_missing", "path": ""}
    path = Path(text)
    if not path.is_file():
        return {"ok": False, "error": "template_missing", "path": str(path)}
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                return {
                    "ok": False,
                    "error": "template_not_png",
                    "path": str(path),
                    "format": image.format,
                }
            width, height = image.size
            mode = image.mode
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return {"ok": False, "error": "template_invalid", "path": str(path), "detail": exc.__class__.__name__}
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return {
        "ok": True,
        "error": "",
        "path": str(path),
        "sha256": digest,
        "width": width,
        "height": height,
        "mode": mode,
        "format": "PNG",
    }
