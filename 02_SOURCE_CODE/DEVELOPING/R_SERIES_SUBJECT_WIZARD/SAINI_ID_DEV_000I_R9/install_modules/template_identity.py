# -*- coding: utf-8 -*-
"""Identify a selected template. Never substitutes another school's artwork."""
import hashlib
from pathlib import Path

from config_validator import validate_template

CONFIRMED_SCHOOL_NAME = "BSM PUBLIC SCHOOL"
R4_REPORTED_TEXT = "NEW BRIGHT FUTURE PUBLIC SCHOOL"
R6_ROOT = Path("/workspace/SAINI_ID_DEV_000I_R6")

# Exact workbook path from the collected live row. This is the same file, not a fallback.
COLLECTED_BY_EXACT_PATH = {}


# Visual inspection of that exact SHA256 on 2026-11-06. R4's NBFP reading is not what the image shows.
INSPECTED_BY_SHA256 = {
    "FE644757E1F23AAAB47C46AE2880F8DFD4CCDE63B645C50B6C10B7C855151B73": {
        "printed_text": "B.S.M. PUBLIC SCHOOL (BUCHCHAKHERI)",
        "sample_portrait": True,
        "r4_reported_text": R4_REPORTED_TEXT,
        "r4_report_matches_image": False,
        "approved_for": "",
    },
}


def _normal_path(value):
    return str(value or "").replace("/", "\\").rstrip("\\")


def locate_template_file(workbook_path):
    """Open the selected path, or the collected copy of that same path. No other template."""
    text = str(workbook_path or "").strip()
    direct = Path(text)
    if direct.is_file():
        return direct
    collected = COLLECTED_BY_EXACT_PATH.get(_normal_path(text))
    if collected is not None and collected.is_file():
        return collected
    return None


def search_confirmed_templates(roots):
    """A template is confirmed only by an explicit confirmation record. None is invented here."""
    found = []
    marker = "CONFIRMED_SCHOOLNAME=BSM PUBLIC SCHOOL"
    for root in roots:
        folder = Path(root)
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".txt", ".json", ".md"}:
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if marker not in text or "CONFIRMED_TEMPLATE_SHA256=" not in text:
                continue
            digest = ""
            for line in text.splitlines():
                if line.startswith("CONFIRMED_TEMPLATE_SHA256="):
                    digest = line.split("=", 1)[1].strip().upper()
            if digest:
                found.append({"record": str(path), "sha256": digest, "school_name": CONFIRMED_SCHOOL_NAME})
    return found


# The user confirmed on 2026-11-07 that this printed name is the same school.
# Acceptance is limited to the cleaned file. The original artwork is not accepted.
USER_CONFIRMED_CLEAN = {
    "B4CEC57AF02B6CB92CDF2EB7262EB5E3F5582207BC23A29D578BA694D707E956": {
        "printed_text": "B.S.M. PUBLIC SCHOOL (BUCHCHAKHERI)",
        "same_school_as": "BSM PUBLIC SCHOOL",
        "basis": "user_explicit_confirmation",
        "sample_portrait": False,
        "mobile_removed": True,
        "final_approval": False,
    },
}


def inspect_selected_template(workbook_template_path, expected_school_name, search_roots=None):
    """Check the selected file only. Mismatch and unknown artwork both fail closed."""
    expected = " ".join(str(expected_school_name or "").split())
    located = locate_template_file(workbook_template_path)
    if located is None:
        return {
            "template": {
                "ok": False,
                "error": "template_missing",
                "path": str(workbook_template_path or ""),
                "resolved_path": "",
            },
            "identity": {"ok": False, "error": "template_missing"},
        }
    template = validate_template(str(located))
    template["workbook_path"] = str(workbook_template_path or "")
    template["resolved_path"] = str(located)
    if not template["ok"]:
        return {"template": template, "identity": {"ok": False, "error": template["error"]}}

    digest = template["sha256"]
    confirmed_clean = USER_CONFIRMED_CLEAN.get(digest)
    if confirmed_clean and expected.upper() == confirmed_clean["same_school_as"]:
        identity = {
            "ok": True,
            "error": "",
            "expected_school_name": expected,
            "printed_text": confirmed_clean["printed_text"],
            "sha256": digest,
            "sample_portrait": False,
            "mobile_removed": True,
            "basis": confirmed_clean["basis"],
            "final_approval": False,
            "r4_reported_text": "",
            "r4_report_matches_image": None,
            "confirmed_records": [],
            "approved_for": expected,
        }
        return {"template": template, "identity": identity}
    inspected = INSPECTED_BY_SHA256.get(digest, {})
    printed = inspected.get("printed_text", "")
    roots = search_roots if search_roots is not None else [
        R6_ROOT,
        Path("/workspace/SAINI_ID_DEV_000I_R4/live_root/ID_CARD_PROJECT/templates"),
    ]
    confirmed = [item for item in search_confirmed_templates(roots) if item["sha256"] == digest]
    exact_print = bool(printed) and printed.upper() == expected.upper()
    approved = exact_print and bool(confirmed) and inspected.get("approved_for") == expected
    identity = {
        "ok": approved,
        "error": "" if approved else "TEMPLATE_IDENTITY_MISMATCH",
        "expected_school_name": expected,
        "printed_text": printed,
        "sha256": digest,
        "sample_portrait": bool(inspected.get("sample_portrait")),
        "r4_reported_text": inspected.get("r4_reported_text", ""),
        "r4_report_matches_image": inspected.get("r4_report_matches_image"),
        "confirmed_records": confirmed,
        "approved_for": inspected.get("approved_for", ""),
    }
    return {"template": template, "identity": identity}
