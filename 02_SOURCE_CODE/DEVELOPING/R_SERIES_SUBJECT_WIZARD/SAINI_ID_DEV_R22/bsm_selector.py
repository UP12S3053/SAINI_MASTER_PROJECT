# -*- coding: utf-8 -*-
"""Fail-closed BSM row selection for the R19 development copy."""
from pathlib import Path

REQUIRED = (
    ("school_code", "school_code"),
    ("schoolname", "SCHOOLNAME"),
    ("template", "template"),
)


class ConfigSelectionError(RuntimeError):
    """BSM configuration cannot be selected safely."""


def school_name_text(value):
    """Return the trimmed text, or empty when the cell has no real text."""
    if value is None:
        return ""
    if type(value).__name__ in {"Series", "DataFrame"}:
        raise ConfigSelectionError("SCHOOLNAME column is ambiguous.")
    try:
        import pandas as pd
        if not isinstance(value, (str, bytes)) and pd.isna(value):
            return ""
    except ConfigSelectionError:
        raise
    except Exception:
        pass
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value).strip()


def _norm(name):
    return "".join(str(name).split()).casefold()


def _mangled(norm, key):
    prefix = key + "."
    suffix = norm[len(prefix):] if norm.startswith(prefix) else ""
    return suffix.isdigit()


def _hits(columns, key):
    return [str(name) for name in columns if _norm(name) == key or _mangled(_norm(name), key)]


def assert_required_headers(columns):
    bad = []
    for key, label in REQUIRED:
        if len(_hits(columns, key)) != 1:
            bad.append(label)
    if bad:
        raise ConfigSelectionError("Required BSM headers are missing or duplicated: " + ", ".join(bad))


def _one_column(columns, key, label):
    hits = _hits(columns, key)
    if len(hits) != 1:
        raise ConfigSelectionError("Required BSM headers are missing or duplicated: " + label)
    return hits[0]


def template_rejection(value):
    """Return a rejection reason, or empty when the template file exists."""
    text = school_name_text(value)
    if not text:
        return "template path missing"
    try:
        exists = Path(text).is_file()
    except OSError:
        return "template file missing"
    if not exists:
        return "template file missing"
    return ""


def select_bsm_row(frame):
    """Return the first fully eligible BSM row, or fail closed.

    An eligible row has a real school name and its own existing template.
    No field is borrowed from another row.
    """
    if frame is None or not hasattr(frame, "columns") or not hasattr(frame, "iterrows"):
        raise ConfigSelectionError("BSM configuration table is missing.")
    assert_required_headers(frame.columns)
    code_col = _one_column(frame.columns, "school_code", "school_code")
    name_col = _one_column(frame.columns, "schoolname", "SCHOOLNAME")
    template_col = _one_column(frame.columns, "template", "template")
    code = frame[code_col].astype(str).str.strip().str.upper()
    matches = frame[code == "BSM"]
    saw_name = False
    saw_missing_template = False
    for _, row in matches.iterrows():
        if not school_name_text(row[name_col]):
            continue
        saw_name = True
        reason = template_rejection(row[template_col])
        if reason:
            saw_missing_template = True
            continue
        return row
    if saw_name and saw_missing_template:
        raise ConfigSelectionError("No eligible BSM row. Missing or invalid template was rejected. No cross-row fallback.")
    raise ConfigSelectionError(
        "No eligible BSM row. Empty or whitespace-only SCHOOLNAME was rejected. No template fallback."
    )
