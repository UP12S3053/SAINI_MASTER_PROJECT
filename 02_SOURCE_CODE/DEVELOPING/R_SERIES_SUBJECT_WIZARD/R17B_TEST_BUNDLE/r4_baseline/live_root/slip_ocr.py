#!/usr/bin/env python3
"""
SAINI RETURNED SLIP OCR
=======================
Scan teacher-filled slips with Gemini Vision.

Folders:
  ID_CARD_PROJECT / RETURNED_SLIPS / {SCHOOL_CODE} / *.jpg
      first data slip (Mode C)
  ID_CARD_PROJECT / RETURNED_CORRECTIONS / {SCHOOL_CODE} / *.jpg
      ID card correction slip (Mode D)
  ID_CARD_PROJECT / CORRECTION_SLIPS / ID_CARD_CORRECTION_SLIP_A4.pdf
      blank print template

Replace PASTE_YOUR_GEMINI_API_KEY_HERE in saini_config.json
or set env GEMINI_API_KEY.

pip install google-genai pillow openpyxl pandas
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import numbers

try:
    from school_status import mark as status_mark
except ImportError:
    def status_mark(*args, **kwargs):
        return {}

# ---------- config ----------
DEFAULT_BASE = Path(__file__).resolve().parent / "candidate_data"
BASE_PROJECT = Path(os.environ.get("SAINI_BASE_PROJECT", str(DEFAULT_BASE)))
CFG_PATH = Path(os.environ.get("SAINI_CONFIG", str(BASE_PROJECT / "saini_config.json")))

CFG: dict[str, Any] = {}
if CFG_PATH.exists():
    try:
        CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        CFG = {}

if CFG.get("BASE_PROJECT"):
    BASE_PROJECT = Path(CFG["BASE_PROJECT"])

RETURNED_SLIPS = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\RETURNED_SLIPS")
RETURNED_CORRECTIONS = BASE_PROJECT / "RETURNED_CORRECTIONS"
CORRECTION_SLIPS = BASE_PROJECT / "CORRECTION_SLIPS"
STUDENT_DATABASE = Path(CFG.get("STUDENT_DATABASE") or (BASE_PROJECT.parent / "student_data.xlsx"))
RAW_OCR_EXCEL = BASE_PROJECT / "WHATSAP" / "RAW_TEXT.xlsx"
RAW_CORR_EXCEL = BASE_PROJECT / "WHATSAP" / "RAW_CORRECTIONS.xlsx"
SCHOOL_CSV_ROOT = Path(os.environ.get("SAINI_SCHOOL_CSV_ROOT", str(BASE_PROJECT / "CSV")))
DEMO_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"

# Option C journal and verifier live beside this source in option_c_modules.
_OPTION_C_MODULES = Path(__file__).resolve().parent / "option_c_modules"
if _OPTION_C_MODULES.is_dir() and str(_OPTION_C_MODULES) not in sys.path:
    sys.path.insert(0, str(_OPTION_C_MODULES))
try:
    from journal import create_journal, complete_journal, mark_recovery_required, load_journal, update_journal
    from gate import authorize as gate_authorize
    from safety import make_approval, validate_approval, school_batch_lock, recovery_school_batch_lock
except ImportError as _option_c_import_error:
    create_journal = complete_journal = mark_recovery_required = load_journal = update_journal = gate_authorize = None
    make_approval = validate_approval = school_batch_lock = recovery_school_batch_lock = None
    _OPTION_C_IMPORT_ERROR = _option_c_import_error
else:
    _OPTION_C_IMPORT_ERROR = None

JOURNAL_ROOT = Path(os.environ.get("SAINI_OPTION_C_JOURNAL", str(BASE_PROJECT / "OPTION_C_JOURNAL")))


def _log(msg: str):
    print(f"{datetime.now().strftime('%H:%M:%S')} | {msg}")


def _cell_text(value: Any) -> str:
    """Stable cell representation for read-back comparisons; blanks stay blank."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _frame_rows_match(expected: pd.DataFrame, actual: pd.DataFrame) -> bool:
    """Compare ordered row payloads and headers, not just row counts or identities."""
    if list(expected.columns) != list(actual.columns) or len(expected) != len(actual):
        return False
    for row_index in range(len(expected)):
        for column in expected.columns:
            if _cell_text(expected.iloc[row_index][column]) != _cell_text(actual.iloc[row_index][column]):
                return False
    return True


def _payload_digest(rows: list[dict]) -> str:
    canonical = [
        {str(k): _cell_text(v) for k, v in sorted(row.items(), key=lambda item: str(item[0]))}
        for row in rows
    ]
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _correction_fields(rec: dict) -> set[str]:
    raw = rec.get("fields_ticked", "")
    values = list(raw) if isinstance(raw, (list, tuple, set)) else str(raw or "").split(",")
    allowed = {"student_name", "father_name", "class", "address", "mob_number"}
    aliases = {"contact": "mob_number", "mobile": "mob_number", "name": "student_name"}
    result = set()
    for value in values:
        key = re.sub(r"\s+", "_", str(value or "").strip().lower())
        if not key:
            continue
        key = aliases.get(key, key)
        if key not in allowed:
            raise RuntimeError(f"correction contains unsupported ticked field: {key}")
        result.add(key)
    if not result:
        raise RuntimeError("correction row has no recognized ticked fields")
    for field in result:
        if not str(rec.get(field) or "").strip():
            raise RuntimeError(f"correction ticked field has no RIGHT value: {field}")
    return result


def _is_gemini_key(k: str) -> bool:
    # 2026 AI Studio: AQ. auth keys. Purani: AIza
    return k.startswith("AQ.") or k.startswith("AIza")


def _pick_api_key() -> str:
    """Read only the explicitly selected config or environment; never scan sibling production configs."""
    raw_candidates = [
        (CFG.get("GEMINI_API_KEY"), f"config:{CFG_PATH}"),
        (os.environ.get("GEMINI_API_KEY"), "env:GEMINI_API_KEY"),
        (os.environ.get("GOOGLE_API_KEY"), "env:GOOGLE_API_KEY"),
    ]
    for val, src in raw_candidates:
        k = str(val or "").strip().strip('"').strip("'")
        if not k or k in (DEMO_KEY, "YOUR_API_KEY", "demo"):
            continue
        if _is_gemini_key(k):
            _log(f"Gemini API key configured from {src}; key material redacted.")
            return k
        _log(f"Ignored Gemini key candidate from {src}; key material redacted.")
    return DEMO_KEY

GEMINI_API_KEY = _pick_api_key()
GEMINI_MODEL = CFG.get("GEMINI_MODEL") or "gemini-3.6-flash"

PROMPT = """You are reading a scanned Indian school teacher slip (Student Data Slip).
The slip has a PRE-PRINTED Photo No. and handwritten fields.

Extract EVERY student slip on this page (usually up to 10 cards).
Return ONLY valid JSON:
{
  "school_code": "",
  "page_label": "",
  "students": [
    {
      "student_unique_id": "",
      "student_name": "",
      "father_name": "",
      "address": "",
      "mob_number": "",
      "class": "",
      "section": ""
    }
  ]
}

Rules:
- student_unique_id is the printed Photo No. (keep letters+digits, uppercase, no spaces).
- Names and address in CAPITAL English letters if possible. Keep Hindi if that is what is written.
- mob_number: digits only, 10 digits if possible.
- If a field is blank, use empty string. Do not invent data.
- Ignore empty slip boxes.
"""

