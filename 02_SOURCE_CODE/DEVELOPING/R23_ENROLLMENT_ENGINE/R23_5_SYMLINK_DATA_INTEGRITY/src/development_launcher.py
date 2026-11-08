# -*- coding: utf-8 -*-
"""R23.2 development enrollment launcher.

One teacher step: give a synthetic CSV or Excel file and a photo folder.
This module does not import the preserved baseline.
"""

import csv
from pathlib import Path

import openpyxl
from PIL import Image

from active_writers import stepE_enroll_from_sheet, step_reassign_mixed
from identity_engine import IdentityEngine, IdentityError, assert_development_path
from legacy_guard import refuse_legacy_entry
from path_guard import preflight_required_photos, require_excel, require_photo_dir, require_workspace
from controlled_writers import IdentityBypassError

MESSAGES = {
    "duplicate_identity": "यह रोल नंबर इसी कक्षा और सेशन में पहले से दर्ज है।",
    "roll_out_of_range": "रोल नंबर केवल 1 से 999 तक चलता है।",
    "roll_invalid": "रोल नंबर सही अंक नहीं है।",
    "roll_limit_pending_user_approval": "Nursery, LKG और UKG की रोल सीमा अभी बंद है।",
    "photo_source_missing": "फोटो फ़ाइल नहीं मिली। रिकॉर्ड नहीं बना।",
    "photo_exists": "इस नाम की फोटो पहले से है। पुरानी फ़ाइल नहीं बदली गई।",
    "class_not_exact": "कक्षा का नाम मान्य सूची में नहीं है।",
    "name_invalid": "छात्र का नाम खाली नहीं हो सकता।",
    "father_invalid": "पिता का नाम खाली नहीं हो सकता।",
    "legacy_entry_blocked": "पुराना प्रोग्राम इस वर्कफ़्लो से नहीं चलेगा।",
    "live_path_refused": "लाइव फ़ोल्डर पर काम बंद है।",
    "live_school_refused": "यह स्कूल कोड डेवलपमेंट में बंद है।",
}


class DevelopmentLauncher:
    def __init__(self, workspace):
        self.workspace = require_workspace(workspace)
        self.engine = None

    def close(self):
        if self.engine is not None:
            self.engine.close()

    def _engine(self):
        raise IdentityBypassError("writer_blocked")

    def enroll_table(self, table_path, photo_dir):
        raise IdentityBypassError("writer_blocked")

    def promote(self, school, session, visible_id, new_class, new_roll):
        raise IdentityBypassError("writer_blocked")

    def run_legacy_baseline(self, entry):
        raise IdentityBypassError("writer_blocked")

    def visible_history(self, school, session, visible_id):
        raise IdentityBypassError("writer_blocked")

    def _enroll_row(self, raw, photo_dir):
        raise IdentityBypassError("writer_blocked")

    def _success(self, created, raw):
        raise IdentityBypassError("writer_blocked")

    def _failure(self, exc):
        return {"ok": False, "code": exc.code, "message": MESSAGES.get(exc.code, exc.code)}

    @staticmethod
    def _reject_key(result):
        if "permanent_key" in str(result):
            raise IdentityError("key_leak_blocked")


class LegacyPathError(IdentityError):
    def __init__(self):
        super().__init__("legacy_entry_blocked")


def read_table(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() == ".xlsx":
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = book.active
            rows = list(sheet.iter_rows(values_only=True))
        finally:
            book.close()
        if not rows:
            return []
        header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        parsed = []
        for raw in rows[1:]:
            if raw is None or all(cell is None or str(cell).strip() == "" for cell in raw):
                continue
            parsed.append({
                header[index]: "" if index >= len(raw) or raw[index] is None else raw[index]
                for index in range(len(header))
            })
        return parsed
    raise IdentityError("table_invalid")


def _roll(value):
    if isinstance(value, bool):
        raise IdentityError("roll_invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    raise IdentityError("roll_invalid")


def prepare_generator_input(created, raw):
    return {
        "school_code": created["school_code"],
        "student_unique_id": created["visible_id"],
        "student_name": created["student_name"],
        "father_name": created["father_name"],
        "class": created["class_name"],
        "roll_number": created["roll_number"],
        "STUDENT_PHOTO_PATH": created.get("photo_path") or "",
        "mob_number": str(raw.get("mob_number") or ""),
        "address": str(raw.get("address") or ""),
    }


def consume_generator_input(row):
    """Read the same student fields as the generator, without drawing a card."""
    consumed = {
        "student_unique_id": row.get("student_unique_id", "Unknown"),
        "student_name": str(row.get("student_name", "")),
        "father_name": str(row.get("father_name", "")),
        "class": str(row.get("class", "")),
        "roll_number": str(row.get("roll_number", "")),
        "school_code": str(row.get("school_code", "")).strip(),
        "photo": str(row.get("STUDENT_PHOTO_PATH", "") or row.get("OK", "")).strip(),
        "mob_number": str(row.get("mob_number", "")),
        "address": str(row.get("address", "")),
    }
    if not consumed["student_unique_id"] or consumed["student_unique_id"] == "Unknown":
        raise IdentityError("generator_id_missing")
    photo = consumed["photo"]
    if photo:
        if not Path(photo).is_file():
            raise IdentityError("generator_photo_missing")
        with Image.open(photo) as image:
            image.load()
            consumed["photo_size"] = image.size
    return consumed
