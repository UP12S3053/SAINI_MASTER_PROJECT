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
        workspace = Path(workspace)
        assert_development_path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace
        self.engine = IdentityEngine(workspace / "identity.sqlite", workspace / "PHOTO_LIBRARY")

    def close(self):
        self.engine.close()

    def enroll_table(self, table_path, photo_dir):
        table_path = Path(table_path)
        photo_dir = Path(photo_dir)
        assert_development_path(table_path)
        assert_development_path(photo_dir)
        results = []
        for raw in read_table(table_path):
            results.append(self._enroll_row(raw, photo_dir))
        return results

    def promote(self, school, session, visible_id, new_class, new_roll):
        try:
            moved = step_reassign_mixed(self.engine, school, session, visible_id, new_class, _roll(new_roll))
        except IdentityError as exc:
            return self._failure(exc)
        return self._success(moved, {})

    def run_legacy_baseline(self, entry):
        refuse_legacy_entry(entry)
        raise LegacyPathError()

    def visible_history(self, school, session, visible_id):
        return [item["visible_id"] for item in self.engine.history(school, session, visible_id)]

    def _enroll_row(self, raw, photo_dir):
        try:
            school = str(raw.get("school_code") or "").strip()
            session = str(raw.get("session") or "").strip()
            class_name = str(raw.get("class") or "").strip()
            roll = _roll(raw.get("roll_number"))
            name = raw.get("student_name")
            father = raw.get("father_name")
            photo_name = str(raw.get("photo_file") or "").strip()
            source = None
            if photo_name:
                source = photo_dir / photo_name
                if not source.is_file():
                    raise IdentityError("photo_source_missing")
            created = stepE_enroll_from_sheet(
                self.engine, school, session, class_name, roll, name, father, source
            )
            return self._success(created, raw)
        except IdentityError as exc:
            return self._failure(exc)

    def _success(self, created, raw):
        prepared = prepare_generator_input(created, raw)
        consumed = consume_generator_input(prepared)
        result = {
            "ok": True,
            "message": "नामांकन हो गया।",
            "visible_id": created["visible_id"],
            "photo_path": created.get("photo_path") or "",
            "history": self.visible_history(created["school_code"], created["session"], created["visible_id"]),
            "generator_input": prepared,
            "generator_consumed": consumed,
        }
        self._reject_key(result)
        return result

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