CORRECTION_PROMPT = """You are reading a scanned Indian school ID CARD CORRECTION SLIP.
Title is ID CARD CORRECTION SLIP. Each page has up to 10 student blocks.
Each block has PHOTO NO and fields:
  STUDENT NAME, FATHER NAME, CLASS, ADDRESS, CONTACT
Each field has WRONG (old) and RIGHT (new) boxes. A checkbox may be ticked.

Extract ONLY blocks that have a Photo No. and at least one RIGHT value written.
Return ONLY valid JSON:
{
  "school_code": "",
  "school_name": "",
  "class": "",
  "section": "",
  "teacher": "",
  "date": "",
  "corrections": [
    {
      "student_unique_id": "",
      "student_name": "",
      "father_name": "",
      "class": "",
      "address": "",
      "mob_number": "",
      "fields_ticked": []
    }
  ]
}

Rules:
- student_unique_id is PHOTO NO. Keep letters+digits, uppercase, no spaces.
- For each field, use the RIGHT / à¤¨à¤¯à¤¾ value if it is written. Ignore WRONG / à¤ªà¥à¤°à¤¾à¤¨à¤¾.
- If RIGHT is blank, leave that field empty. Do not copy WRONG into the result.
- CONTACT = mob_number, digits only.
- fields_ticked: list which fields had a tick, e.g. ["student_name", "father_name"].
- Do not invent data. Skip empty blocks. Names in CAPITAL English if possible.
"""


def key_ok() -> bool:
    k = (GEMINI_API_KEY or "").strip()
    return bool(k) and k not in (DEMO_KEY, "YOUR_API_KEY", "demo")


def extract_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def ocr_image(path: Path, prompt: str | None = None) -> dict:
    """Gemini Vision. Tries new google.genai then old google.generativeai."""
    prompt = prompt or PROMPT
    if not key_ok():
        raise RuntimeError(
            "Gemini API key demo hai. saini_config.json mein PASTE_YOUR_GEMINI_API_KEY_HERE "
            "ko apni asli key se badlo, ya env GEMINI_API_KEY set karo."
        )

    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = path.read_bytes()

    # New SDK
    try:
        from google import genai
        from google.genai import types
        # vertexai=False: Cloud OAuth / ADC mat use karo
        client = genai.Client(api_key=GEMINI_API_KEY, vertexai=False)
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return extract_json(resp.text or "")
    except ImportError:
        pass
    except Exception as e:
        _log(f"google.genai failed, trying old SDK: {e}")

    # Old SDK
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_API_KEY)
        model = genai_old.GenerativeModel(GEMINI_MODEL)
        from PIL import Image
        img = Image.open(path)
        resp = model.generate_content([prompt, img])
        return extract_json(getattr(resp, "text", "") or "")
    except Exception as e:
        raise RuntimeError(f"OCR failed for {path.name}: {e}") from e


def clean_uid(uid: str, school_code: str) -> str:
    u = re.sub(r"[^A-Za-z0-9]", "", str(uid or "")).upper()
    sc = school_code.upper()
    if u and not u.startswith(sc) and u.isdigit():
        # sometimes teacher writes only number
        return u
    return u


def clean_name(v: str) -> str:
    t = " ".join(str(v or "").strip().split())
    return t.upper()


def clean_mob(v: str) -> str:
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) >= 10:
        return d[-10:]
    return d


def list_scans(school_code: str, root: Path | None = None) -> list[Path]:
    folder = (root or RETURNED_SLIPS) / school_code.upper()
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            if p.name.startswith("_"):
                continue
            files.append(p)
    return files


def collect_students(school_code: str) -> tuple[list[dict], list[Path]]:
    files = list_scans(school_code)
    if not files:
        _log(f"No scans in {RETURNED_SLIPS / school_code.upper()}")
        return [], []

    rows = []
    ok_files = []
    for path in files:
        _log(f"OCR: {path.name}")
        try:
            data = ocr_image(path)
        except Exception as e:
            _log(str(e))
            continue
        students = data.get("students") or []
        if not students:
            _log(f"  no students found in {path.name}")
            continue
        for s in students:
            uid = clean_uid(s.get("student_unique_id", ""), school_code)
            name = clean_name(s.get("student_name", ""))
            father = clean_name(s.get("father_name", ""))
            if not uid and not name:
                continue
            rows.append({
                "school_code": school_code.upper(),
                "student_unique_id": uid,
                "student_name": name,
                "father_name": father,
                "class": clean_name(s.get("class", "")),
                "section": clean_name(s.get("section", "")),
                "address": clean_name(s.get("address", "")),
                "mob_number": clean_mob(s.get("mob_number", "")),
                "source": "slip_ocr",
                "scan_file": path.name,
            })
        ok_files.append(path)
        _log(f"  extracted {len(students)} slips")
    return rows, ok_files


def _col_map(sheet) -> dict[str, int]:
    m = {}
    for i, cell in enumerate(sheet[1], 1):
        key = str(cell.value or "").strip()
        if key:
            m[key] = i
    return m


def _ensure_headers(sheet, needed: list[str]):
    headers = [str(c.value or "").strip() for c in sheet[1]]
    last = len(headers)
    for name in needed:
        if name not in headers:
            last += 1
            sheet.cell(1, last, name)
            headers.append(name)


