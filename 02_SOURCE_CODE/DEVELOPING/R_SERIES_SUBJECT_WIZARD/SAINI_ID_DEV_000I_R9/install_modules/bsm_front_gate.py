# -*- coding: utf-8 -*-
"""Approve only the cleaned BSM front template. This module does not draw or save a card."""
from pathlib import Path

APPROVED_SHA256 = "B4CEC57AF02B6CB92CDF2EB7262EB5E3F5582207BC23A29D578BA694D707E956"
APPROVED_FILENAME = "BSM_PUBLIC_SCHOOL_CLEAN.png"
SCHOOL_NAME = "BSM PUBLIC SCHOOL"


def require_approved_front(workbook_path):
    """Return the approved template path, or an error. Never falls back to BSM.png."""
    from bsm_config_loader import load_school_config

    loaded = load_school_config(workbook_path, "BSM")
    if not loaded.get("success"):
        return "", loaded.get("error") or "BSM configuration rejected"
    if loaded.get("selected_excel_row") != 13:
        return "", "BSM selection did not stay on Excel row 13"
    if loaded.get("selected_school_name") != SCHOOL_NAME:
        return "", "BSM school name is not the approved name"
    path = str(loaded.get("selected_template_path") or "").strip()
    filename = Path(path).name
    if filename.upper() == "BSM.PNG":
        return "", "Original BSM.png is not the approved template"
    if filename != APPROVED_FILENAME:
        return "", "Approved template filename was not selected"
    digest = str(loaded.get("template", {}).get("sha256") or "").upper()
    if digest != APPROVED_SHA256:
        return "", "Approved template hash was not verified"
    return path, ""
