# -*- coding: utf-8 -*-
"""Fail-closed BSM row selection.

Reject a BSM row when SCHOOLNAME is missing or whitespace-only.
Keep the first remaining BSM row from top to bottom and return that row only.
"""
from collections import Counter

REQUIRED_UNIQUE_HEADERS = ("school_code", "SCHOOLNAME", "template")


class ConfigSelectionError(RuntimeError):
    """BSM configuration cannot be selected safely."""


def school_name_text(value):
    """Return the trimmed school name, or empty when the cell has no real name."""
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
        if value != value:  # NaN that pandas.isna did not catch
            return ""
    except Exception:
        pass
    return str(value).strip()


def _mangled_duplicate(names, header):
    prefix = header + "."
    for name in names:
        suffix = name[len(prefix):] if name.startswith(prefix) else ""
        if suffix.isdigit():
            return True
    return False


def assert_required_headers(columns):
    names = [str(column) for column in columns]
    counts = Counter(names)
    bad = []
    for header in REQUIRED_UNIQUE_HEADERS:
        if counts.get(header, 0) != 1 or _mangled_duplicate(names, header):
            bad.append(header)
    if bad:
        raise ConfigSelectionError(
            "Required BSM headers are missing or duplicated: " + ", ".join(bad)
        )


def select_bsm_row(frame):
    """Return the first eligible BSM row, or fail closed.

    Non-BSM schools are ignored. No field is taken from a later row.
    """
    if frame is None or not hasattr(frame, "columns") or not hasattr(frame, "iterrows"):
        raise ConfigSelectionError("BSM configuration table is missing.")
    assert_required_headers(frame.columns)
    code = frame["school_code"].astype(str).str.strip().str.upper()
    matches = frame[code == "BSM"]
    for _, row in matches.iterrows():
        if school_name_text(row["SCHOOLNAME"]):
            return row
    raise ConfigSelectionError(
        "No eligible BSM row. Empty or whitespace-only SCHOOLNAME was rejected. "
        "No template fallback."
    )