def update_student_excel(school_code: str, rows: list[dict], *, correction: bool = False) -> tuple[int, int]:
    """Update existing UID rows; correction mode changes only explicitly ticked fields."""
    if not rows:
        return 0, 0
    if not STUDENT_DATABASE.exists():
        raise FileNotFoundError(
            f"student_data.xlsx missing: {STUDENT_DATABASE}; refusing false-success return"
        )

    # Reject duplicate incoming identities before changing any sink.
    incoming_keys = set()
    duplicate_incoming = set()
    for rec in rows:
        uid = str(rec.get("student_unique_id") or "").strip().upper()
        rec_school = str(rec.get("school_code") or school_code).strip().upper()
        if not uid:
            continue
        key = (rec_school, uid)
        if key in incoming_keys:
            duplicate_incoming.add(key)
        incoming_keys.add(key)
    if duplicate_incoming:
        raise RuntimeError(
            "duplicate incoming school_code + student_unique_id keys; refusing ambiguous batch: "
            + repr(sorted(duplicate_incoming)[:10])
        )

    book = load_workbook(STUDENT_DATABASE)
    sheet = book.active
    needed = ["timestamp", "school_code", "student_unique_id", "student_name",
              "father_name", "class", "address", "mob_number", "source"]
    existing_headers = {str(cell.value or "").strip() for cell in sheet[1]}
    if "school_code" not in existing_headers or "student_unique_id" not in existing_headers:
        raise RuntimeError(
            "safe composite matching requires existing school_code and student_unique_id headers; "
            "workbook left unsaved"
        )
    _ensure_headers(sheet, needed)
    cmap = _col_map(sheet)

    # Snapshot pre-existing populated cells and workbook structure across ALL sheets.
    # Formula text is captured as formula text (not cached values) and is compared
    # with data_only=False after save. This avoids false failures on formula cells.
    preserved_cells = {}
    preserved_styles = {}
    sheet_structure = {}
    for existing_sheet in book.worksheets:
        sheet_structure[existing_sheet.title] = {
            "sheet_state": existing_sheet.sheet_state,
            "merged_ranges": tuple(sorted(str(rng) for rng in existing_sheet.merged_cells.ranges)),
            "freeze_panes": str(existing_sheet.freeze_panes or ""),
            "sheet_format": (existing_sheet.sheet_format.defaultRowHeight, existing_sheet.sheet_format.defaultColWidth),
            "row_dimensions": tuple(sorted((int(k), v.height, v.hidden, v.outlineLevel) for k, v in existing_sheet.row_dimensions.items())),
            "column_dimensions": tuple(sorted((str(k), v.width, v.hidden, v.outlineLevel) for k, v in existing_sheet.column_dimensions.items())),
        }
        for existing_row in existing_sheet.iter_rows():
            for existing_cell in existing_row:
                if existing_cell.value is not None and str(existing_cell.value).strip() != "":
                    preserved_cells[(existing_sheet.title, existing_cell.coordinate)] = existing_cell.value
                if existing_cell.has_style:
                    preserved_styles[(existing_sheet.title, existing_cell.coordinate)] = (
                        tuple(existing_cell._style or ()), existing_cell.number_format,
                    )
    expected_written_cells = []

    # Composite identity prevents a UID from one school matching another school.
    # Ambiguous duplicate keys are rejected before workbook.save().
    uid_to_row = {}
    uid_col = cmap.get("student_unique_id")
    school_col = cmap.get("school_code")
    if not uid_col or not school_col:
        raise RuntimeError("school_code and student_unique_id columns are required for safe matching")

    target_school = str(school_code or "").strip().upper()

    incoming_schools = {
        str(rec.get("school_code") or school_code).strip().upper()
        for rec in rows
    }
    if incoming_schools != {target_school}:
        raise RuntimeError(
            "incoming records contain unexpected school_code; refusing update"
        )

    duplicate_keys = set()
    uid_to_row = {}
    for r in range(2, sheet.max_row + 1):
        uid = str(sheet.cell(r, uid_col).value or "").strip().upper()
        existing_school = str(
            sheet.cell(r, school_col).value or ""
        ).strip().upper()

        if existing_school != target_school:
            continue

        if uid:
            key = (existing_school, uid)
            if key in uid_to_row:
                duplicate_keys.add(key)
            else:
                uid_to_row[key] = r

    if duplicate_keys:
        sample = sorted(duplicate_keys)[:10]
        raise RuntimeError(
            "duplicate school_code + student_unique_id keys for target school; "
            "refusing ambiguous update: " + repr(sample)
        )
    updated = added = 0
    field_map = {
        "student_name": "student_name",
        "father_name": "father_name",
        "class": "class",
        "address": "address",
        "mob_number": "mob_number",
        "source": "source",
    }
    if correction:
        for rec in rows:
            uid = str(rec.get("student_unique_id") or "").strip().upper()
            rec_school = str(rec.get("school_code") or school_code).strip().upper()
            if not uid or (rec_school, uid) not in uid_to_row:
                raise RuntimeError("correction UID does not exist in student database; refusing to add a new student")
            _correction_fields(rec)

    for rec in rows:
        uid = str(rec.get("student_unique_id") or "").strip().upper()
        rec_school = str(rec.get("school_code") or school_code).strip().upper()
        key = (rec_school, uid)
        if uid and key in uid_to_row:
            r = uid_to_row[key]
            selected_correction_fields = _correction_fields(rec) if correction else set()
            for src, colname in field_map.items():
                if correction and (src == "source" or src not in selected_correction_fields):
                    continue
                col = cmap.get(colname)
                if not col:
                    continue
                val = rec.get(src, "")
                if val is None or not str(val).strip():
                    continue
                cell = sheet.cell(r, col)
                if not correction:
                    # Normal OCR never overwrites populated/manual cells.
                    existing = cell.value
                    if existing is not None and str(existing).strip():
                        continue
                if src == "mob_number":
                    cell.number_format = numbers.FORMAT_TEXT
                    cell.value = str(val)
                else:
                    cell.value = val
                expected_written_cells.append((cell.coordinate, cell.value))
            updated += 1
        else:
            r = sheet.max_row + 1
            for colname, val in rec.items():
                if colname in ("scan_file", "section", "timestamp"):
                    continue
                col = cmap.get(colname)
                if col:
                    cell = sheet.cell(r, col)
                    if colname == "mob_number":
                        cell.number_format = numbers.FORMAT_TEXT
                    cell.value = val
                    expected_written_cells.append((cell.coordinate, cell.value))
            if uid:
                uid_to_row[(rec_school, uid)] = r
            added += 1

    book.save(STUDENT_DATABASE)

    # Independent workbook read-back for this write: verify every nonblank batch UID
    # is present under the same school composite key before returning success.
    check_book = load_workbook(STUDENT_DATABASE, read_only=False, data_only=False)
    try:
        if check_book.sheetnames != book.sheetnames:
            raise RuntimeError("Excel workbook sheet names/order changed during update")
        written_coordinates = {coordinate for coordinate, _ in expected_written_cells}
        for title, expected_structure in sheet_structure.items():
            actual_sheet = check_book[title]
            actual_structure = {
                "sheet_state": actual_sheet.sheet_state,
                "merged_ranges": tuple(sorted(str(rng) for rng in actual_sheet.merged_cells.ranges)),
                "freeze_panes": str(actual_sheet.freeze_panes or ""),
                "sheet_format": (actual_sheet.sheet_format.defaultRowHeight, actual_sheet.sheet_format.defaultColWidth),
                "row_dimensions": tuple(sorted((int(k), v.height, v.hidden, v.outlineLevel) for k, v in actual_sheet.row_dimensions.items())),
                "column_dimensions": tuple(sorted((str(k), v.width, v.hidden, v.outlineLevel) for k, v in actual_sheet.column_dimensions.items())),
            }
            if actual_structure != expected_structure:
                raise RuntimeError(f"Excel workbook structure changed on sheet {title!r}")
        for (title, coordinate), expected_value in preserved_cells.items():
            if title == sheet.title and coordinate in written_coordinates:
                continue
            actual_value = check_book[title][coordinate].value
            if _cell_text(actual_value) != _cell_text(expected_value):
                raise RuntimeError(f"Excel preserved-cell mismatch at {title}!{coordinate}; refusing sink verification")
        for (title, coordinate), expected_style in preserved_styles.items():
            if title == sheet.title and coordinate in written_coordinates:
                # Writing into blank cells is allowed; formatting must still remain
                # the same except the explicit mobile-number text format change.
                actual_cell = check_book[title][coordinate]
                actual_style = (tuple(actual_cell._style or ()), actual_cell.number_format)
                if expected_style != actual_style and not (
                    coordinate in written_coordinates and actual_cell.number_format == numbers.FORMAT_TEXT
                    and expected_style[0][:3] == actual_style[0][:3]
                    and expected_style[0][4:] == actual_style[0][4:]
                ):
                    raise RuntimeError(f"Excel cell style changed at {title}!{coordinate}")
                continue
            actual_cell = check_book[title][coordinate]
            actual_style = (tuple(actual_cell._style or ()), actual_cell.number_format)
            if expected_style != actual_style:
                raise RuntimeError(f"Excel cell style changed at {title}!{coordinate}")
        check_sheet = check_book[sheet.title]
        check_cmap = _col_map(check_sheet)
        check_uid_col = check_cmap.get("student_unique_id")
        check_school_col = check_cmap.get("school_code")
        if not check_uid_col or not check_school_col:
            raise RuntimeError("Excel read-back missing composite identity columns")

        # Verify each value this operation intended to write. Preserved cells on
        # every worksheet were already compared above using formula-aware loading.
        for coordinate, expected_value in expected_written_cells:
            actual_value = check_sheet[coordinate].value
            if _cell_text(actual_value) != _cell_text(expected_value):
                raise RuntimeError(
                    f"Excel write payload mismatch at {coordinate}; refusing sink verification"
                )

        written_keys = set()
        for rr in range(2, check_sheet.max_row + 1):
            check_uid = str(check_sheet.cell(rr, check_uid_col).value or "").strip().upper()
            check_school = str(check_sheet.cell(rr, check_school_col).value or "").strip().upper()
            if check_uid and check_school:
                written_keys.add((check_school, check_uid))
        missing_keys = sorted(incoming_keys - written_keys)
        if missing_keys:
            raise RuntimeError(
                "Excel read-back missing batch identities: " + repr(missing_keys[:10])
            )
    finally:
        check_book.close()

    _log(f"student_data.xlsx written and read-back checked â†’ updated {updated}, added {added}")
    return updated, added


_RAW_BATCH_COLUMN = "_optionc_batch_id"


def _write_raw_batch(path: Path, rows: list[dict], batch_id: str | None, sink_label: str) -> bool:
    """Atomically append only missing rows for a stable batch; exact retries are verified.

    The private batch column makes a retry distinguishable from a later legitimate OCR
    of the same student. Reusing a batch ID with changed content fails closed.
    """
    if not rows:
        return False
    if not batch_id:
        # Backwards-compatible helper use in unit tests; production paths always pass
        # the journal batch ID so recovery is idempotent.
        batch_id = "UNBOUND-" + uuid.uuid4().hex
    incoming = pd.DataFrame(rows).fillna("")
    if _RAW_BATCH_COLUMN in incoming.columns:
        raise RuntimeError(f"reserved raw sink column present in input: {_RAW_BATCH_COLUMN}")
    incoming[_RAW_BATCH_COLUMN] = str(batch_id)
    keys = []
    for rec in rows:
        school = _cell_text(rec.get("school_code", "")).upper()
        uid = _cell_text(rec.get("student_unique_id", rec.get("unique_id", ""))).upper()
        if not school or not uid:
            raise RuntimeError(f"{sink_label} row missing composite identity")
        key = (school, uid)
        if key in keys:
            raise RuntimeError(f"{sink_label} batch contains duplicate composite identity: {key}")
        keys.append(key)

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_excel(path, dtype=str).fillna("")
    else:
        old = pd.DataFrame()
    columns = list(old.columns) + [c for c in incoming.columns if c not in old.columns]
    old = old.reindex(columns=columns, fill_value="")
    incoming = incoming.reindex(columns=columns, fill_value="")
    batch_rows = old[old[_RAW_BATCH_COLUMN].astype(str) == str(batch_id)] if _RAW_BATCH_COLUMN in old.columns else old.iloc[0:0]
    existing_by_key = {}
    for _, row in batch_rows.iterrows():
        key = (_cell_text(row.get("school_code", "")).upper(),
               _cell_text(row.get("student_unique_id", row.get("unique_id", ""))).upper())
        if key in existing_by_key:
            raise RuntimeError(f"{sink_label} has duplicate rows for batch {batch_id} and identity {key}")
        existing_by_key[key] = row.to_dict()

    append_rows = []
    incoming_columns = list(incoming.columns)
    for idx, row in incoming.iterrows():
        key = keys[idx]
        expected = row.to_dict()
        if key in existing_by_key:
            actual = existing_by_key[key]
            if any(_cell_text(actual.get(col, "")) != _cell_text(expected.get(col, "")) for col in incoming_columns):
                raise RuntimeError(f"{sink_label} batch ID reused with conflicting payload: {batch_id} / {key}")
            continue
        append_rows.append(expected)

    combined = pd.concat([old, pd.DataFrame(append_rows, columns=columns)], ignore_index=True).fillna("")
    if not append_rows:
        # Exact same-batch retry: verify current on-disk workbook and do not append.
        current = pd.read_excel(path, dtype=str).fillna("")
        if not _frame_rows_match(combined.reset_index(drop=True), current.reindex(columns=columns, fill_value="").reset_index(drop=True)):
            raise RuntimeError(f"{sink_label} idempotent retry read-back mismatch")
        _log(f"{sink_label} exact batch retry verified without append: batch={batch_id}")
        return True

    tmp = path.with_name(path.stem + ".optionc_tmp.xlsx")
    try:
        combined.to_excel(tmp, index=False)
        staged = pd.read_excel(tmp, dtype=str).fillna("")
        if not _frame_rows_match(combined.reset_index(drop=True), staged.reset_index(drop=True)):
            raise RuntimeError(f"{sink_label} staged exact-payload read-back mismatch")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    final = pd.read_excel(path, dtype=str).fillna("")
    if not _frame_rows_match(combined.reset_index(drop=True), final.reset_index(drop=True)):
        raise RuntimeError(f"{sink_label} final exact-payload read-back mismatch")
    _log(f"{sink_label} batch payload verified: batch={batch_id}; added={len(append_rows)}; total={len(rows)}")
    return True


def write_raw_ocr(rows: list[dict], batch_id: str | None = None):
    return _write_raw_batch(RAW_OCR_EXCEL, rows, batch_id, "RAW_TEXT.xlsx")

def write_school_csv(rows: list[dict], school_code: str, *, correction: bool = False):
    # Append to an existing Individual CSV; never create a Common CSV.
    if not rows:
        return False

    code = str(school_code or "").strip().upper()
    if not code or any(ch in code for ch in ("/", "\\", ":", "\x00")) or code in (".", ".."):
        _log("Individual CSV skipped: invalid school code.")
        return False

    target = SCHOOL_CSV_ROOT / f"{code}.csv"
    if not target.is_file() or target.stat().st_size == 0:
        _log(f"Individual CSV missing; CSV sink skipped without blocking other processing: {target}")
        return False

    aliases = {
        "student_name": ["student_name"],
        "class": ["class"],
        "school_code": ["school_code"],
        "mob_number": ["mob_number", "mobile"],
        "address": ["address"],
        "father_name": ["father_name"],
        "student_unique_id": ["student_unique_id", "unique_id"],
        "mother_name": ["mother_name"],
    }
    old = pd.read_csv(target, dtype=str, keep_default_na=False, low_memory=False)
    headers = list(old.columns)
    lower = {str(h).lower().strip(): h for h in headers}
    school_header = lower.get("school_code")
    uid_header = lower.get("student_unique_id") or lower.get("unique_id")
    if not school_header or not uid_header:
        raise RuntimeError(f"Individual CSV missing required school_code/student_unique_id headers: {target}")

    def norm(value):
        return str(value or "").strip().upper()

    existing_keys = set()
    for _, old_row in old.iterrows():
        old_school = norm(old_row.get(school_header, ""))
        old_uid = norm(old_row.get(uid_header, ""))
        if old_school and old_uid:
            existing_keys.add((old_school, old_uid))

    new_lines = []
    batch_keys = {}
    verified_existing = 0
    skipped_invalid = 0
    correction_modified = False
    compared_headers = [
        lower[candidate.lower()]
        for candidates in aliases.values()
        for candidate in candidates
        if candidate.lower() in lower
    ]

    def make_csv_line(rec):
        line = {h: "" for h in headers}
        for logical, candidates in aliases.items():
            val = rec.get(logical, "")
            if val is None:
                val = ""
            for candidate in candidates:
                actual = lower.get(candidate.lower())
                if actual:
                    line[actual] = str(val)
                    break
        # Timestamp intentionally remains untouched.
        return line

    def same_payload(existing_row, expected_line):
        return all(_cell_text(existing_row.get(h, "")) == _cell_text(expected_line.get(h, ""))
                   for h in compared_headers)

    for rec in rows:
        rec_school = norm(rec.get("school_code") or code)
        uid = norm(rec.get("student_unique_id") or rec.get("unique_id"))
        if rec_school != code or not uid:
            skipped_invalid += 1
            continue
        key = (rec_school, uid)
        line = make_csv_line(rec)
        if key in batch_keys:
            if not same_payload(batch_keys[key], line):
                raise RuntimeError(f"Individual CSV incoming duplicate identity has conflicting payload: {key}")
            continue
        batch_keys[key] = line
        if correction:
            if key not in existing_keys:
                raise RuntimeError(f"correction UID missing from Individual CSV; refusing to add a student: {key}")
            matches = old[(old[school_header].map(norm) == rec_school) & (old[uid_header].map(norm) == uid)]
            if len(matches) != 1:
                raise RuntimeError(f"Individual CSV existing identity is not unique: {key}")
            selected = _correction_fields(rec)
            row_index = matches.index[0]
            for field in selected:
                actual_col = next((lower[candidate.lower()] for candidate in aliases.get(field, [field]) if candidate.lower() in lower), None)
                if not actual_col:
                    raise RuntimeError(f"Individual CSV missing correction field column: {field}")
                old.at[row_index, actual_col] = str(rec.get(field) or "")
            correction_modified = True
            verified_existing += 1
            continue
        if key in existing_keys:
            matches = old[(old[school_header].map(norm) == rec_school) & (old[uid_header].map(norm) == uid)]
            if len(matches) != 1:
                raise RuntimeError(f"Individual CSV existing identity is not unique: {key}")
            if not same_payload(matches.iloc[0].to_dict(), line):
                raise RuntimeError(f"Individual CSV existing identity has different payload; refusing to claim verification: {key}")
            verified_existing += 1
            continue
        new_lines.append(line)

    if not batch_keys or skipped_invalid:
        _log(f"Individual CSV not verified: valid={len(batch_keys)} invalid={skipped_invalid}: {target}")
        return False

    if not new_lines and not correction_modified:
        final_check = pd.read_csv(target, dtype=str, keep_default_na=False, low_memory=False)
        if list(final_check.columns) != headers or not _frame_rows_match(old.reset_index(drop=True), final_check.reset_index(drop=True)):
            raise RuntimeError(f"Individual CSV existing-payload final read-back mismatch: {target}")
        _log(f"Individual CSV exact existing payload verified: {target}; existing={verified_existing}")
        return True

    combined = pd.concat([old, pd.DataFrame(new_lines, columns=headers)], ignore_index=True)
    expected_rows = len(combined)
    temp_path = target.with_name(target.name + ".optionc_tmp")
    try:
        combined.to_csv(temp_path, index=False)
        check = pd.read_csv(temp_path, dtype=str, keep_default_na=False, low_memory=False)
        if list(check.columns) != headers or len(check) != expected_rows:
            raise RuntimeError(f"Individual CSV read-back mismatch: {target}")
        if not _frame_rows_match(combined.reset_index(drop=True), check.reset_index(drop=True)):
            raise RuntimeError(f"Individual CSV exact payload read-back mismatch: {target}")
        check_keys = {
            (norm(r.get(school_header, "")), norm(r.get(uid_header, "")))
            for _, r in check.iterrows()
        }
        missing = [key for key in batch_keys if key not in check_keys]
        if missing:
            raise RuntimeError(f"Individual CSV read-back missing batch identities: {missing[:10]}")
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    final_check = pd.read_csv(target, dtype=str, keep_default_na=False, low_memory=False)
    if list(final_check.columns) != headers or len(final_check) != expected_rows:
        raise RuntimeError(f"Individual CSV final read-back mismatch: {target}")
    if not _frame_rows_match(combined.reset_index(drop=True), final_check.reset_index(drop=True)):
        raise RuntimeError(f"Individual CSV final exact payload mismatch: {target}")
    _log(f"Individual CSV exact payload read-back verified: {target}; added={len(new_lines)}; already_verified={verified_existing}; invalid={skipped_invalid}")
    return True


def _piper_paths() -> tuple[Path, Path, Path]:
    """Resolve local Piper executable, voice model and its JSON config."""
    venv = Path(r"D:\PiperTTS\venv\Scripts")
    exe_candidates = [venv / "piper.exe", venv / "piper"]
    exe = next((x for x in exe_candidates if x.exists()), None)
    voices = Path(r"D:\PiperTTS\voices")
    model_candidates = [
        voices / "hi_IN-priyamvada-medium.onnx",
        voices / "hi_IN-priyamvada-medium" / "hi_IN-priyamvada-medium.onnx",
    ]
    model = next((x for x in model_candidates if x.exists()), None)
    if exe is None or model is None:
        raise RuntimeError(
            "Piper local setup not found. Expected D:\\PiperTTS\\venv\\Scripts\\piper.exe "
            "and D:\\PiperTTS\\voices\\hi_IN-priyamvada-medium.onnx."
        )
    config = Path(str(model) + ".json")
    if not config.exists():
        raise RuntimeError(f"Piper voice config missing: {config}")
    return exe, model, config


def _mobile_as_hindi_digits(value: str) -> str:
    digit_words = {
        "0": "à¤¶à¥‚à¤¨à¥à¤¯", "1": "à¤à¤•", "2": "à¤¦à¥‹", "3": "à¤¤à¥€à¤¨", "4": "à¤šà¤¾à¤°",
        "5": "à¤ªà¤¾à¤à¤š", "6": "à¤›à¤¹", "7": "à¤¸à¤¾à¤¤", "8": "à¤†à¤ ", "9": "à¤¨à¥Œ",
    }
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return " ".join(digit_words[d] for d in digits)


def _sanitize_piper_text(value: str) -> str:
    """Remove invalid Unicode surrogate/control characters before Piper/espeak."""
    value = str(value or "")
    value = value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    value = "".join(
        ch if (ch in "\\t\\r\\n" or ord(ch) >= 32) else " "
        for ch in value
    )
    return " ".join(value.split()).strip()


def _build_hindi_narration(rows: list[dict]) -> list[str]:
    """One plain Hindi narration passage per student; no intro/outro."""
    entries = []
    for rec in rows:
        student = str(rec.get("student_name", "") or "").strip()
        father = str(rec.get("father_name", "") or "").strip()
        student_class = str(rec.get("class", "") or "").strip()
        address = str(rec.get("address", "") or "").strip()
        mobile = _mobile_as_hindi_digits(rec.get("mob_number", ""))
        fields = []
        if student: fields.append(student)
        if father: fields.append(f"à¤ªà¤¿à¤¤à¤¾ {father}")
        if student_class: fields.append(f"à¤•à¤•à¥à¤·à¤¾ {student_class}")
        if address: fields.append(address)
        if mobile: fields.append(f"à¤®à¥‹à¤¬à¤¾à¤‡à¤² {mobile}")
        if fields:
            entries.append(", ".join(fields) + ".")
    return entries


def create_combined_audio(rows: list[dict], school_code: str) -> str | None:
    """Create local Piper Priyamvada speech using Python API, then combine to WAV/MP3.

    Uses PiperVoice.synthesize_wav directly instead of sending Unicode text to
    piper.exe stdin. This avoids Windows console/subprocess encoding issues.
    """
    if not rows:
        return None

    temp_dir = None
    try:
        import tempfile
        import wave
        import subprocess
        import shutil as _shutil
        from piper.voice import PiperVoice

        # Resolve model/config; direct Python API does not need piper.exe.
        _exe, model, config = _piper_paths()
        if not model.exists() or not config.exists():
            raise RuntimeError(f"Piper model/config missing: {model} | {config}")

        entries = [_sanitize_piper_text(item) for item in _build_hindi_narration(rows)]
        entries = [item for item in entries if item]
        if not entries:
            _log("Combined audio skipped: no requested fields found.")
            return None

        audio_dir = BASE_PROJECT / "WHATSAP" / "SLIP_AUDIO"
        audio_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = audio_dir / f"{school_code.upper()}_ALL_STUDENTS_PRIYAMVADA_{stamp}.wav"
        mp3_path = wav_path.with_suffix(".mp3")

        # Load the ONNX voice once for the entire batch.
        _log("Loading local Piper Priyamvada voice...")
        voice = PiperVoice.load(str(model))

        temp_dir = Path(tempfile.mkdtemp(prefix="piper_slips_", dir=str(audio_dir)))
        wav_parts = []

        for i, text in enumerate(entries, 1):
            part = temp_dir / f"part_{i:04d}.wav"
            # Python API handles Unicode Hindi directly; no console stdin.
            with wave.open(str(part), "wb") as out:
                voice.synthesize_wav(text, out)

            if not part.exists() or part.stat().st_size < 1000:
                raise RuntimeError(
                    f"Piper generated an empty/short WAV for student {i} "
                    f"(bytes={part.stat().st_size if part.exists() else 0})."
                )
            wav_parts.append(part)
            if i % 10 == 0 or i == len(entries):
                _log(f"Priyamvada voice: generated {i}/{len(entries)} student clips")

        # Combine PCM WAV clips. Stream each clip into the output to avoid
        # keeping the entire school audio in RAM.
        with wave.open(str(wav_parts[0]), "rb") as first:
            params = first.getparams()

        with wave.open(str(wav_path), "wb") as out:
            out.setparams(params)
            for idx, part in enumerate(wav_parts, 1):
                with wave.open(str(part), "rb") as clip:
                    clip_params = clip.getparams()
                    if (
                        clip_params.nchannels,
                        clip_params.sampwidth,
                        clip_params.framerate,
                        clip_params.comptype,
                    ) != (
                        params.nchannels,
                        params.sampwidth,
                        params.framerate,
                        params.comptype,
                    ):
                        raise RuntimeError(
                            "Piper produced incompatible WAV clip formats; cannot safely combine."
                        )
                    while True:
                        chunk = clip.readframes(16384)
                        if not chunk:
                            break
                        out.writeframesraw(chunk)

        # Create MP3 only if ffmpeg is installed; otherwise retain WAV.
        ffmpeg = _shutil.which("ffmpeg")
        if ffmpeg:
            result = subprocess.run(
                [
                    ffmpeg, "-y", "-i", str(wav_path),
                    "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            if result.returncode == 0 and mp3_path.exists() and mp3_path.stat().st_size > 1000:
                wav_path.unlink(missing_ok=True)
                _log(f"Combined Priyamvada MP3 created: {mp3_path}")
                return str(mp3_path)
            _log("FFmpeg MP3 conversion failed; retaining combined WAV.")

        _log(f"Combined Priyamvada WAV created: {wav_path} (install ffmpeg to also create MP3)")
        return str(wav_path)

    except Exception as e:
        _log(f"Priyamvada audio generation failed: {e}")
        return None
    finally:
        if temp_dir and temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)



def _request_batch_audio_approval(rows: list[dict], school_code: str, batch_id: str, kind_label: str) -> tuple[str | None, dict | None, bool]:
    """Create and explicitly approve audio bound to this exact batch and payload. Fail closed."""
    audio_file = None
    approval_evidence = None
    try:
        if not rows or make_approval is None or validate_approval is None:
            _log(f"{kind_label} audio approval unavailable; no sink writes will occur; input scans will remain in place.")
            return None, None, False
        audio_file = create_combined_audio(rows, school_code)
        if not audio_file:
            _log(f"{kind_label} audio generation failed; no sink writes will occur; input scans will remain in place.")
            return None, None, False
        approval_evidence = make_approval(
            batch_id=batch_id, school_code=school_code, audio_path=audio_file, rows=rows
        )
        print(f"\nPRIYAMVADA voice audio ready for {kind_label}:")
        print(audio_file)
        print("Please listen to the complete audio and verify this batch before approving.")
        choice = input(f"Approve this {kind_label} batch after listening? [Y/N]: ").strip().upper()
        if choice != "Y":
            _log(f"{kind_label} batch was not approved; no sink writes will occur; input scans will remain in place.")
            return audio_file, approval_evidence, False
        approval_evidence["approved"] = True
        if not validate_approval(
            approval_evidence, batch_id=batch_id, school_code=school_code,
            audio_path=audio_file, rows=rows
        ):
            _log(f"{kind_label} approval fingerprint mismatch; no sink writes will occur; input scans will remain in place.")
            return audio_file, approval_evidence, False
        _log(f"{kind_label} audio approval validated for batch {batch_id}; fingerprints rechecked.")
        return audio_file, approval_evidence, True
    except (EOFError, KeyboardInterrupt):
        _log(f"{kind_label} approval prompt interrupted; batch denied and no sinks will be written.")
        return audio_file, approval_evidence, False
    except Exception as exc:
        # Do not log exception text from external audio/config providers; it may contain sensitive data.
        _log(f"{kind_label} audio approval failed ({type(exc).__name__}); batch denied; no sink writes will occur and input scans will remain in place.")
        return audio_file, approval_evidence, False


def _begin_option_c_journal(school_code: str, rows: list[dict], kind: str, *, batch_id: str | None = None, approval_evidence: dict | None = None) -> dict:
    """Create a batch-bound journal before the first sink is mutated."""
    if any(x is None for x in (create_journal, complete_journal, mark_recovery_required, gate_authorize)):
        raise RuntimeError(f"Option C journal/Gate modules unavailable: {_OPTION_C_IMPORT_ERROR}")
    batch_id = batch_id or (datetime.now().strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex[:8])
    fingerprint = _payload_digest(rows)
    raw_path = RAW_CORR_EXCEL if kind == "correction" else RAW_OCR_EXCEL
    csv_path = SCHOOL_CSV_ROOT / f"{school_code}.csv"
    journal_path = JOURNAL_ROOT / f"{batch_id}.json"
    record = {
        "schema_version": 2, "batch_id": batch_id, "school_code": school_code,
        "content_fingerprint": fingerprint, "state": "PREPARED",
        "kind": kind, "recovery_required": False, "invalidated": False,
        "approval_evidence": approval_evidence,
        "sinks": {name: {"state": "pending"} for name in ("excel", "raw_ocr", "csv")},
        "verification": {
            "kind": kind, "batch_id": batch_id, "school_code": school_code,
            "content_fingerprint": fingerprint, "expected_rows": rows,
            "excel_path": str(STUDENT_DATABASE), "raw_path": str(raw_path),
            "csv_path": str(csv_path),
        },
    }
    JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
    create_journal(journal_path, record)
    return {"path": str(journal_path), "record": record}


def _excel_batch_snapshot(rows: list[dict], school_code: str) -> list[dict]:
    """Capture the expected post-write Excel state while preserving pre-existing manual values."""
    if not STUDENT_DATABASE.is_file():
        raise FileNotFoundError("student database missing before completion snapshot")
    frame = pd.read_excel(STUDENT_DATABASE, dtype=str).fillna("")
    lower = {str(column).strip().lower(): column for column in frame.columns}
    school_col = lower.get("school_code")
    uid_col = lower.get("student_unique_id")
    if not school_col or not uid_col:
        raise RuntimeError("Excel completion snapshot missing composite identity headers")
    result = []
    fields = ("school_code", "student_unique_id", "student_name", "father_name", "class", "address", "mob_number", "source")
    for row in rows:
        key_school = str(row.get("school_code") or school_code).strip().upper()
        key_uid = str(row.get("student_unique_id") or "").strip().upper()
        matches = frame[(frame[school_col].astype(str).str.strip().str.upper() == key_school) &
                        (frame[uid_col].astype(str).str.strip().str.upper() == key_uid)]
        if len(matches) != 1:
            raise RuntimeError("Excel completion snapshot identity missing or ambiguous")
        actual = matches.iloc[0]
        snap = {}
        for field in fields:
            column = lower.get(field)
            if column is not None:
                snap[field] = _cell_text(actual.get(column, ""))
        result.append(snap)
    return result


def _csv_batch_snapshot(rows: list[dict], school_code: str) -> list[dict]:
    path = SCHOOL_CSV_ROOT / f"{school_code}.csv"
    if not path.is_file():
        raise FileNotFoundError("Individual CSV missing before completion snapshot")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
    lower = {str(column).strip().lower(): column for column in frame.columns}
    school_col = lower.get("school_code")
    uid_col = lower.get("student_unique_id") or lower.get("unique_id")
    if not school_col or not uid_col:
        raise RuntimeError("CSV completion snapshot missing composite identity headers")
    aliases = {"student_name": ("student_name",), "class": ("class",), "school_code": ("school_code",),
               "mob_number": ("mob_number", "mobile"), "address": ("address",),
               "father_name": ("father_name",), "student_unique_id": ("student_unique_id", "unique_id"),
               "mother_name": ("mother_name",)}
    result = []
    for row in rows:
        sc = str(row.get("school_code") or school_code).strip().upper()
        uid = str(row.get("student_unique_id") or row.get("unique_id") or "").strip().upper()
        matches = frame[(frame[school_col].map(lambda x: str(x).strip().upper()) == sc) &
                        (frame[uid_col].map(lambda x: str(x).strip().upper()) == uid)]
        if len(matches) != 1:
            raise RuntimeError("CSV completion snapshot identity missing or ambiguous")
        actual = matches.iloc[0]
        snap = {}
        for logical, candidates in aliases.items():
            column = next((lower[candidate] for candidate in candidates if candidate in lower), None)
            if column is not None:
                snap[logical] = _cell_text(actual.get(column, ""))
        result.append(snap)
    return result


def _complete_option_c_journal(journal_ctx: dict, rows: list[dict], kind: str) -> bool:
    """Finalize only after independent read-back of Excel, Raw OCR and CSV."""
    record = journal_ctx["record"]
    record["verification"]["expected_rows"] = rows
    # Existing nonblank/manual Excel fields are intentionally not overwritten.
    # Bind a post-write snapshot to the journal so independent verifier/Gate can
    # compare the live workbook to the exact state verified by this batch.
    excel_snapshot = _excel_batch_snapshot(rows, record["school_code"])
    record["verification"]["excel_expected_rows"] = excel_snapshot
    record["verification"]["excel_snapshot_fingerprint"] = _payload_digest(excel_snapshot)
    csv_snapshot = _csv_batch_snapshot(rows, record["school_code"])
    record["verification"]["csv_expected_rows"] = csv_snapshot
    record["verification"]["csv_snapshot_fingerprint"] = _payload_digest(csv_snapshot)
    # The journal helper and Gate independently re-read the configured sinks.
    complete_journal(journal_ctx["path"], record["verification"])
    ok, reason = gate_authorize(
        journal_ctx["path"], expected_batch_id=record["batch_id"],
        expected_school_code=record["school_code"],
        expected_fingerprint=record["content_fingerprint"],
    )
    if not ok:
        mark_recovery_required(journal_ctx["path"], f"post-completion Gate rejected batch: {reason}")
        raise RuntimeError(f"Option C Gate rejected completed batch: {reason}")
    # Publish a minimal handoff only after the Gate has independently re-read
    # and authorized all three live sinks. The GUI still re-authorizes the journal
    # and re-verifies the sinks; this pointer is discovery, not proof.
    handoff = {
        "schema_version": 1,
        "batch_id": record["batch_id"],
        "school_code": record["school_code"],
        "content_fingerprint": record["content_fingerprint"],
        "journal_path": str(Path(journal_ctx["path"]).resolve()),
    }
    handoff_path = JOURNAL_ROOT / "latest_verified_batch.handoff"
    temp_path = handoff_path.with_suffix(handoff_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(handoff, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temp_path, handoff_path)
    _log(f"Option C Gate independently authorized batch {record['batch_id']} ({kind}); handoff published")
    return True



def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file's contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def archive_scans_nonblocking(files: list[Path], school_code: str, root: Path | None = None) -> list[dict]:
    """Move scans to _done after three data sinks are verified; archive is not a required sink."""
    done = (root or RETURNED_SLIPS) / school_code.upper() / "_done"
    done.mkdir(parents=True, exist_ok=True)
    evidence = []
    for source in files:
        try:
            if not source.is_file():
                _log(f"Archive warning: source scan missing; left unprocessed: {source}")
                continue
            source_hash = _sha256_file(source)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            destination = done / f"{stamp}_{source.name}"
            if destination.exists():
                _log(f"Archive warning: destination already exists; scan left in place: {source}")
                continue
            shutil.move(str(source), str(destination))
            if not destination.is_file() or source.exists():
                _log(f"Archive warning: move verification failed for {source}; inspect {destination}")
                continue
            destination_hash = _sha256_file(destination)
            if destination_hash != source_hash:
                _log(f"Archive warning: SHA-256 mismatch for moved scan {destination}; manual inspection required")
                continue
            evidence.append({
                "source_name": source.name,
                "archive_path": str(destination),
                "sha256": destination_hash,
                "source_removed": not source.exists(),
            })
            _log(f"Scan moved to _done (non-gating): {destination.name}; SHA-256 verified")
        except Exception as exc:
            _log(f"Archive warning: scan was not fully verified ({type(exc).__name__}): {source}")
    return evidence


def process_school(school_code: str) -> dict:
    """Option C: OCR, obtain explicit audio approval, then commit and verify three data sinks."""
    school_code = school_code.strip().upper()
    RETURNED_SLIPS.joinpath(school_code).mkdir(parents=True, exist_ok=True)
    rows, files = collect_students(school_code)
    if not rows:
        try:
            status_mark(school_code, "slips_returned", done=False, count=0, note="no scans")
        except Exception:
            pass
        return {"school": school_code, "extracted": 0, "updated": 0, "added": 0}

    # Approval is bound to this exact batch, audio bytes, school and payload.
    batch_id = datetime.now().strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex[:8]
    audio_file, approval_evidence, is_approved = _request_batch_audio_approval(
        rows, school_code, batch_id, "slip"
    )
    approved = len(rows) if is_approved else 0

    if not approved:
        return {
            "school": school_code, "extracted": len(rows), "updated": 0, "added": 0,
            "scans": len(files), "audio_file": audio_file, "approved": 0,
            "verification_required": True, "committed": False,
        }

    # Begin batch journal before first sink mutation. Missing CSV or any failed sink
    # is a hard failure for this three-sink Option C batch; it is never marked complete.
    if school_batch_lock is None:
        raise RuntimeError("Option C school lock module unavailable; refusing all sink writes")
    with school_batch_lock(JOURNAL_ROOT / "locks", school_code, batch_id):
        # Revalidate immediately before the first mutation; stale approvals fail closed.
        if not validate_approval(approval_evidence, batch_id=batch_id, school_code=school_code, audio_path=audio_file, rows=rows):
            raise RuntimeError("audio approval fingerprint mismatch; no sink writes permitted")
        journal_ctx = _begin_option_c_journal(school_code, rows, "slip", batch_id=batch_id, approval_evidence=approval_evidence)
        try:
            # Prefer direct update to final student_data.xlsx
            # RAW_TEXT and CSV are secondary; failure there should not block the main database
            raw_written = False
            try:
                raw_written = write_raw_ocr(rows, batch_id=batch_id)
            except Exception as raw_exc:
                _log(f"RAW_TEXT write warning (non-blocking): {raw_exc}")

            csv_written = False
            try:
                csv_written = write_school_csv(rows, school_code)
            except Exception as csv_exc:
                _log(f"Individual CSV write warning (non-blocking): {csv_exc}")

            # Direct update to local final database (student_data.xlsx)
            updated, added = update_student_excel(school_code, rows)
            _complete_option_c_journal(journal_ctx, rows, "slip")
            archive_scans_nonblocking(files, school_code, RETURNED_SLIPS)
        except Exception as exc:
            try:
                mark_recovery_required(journal_ctx["path"], str(exc))
            except Exception:
                pass
            raise

    try:
        status_mark(school_code, "slips_returned", done=True, count=len(rows), note=f"{len(files)} scans")
        status_mark(school_code, "data_filled", done=True, count=updated + added, note=f"upd {updated} add {added}")
    except Exception:
        pass

    return {
        "school": school_code, "extracted": len(rows), "updated": updated, "added": added,
        "scans": len(files), "audio_file": audio_file, "approved": approved,
        "csv_verified": bool(csv_written),
        "committed": True, "fully_verified": bool(csv_written),
    }


def collect_corrections(school_code: str) -> tuple[list[dict], list[Path]]:
    files = list_scans(school_code, RETURNED_CORRECTIONS)
    if not files:
        _log(f"No correction scans in {RETURNED_CORRECTIONS / school_code.upper()}")
        return [], []

    rows = []
    ok_files = []
    for path in files:
        _log(f"OCR correction: {path.name}")
        try:
            data = ocr_image(path, CORRECTION_PROMPT)
        except Exception as e:
            _log(str(e))
            continue
        items = data.get("corrections") or data.get("students") or []
        if not items:
            _log(f"  no corrections found in {path.name}")
            continue
        header_class = clean_name(data.get("class", ""))
        header_sec = clean_name(data.get("section", ""))
        for s in items:
            uid = clean_uid(s.get("student_unique_id", ""), school_code)
            if not uid:
                continue
            rec = {
                "school_code": school_code.upper(),
                "student_unique_id": uid,
                "student_name": clean_name(s.get("student_name", "")),
                "father_name": clean_name(s.get("father_name", "")),
                "class": clean_name(s.get("class", "")) or header_class,
                "section": clean_name(s.get("section", "")) or header_sec,
                "address": clean_name(s.get("address", "")),
                "mob_number": clean_mob(s.get("mob_number", "")),
                "source": "correction_slip",
                "scan_file": path.name,
                "fields_ticked": ",".join(s.get("fields_ticked") or []),
            }
            if not any(rec[k] for k in ("student_name", "father_name", "class", "address", "mob_number")):
                continue
            rows.append(rec)
        ok_files.append(path)
        _log(f"  extracted {len(items)} correction blocks")
    return rows, ok_files


def write_raw_corrections(rows: list[dict], batch_id: str | None = None):
    """Batch-aware, idempotent correction history sink with exact read-back."""
    return _write_raw_batch(RAW_CORR_EXCEL, rows, batch_id, "RAW_CORRECTIONS.xlsx")


def process_corrections(school_code: str) -> dict:
    """Mode D: apply RIGHT values from correction slips onto existing UID rows."""
    school_code = school_code.strip().upper()
    RETURNED_CORRECTIONS.joinpath(school_code).mkdir(parents=True, exist_ok=True)
    CORRECTION_SLIPS.mkdir(parents=True, exist_ok=True)
    rows, files = collect_corrections(school_code)
    if not rows:
        try:
            status_mark(school_code, "corrections_applied", done=False, count=0, note="no scans")
        except Exception:
            pass
        return {"school": school_code, "extracted": 0, "updated": 0, "added": 0, "kind": "correction"}

    # Correction rows require the same explicit, batch-bound audio approval as new slips.
    correction_batch_id = datetime.now().strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex[:8]
    audio_file, approval_evidence, is_approved = _request_batch_audio_approval(
        rows, school_code, correction_batch_id, "correction"
    )
    if not is_approved:
        return {"school": school_code, "extracted": len(rows), "approved": 0,
                "updated": 0, "added": 0, "scans": len(files), "kind": "correction",
                "audio_file": audio_file, "verification_required": True, "committed": False}
    approved_rows = rows

    if school_batch_lock is None:
        raise RuntimeError("Option C school lock module unavailable; refusing correction sink writes")
    with school_batch_lock(JOURNAL_ROOT / "locks", school_code, correction_batch_id):
        # Revalidate immediately before any sink mutation; approval cannot be reused.
        if not validate_approval(approval_evidence, batch_id=correction_batch_id, school_code=school_code,
                                 audio_path=audio_file, rows=approved_rows):
            raise RuntimeError("correction audio approval fingerprint mismatch; no sink writes permitted")
        journal_ctx = _begin_option_c_journal(
            school_code, approved_rows, "correction", batch_id=correction_batch_id,
            approval_evidence=approval_evidence
        )
        try:
            raw_written = write_raw_corrections(approved_rows, batch_id=correction_batch_id)
            if not raw_written:
                raise RuntimeError(f"Raw corrections sink not verified for {school_code}; batch cannot complete")
            csv_written = write_school_csv(approved_rows, school_code, correction=True)
            if not csv_written:
                raise RuntimeError(f"Individual CSV sink not verified for correction batch {school_code}; batch cannot complete")
            updated, added = update_student_excel(school_code, approved_rows, correction=True)
            _complete_option_c_journal(journal_ctx, approved_rows, "correction")
            archive_scans_nonblocking(files, school_code, RETURNED_CORRECTIONS)
        except Exception as exc:
            try:
                mark_recovery_required(journal_ctx["path"], str(exc))
            except Exception:
                pass
            raise

    try:
        status_mark(school_code, "corrections_applied", done=True, count=updated,
                    note=f"{len(files)} scans, add {added}")
    except Exception:
        pass

    return {
        "school": school_code,
        "extracted": len(rows),
        "approved": len(approved_rows),
        "updated": updated,
        "added": added,
        "scans": len(files),
        "kind": "correction",
        "audio_file": audio_file,
        "csv_verified": bool(csv_written),
        "committed": True,
        "fully_verified": bool(csv_written),
    }


def recover_batch(batch_id: str) -> dict:
    """Resume one exact failed batch after fresh audio approval and lock-owner reconciliation."""
    if any(x is None for x in (load_journal, update_journal, recovery_school_batch_lock,
                               validate_approval, mark_recovery_required)):
        raise RuntimeError("recovery modules unavailable; refusing recovery")
    batch_id = str(batch_id or "").strip()
    if not batch_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", batch_id):
        raise ValueError("invalid batch ID")
    journal_path = JOURNAL_ROOT / f"{batch_id}.json"
    record = load_journal(journal_path)
    if record.get("state") != "RECOVERY_REQUIRED" or not record.get("recovery_required"):
        raise RuntimeError("only a RECOVERY_REQUIRED batch can be resumed")
    if record.get("batch_id") != batch_id:
        raise RuntimeError("journal batch ID mismatch")
    school = str(record.get("school_code") or "").strip().upper()
    kind = str(record.get("kind") or "slip")
    if kind not in {"slip", "correction"} or not school:
        raise RuntimeError("journal kind/school schema invalid")
    verification = record.get("verification") or {}
    rows = verification.get("expected_rows")
    if not isinstance(rows, list) or not rows or _payload_digest(rows) != record.get("content_fingerprint"):
        raise RuntimeError("journal payload fingerprint invalid; refusing recovery")
    expected_paths = {
        "excel_path": str(STUDENT_DATABASE),
        "raw_path": str(RAW_CORR_EXCEL if kind == "correction" else RAW_OCR_EXCEL),
        "csv_path": str(SCHOOL_CSV_ROOT / f"{school}.csv"),
    }
    for key, expected_path in expected_paths.items():
        if str(verification.get(key) or "") != expected_path:
            raise RuntimeError(f"recovery sink configuration changed for {key}; refusing cross-path resume")
    audio_file, approval_evidence, approved = _request_batch_audio_approval(rows, school, batch_id, f"{kind} recovery")
    if not approved:
        return {"batch_id": batch_id, "school": school, "recovered": False, "reason": "audio_not_approved"}
    with recovery_school_batch_lock(JOURNAL_ROOT / "locks", school, batch_id, journal_path):
        if not validate_approval(approval_evidence, batch_id=batch_id, school_code=school,
                                 audio_path=audio_file, rows=rows):
            raise RuntimeError("recovery audio approval fingerprint mismatch")
        update_journal(journal_path, {"state": "COMMITTING", "recovery_required": False,
                                      "approval_evidence": approval_evidence,
                                      "recovery_attempted_at": datetime.now().isoformat(timespec="seconds")})
        try:
            if kind == "correction":
                if not write_raw_corrections(rows, batch_id=batch_id):
                    raise RuntimeError("Raw corrections sink not verified during recovery")
            else:
                if not write_raw_ocr(rows, batch_id=batch_id):
                    raise RuntimeError("Raw OCR sink not verified during recovery")
            csv_written = write_school_csv(rows, school, correction=(kind == "correction"))
            if not csv_written:
                raise RuntimeError("CSV sink not verified during recovery")
            updated, added = update_student_excel(school, rows, correction=(kind == "correction"))
            journal_ctx = {"path": str(journal_path), "record": record}
            _complete_option_c_journal(journal_ctx, rows, kind)
        except Exception as exc:
            try:
                mark_recovery_required(journal_path, str(exc))
            except Exception:
                pass
            raise
    return {"batch_id": batch_id, "school": school, "kind": kind, "recovered": True,
            "updated": updated, "added": added, "csv_verified": bool(csv_written), "committed": True}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--school")
    p.add_argument("--kind", choices=["slip", "correction"], default="slip")
    p.add_argument("--recover-batch", help="resume an exact RECOVERY_REQUIRED batch after fresh audio approval")
    args = p.parse_args()
    if args.recover_batch:
        print(recover_batch(args.recover_batch))
    elif args.school:
        if args.kind == "correction":
            print(process_corrections(args.school))
        else:
            print(process_school(args.school))
    else:
        p.error("provide --school or --recover-batch")
