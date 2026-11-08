#!/usr/bin/env python3
"""
SAINI SCHOOL MASTER PROCESSOR - PERFECTED v2.0
================================================
Key Improvements:
- Centralized, portable configuration with pathlib
- Non-destructive database updates (no more data loss on re-runs)
- Proper cleaning: display names keep spaces/casing; only matching keys are aggressive
- Smart unique_id detection from Google Form / OCR columns (photo_no, unique_id, etc.)
- Robust logging to file + console
- Better error handling, validation, summaries
- Cleaner code structure with functions
- Reliable font loading (Windows + fallback)
- Improved Step 1 number assignment using strict CLASS_RANGES
- Print sheets: more info in header, robust layout
- All critical paths checked and created safely
- Graceful handling of missing files / empty data

Author: Grok (refactored for SAINI SCHOOL UNIFORMS)
Date: 2026-07-09
"""

import os
import re
import sys
import time
import shutil
import subprocess
import logging
import sys
sys.path.insert(0, r'D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules')
from gate import authorize
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import parse_qs, urlparse
import pandas as pd
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None
from PIL import Image, ImageDraw, ImageFont
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
from copy import copy
import argparse
import json
import hashlib

try:
    import saini_db
except ImportError:
    saini_db = None
try:
    from school_status import mark as status_mark, dashboard_text, school_detail
except ImportError:
    def status_mark(*args, **kwargs):
        return {}
    def dashboard_text():
        return "school_status.py not found next to MAIN_ASSISTANT.py"
    def school_detail(code):
        return dashboard_text()

# ====================== USER CONFIGURATION (EDIT IF NEEDED) ======================
# Override any path with env var, e.g. SAINI_BASE_PROJECT, or a config JSON.
# Config file: ID_CARD_PROJECT/saini_config.json  { "BASE_PROJECT": "D:\\..." }
# Base folder of your ID_CARD_PROJECT
BASE_PROJECT = Path(os.environ.get(
    "SAINI_BASE_PROJECT",
    r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT"
))
_CFG_JSON = Path(os.environ.get("SAINI_CONFIG", str(BASE_PROJECT / "saini_config.json")))
if _CFG_JSON.exists():
    try:
        _cfg = json.loads(_CFG_JSON.read_text(encoding="utf-8"))
        if _cfg.get("BASE_PROJECT"):
            BASE_PROJECT = Path(_cfg["BASE_PROJECT"])
    except Exception:
        pass

# Core folders (auto-created)
PHOTO_LIBRARY       = BASE_PROJECT / "PHOTO_LIBRARY"
INPUT_WHATSAP       = BASE_PROJECT / "WHATSAP"          # raw class folders from WhatsApp
RENAME_OUTPUT       = BASE_PROJECT / "INPUT"            # renamed photos
PIPELINE_OUTPUT     = BASE_PROJECT / "OUTPUT"           # after background removal / passport crop
PRINT_SHEETS_FOLDER = BASE_PROJECT / "PRINT_SHEETS"
RETURNED_SLIPS      = BASE_PROJECT / "RETURNED_SLIPS"   # teacher-filled first data slip
RETURNED_CORRECTIONS = BASE_PROJECT / "RETURNED_CORRECTIONS"  # filled correction slip scans
CORRECTION_SLIPS    = BASE_PROJECT / "CORRECTION_SLIPS"  # blank ID_CARD_CORRECTION_SLIP_A4.pdf
LOGS_DIR            = BASE_PROJECT / "LOGS"

# External paths
GOOGLE_DRIVE_PHOTOS = Path(r"D:\SHRI_JAI_SHRI_RAM\PHOTOCHAMBER")
STUDENT_DATABASE    = BASE_PROJECT.parent / "student_data.xlsx"

# Scripts
# New Advanced Studio Pipeline
STUDIO_PIPELINE = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_AI_STUDIO\run_studio_pipeline.py")
OLD_PIPELINE_SCRIPT = BASE_PROJECT / "passport_lab_pipeline_hotfix.py"
PHOTO_DOWNLOADER = Path(r"D:\AGENT_TOOLS\photo_downloader.py")
# Studio Pipeline Settings
STUDIO_BG_COLOR = "W"           # W / R / B / G / LG / LB
STUDIO_GFPGAN_BLEND = "0.65"
STUDIO_QUALITY = "95"

ID_CARD_SCRIPT_CANDIDATES = [
    BASE_PROJECT / "SAINI_ID_CARD.py",
    BASE_PROJECT.parent / "SAINI_ID_CARD.py",
    BASE_PROJECT / "SAINI_ID_CARD.py",
]

# Data sources
RAW_OCR_EXCEL   = INPUT_WHATSAP / "RAW_TEXT.xlsx"
CSV_ROOT = Path('D:\\SHRI_JAI_SHRI_RAM\\project_panels\\ID_CARD_PROJECT\\CSV')
ID_SOURCE_CSV = BASE_PROJECT / "ID_SOURCE.csv"
ID_SOURCE_JSON = BASE_PROJECT / "ID_SOURCE.json"

# Live Google Sheet (hub) â€” enrollment (Mode E)
HUB_SHEET_ID = "1YBdVdNmCK5-YhjGQ44LZDeBjN7K3xOJSNOYvL_WIuOQ"
HUB_TAB = "Form_Responses_1"
SCHOOL_MASTER_TAB = "SCHOOL_MASTER"
SERVICE_ACCOUNT_JSON = BASE_PROJECT.parent / "service_account.json"

# Pipeline quality settings (passed to passport_lab_pipeline_hotfix.py)
PIPELINE_SETTINGS = {
    "--mode": "drive",
    "--bg": "white",
    "--face-crop": "",
    "--head-gap-top": "0.14",
    "--pocket-gap-bottom": "0.11",
    "--min-top-gap-px": "35",
    "--min-bottom-gap-px": "20",
    "--hair-clean": "0.75",
    "--model": "isnet-general-use",
    "--jobs": "1",
    "--skip-existing": "",
    "--quality": "98"
}

# Number ranges per class (used for auto numbering + grouping)
# ====================== CLASS RANGES & NAMING LOGIC ======================
CLASS_RANGES = {
    "NUR":  ("NUR",  10000, 10999),
    "LKG":  ("LKG",  20000, 20999),
    "UKG":  ("UKG",  30000, 30999),
    "I":    ("I",    1000,  1999),
    "II":   ("II",   2000,  2999),
    "III":  ("III",  3000,  3999),
    "IV":   ("IV",   4000,  4999),
    "V":    ("V",    5000,  5999),
    "VI":   ("VI",   6000,  6999),
    "VII":  ("VII",  7000,  7999),
    "VIII": ("VIII", 8000,  8999),
    "IX":   ("IX",   9000,  9999),
    "X":    ("X",    100,   999),
    "XI":   ("XI",   100,   999),
    "XII":  ("XII",  100,   999),
    "MIX":  ("MIX",  50000, 59999)
}

# Teachers often write L.K.G / L.K.G. / U.K.G / NURSERY â€” map all to CLASS_RANGES keys
CLASS_ALIASES = {
    "LKG": "LKG", "LK": "LKG", "LOWERKG": "LKG",
    "LOWERKINDERGARTEN": "LKG", "LOWERKINDER": "LKG",
    "KINDERGARTEN": "LKG", "KG": "LKG",
    "UKG": "UKG", "UK": "UKG", "UPPERKG": "UKG",
    "UPPERKINDERGARTEN": "UKG", "UPPERKINDER": "UKG",
    "NUR": "NUR", "NURS": "NUR", "NURSERY": "NUR",
    "NURSARY": "NUR", "NURSERYCLASS": "NUR", "PRENUR": "NUR",
    "PRENURSERY": "NUR",
    "MIX": "MIX", "MIXED": "MIX", "MIXCLASS": "MIX",
    "I": "I", "1": "I", "1ST": "I", "IST": "I", "FIRST": "I", "CLASS1": "I", "CLASS I": "I",
    "II": "II", "2": "II", "2ND": "II", "SECOND": "II", "CLASS2": "II",
    "III": "III", "3": "III", "3RD": "III", "THIRD": "III", "CLASS3": "III",
    "IV": "IV", "4": "IV", "4TH": "IV", "FOURTH": "IV", "CLASS4": "IV",
    "V": "V", "5": "V", "5TH": "V", "FIFTH": "V", "CLASS5": "V",
    "VI": "VI", "6": "VI", "6TH": "VI", "SIXTH": "VI", "CLASS6": "VI",
    "VII": "VII", "7": "VII", "7TH": "VII", "SEVENTH": "VII", "CLASS7": "VII",
    "VIII": "VIII", "8": "VIII", "8TH": "VIII", "EIGHTH": "VIII", "CLASS8": "VIII",
    "IX": "IX", "9": "IX", "9TH": "IX", "NINTH": "IX", "CLASS9": "IX",
    "X": "X", "10": "X", "10TH": "X", "TENTH": "X", "CLASS10": "X",
    "XI": "XI", "11": "XI", "11TH": "XI", "ELEVENTH": "XI", "CLASS11": "XI",
    "XII": "XII", "12": "XII", "12TH": "XII", "TWELFTH": "XII", "CLASS12": "XII",
}


def extract_class_number(stem: str, school: str, cls: str) -> int | None:
    stem = str(stem or "").upper()
    school = str(school or "").upper()
    cls = str(cls or "").upper()
    try:
        if cls in ("X", "XI", "XII"):
            prefix = school + cls
            if stem.startswith(prefix):
                num_str = "".join(filter(str.isdigit, stem[len(prefix):]))
                return int(num_str) if num_str else None
        if stem.startswith(school):
            num_str = "".join(filter(str.isdigit, stem[len(school):]))
            return int(num_str) if num_str else None
    except Exception:
        return None
    return None


def is_official_photo_uid(school_code: str, uid: str) -> bool:
    u = str(uid or "").strip().upper()
    sc = str(school_code or "").strip().upper()
    if not u.startswith(sc) or u == sc:
        return False
    rest = u[len(sc):]
    return bool(re.fullmatch(r"(XII|XI|X)\d{3}", rest) or re.fullmatch(r"\d{4,5}", rest))


def next_official_uid(school_code: str, class_name: str, used: set) -> str:
    """WhatsApp Step-1 jaisi ID: AJPXII108, AJP1104, AJP10001."""
    sc = school_code.upper()
    cls = class_name if class_name in CLASS_RANGES else "MIX"
    _, lo, hi = CLASS_RANGES[cls]
    highest = lo - 1
    stems = {str(x).upper() for x in used}
    scan_dirs = [PHOTO_LIBRARY / sc, RENAME_OUTPUT, PIPELINE_OUTPUT, GOOGLE_DRIVE_PHOTOS / sc]
    for folder in scan_dirs:
        if folder.exists():
            for f in folder.glob("*.jpg"):
                stems.add(f.stem.upper())
            for f in folder.glob("*.jpeg"):
                stems.add(f.stem.upper())
    for stem in stems:
        n = extract_class_number(stem, sc, cls)
        if n is not None and lo <= n <= hi:
            highest = max(highest, n)
    nxt = highest + 1
    if nxt > hi:
        logger.warning(f"Class {cls} range full ({lo}-{hi}), MIX series use")
        return next_official_uid(sc, "MIX", used)
    if cls in ("X", "XI", "XII"):
        uid = f"{sc}{cls}{nxt:03d}"
    elif lo >= 10000:
        uid = f"{sc}{nxt:05d}"
    else:
        uid = f"{sc}{nxt:04d}"
    return uid.upper()


def normalize_class_name(text) -> str:
    """LKG / L.K.G / L.K.G. / U.K.G. / NURSERY â€” sab ek canonical key banate hain."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    raw = str(text).strip().upper()
    if not raw or raw in ("NAN", "NONE", "NULL"):
        return ""
    raw = raw.replace("CLASS", " ").replace("STD", " ").replace("STANDARD", " ")
    compact = "".join(ch for ch in raw if ch.isalnum())
    if compact in CLASS_RANGES:
        return compact
    if compact in CLASS_ALIASES:
        return CLASS_ALIASES[compact]
    # "L K G", "L. K. G." already compacted to LKG above
    return compact if compact in CLASS_RANGES else compact

# Print sheet layout (A4 @ 300 DPI) â€” 10 student slips per page
PAGE_W, PAGE_H = 2480, 3508
STUDENTS_PER_PAGE = 10
SLIP_MARGIN = 70
SLIP_GAP_X = 28
SLIP_GAP_Y = 18
HEADER_H = 210
FOOTER_H = 80
PHOTO_W, PHOTO_H = 280, 350

# ====================== LOGGING SETUP ======================
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"SAINI_MASTER_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("SAINI_MASTER")

logger = setup_logging()

# ====================== HELPER FUNCTIONS ======================
def safe_makedirs(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_font(size: int):
    """Robust font loader for Windows (falls back to default)"""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux fallback
    ]
    for fp in candidates:
        p = Path(fp)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    logger.warning("No TrueType font found, using default (may look bad)")
    return ImageFont.load_default()

def normalize_key(text) -> str:
    """Aggressive normalize ONLY for duplicate detection / synthetic ID"""
    if pd.isna(text) or str(text).strip().lower() in ["nan", "", "none"]:
        return ""
    t = str(text).strip().upper()
    return "".join(c for c in t if c.isalnum())  # keep letters+numbers only

def clean_for_display(text) -> str:
    """Keep readable names with proper spacing (used for final DB storage)"""
    if pd.isna(text):
        return ""
    t = str(text).strip()
    t = " ".join(t.split())  # collapse multiple spaces
    return t.upper()  # school prefers CAPITAL as per print sheet header

def fix_mobile(x) -> str:
    if pd.isna(x):
        return ""
    x = str(x).strip().replace(".0", "").replace(".00", "")
    digits = "".join(filter(str.isdigit, x))
    return digits[:10] if len(digits) >= 10 else digits

def resolve_school_csv(school_code: str):
    # Resolve the school's Individual CSV from the single shared root.
    code = str(school_code or "").strip().upper()
    if not code or "/" in code or chr(92) in code or ":" in code or chr(0) in code or code in (".", ".."):
        logger.error("Invalid school code for Individual CSV lookup.")
        return None, None

    path = CSV_ROOT / f"{code}.csv"
    if path.is_file() and path.stat().st_size > 0:
        logger.info(f"Individual school CSV: {path}")
        return path, None

    logger.warning(f"Individual CSV not found for school code {code}: {path}")
    return None, None


def prepare_id_source(school_code: str):
    """Local Excel is the only ID-card source; CSV is not a fallback."""
    code = str(school_code or "").strip().upper()
    main_file = Path(STUDENT_DATABASE)

    if not main_file.is_file():
        logger.error(f"Local student Excel is missing; refusing ID-card launch: {main_file}")
        return None, None, "none"

    meta = {
        "school_code": code,
        "source": "student_data",
        "path": str(main_file),
        "prepared_at": datetime.now().isoformat(),
        "mode": "xlsx",
    }
    ID_SOURCE_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info(f"ID source = LOCAL EXCEL ONLY -> {main_file.name}")
    return main_file, None, "xlsx"

def find_id_column(df: pd.DataFrame) -> str | None:
    """Look for a column that likely contains the student_unique_id / photo number"""
    candidates = [
        "student_unique_id", "unique_id", "photo_id", "student_id",
        "id", "photo_number", "photo_no", "roll_no", "admission_no", "sr_no"
    ]
    for col in df.columns:
        if str(col).lower().strip() in candidates:
            return col
    return None

def get_class_bucket(num: int) -> int:
    """Return the bucket prefix used for grouping in print sheets"""
    if num >= 10000:
        return (num // 10000) * 10000   # For NUR, LKG, UKG and higher
    elif num >= 1000:
        return (num // 1000) * 1000
    else:
        return (num // 100) * 100

# Header names â€” NEVER write by column letter (C, H, J). Always by name.
HEADER_ALIASES = {
    "timestamp": ["timestamp", "Timestamp", "time stamp"],
    "student_name": ["student_name", "Student Name", "name"],
    "class": ["class", "Class"],
    "school_code": ["school_code", "School Code", "school"],
    "mob_number": ["mob_number", "mobile", "Mobile", "mob"],
    "address": ["address", "Address"],
    "father_name": ["father_name", "Father Name", "father"],
    "student_unique_id": ["student_unique_id", "unique_id", "photo_no", "Photo No"],
    "roll_number": ["roll_number", "roll_no", "Roll"],
    "STUDENT_PHOTO_PATH": ["STUDENT_PHOTO_PATH", "photo_path", "photo"],
    "GOOGLE_FILE_ID": ["GOOGLE_FILE_ID", "file_id"],
    "mother_name": ["mother_name", "Mother Name", "mother"],
    "source": ["source"],
}


def sheet_header_map(sheet) -> dict:
    """header text -> 1-based column index (first match wins)."""
    mapping = {}
    for idx, cell in enumerate(sheet[1], 1):
        raw = str(cell.value or "").strip()
        if not raw or raw in mapping:
            continue
        mapping[raw] = idx
        mapping[raw.lower()] = idx
    return mapping


def col_index(hmap: dict, logical: str):
    for alias in HEADER_ALIASES.get(logical, [logical]):
        if alias in hmap:
            return hmap[alias]
        if alias.lower() in hmap:
            return hmap[alias.lower()]
    return None


def write_by_name(sheet, row_idx: int, hmap: dict, data: dict, template_row: int = 2):
    """Write dict keys into the sheet using header names only."""
    for logical, value in data.items():
        col = col_index(hmap, logical)
        if not col:
            continue
        dest = sheet.cell(row=row_idx, column=col)
        dest.value = value
        if logical == "mob_number":
            dest.number_format = "@"
        if template_row and template_row >= 2:
            src = sheet.cell(row=template_row, column=col)
            try:
                if src.font:
                    dest.font = copy(src.font)
                if src.fill:
                    dest.fill = copy(src.fill)
                if src.alignment:
                    dest.alignment = copy(src.alignment)
                if src.border:
                    dest.border = copy(src.border)
            except Exception:
                pass


def class_from_uid(school_code: str, uid: str) -> str:
    """VINAYX100 â†’ X, AJPXII108 â†’ XII, AJP10012 â†’ NUR."""
    u = str(uid or "").strip().upper()
    sc = str(school_code or "").strip().upper()
    if not u.startswith(sc):
        return ""
    for cls in ("XII", "XI", "X"):
        if u.startswith(sc + cls):
            return cls
    n = extract_class_number(u, sc, "I")
    if n is None:
        return ""
    for cls, info in CLASS_RANGES.items():
        if cls in ("X", "XI", "XII", "MIX"):
            continue
        _, lo, hi = info
        if lo <= n <= hi:
            return cls
    if 50000 <= n <= 59999:
        return "MIX"
    return ""


def reverse_class_map(bucket: int) -> str:
    """Return class name from bucket number"""
    for cls, info in CLASS_RANGES.items():
        if len(info) == 3:  # New format: (display_name, start, end)
            _, lo, hi = info
        else:  # Old format fallback
            lo, hi = info
        if lo <= bucket <= hi:
            return cls
    return f"BUCKET_{bucket}"

# ====================== STEP 1: SMART RENAMING (FINAL FIXED & ROBUST) ======================
def step1_smart_rename(school_code: str) -> int:
    logger.info("=== STEP 1: Smart Renaming + Highest Number Logic ===")
    safe_makedirs(RENAME_OUTPUT)

    backup_name = f"{school_code}_Originals_{datetime.now().strftime('%Y-%m-%d_%H-%M')}"
    backup_dir = INPUT_WHATSAP / backup_name
    safe_makedirs(backup_dir)
    logger.info(f"Originals backed up to: {backup_dir.name}")

    school_lib = PHOTO_LIBRARY / school_code
    safe_makedirs(school_lib)

    total_renamed = 0

    for folder in sorted(os.listdir(INPUT_WHATSAP)):
        folder_path = INPUT_WHATSAP / folder
        if not folder_path.is_dir() or folder.startswith(f"{school_code}_Originals_"):
            continue

        class_name = normalize_class_name(folder)

        if class_name not in CLASS_RANGES:
            logger.warning(f"Skipping unknown class folder: {folder} (normalized: {class_name})")
            continue

        display_name, range_start, range_end = CLASS_RANGES[class_name]
        logger.info(f"Processing Class: {class_name} (range {range_start}-{range_end})")

        # ==================== STRONG HIGHEST NUMBER LOGIC ====================
        highest = range_start - 1
        
        def extract_number(stem: str, school: str, cls: str) -> int | None:
            """Safely extract number from filename"""
            stem = stem.upper()
            school = school.upper()
            cls = cls.upper()
            
            try:
                # Special handling for Roman classes
                if cls in ("X", "XI", "XII"):
                    prefix = school + cls
                    if stem.startswith(prefix):
                        num_part = stem[len(prefix):]
                        num_str = "".join(filter(str.isdigit, num_part))
                        if num_str:
                            return int(num_str)
                else:
                    # Normal classes (I to IX, NUR, LKG, UKG)
                    if stem.startswith(school):
                        num_part = stem[len(school):]
                        num_str = "".join(filter(str.isdigit, num_part))
                        if num_str:
                            return int(num_str)
            except:
                pass
            return None

        # 1. Check PHOTO_LIBRARY
        if school_lib.exists():
            for f in school_lib.glob("*.jpg"):
                num = extract_number(f.stem, school_code, class_name)
                if num is not None and range_start <= num <= range_end:
                    highest = max(highest, num)

        # 2. Also check INPUT folder (RENAME_OUTPUT) for safety
        if RENAME_OUTPUT.exists():
            for f in RENAME_OUTPUT.glob("*.jpg"):
                num = extract_number(f.stem, school_code, class_name)
                if num is not None and range_start <= num <= range_end:
                    highest = max(highest, num)

        next_num = highest + 1
        logger.info(f"   Last used: {highest} â†’ Starting new from: {next_num}")
        # ===================================================================

        files = sorted([f for f in folder_path.iterdir() 
                       if f.suffix.lower() in (".jpg", ".jpeg", ".png")])

        for src_file in files:
            if class_name in ("X", "XI", "XII"):
                new_name = f"{school_code}{class_name}{next_num:03d}.jpg"
            elif range_start >= 10000:   # NUR, LKG, UKG
                new_name = f"{school_code}{next_num:05d}.jpg"
            else:                        # I to IX
                new_name = f"{school_code}{next_num:04d}.jpg"

            dst = RENAME_OUTPUT / new_name

            shutil.copy2(src_file, dst)
            shutil.copy2(src_file, backup_dir / new_name)

            next_num += 1
            total_renamed += 1
            logger.info(f"  {src_file.name} â†’ {new_name}")

    logger.info(f"âœ… Step 1 done. Total photos renamed: {total_renamed}")
    try:
        status_mark(school_code, "photos_received", done=total_renamed > 0, count=total_renamed,
                    note=f"renamed {total_renamed}")
    except Exception as e:
        logger.warning(f"Status update failed (step1): {e}")
    return total_renamed

# ====================== STEP 2: RUN PIPELINE ======================
def step2_run_pipeline(bg_color: str, school_code: str = None, source_folder: Path = None):
    """
    Step 2: Run Advanced ID Card AI Studio Pipeline
    (Replaces old passport_lab_pipeline_hotfix.py)
    """
    logger.info("=== STEP 2: Running ID_CARD_AI_STUDIO Pipeline ===")

    source_folder = Path(source_folder) if source_folder else RENAME_OUTPUT
    output_folder = PIPELINE_OUTPUT

    # Prefer new Studio pipeline
    if STUDIO_PIPELINE.exists():
        pipeline_script = STUDIO_PIPELINE
        use_studio = True
        logger.info("Using NEW Advanced Studio Pipeline")
    elif OLD_PIPELINE_SCRIPT.exists():
        pipeline_script = OLD_PIPELINE_SCRIPT
        use_studio = False
        logger.warning("Studio not found â†’ falling back to OLD pipeline")
    else:
        logger.error("No pipeline script found!")
        return

    if use_studio:
        cmd = [
            sys.executable,
            str(pipeline_script),
            "--source", str(source_folder),
            "--output", str(output_folder),
            "--bg", bg_color,
            "--gfpgan-blend", "0.65",
            "--skip-existing",
            "--quality", "95"
        ]
    else:
        # Old pipeline fallback (purana command)
        cmd = ["python", str(pipeline_script),
               "--source", str(source_folder),
               "--output", str(output_folder)]
        for k, v in PIPELINE_SETTINGS.items():
            cmd.append(k)
            if v:
                cmd.append(v)

    logger.info("Command: " + " ".join(cmd))

    try:
        # Studio pipeline apne folder se chalani chahiye
        cwd = str(STUDIO_PIPELINE.parent) if use_studio else str(BASE_PROJECT)
        subprocess.run(cmd, cwd=cwd, check=True)
        logger.info("âœ… Pipeline completed successfully.")
        try:
            n = len(list(output_folder.glob("*.jpg"))) if output_folder.exists() else 0
            status_mark(school_code or "", "pipeline_done", done=True, count=n, note="studio/old pipeline ok")
        except Exception as e:
            logger.warning(f"Status update failed (step2): {e}")
    except FileNotFoundError as e:
        logger.error(f"Pipeline script missing: {e}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Pipeline failed with code {e.returncode}")
    except Exception as e:
        logger.error(f"Pipeline error: {e}")

# ====================== STEP 3: COPY TO LIBRARY + GDRIVE ======================
def step3_copy_to_library(school_code: str):
    logger.info("=== STEP 3: Copying processed photos to Library + Google Drive ===")
    school_lib = PHOTO_LIBRARY / school_code
    safe_makedirs(school_lib)

    # Google Drive path check
    school_drive = None
    try:
        if GOOGLE_DRIVE_PHOTOS.exists():
            school_drive = GOOGLE_DRIVE_PHOTOS / school_code
            safe_makedirs(school_drive)
            logger.info(f"Google Drive path available: {school_drive}")
        else:
            logger.warning(f"Google Drive path not found â†’ {GOOGLE_DRIVE_PHOTOS}")
            logger.warning("Skipping Google Drive copy. Only local library will be updated.")
    except Exception as e:
        logger.warning(f"Google Drive access error: {e}")
        logger.warning("Skipping Google Drive copy.")

    main_photos = [f for f in PIPELINE_OUTPUT.iterdir()
                   if f.is_file() and "_" not in f.name and f.suffix.lower() in (".jpg", ".jpeg")]

    copied = 0
    drive_copied = 0

    for photo in main_photos:
        # Local Library (always)
        dst_lib = school_lib / photo.name
        if not dst_lib.exists() or dst_lib.stat().st_size == 0:
            shutil.copy2(photo, dst_lib)
        copied += 1
        logger.info(f"  âœ“ Local: {photo.name}")

        # Google Drive (only if available)
        if school_drive is not None:
            try:
                dst_drive = school_drive / photo.name
                if not dst_drive.exists() or dst_drive.stat().st_size == 0:
                    shutil.copy2(photo, dst_drive)
                drive_copied += 1
            except Exception as e:
                logger.warning(f"  Drive copy failed for {photo.name}: {e}")

    logger.info(f"âœ… {copied} photos copied to local library.")
    if school_drive:
        logger.info(f"âœ… {drive_copied} photos also copied to Google Drive.")
    else:
        logger.info("âš  Google Drive skip à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾ (path available à¤¨à¤¹à¥€à¤‚ à¤¥à¤¾)à¥¤")

    try:
        status_mark(school_code, "library_copied", done=copied > 0, count=copied)
    except Exception as e:
        logger.warning(f"Status update failed (step3): {e}")

# ====================== STEP 4: UPDATE DATABASE (FINAL PERFECT VERSION) ======================
def step4_update_photo_db(school_code: str):
    logger.info("=== STEP 4: Updating Database (Sequence Preserved + Series Wise + Formatting Safe) ===")
    
    master = STUDENT_DATABASE
    if not master.exists():
        logger.error("student_data.xlsx file not found!")
        return

    # Load workbook (this preserves ALL formatting and original order)
    book = openpyxl.load_workbook(master)
    sheet = book.active

    # Read data only for duplicate check (we will NOT rewrite the whole file)
    df_master = pd.read_excel(master, dtype=str)

    # Get existing UIDs of current school only
    existing_uids = set()
    if not df_master.empty and "student_unique_id" in df_master.columns:
        df_school = df_master[df_master["school_code"].astype(str).str.upper() == school_code.upper()].copy()
        if not df_school.empty:
            existing_uids = set(df_school["student_unique_id"].dropna().astype(str).str.strip())

    school_lib = PHOTO_LIBRARY / school_code
    if not school_lib.exists():
        logger.warning(f"Photo library folder not found: {school_lib}")
        return

    photo_files = sorted([f.name for f in school_lib.glob("*.jpg")])
    logger.info(f"Found {len(photo_files)} photos in library for {school_code}")

    if not photo_files:
        logger.info("No photos found in library.")
        return

    # Collect only NEW valid photos
    new_rows = []
    for photo_name in photo_files:
        uid = Path(photo_name).stem.strip()
        
        if uid in existing_uids:
            continue
        if not uid.startswith(school_code):
            logger.warning(f"Skipping invalid photo (wrong school): {photo_name}")
            continue

        new_rows.append({
            "timestamp": datetime.now().isoformat(),
            "school_code": school_code,
            "student_unique_id": uid,
            "STUDENT_PHOTO_PATH": str((school_lib / photo_name).resolve())
        })

    if not new_rows:
        logger.info("âœ… No new records to add. Database is already up to date.")
        return

    # ==================== PERFECT SORTING LOGIC ====================
    def get_sort_key(row):
        uid = row["student_unique_id"].upper()
        
        # Roman classes à¤•à¥‹ à¤¸à¤¬à¤¸à¥‡ à¤…à¤‚à¤¤ à¤®à¥‡à¤‚ à¤°à¤–à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ priority
        if uid.startswith(school_code + "XII"):
            series_priority = 3   # XII à¤¸à¤¬à¤¸à¥‡ à¤…à¤‚à¤¤ à¤®à¥‡à¤‚
            num_str = uid.replace(school_code + "XII", "")
        elif uid.startswith(school_code + "XI"):
            series_priority = 2   # XI à¤¦à¥‚à¤¸à¤°à¥‡ à¤¨à¤‚à¤¬à¤° à¤ªà¤°
            num_str = uid.replace(school_code + "XI", "")
        elif uid.startswith(school_code + "X"):
            series_priority = 1   # X à¤ªà¤¹à¤²à¥‡ (Roman à¤®à¥‡à¤‚)
            num_str = uid.replace(school_code + "X", "")
        else:
            series_priority = 0   # Normal classes (I-IX, NUR, LKG, UKG) à¤¸à¤¬à¤¸à¥‡ à¤ªà¤¹à¤²à¥‡
            num_str = "".join(filter(str.isdigit, uid.replace(school_code, "")))
        
        try:
            num = int(num_str) if num_str else 0
        except:
            num = 999999
        
        return (series_priority, num)
    
    new_rows = sorted(new_rows, key=get_sort_key)
    # ============================================================

    # Append by HEADER NAME only (not column A/C/H/J)
    hmap = sheet_header_map(sheet)
    start_row = sheet.max_row + 1
    template_row = max(2, sheet.max_row)

    for row_data in new_rows:
        write_by_name(sheet, start_row, hmap, row_data, template_row)
        start_row += 1

    book.save(master)
    logger.info(f"âœ… {len(new_rows)} new records added successfully in correct series order.")
    logger.info("âœ… Old records sequence and formatting preserved 100%.")
    try:
        status_mark(school_code, "db_updated", done=True, count=len(new_rows),
                    note=f"{len(new_rows)} new photo rows")
    except Exception as e:
        logger.warning(f"Status update failed (step4): {e}")

# ====================== STEP 5: PRINT SHEETS + COMBINED PDF ======================
def step5_generate_print_sheets(school_code: str):
    logger.info("=== STEP 5: Generating Teacher Slips (10 per A4, photo + address) ===")
    safe_makedirs(PRINT_SHEETS_FOLDER)
    
    # Current batch ki photos (naye students only)
    all_photos = sorted([
        f.name for f in PIPELINE_OUTPUT.glob("*.jpg") 
        if f.is_file() and "_" not in f.name
    ])
    
    if not all_photos:
        logger.warning("No new photos found for print sheets.")
        return

    # Group by class bucket
    class_groups = defaultdict(list)
    for fname in all_photos:
        try:
            num_str = "".join(filter(str.isdigit, Path(fname).stem.replace(school_code, "")))
            num = int(num_str)
            bucket = get_class_bucket(num)
            class_groups[bucket].append(fname)
        except Exception:
            class_groups[0].append(fname)

    logger.info(f"Total classes/buckets: {len(class_groups)} | Total photos: {len(all_photos)}")

    # ==================== SEPARATE BIG & SMALL CLASSES ====================
    big_classes = {}      # 5 or more students
    small_classes = {}    # less than 5 students

    for bucket, photos in class_groups.items():
        if len(photos) >= 5:
            big_classes[bucket] = photos
        else:
            small_classes[bucket] = photos

    logger.info(f"Big classes (â‰¥5): {len(big_classes)} | Small classes (<5): {len(small_classes)}")

    all_sheet_paths = []
    font_title = get_font(48)
    font_sub = get_font(26)
    font_lab = get_font(22)
    font_id = get_font(28)
    font_class = get_font(36)
    font_small = get_font(20)
    font_serial = get_font(26)

    def _box(draw, xy, width=2):
        draw.rectangle(xy, outline=(0, 0, 0), width=width)

    def _field(draw, x, y, w, h, label):
        _box(draw, [x, y, x + w, y + h], 2)
        draw.text((x + 8, y + 4), label, fill=(0, 0, 0), font=font_lab)

    def create_page(batch_photos, page_label, page_num, total_pages):
        """10 slips per A4: photo + printed Photo No. + name/father/address/mobile."""
        page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
        draw = ImageDraw.Draw(page)

        # outer border
        _box(draw, [40, 40, PAGE_W - 40, PAGE_H - 40], 4)

        title = "STUDENT DATA SLIP  /  Teacher Fill Form"
        tw = draw.textlength(title, font=font_title)
        draw.text(((PAGE_W - tw) / 2, 55), title, fill=(0, 0, 0), font=font_title)

        sub = "CAPITAL LETTERS ONLY  |  Photo No. + CLASS printed  |  Galat class ho to photo ke neeche NEW class likho"
        sw = draw.textlength(sub, font=font_sub)
        draw.text(((PAGE_W - sw) / 2, 115), sub, fill=(40, 40, 40), font=font_sub)

        # header write-in boxes
        hx, hy, hh = 70, 155, 78
        specs = [
            (920, f"School: {school_code}"),
            (280, page_label),
            (220, "Section"),
            (420, "Teacher"),
            (360, "Date DD/MM/YYYY"),
        ]
        for w, lab in specs:
            _field(draw, hx, hy, w, hh, lab)
            hx += w

        usable_w = PAGE_W - 2 * SLIP_MARGIN
        usable_h = PAGE_H - HEADER_H - FOOTER_H - 50
        card_w = (usable_w - SLIP_GAP_X) // 2
        card_h = (usable_h - 4 * SLIP_GAP_Y) // 5
        start_x = SLIP_MARGIN
        start_y = HEADER_H + 40

        for idx, fname in enumerate(batch_photos[:STUDENTS_PER_PAGE]):
            col = idx % 2
            row = idx // 2
            x = start_x + col * (card_w + SLIP_GAP_X)
            y = start_y + row * (card_h + SLIP_GAP_Y)
            uid = Path(fname).stem

            _box(draw, [x, y, x + card_w, y + card_h], 3)

            # serial badge
            draw.rectangle([x, y, x + 70, y + 44], fill=(20, 20, 20))
            draw.text((x + 18, y + 8), str(idx + 1 + (page_num - 1) * STUDENTS_PER_PAGE), fill=(255, 255, 255), font=font_serial)

            draw.text((x + 82, y + 8), f"Photo No.  {uid}   (PRINTED)", fill=(0, 0, 0), font=font_id)

            # photo
            px, py = x + 16, y + 56
            _box(draw, [px, py, px + PHOTO_W, py + PHOTO_H], 2)
            try:
                img = Image.open(PIPELINE_OUTPUT / fname).convert("RGB")
                img = img.resize((PHOTO_W, PHOTO_H), Image.Resampling.LANCZOS)
                page.paste(img, (px, py))
            except Exception as e:
                logger.warning(f"Could not paste {fname}: {e}")
                draw.text((px + 70, py + PHOTO_H // 2 - 10), "PHOTO", fill=(120, 120, 120), font=font_id)

            cls_now = class_from_uid(school_code, uid) or "?"
            band_y = py + PHOTO_H
            band_h = 52
            draw.rectangle([px, band_y, px + PHOTO_W, band_y + band_h], outline=(0, 0, 0), width=2, fill=(255, 255, 255))
            cls_line = f"(CLASS: {cls_now})"
            cw = draw.textlength(cls_line, font=font_class)
            draw.text((px + (PHOTO_W - cw) / 2, band_y + 6), cls_line, fill=(0, 0, 0), font=font_class)
            hint = "Wrong? write NEW class"
            hw = draw.textlength(hint, font=font_small)
            draw.text((px + (PHOTO_W - hw) / 2, band_y + band_h + 2), hint, fill=(80, 80, 80), font=font_small)

            # writable fields
            fx = px + PHOTO_W + 16
            fw = x + card_w - fx - 16
            fy = y + 56
            name_h = int(card_h * 0.18)
            fat_h = int(card_h * 0.18)
            addr_h = int(card_h * 0.28)
            mob_h = int(card_h * 0.16)
            _field(draw, fx, fy, fw, name_h, "Student Name")
            fy += name_h
            _field(draw, fx, fy, fw, fat_h, "Father Name")
            fy += fat_h
            _field(draw, fx, fy, fw, addr_h, "Address")
            fy += addr_h
            _field(draw, fx, fy, fw, mob_h, "Mobile")
            # 10 digit guides
            box = fw / 10.0
            for k in range(1, 10):
                xx = fx + int(k * box)
                draw.line([(xx, fy + 28), (xx, fy + mob_h - 8)], fill=(160, 160, 160), width=1)

        info = f"School: {school_code}  |  {page_label}  |  Page {page_num}/{total_pages}  |  {datetime.now().strftime('%d-%b-%Y')}  |  10 slips / page"
        draw.text((70, PAGE_H - 70), info, fill=(60, 60, 60), font=font_small)
        return page

    # ==================== 1. PROCESS BIG CLASSES (Normal) ====================
    for bucket, photos in sorted(big_classes.items()):
        class_label = reverse_class_map(bucket)
        total = len(photos)
        pages = (total + STUDENTS_PER_PAGE - 1) // STUDENTS_PER_PAGE
        logger.info(f"  Big Class {class_label}: {total} students â†’ {pages} page(s)")

        for p in range(pages):
            start = p * STUDENTS_PER_PAGE
            batch = photos[start : start + STUDENTS_PER_PAGE]
            page = create_page(batch, f"Class: {class_label}", p+1, pages)

            sheet_name = f"PRINT_SHEET_{school_code}_{class_label}_P{p+1}.jpg"
            sheet_path = PRINT_SHEETS_FOLDER / sheet_name
            page.save(sheet_path, quality=95)
            all_sheet_paths.append(sheet_path)
            logger.info(f"    Saved: {sheet_name}")

    # ==================== 2. PROCESS SMALL CLASSES (Combine them) ====================
    if small_classes:
        # Saari small classes ki photos ek list mein daalo
        combined_small = []
        small_labels = []
        for bucket, photos in sorted(small_classes.items()):
            class_label = reverse_class_map(bucket)
            combined_small.extend(photos)
            small_labels.append(f"{class_label}({len(photos)})")

        total_small = len(combined_small)
        pages = (total_small + STUDENTS_PER_PAGE - 1) // STUDENTS_PER_PAGE
        label_text = " + ".join(small_labels)
        logger.info(f"  Small Classes Combined: {label_text} â†’ Total {total_small} students â†’ {pages} page(s)")

        for p in range(pages):
            start = p * STUDENTS_PER_PAGE
            batch = combined_small[start : start + STUDENTS_PER_PAGE]
            page = create_page(batch, f"Small Classes", p+1, pages)

            sheet_name = f"PRINT_SHEET_{school_code}_SMALL_CLASSES_P{p+1}.jpg"
            sheet_path = PRINT_SHEETS_FOLDER / sheet_name
            page.save(sheet_path, quality=95)
            all_sheet_paths.append(sheet_path)
            logger.info(f"    Saved: {sheet_name}")

    # ==================== COMBINED PDF ====================
    if all_sheet_paths:
        try:
            images = [Image.open(p) for p in all_sheet_paths]
            pdf_path = PRINT_SHEETS_FOLDER / f"SAINI_ALL_PRINT_SHEETS_{school_code}.pdf"
            images[0].save(pdf_path, save_all=True, append_images=images[1:],
                           quality=95, dpi=(300, 300))
            logger.info(f"âœ… Combined PDF created: {pdf_path.name} ({len(images)} pages)")
        except Exception as e:
            logger.error(f"PDF creation failed: {e}")
        try:
            status_mark(school_code, "slips_sent", done=True, count=len(all_photos),
                        note=f"{len(all_sheet_paths)} sheets")
        except Exception as e:
            logger.warning(f"Status update failed (step5): {e}")
    else:
        logger.warning("No print sheets were generated.")

# ====================== STEP 5C: RETURNED SLIPS â†’ GEMINI OCR â†’ EXCEL ======================
def step5c_process_returned_slips(school_code: str) -> int:
    """Scan folder: RETURNED_SLIPS/{SCHOOL_CODE}/*.jpg
    Gemini OCR â†’ student_data.xlsx + Google CSV + RAW_TEXT.xlsx
    """
    logger.info("=== STEP 5C: Returned teacher slips (Gemini OCR) ===")
    slip_dir = RETURNED_SLIPS / school_code
    safe_makedirs(slip_dir)
    scans = [
        p for p in slip_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and not p.name.startswith("_")
    ]
    if not scans:
        logger.info(f"No new scans in {slip_dir}")
        logger.info("Teacher-filled slips yahan rakho, phir Mode C chalao.")
        return 0
    try:
        from slip_ocr import process_school
        result = process_school(school_code)
        logger.info(f"OCR result: {result}")
        return int(result.get("approved") or 0)
    except RuntimeError as e:
        logger.error(str(e))
        return 0
    except Exception as e:
        logger.exception(f"Slip OCR failed: {e}")
        return 0


# ====================== STEP 5D: CORRECTION SLIPS â†’ GEMINI OCR â†’ EXCEL ======================
def step5d_process_corrections(school_code: str) -> int:
    """Scan folder: RETURNED_CORRECTIONS/{SCHOOL_CODE}/*.jpg
    Gemini OCR RIGHT values â†’ student_data.xlsx by PHOTO NO / UID
    Blank template: CORRECTION_SLIPS/ID_CARD_CORRECTION_SLIP_A4.pdf
    """
    logger.info("=== STEP 5D: ID card correction slips (Gemini OCR) ===")
    slip_dir = RETURNED_CORRECTIONS / school_code
    safe_makedirs(slip_dir)
    safe_makedirs(CORRECTION_SLIPS)
    scans = [
        p for p in slip_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and not p.name.startswith("_")
    ]
    if not scans:
        logger.info(f"No correction scans in {slip_dir}")
        logger.info("Filled correction slips yahan rakho, phir Mode D chalao.")
        logger.info(f"Blank template: {CORRECTION_SLIPS / 'ID_CARD_CORRECTION_SLIP_A4.pdf'}")
        return 0
    try:
        from slip_ocr import process_corrections
        result = process_corrections(school_code)
        logger.info(f"Correction OCR result: {result}")
        return int(result.get("approved") or 0)
    except RuntimeError as e:
        logger.error(str(e))
        return 0
    except Exception as e:
        logger.exception(f"Correction OCR failed: {e}")
        return 0


# ====================== STEP 6: DATA MERGING (STRONG & SYNTHETIC-ID FREE) ======================
def _is_blank(v) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return True
    s = str(v).strip().upper()
    return s in ("", "NAN", "NONE", "NULL", "NAT")


def step6_data_merge(school_code: str, overwrite: bool = False):
    """
    Default: sirf KHALI fields bharo. Refined data mat chhedo.
    overwrite=True tabhi jab tum explicitly force karo.
    """
    logger.info("=== STEP 6: Data merge (FILL-EMPTY ONLY, no refine) ===")
    master = STUDENT_DATABASE
    if not master.exists():
        logger.error("student_data.xlsx missing")
        return

    csv_path, csv_day = resolve_school_csv(school_code)
    if csv_path:
        df_google = pd.read_csv(csv_path, dtype=str, low_memory=False)
        logger.info(f"Step6 incoming = daily CSV {csv_day} ({csv_path.name})")
    else:
        # No Common CSV fallback: the Individual CSV is optional for this merge.
        df_google = pd.DataFrame()
    df_ocr = pd.read_excel(RAW_OCR_EXCEL, dtype=str) if RAW_OCR_EXCEL.exists() else pd.DataFrame()

    for df in (df_google, df_ocr):
        if not df.empty and "school_code" in df.columns:
            df.drop(df.index[df["school_code"].astype(str).str.upper().str.strip() != school_code], inplace=True)

    incoming = []
    for df, source in ((df_google, "google"), (df_ocr, "ocr")):
        if df.empty:
            continue
        id_col = find_id_column(df)
        if not id_col:
            continue
        for _, row in df.iterrows():
            uid = str(row.get(id_col, "")).strip().upper()
            if not uid:
                continue
            incoming.append({
                "student_unique_id": uid,
                "school_code": school_code,
                "student_name": clean_for_display(row.get("student_name", "")),
                "father_name": clean_for_display(row.get("father_name", "")),
                "class": normalize_class_name(row.get("class", "")),
                "mob_number": fix_mobile(row.get("mob_number", "")),
                "address": clean_for_display(row.get("address", "")),
                "source": source,
                "timestamp": datetime.now().isoformat(),
            })

    if not incoming:
        logger.info("No incoming form/OCR rows.")
        return

    # last source wins inside incoming only
    by_uid = {}
    for rec in incoming:
        by_uid[rec["student_unique_id"]] = rec

    backup = master.with_name(master.stem + f"_BACKUP_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx")
    shutil.copy2(master, backup)
    logger.info(f"Backup: {backup.name}")

    book = openpyxl.load_workbook(master)
    sheet = book.active
    hmap = sheet_header_map(sheet)
    uid_col = col_index(hmap, "student_unique_id")
    if not uid_col:
        logger.error("student_unique_id column missing")
        return

    uid_to_row = {}
    for r in range(2, sheet.max_row + 1):
        u = str(sheet.cell(r, uid_col).value or "").strip().upper()
        if u:
            uid_to_row[u] = r

    fillable = ("student_name", "father_name", "class", "mob_number", "address")
    updated = added = skipped_filled = 0
    template_row = max(2, sheet.max_row)

    for uid, rec in by_uid.items():
        if uid in uid_to_row:
            r = uid_to_row[uid]
            patch = {}
            for key in fillable:
                new_v = rec.get(key, "")
                if not new_v:
                    continue
                col = col_index(hmap, key)
                if not col:
                    continue
                old_v = sheet.cell(r, col).value
                if overwrite or _is_blank(old_v):
                    patch[key] = new_v
                else:
                    skipped_filled += 1
            if patch:
                write_by_name(sheet, r, hmap, patch, template_row)
                updated += 1
        else:
            # naya UID â€” photo-less row add
            r = sheet.max_row + 1
            write_by_name(sheet, r, hmap, rec, template_row)
            uid_to_row[uid] = r
            added += 1

    book.save(master)
    logger.info(f"Step6 fill-empty: updated_rows={updated} added={added} kept_manual_cells={skipped_filled}")

# ====================== STEP 7: SAFE PHOTO SYNC ======================
def step7_sync_photos(school_code: str):
    logger.info("=== STEP 7: Syncing Photos into PHOTO_LIBRARY ===")
    master = STUDENT_DATABASE
    if not master.exists():
        logger.warning("No master database found. Skipping photo sync.")
        return

    df = pd.read_excel(master, dtype=str)
    df_school = df[df["school_code"] == school_code].copy()
    if df_school.empty:
        logger.info("No records for this school in database.")
        return

    target_folder = PHOTO_LIBRARY / school_code
    safe_makedirs(target_folder)
    backup_dir = PHOTO_LIBRARY / f"{school_code}_SYNC_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}"
    safe_makedirs(backup_dir)

    copied = 0
    for _, row in df_school.iterrows():
        uid = str(row.get("student_unique_id", "")).strip()
        src = str(row.get("STUDENT_PHOTO_PATH", "")).strip()
        if not uid or not src or not Path(src).exists():
            continue

        dest = target_folder / f"{uid}.jpg"
        try:
            src_path = Path(src).resolve()
            dest_path = dest.resolve()

            # à¤…à¤—à¤° source à¤”à¤° destination à¤à¤• à¤¹à¥€ à¤«à¤¾à¤‡à¤² à¤¹à¥ˆ à¤¤à¥‹ skip à¤•à¤°à¥‹
            if src_path == dest_path:
                continue

            if dest.exists():
                shutil.copy2(dest, backup_dir / f"{uid}_old.jpg")

            shutil.copy2(src, dest)
            copied += 1
        except Exception as e:
            logger.warning(f"Sync error for {uid}: {e}")

    logger.info(f"âœ… Step 7 done. {copied} photos synced/verified in PHOTO_LIBRARY.")


# ====================== STEP 7B: SMART PHOTO PATH UPDATE (LOCAL + DRIVE) ======================
def step7b_update_photo_path(school_code: str):
    """
    Smart Photo Path Updater:
    1. à¤ªà¤¹à¤²à¥‡ PHOTO_LIBRARY à¤®à¥‡à¤‚ local photo à¤¢à¥‚à¤‚à¤¢à¤¤à¤¾ à¤¹à¥ˆ
    2. à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾ à¤¤à¥‹ GETID.xlsx à¤¸à¥‡ Drive Link à¤²à¥‡à¤¤à¤¾ à¤¹à¥ˆ
    3. student_data.xlsx à¤•à¥‡ STUDENT_PHOTO_PATH à¤•à¥‹ update à¤•à¤°à¤¤à¤¾ à¤¹à¥ˆ
    """
    logger.info("=== STEP 7B: Smart Photo Path Update (Local Preferred + Drive Fallback) ===")
    
    master = STUDENT_DATABASE
    if not master.exists():
        logger.error("student_data.xlsx not found!")
        return

    # ---------- 1. Local Photos Map à¤¬à¤¨à¤¾à¤“ ----------
    school_lib = PHOTO_LIBRARY / school_code
    local_map = {}
    if school_lib.exists():
        for f in school_lib.glob("*.jpg"):
            local_map[f.stem.upper()] = str(f.resolve())
        logger.info(f"Local photos found: {len(local_map)}")

    # ---------- 2. GETID.xlsx à¤¸à¥‡ Drive Links Map à¤¬à¤¨à¤¾à¤“ ----------
    getid_path = BASE_PROJECT.parent / "SAINI_ID_CARD (Responses).xlsx"   # â† à¤…à¤ªà¤¨à¤¾ path à¤¬à¤¦à¤² à¤¸à¤•à¤¤à¥‡ à¤¹à¥‹
    drive_map = {}
    
    if getid_path.exists():
        try:
            df_getid = pd.read_excel(
    getid_path,
    sheet_name="GETID",
    dtype=str
)
            for _, row in df_getid.iterrows():
                file_name = str(row.get("File Name", "")).strip()
                if not file_name:
                    continue
                clean = file_name.replace(".jpg", "").replace(".jpeg", "").replace(".JPG", "").replace(".JPEG", "").strip().upper()
                link = str(row.get("Direct Link", "")).strip()
                if clean and link:
                    drive_map[clean] = link
            logger.info(f"Drive links from GETID: {len(drive_map)}")
        except Exception as e:
            logger.error(f"GETID.xlsx à¤ªà¤¢à¤¼à¤¨à¥‡ à¤®à¥‡à¤‚ error: {e}")
    else:
        logger.warning(f"GETID.xlsx à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾ â†’ {getid_path}")

    if not local_map and not drive_map:
        logger.warning("à¤¨à¤¾ local photos à¤®à¤¿à¤²à¥‡, à¤¨à¤¾ Drive linksà¥¤ à¤•à¥à¤› update à¤¨à¤¹à¥€à¤‚ à¤¹à¥‹à¤—à¤¾à¥¤")
        return

    # ---------- 3. student_data.xlsx à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤°à¥‹ ----------
    book = openpyxl.load_workbook(master)
    sheet = book.active

    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    
    try:
        uid_col     = headers.index("student_unique_id") + 1
        photo_col   = headers.index("STUDENT_PHOTO_PATH") + 1
        school_col  = headers.index("school_code") + 1
    except ValueError as e:
        logger.error(f"à¤œà¤°à¥‚à¤°à¥€ column à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾: {e}")
        return

    updated = 0
    local_used = 0
    drive_used = 0

    for row_idx in range(2, sheet.max_row + 1):
        school = str(sheet.cell(row=row_idx, column=school_col).value or "").strip().upper()
        if school != school_code.upper():
            continue

        uid = str(sheet.cell(row=row_idx, column=uid_col).value or "").strip().upper()
        if not uid:
            continue

        # Priority 1: Drive Link
        if uid in drive_map:
            sheet.cell(row=row_idx, column=photo_col).value = drive_map[uid]
            updated += 1
            drive_used += 1
            continue

        # Priority 2: Local Path
        if uid in local_map:
            sheet.cell(row=row_idx, column=photo_col).value = local_map[uid]
            updated += 1
            local_used += 1


    # ---------- Save with Permission Error Handling ----------
    try:
        book.save(master)
        logger.info(f"âœ… Total Updated : {updated}")
        logger.info(f"   â†’ Local Path  : {local_used}")
        logger.info(f"   â†’ Drive Link  : {drive_used}")
    except PermissionError:
        logger.error("=" * 60)
        logger.error("âŒ PERMISSION DENIED!")
        logger.error("student_data.xlsx à¤«à¤¾à¤‡à¤² Excel à¤¯à¤¾ à¤•à¤¿à¤¸à¥€ à¤”à¤° à¤ªà¥à¤°à¥‹à¤—à¥à¤°à¤¾à¤® à¤®à¥‡à¤‚ à¤–à¥à¤²à¥€ à¤¹à¥à¤ˆ à¤¹à¥ˆà¥¤")
        logger.error("à¤•à¥ƒà¤ªà¤¯à¤¾ Excel à¤ªà¥‚à¤°à¥€ à¤¤à¤°à¤¹ à¤¬à¤‚à¤¦ à¤•à¤°à¤•à¥‡ à¤«à¤¿à¤° à¤¸à¥‡ Run à¤•à¤°à¥‡à¤‚à¥¤")
        logger.error("=" * 60)
        raise
    except Exception as e:
        logger.error(f"Save à¤•à¤°à¤¤à¥‡ à¤¸à¤®à¤¯ error à¤†à¤¯à¤¾: {e}")
        raise

# ====================== STEP R: FULLY AUTOMATIC REASSIGN MIXED PHOTOS ======================
def step_reassign_mixed(school_code: str):
    """
    Fully Automatic Reassign System
    - MIX range (50000-59999) à¤•à¥€ photos à¤¢à¥‚à¤‚à¤¢à¤¤à¤¾ à¤¹à¥ˆ
    - Name + Father Name + Valid Class à¤¹à¥‹à¤¨à¥‡ à¤ªà¤° target class à¤®à¥‡à¤‚ shift à¤•à¤°à¤¤à¤¾ à¤¹à¥ˆ
    - Duplicate prevention + next free number + safe rename + Excel update
    """
    logger.info("=== STEP R: Fully Automatic Reassign of MIXED Photos ===")
    
    master = STUDENT_DATABASE
    if not master.exists():
        logger.error("student_data.xlsx à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾!")
        return

    school_lib = PHOTO_LIBRARY / school_code
    if not school_lib.exists():
        logger.warning(f"Photo library à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾: {school_lib}")
        return

    # ---------- 1. Excel Load ----------
    book = openpyxl.load_workbook(master)
    sheet = book.active
    hmap = sheet_header_map(sheet)

    uid_col     = col_index(hmap, "student_unique_id")
    name_col    = col_index(hmap, "student_name")
    father_col  = col_index(hmap, "father_name")
    class_col   = col_index(hmap, "class")
    photo_col   = col_index(hmap, "STUDENT_PHOTO_PATH")
    school_col  = col_index(hmap, "school_code")

    required = [uid_col, name_col, father_col, class_col, photo_col, school_col]
    if not all(required):
        logger.error("à¤œà¤°à¥‚à¤°à¥€ columns à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥‡!")
        return

    # ---------- 2. Existing UIDs (Duplicate Protection) ----------
    existing_uids = set()
    for r in range(2, sheet.max_row + 1):
        u = str(sheet.cell(r, uid_col).value or "").strip().upper()
        if u:
            existing_uids.add(u)

    # ---------- 3. Find MIX candidates ----------
    mix_candidates = []
    for r in range(2, sheet.max_row + 1):
        school = str(sheet.cell(r, school_col).value or "").strip().upper()
        if school != school_code.upper():
            continue

        uid = str(sheet.cell(r, uid_col).value or "").strip().upper()
        if not uid.startswith(school_code.upper()):
            continue

        num_part = "".join(filter(str.isdigit, uid.replace(school_code.upper(), "")))
        try:
            num = int(num_part)
        except:
            continue
        if not (50000 <= num <= 59999):
            continue

        name   = clean_for_display(sheet.cell(r, name_col).value)
        father = clean_for_display(sheet.cell(r, father_col).value)
        cls_raw = sheet.cell(r, class_col).value
        cls    = normalize_class_name(cls_raw)

        mix_candidates.append({
            "row": r,
            "uid": uid,
            "name": name,
            "father": father,
            "class": cls,
            "class_raw": str(cls_raw or "").strip()
        })

    if not mix_candidates:
        logger.info(f"âœ… {school_code} à¤•à¥‡ à¤²à¤¿à¤ à¤•à¥‹à¤ˆ MIX photo à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥€à¥¤")
        return

    logger.info(f"Total MIX candidates found: {len(mix_candidates)}")

    # ---------- 4. Next available number helper ----------
    def get_next_number(target_class: str) -> int | None:
        if target_class not in CLASS_RANGES:
            return None
        _, range_start, range_end = CLASS_RANGES[target_class]
        highest = range_start - 1

        def extract_num(stem: str) -> int | None:
            stem = stem.upper()
            sc = school_code.upper()
            try:
                if target_class in ("X", "XI", "XII"):
                    prefix = sc + target_class
                    if stem.startswith(prefix):
                        num_str = "".join(filter(str.isdigit, stem[len(prefix):]))
                        return int(num_str) if num_str else None
                else:
                    if stem.startswith(sc):
                        num_str = "".join(filter(str.isdigit, stem[len(sc):]))
                        return int(num_str) if num_str else None
            except:
                return None
            return None

        # PHOTO_LIBRARY check
        for f in school_lib.glob("*.jpg"):
            n = extract_num(f.stem)
            if n is not None and range_start <= n <= range_end:
                highest = max(highest, n)

        # existing_uids check
        for uid in existing_uids:
            n = extract_num(uid)
            if n is not None and range_start <= n <= range_end:
                highest = max(highest, n)

        next_num = highest + 1
        if next_num > range_end:
            logger.warning(f"Class {target_class} range full!")
            return None
        return next_num

    # ---------- 5. Process ----------
    success = 0
    skipped = 0
    conflicts = 0
    backup_dir = PHOTO_LIBRARY / f"{school_code}_MIX_REASSIGN_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}"
    safe_makedirs(backup_dir)

    for item in mix_candidates:
        row = item["row"]
        old_uid = item["uid"]
        name = item["name"]
        father = item["father"]
        target_class = item["class"]

        if not name or not father:
            logger.info(f"  SKIP (incomplete data): {old_uid}")
            skipped += 1
            continue

        if target_class not in CLASS_RANGES:
            logger.warning(
                f"  SKIP (invalid class '{item.get('class_raw', target_class)}' â†’ '{target_class}'): {old_uid}"
            )
            skipped += 1
            continue

        next_num = get_next_number(target_class)
        if next_num is None:
            logger.warning(f"  SKIP (no free number): {old_uid}")
            conflicts += 1
            continue

        # New UID build
        if target_class in ("X", "XI", "XII"):
            new_uid = f"{school_code}{target_class}{next_num:03d}"
        elif CLASS_RANGES[target_class][1] >= 10000:
            new_uid = f"{school_code}{next_num:05d}"
        else:
            new_uid = f"{school_code}{next_num:04d}"

        new_uid = new_uid.upper()

        if new_uid in existing_uids:
            logger.warning(f"  CONFLICT: {old_uid} â†’ {new_uid}")
            conflicts += 1
            continue

        new_photo = school_lib / f"{new_uid}.jpg"

        def find_mix_photo(uid: str):
            """JPSN folder, purane MIX backups, OUTPUT, INPUT â€” kahi bhi mil jaye."""
            names = [f"{uid}.jpg", f"{uid}.jpeg", f"{uid}.JPG", f"{uid}.JPEG"]
            search_dirs = [school_lib, PIPELINE_OUTPUT, RENAME_OUTPUT]
            try:
                for p in PHOTO_LIBRARY.iterdir():
                    if p.is_dir() and p.name.upper().startswith(f"{school_code.upper()}_MIX_REASSIGN_BACKUP"):
                        search_dirs.append(p)
            except Exception:
                pass
            for folder in search_dirs:
                if not folder.exists():
                    continue
                for n in names:
                    cand = folder / n
                    if cand.exists() and cand.is_file():
                        return cand
            return None

        found = find_mix_photo(old_uid)
        if found is None:
            logger.warning(f"  SKIP (photo missing): {old_uid}")
            skipped += 1
            continue

        old_photo = school_lib / f"{old_uid}.jpg"
        if found.resolve() != old_photo.resolve():
            try:
                shutil.copy2(found, old_photo)
                logger.info(f"  â†© photo restore: {found.parent.name}/{found.name}")
            except Exception as e:
                logger.warning(f"  SKIP (restore fail {old_uid}): {e}")
                skipped += 1
                continue

        try:
            # Backup
            shutil.copy2(old_photo, backup_dir / f"{old_uid}.jpg")

            # Rename
            shutil.move(str(old_photo), str(new_photo))

            # Excel update â€” UID + photo path + canonical class (LKG not L.K.G.)
            sheet.cell(row=row, column=uid_col).value = new_uid
            sheet.cell(row=row, column=photo_col).value = str(new_photo.resolve())
            sheet.cell(row=row, column=class_col).value = target_class

            existing_uids.add(new_uid)
            existing_uids.discard(old_uid)

            success += 1
            logger.info(f"  âœ… {old_uid} â†’ {new_uid} ({target_class}) | {name}")

        except Exception as e:
            logger.error(f"  FAILED {old_uid}: {e}")
            if new_photo.exists() and not old_photo.exists():
                try:
                    shutil.move(str(new_photo), str(old_photo))
                except:
                    pass

    # ---------- 6. Save ----------
    try:
        book.save(master)
        logger.info("=" * 60)
        logger.info(f"âœ… Reassign Complete â†’ {school_code}")
        logger.info(f"   Successful : {success}")
        logger.info(f"   Skipped    : {skipped}")
        logger.info(f"   Conflicts  : {conflicts}")
        logger.info(f"   Backup     : {backup_dir.name}")
        logger.info("=" * 60)

        try:
            status_mark(school_code, "reassign_done", done=True, count=success,
                        note=f"{success} MIX reassigned")
        except:
            pass

    except PermissionError:
        logger.error("âŒ Excel à¤«à¤¾à¤‡à¤² à¤–à¥à¤²à¥€ à¤¹à¥ˆ! à¤¬à¤‚à¤¦ à¤•à¤°à¤•à¥‡ à¤«à¤¿à¤° à¤¸à¥‡ à¤šà¤²à¤¾à¤“à¥¤")
        raise

# ====================== STEP 8: LAUNCH ID CARD GENERATOR ======================
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_master_roster_authorization(school_code: str, config_xlsx: Path, student_xlsx: Path, manifest_path: Path):
    """Create a hash-bound, explicit operator-approved Mode B roster snapshot.

    Duplicate (school_code, student_unique_id) rows are excluded, never merged/deleted.
    This is NOT an OCR batch journal and must not be used for Modes C/D.
    """
    code = str(school_code or "").strip().upper()
    if not code:
        raise RuntimeError("School code is required for master-roster authorization")
    for path in (config_xlsx, student_xlsx):
        if not path.is_file():
            raise RuntimeError(f"Required Excel workbook missing: {path}")

    cfg = pd.read_excel(config_xlsx, sheet_name="Sheet1", dtype=str).fillna("")
    stu = pd.read_excel(student_xlsx, sheet_name="Sheet1", dtype=str).fillna("")
    if "school_code" not in cfg.columns or "school_code" not in stu.columns:
        raise RuntimeError("Both Excel workbooks must contain school_code column")
    if "student_unique_id" not in stu.columns:
        raise RuntimeError("student_data.xlsx must contain student_unique_id column")
    cfg_codes = {str(v).strip().upper() for v in cfg["school_code"] if str(v).strip()}
    if code not in cfg_codes:
        raise RuntimeError(f"School {code} is not present in school_config_front.xlsx")

    rows_by_key = {}
    display = {}
    for idx, row in stu.iterrows():
        row_school = str(row.get("school_code", "")).strip().upper()
        uid = str(row.get("student_unique_id", "")).strip().upper()
        if not row_school or row_school == "NAN" or not uid or uid == "NAN":
            continue
        key = (row_school, uid)
        rows_by_key.setdefault(key, []).append(int(idx) + 2)
        display[key] = (row_school, uid)

    allowed, blocked = {}, {}
    for key, excel_rows in rows_by_key.items():
        row_school, uid = display[key]
        if len(excel_rows) > 1:
            blocked.setdefault(row_school, []).append({
                "student_unique_id": uid,
                "excel_rows": excel_rows,
                "reason": "duplicate_student_unique_id",
            })
        else:
            allowed.setdefault(row_school, []).append(uid)
    for key in allowed:
        allowed[key] = sorted(set(allowed[key]))
    for key in blocked:
        blocked[key] = sorted(blocked[key], key=lambda x: x["student_unique_id"])

    if not allowed.get(code):
        raise RuntimeError(f"No unambiguous student IDs available for school {code}; refusing launch")
    print("\nMODE B MASTER-ROSTER AUTHORIZATION")
    print(f"School: {code}")
    print(f"Config workbook: {config_xlsx}")
    print(f"Student workbook: {student_xlsx}")
    print(f"Eligible unique IDs for {code}: {len(allowed[code])}")
    print(f"Duplicate IDs blocked across all schools: {sum(len(v) for v in blocked.values())}")
    print("This authorizes only the current Excel snapshot for ID-card generation.")
    print("Option C/D OCR Gate is unchanged. No student workbook is modified.")
    phrase = f"AUTHORIZE MASTER ROSTER {code}"
    typed = input(f"To approve this exact snapshot, type exactly: {phrase}\n> ").strip().upper()
    if typed != phrase:
        raise RuntimeError("Master-roster authorization not approved; no GUI launched")

    manifest = {
        "schema_version": 1,
        "mode": "MASTER_ROSTER",
        "allowed_outputs": ["IDCARD"],
        "school_codes": sorted(cfg_codes),
        "config_path": str(config_xlsx.resolve()),
        "student_path": str(student_xlsx.resolve()),
        "config_sha256": _sha256_file(config_xlsx),
        "student_sha256": _sha256_file(student_xlsx),
        "student_ids_by_school": allowed,
        "blocked_duplicate_ids_by_school": blocked,
        "unambiguous_student_id_count": sum(len(v) for v in allowed.values()),
        "blocked_duplicate_id_count": sum(len(v) for v in blocked.values()),
        "approved_by_interactive_operator": True,
        "approval_phrase": phrase,
        "authorized_school": code,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temp_path, manifest_path)
    return manifest_path


def step8_launch_id_card(school_code: str = "", workflow_mode: str = ""):
    """Launch ID-card GUI; Mode B uses explicit Excel roster auth, C/D retain OCR Gate."""
    logger.info("=== STEP 8: Launching SAINI ID Card Generator (Excel-only) ===")
    src, day, source_mode = prepare_id_source(school_code)
    if not src or source_mode != "xlsx":
        logger.error("Local Excel source unavailable; refusing ID-card launch.")
        return False

    # Prefer the explicitly uploaded/root production entrypoint, then configured project copy.
    candidates = [BASE_PROJECT.parent / "SAINI_ID_CARD.py", *ID_CARD_SCRIPT_CANDIDATES]
    script_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if not script_path:
        logger.error("SAINI_ID_CARD.py not found in expected locations; refusing launch.")
        return False

    env = os.environ.copy()
    for key in ("SAINI_GATE_JOURNAL", "SAINI_GATE_BATCH_ID", "SAINI_GATE_FINGERPRINT",
                "SAINI_MASTER_ROSTER_MANIFEST", "SAINI_MASTER_ROSTER_CONFIG_XLSX",
                "SAINI_MASTER_ROSTER_STUDENT_XLSX", "SAINI_AUTH_MODE"):
        env.pop(key, None)
    env["SAINI_ID_SOURCE_CSV"] = ""
    env["SAINI_ID_SOURCE_DATE"] = ""
    env["SAINI_SCHOOL_CODE"] = str(school_code or "").strip().upper()
    env["SAINI_USE_STUDENT_DATA"] = "1"
    env["SAINI_DEV_CONFIG_XLSX"] = str(BASE_PROJECT.parent / "school_config_front.xlsx")
    env["SAINI_DEV_STUDENT_XLSX"] = str(STUDENT_DATABASE)

    if str(workflow_mode or "").strip().upper() in ("B", "E"):
        config_xlsx = BASE_PROJECT.parent / "school_config_front.xlsx"
        manifest_path = BASE_PROJECT.parent / "MASTER_ROSTER_AUTHORIZATION.json"
        try:
            manifest_path = _create_master_roster_authorization(
                school_code, config_xlsx, Path(STUDENT_DATABASE), manifest_path
            )
        except Exception as exc:
            logger.error(f"Mode B master-roster authorization failed; GUI not launched: {exc}")
            return False
        env["SAINI_AUTH_MODE"] = "MASTER_ROSTER"
        env["SAINI_MASTER_ROSTER_MANIFEST"] = str(manifest_path)
        env["SAINI_MASTER_ROSTER_CONFIG_XLSX"] = str(config_xlsx.resolve())
        env["SAINI_MASTER_ROSTER_STUDENT_XLSX"] = str(Path(STUDENT_DATABASE).resolve())
        logger.info("Mode B/E authorization: hash-bound Local Excel master roster; Option C stays for slip OCR only.")
    else:
        # Modes A/C/D/E must continue using real independently verified Option C Gate evidence.
        try:
            config_path = Path(__file__).resolve().parent / "saini_config.json"
            if not config_path.is_file():
                raise RuntimeError(f"Config file missing: {config_path}")
            config_data = json.loads(config_path.read_text(encoding="utf-8-sig"))
            base_project_value = str(config_data.get("BASE_PROJECT") or "").strip()
            if not base_project_value:
                raise RuntimeError("BASE_PROJECT missing from saini_config.json")
            journal_root = (Path(base_project_value).resolve() / "OPTION_C_JOURNAL").resolve()
            handoff_path = journal_root / "latest_verified_batch.handoff"
            if not handoff_path.is_file():
                raise RuntimeError(f"Validated Option C handoff missing: {handoff_path}")
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            if not isinstance(handoff, dict) or handoff.get("schema_version") != 1:
                raise RuntimeError("Unsupported or invalid handoff schema")
            handoff_batch = str(handoff.get("batch_id") or "").strip()
            handoff_school = str(handoff.get("school_code") or "").strip().upper()
            handoff_fingerprint = str(handoff.get("content_fingerprint") or "").strip()
            handoff_journal_value = str(handoff.get("journal_path") or "").strip()
            expected_school = str(school_code or "").strip().upper()
            if not expected_school or handoff_school != expected_school:
                raise RuntimeError(f"Handoff school mismatch: requested={expected_school!r}, handoff={handoff_school!r}")
            if not handoff_batch or not handoff_fingerprint or not handoff_journal_value:
                raise RuntimeError("Handoff missing batch ID, fingerprint or journal path")
            handoff_journal = Path(handoff_journal_value).resolve()
            if handoff_journal.parent != journal_root or not handoff_journal.is_file():
                raise RuntimeError("Handoff journal missing or outside configured journal directory")
            env["SAINI_GATE_JOURNAL"] = str(handoff_journal)
            env["SAINI_GATE_BATCH_ID"] = handoff_batch
            env["SAINI_GATE_FINGERPRINT"] = handoff_fingerprint
            env["SAINI_AUTH_MODE"] = "OPTION_C_GATE"
        except Exception as exc:
            logger.error(f"ID-card launch blocked: validated Gate evidence unavailable: {exc}")
            return False

    logger.info(f"ID-card source confirmed: Local Excel -> {src}")
    logger.info(f"Launching ID-card interface: {script_path}")
    try:
        result = subprocess.run([sys.executable, str(script_path)], cwd=str(script_path.parent), env=env)
        if result.returncode != 0:
            logger.error("ID-card interface returned non-zero status; no alternate-source fallback attempted.")
            return False
        return True
    except Exception as exc:
        logger.error(f"Failed to launch ID-card generator: {exc}")
        return False

# ====================== MODE E: ENROLL FROM LIVE GOOGLE SHEET ======================
def _is_garbage_school_code(val) -> bool:
    t = str(val or "").strip()
    if not t or t.lower() in ("nan", "none", "null"):
        return True
    return bool(re.fullmatch(r"\d+(\.0)?", t))


def _drive_file_id(val) -> str:
    v = str(val or "").strip()
    if not v or v.lower() in ("nan", "none"):
        return ""
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", v):
        return v
    m = re.search(r"/d/([A-Za-z0-9_-]+)", v)
    if m:
        return m.group(1)
    q = parse_qs(urlparse(v).query)
    return (q.get("id") or [""])[0]


def _gspread_client():
    if gspread is None or Credentials is None:
        raise RuntimeError("pip install gspread google-auth google-api-python-client")
    creds_file = SERVICE_ACCOUNT_JSON
    if not creds_file.exists():
        alt = Path(__file__).resolve().parent / "service_account.json"
        creds_file = alt if alt.exists() else creds_file
    if not creds_file.exists():
        raise FileNotFoundError(f"service_account.json not found: {SERVICE_ACCOUNT_JSON}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
    return gspread.authorize(creds), creds


def _drive_service(creds):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=creds)


def _download_drive_file(creds, file_id: str, dest: Path):
    """photo_downloader.py jaisa: shortcut / folder / image resolve karke RAW file INPUT mein."""
    from googleapiclient.http import MediaIoBaseDownload
    svc = _drive_service(creds)

    def _meta(fid):
        return svc.files().get(
            fileId=fid,
            fields="id,name,mimeType,trashed,shortcutDetails/targetId,shortcutDetails/targetMimeType",
            supportsAllDrives=True,
        ).execute()

    meta = _meta(file_id)
    if meta.get("trashed"):
        raise RuntimeError("Drive file Trash mein hai")
    mime = meta.get("mimeType") or ""
    rid = file_id
    if mime == "application/vnd.google-apps.shortcut":
        rid = (meta.get("shortcutDetails") or {}).get("targetId")
        if not rid:
            raise RuntimeError("Shortcut ka target nahi mila")
        meta = _meta(rid)
        mime = meta.get("mimeType") or ""
    if mime == "application/vnd.google-apps.folder":
        res = svc.files().list(
            q=f"'{rid}' in parents and mimeType contains 'image/' and trashed=false",
            fields="files(id,name,mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=10,
            orderBy="name",
        ).execute()
        files = res.get("files") or []
        if not files:
            raise RuntimeError("Folder mein image nahi")
        rid = files[0]["id"]
        mime = files[0].get("mimeType") or ""
    if mime and not (mime.startswith("image/") or mime in ("application/octet-stream",)):
        raise RuntimeError(f"Image nahi hai (mime={mime})")

    dest.parent.mkdir(parents=True, exist_ok=True)
    req = svc.files().get_media(fileId=rid, supportsAllDrives=True)
    with dest.open("xb") as fh:
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("Download empty")
    return rid


def _drive_find_child_folder(svc, parent_id: str, name: str):
    q = (
        f"'{parent_id}' in parents and name = '{name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = svc.files().list(
        q=q, fields="files(id,name)", pageSize=5,
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = res.get("files") or []
    return files[0]["id"] if files else None


def _drive_find_named_folder(svc, name: str):
    q = (
        f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    res = svc.files().list(
        q=q, fields="files(id,name)", pageSize=10,
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = res.get("files") or []
    return files[0]["id"] if files else None


def _upload_to_photochamber(creds, school_code: str, local_path: Path, filename: str) -> bool:
    """PHOTOCHAMBER upload.
    Service account ki storage quota 0 hoti hai â€” naya file kabhi SA se create mat karo.
    Shared Drive ho to create allowed (quota drive ki).
    My Drive ho to D:\\SHRI_JAI_SHRI_RAM\\PHOTOCHAMBER\\PHOTOCHAMBER par copy. Desktop sync user quota se upload karega.
    """
    from googleapiclient.http import MediaFileUpload
    svc = _drive_service(creds)
    root = _drive_find_named_folder(svc, "PHOTOCHAMBER")
    drive_id = ""
    if root:
        meta = svc.files().get(fileId=root, fields="id,driveId", supportsAllDrives=True).execute()
        drive_id = meta.get("driveId") or ""
    school_folder = _drive_find_child_folder(svc, root, school_code) if root else None
    if drive_id and not school_folder:
        created = svc.files().create(
            body={"name": school_code, "mimeType": "application/vnd.google-apps.folder", "parents": [root]},
            fields="id",
            supportsAllDrives=True,
        ).execute()
        school_folder = created["id"]
    if school_folder:
        q = f"'{school_folder}' in parents and name = '{filename}' and trashed = false"
        exist = (svc.files().list(
            q=q, fields="files(id,name)", pageSize=3,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files") or [])
        if exist:
            media = MediaFileUpload(str(local_path), mimetype="image/jpeg", resumable=True)
            svc.files().update(fileId=exist[0]["id"], media_body=media, supportsAllDrives=True).execute()
            logger.info(f"  Drive update PHOTOCHAMBER/{school_code}/{filename}")
            return True
        if drive_id:
            media = MediaFileUpload(str(local_path), mimetype="image/jpeg", resumable=True)
            svc.files().create(
                body={"name": filename, "parents": [school_folder]},
                media_body=media, fields="id", supportsAllDrives=True,
            ).execute()
            logger.info(f"  Shared Drive create PHOTOCHAMBER/{school_code}/{filename}")
            return True
    dest_dir = GOOGLE_DRIVE_PHOTOS / school_code
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if not dest.exists() or dest.stat().st_size != local_path.stat().st_size:
        shutil.copy2(local_path, dest)
    if not getattr(_upload_to_photochamber, "_told", False):
        logger.info("PHOTOCHAMBER naya file user Drive se jayega (D:\\SHRI_JAI_SHRI_RAM\\PHOTOCHAMBER). Service account se create band â€” quota 0.")
        _upload_to_photochamber._told = True
    logger.info(f"  PHOTOCHAMBER local sync {dest}")
    return True


def _upload_drive_replace(creds, file_id: str, local_path: Path) -> bool:
    """Processed photo ko USI Drive file par wapas overwrite karo."""
    from googleapiclient.http import MediaFileUpload
    svc = _drive_service(creds)
    media = MediaFileUpload(str(local_path), mimetype="image/jpeg", resumable=True)
    try:
        svc.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"  Drive replace fail {file_id}: {e}")
        return False


def _xlsx_tab_records(creds, file_id: str, tab_name: str) -> list:
    import io
    from googleapiclient.http import MediaIoBaseDownload
    svc = _drive_service(creds)
    req = svc.files().export_media(
        fileId=file_id,
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.seek(0)
    xl = pd.ExcelFile(buf)
    tab = tab_name if tab_name in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(xl, sheet_name=tab, dtype=str).fillna("")
    return df.to_dict(orient="records")


def _school_master_entry(creds, school_code: str):
    rows = _xlsx_tab_records(creds, HUB_SHEET_ID, SCHOOL_MASTER_TAB)
    want = str(school_code).strip().upper()
    for r in rows:
        if str(r.get("SCHOOL_CODE", "")).strip().upper() == want:
            return r
    return None


def _school_sheet_rows(creds, school_code: str):
    """SCHOOL_MASTER wali school sheet (MPA - MPA / STUDENTS). Hub me na ho to bhi enroll ho."""
    info = _school_master_entry(creds, school_code)
    if not info or not str(info.get("SHEET_ID", "")).strip():
        return []
    sid = str(info.get("SHEET_ID")).strip()
    tab = str(info.get("RESPONSE_SHEET_NAME") or "STUDENTS").strip() or "STUDENTS"
    try:
        rows = _xlsx_tab_records(creds, sid, tab)
    except Exception as e:
        logger.warning(f"School sheet export fail: {e}")
        return []
    for r in rows:
        r["school_code"] = school_code
        r["_from_school_sheet"] = "1"
    logger.info(f"School sheet rows: {len(rows)} ({sid})")
    return rows


def _write_uids_to_school_google_sheet(gc, school_code: str, creds, updates: list):
    """Individual SCHOOL sheet STUDENTS tab par official UID likho.
    Match: Drive file id, phir mobile+name, phir name+father+class.
    Same naam ki do rows (Faika) alag file id se alag UID leti hain.
    """
    if not updates:
        return 0
    info = _school_master_entry(creds, school_code)
    if not info or not str(info.get("SHEET_ID", "")).strip():
        logger.warning("SCHOOL_MASTER mein is school ki SHEET_ID nahi")
        return 0
    sid = str(info.get("SHEET_ID")).strip()
    tab = str(info.get("RESPONSE_SHEET_NAME") or "STUDENTS").strip() or "STUDENTS"
    ws = None
    for attempt in range(1, 4):
        try:
            ws = gc.open_by_key(sid).worksheet(tab)
            break
        except Exception as e:
            logger.warning(f"School sheet open attempt {attempt}: {e}")
            time.sleep(2 * attempt)
    if ws is None:
        logger.error(f"{school_code} Google STUDENTS sheet nahi khuli â€” UID wahan nahi likhe")
        return 0
    headers = ws.row_values(1)
    hmap = {str(h).strip().lower(): i + 1 for i, h in enumerate(headers)}
    uid_c = hmap.get("student_unique_id") or hmap.get("photo_no")
    photo_c = hmap.get("student_photo_path")
    name_c = hmap.get("student_name")
    fat_c = hmap.get("father_name")
    cls_c = hmap.get("class")
    mob_c = hmap.get("mob_number") or hmap.get("mobile")
    file_c = hmap.get("google_file_id")
    if not uid_c or not name_c:
        logger.error("School sheet mein student_unique_id / student_name column nahi")
        return 0
    by_file, by_mob, by_key = {}, {}, {}
    for u in updates:
        fid = str(u.get("gfile") or "").strip()
        if fid:
            by_file[fid] = u
        mob = fix_mobile(u.get("mobile", ""))
        if mob:
            by_mob[(normalize_key(u.get("name")), mob)] = u
        by_key.setdefault(_person_key(u["name"], u["father"], u["klass"]), u)
    written = 0
    used_uid = set()
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        def cell(col):
            if not col or col - 1 >= len(row):
                return ""
            return row[col - 1]
        fid = _drive_file_id(cell(file_c)) or _drive_file_id(cell(photo_c))
        rec = by_file.get(fid) if fid else None
        if rec is None and mob_c:
            rec = by_mob.get((normalize_key(cell(name_c)), fix_mobile(cell(mob_c))))
        if rec is None:
            rec = by_key.get(_person_key(cell(name_c), cell(fat_c), cell(cls_c)))
        if not rec or not rec.get("uid"):
            continue
        if rec["uid"] in used_uid and fid and fid != str(rec.get("gfile") or ""):
            continue
        ws.update_cell(i, uid_c, rec["uid"])
        if photo_c and rec.get("photo"):
            ws.update_cell(i, photo_c, rec["photo"])
        if file_c and rec.get("gfile"):
            ws.update_cell(i, file_c, rec["gfile"])
        used_uid.add(rec["uid"])
        written += 1
        logger.info(f"  SHEET UID {rec['uid']} â†’ {rec['name']} row {i}")
    logger.info(f"{school_code} STUDENTS sheet updated rows: {written}")
    return written


def _load_hub_rows_via_drive(creds) -> list:
    """Google Sheets values API skip. File ko xlsx export karke pandas se padho."""
    import io
    from googleapiclient.http import MediaIoBaseDownload
    svc = _drive_service(creds)
    req = svc.files().export_media(
        fileId=HUB_SHEET_ID,
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.seek(0)
    xl = pd.ExcelFile(buf)
    names = xl.sheet_names
    tab = HUB_TAB if HUB_TAB in names else names[0]
    logger.info(f"Drive export sheets={names} | using={tab}")
    df = pd.read_excel(xl, sheet_name=tab, dtype=str)
    return df.fillna("").to_dict(orient="records")


def _person_key(name, father, klass) -> str:
    return f"{normalize_key(name)}|{normalize_key(father)}|{normalize_class_name(klass)}"


def _clean_id_token(val) -> str:
    s = str(val or "").strip()
    if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
        s = s[:-2]
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def _parse_enroll_ts(raw):
    from datetime import datetime
    if raw is None or str(raw).strip() in ('', '-', 'None'):
        return None
    if hasattr(raw, 'year'):
        try:
            return datetime(raw.year, raw.month, raw.day, getattr(raw, 'hour', 0), getattr(raw, 'minute', 0), getattr(raw, 'second', 0))
        except Exception:
            return None
    s = str(raw).strip().replace('T', ' ')[:19]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%Y-%m-%d %H:%M', '%d-%m-%Y %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def write_enroll_to_local_xlsx(item):
    """Update official UID on existing local row. Do not append duplicates."""
    from openpyxl import load_workbook
    path = STUDENT_DATABASE
    if not path.exists():
        logger.warning("STUDENT_DATABASE missing")
        return False
    wb = load_workbook(path)
    ws = wb.active
    headers = [str(c.value).strip() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
    idx = {h.lower(): i + 1 for i, h in enumerate(headers) if h}
    def col(*names):
        for n in names:
            if n.lower() in idx:
                return idx[n.lower()]
        return None
    c_name = col("student_name")
    c_class = col("class")
    c_school = col("school_code")
    c_uid = col("student_unique_id")
    c_photo = col("STUDENT_PHOTO_PATH")
    c_father = col("father_name")
    if not all([c_name, c_class, c_school, c_uid]):
        logger.warning("local xlsx columns missing")
        return False
    uid = str(item.get("uid") or "").strip()
    name = str(item.get("name") or "").strip().upper()
    klass = str(item.get("klass") or "").strip().upper()
    school = str(item.get("school") or "").strip().upper()
    father = str(item.get("father") or "").strip().upper()
    hits = []
    for r in range(2, ws.max_row + 1):
        if str(ws.cell(r, c_school).value or "").strip().upper() != school:
            continue
        if str(ws.cell(r, c_name).value or "").strip().upper() != name:
            continue
        if str(ws.cell(r, c_class).value or "").strip().upper() != klass:
            continue
        hits.append(r)
    if father and c_father and len(hits) > 1:
        fhits = [r for r in hits if father in str(ws.cell(r, c_father).value or "").upper() or str(ws.cell(r, c_father).value or "").upper() in father]
        if fhits:
            hits = fhits
    if not hits:
        logger.warning("  LOCAL XLSX no row for %s %s %s", school, name, klass)
        return False
    if len(hits) != 1:
        logger.warning(
            "  LOCAL XLSX ambiguous match: %s %s %s; rows=%s. No update.",
            school, name, klass, hits
        )
        return False
    hit = hits[0]
    ws.cell(hit, c_uid, uid)
    if c_photo:
        try:
            outp = PIPELINE_OUTPUT / (uid + ".jpg")
        except Exception:
            outp = None
        if outp is not None and outp.exists():
            ws.cell(hit, c_photo, str(outp))
    wb.save(path)
    logger.info("  LOCAL XLSX UID %s updated row %s %s", uid, hit, path.name)
    return True
def stepE_enroll_from_sheet(school_code: str, bg_color: str = "W", cutoff=None, auto: bool = False, shared_rows=None, night_cards=None) -> int:
    """
    Mode E pipeline:
      1) Hub sheet se school rows padho (81769 garbage skip)
      2) Form ki UNPROCESSED photo Drive se local INPUT mein download
      3) Photo AI Lab (studio pipeline) se crop/finish
      4) Processed photo USI Drive file par wapas upload
      5) Processed copy PHOTO_LIBRARY + student_data.xlsx
    ID card ke liye sirf processed PHOTO_LIBRARY path use hota hai.
    """
    logger.info("=== MODE E: Enroll + RAW download + AI Lab + Drive replace ===")
    if _is_garbage_school_code(school_code):
        logger.error(f"{school_code} garbage code hai. AMAR / STVN / AIPS jaisa code dalo.")
        return 0

    master = STUDENT_DATABASE
    if not master.exists():
        logger.error("student_data.xlsx missing")
        return 0

    try:
        gc, creds = _gspread_client()
    except Exception as e:
        logger.error(f"Google login fail: {e}")
        return -1

    rows = None
    last_err = None
    if shared_rows is not None:
        rows = [dict(r) for r in shared_rows]
        logger.info(f"Hub rows shared: {len(rows)}")
        last_err = None
    for attempt in range(1, 5):
        if rows is not None and shared_rows is not None and attempt == 1:
            school_rows = _school_sheet_rows(creds, school_code)
            have = set()
            for rec in rows:
                fid = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
                if fid:
                    have.add(fid)
            added = 0
            for rec in school_rows:
                fid = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
                uid_already = str(rec.get("student_unique_id") or "").strip()
                local = str(rec.get("STUDENT_PHOTO_PATH") or "")
                if uid_already and local.lower().startswith(("d:\\", "d:/")):
                    continue
                if fid and fid in have:
                    continue
                rows.append(rec)
                if fid:
                    have.add(fid)
                added += 1
            logger.info(f"School sheet se extra rows (Drive link, UID khali): {added}")
            break
        try:
            rows = _load_hub_rows_via_drive(creds)
            logger.info(f"Hub rows via Drive export: {len(rows)}")
            school_rows = _school_sheet_rows(creds, school_code)
            have = set()
            for rec in rows:
                fid = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
                if fid:
                    have.add(fid)
            added = 0
            for rec in school_rows:
                fid = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
                uid_already = str(rec.get("student_unique_id") or "").strip()
                local = str(rec.get("STUDENT_PHOTO_PATH") or "")
                if uid_already and local.lower().startswith(("d:\\", "d:/")):
                    continue
                if fid and fid in have:
                    continue
                rows.append(rec)
                if fid:
                    have.add(fid)
                added += 1
            logger.info(f"School sheet se extra rows (Drive link, UID khali): {added}")
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.warning(f"Drive export attempt {attempt}/4 fail: {e}")
            time.sleep(2 * attempt)
    if rows is None:
        school_csv, _ = resolve_school_csv(school_code)
        if school_csv is not None:
            logger.warning(f"Drive export failed; using this school's Individual CSV only: {school_csv}")
            df = pd.read_csv(school_csv, dtype=str, low_memory=False).fillna("")
            if "school_code" not in df.columns:
                logger.error(f"Individual CSV has no school_code column: {school_csv}")
                return -1
            df = df[df["school_code"].astype(str).str.strip().str.upper() == str(school_code).strip().upper()]
            rows = df.to_dict(orient="records")
        else:
            logger.error(f"Hub data load failed and school Individual CSV is unavailable: {last_err}")
            return -1

    hub = None
    try:
        hub = gc.open_by_key(HUB_SHEET_ID).worksheet(HUB_TAB)
    except Exception as e:
        logger.warning(f"STATUS write handle skip (Sheets 500 ho sakti hai): {e}")
        hub = None

    hidx = {}
    if hub is not None:
        headers = hub.row_values(1)
        extra = ["STATUS", "PHOTO_NO", "ENROLLMENT_NO", "LOCAL_PHOTO_PATH"]
        for h in extra:
            if h not in headers:
                headers.append(h)
                hub.update_cell(1, len(headers), h)
        hidx = {h: i + 1 for i, h in enumerate(hub.row_values(1))}

    book = openpyxl.load_workbook(master)
    sheet = book.active
    hmap = sheet_header_map(sheet)
    uid_col = col_index(hmap, "student_unique_id")
    school_col = col_index(hmap, "school_code")
    if not uid_col or not school_col:
        logger.error("student_data.xlsx mein student_unique_id / school_code column nahi")
        return 0

    if saini_db is not None:
        imported = saini_db.import_xlsx_if_empty(BASE_PROJECT, master)
        if imported:
            logger.info(f"saini.db bana: {imported} purani rows import. Excel master nahi raha.")
        else:
            logger.info(f"saini.db ready: {saini_db.count(BASE_PROJECT)} students")
    existing = set()
    existing_people = set()
    person_uid = {}
    name_col = col_index(hmap, "student_name")
    father_col = col_index(hmap, "father_name")
    class_col = col_index(hmap, "class")
    for r in range(2, sheet.max_row + 1):
        sc = str(sheet.cell(r, school_col).value or "").strip().upper()
        uid = str(sheet.cell(r, uid_col).value or "").strip().upper()
        if sc == school_code.upper() and uid:
            existing.add(uid)
            if name_col:
                pk = _person_key(
                    sheet.cell(r, name_col).value,
                    sheet.cell(r, father_col).value if father_col else "",
                    sheet.cell(r, class_col).value if class_col else "",
                )
                existing_people.add(pk)
                if is_official_photo_uid(school_code, uid):
                    person_uid[pk] = uid
    if saini_db is not None:
        existing |= saini_db.school_uids(BASE_PROJECT, school_code)

    raw_dir = BASE_PROJECT / "ENROLL_RAW" / school_code
    # SAFETY: Mode E must not delete ENROLL_RAW or other folders.
    school_lib = PHOTO_LIBRARY / school_code
    school_drive = GOOGLE_DRIVE_PHOTOS / school_code
    safe_makedirs(raw_dir)
    safe_makedirs(PIPELINE_OUTPUT)
    safe_makedirs(school_lib)
    try:
        safe_makedirs(school_drive)
    except Exception:
        school_drive = None

    # purani INPUT/OUTPUT is school ke temp files saaf â€” dusre school mix na hon
    pending = []
    enrolled = skipped = garbage = bad = raw_ok = 0

    # same name+father+class: teacher pehle galat, baad me theek dalta hai. sirf latest rakho.
    latest = {}
    latest_order = []
    for i, rec in enumerate(rows, start=2):
        raw_sc = rec.get("school_code", "")
        if _is_garbage_school_code(raw_sc) or str(raw_sc).strip().upper() != school_code.upper():
            continue
        name = clean_for_display(rec.get("student_name", ""))
        klass = normalize_class_name(rec.get("class", ""))
        if not name or not klass:
            continue
        pk = _person_key(name, rec.get("father_name", ""), klass)
        ts = _parse_enroll_ts(rec.get("timestamp") or rec.get("Timestamp") or rec.get("time stamp"))
        prev = latest.get(pk)
        if prev is None:
            latest[pk] = (ts, i, rec)
            latest_order.append(pk)
            continue
        old_ts = prev[0]
        if ts is not None and (old_ts is None or ts >= old_ts):
            logger.info(f"  OLD ENTRY DROP {name} / {klass} row {prev[1]} â€” latest row {i}")
            latest[pk] = (ts, i, rec)
            skipped += 1
        else:
            logger.info(f"  OLD ENTRY DROP {name} / {klass} row {i}")
            skipped += 1
    rows = [latest[pk][2] | {"_sheet_row": latest[pk][1]} for pk in latest_order]
    logger.info(f"Latest-only rows for {school_code}: {len(rows)} (purani duplicate hata di)")

    for i, rec in enumerate(rows, start=2):
        raw_sc = rec.get("school_code", "")
        if _is_garbage_school_code(raw_sc):
            garbage += 1
            continue
        if str(raw_sc).strip().upper() != school_code.upper():
            continue
        if cutoff:
            rec_ts = _parse_enroll_ts(rec.get('timestamp') or rec.get('Timestamp') or rec.get('time stamp'))
            if rec_ts is None:
                logger.info('  SKIP no timestamp (cutoff on): row %s %s', i, rec.get('student_name'))
                skipped += 1
                continue
            if rec_ts <= cutoff:
                logger.info('  SKIP before cutoff %s: %s / %s', rec_ts, rec.get('student_name'), rec.get('class'))
                skipped += 1
                continue

        st = str(rec.get("STATUS") or "").strip().upper()
        if st in ("ENROLLED_PHOTO_OK", "DONE", "AI_DONE"):
            skipped += 1
            continue

        name = clean_for_display(rec.get("student_name", ""))
        klass = normalize_class_name(rec.get("class", ""))
        form_uid = _clean_id_token(rec.get("student_unique_id", "")).upper()
        if form_uid in ("G", "NA", "N/A", "-", "NONE"):
            form_uid = ""
        roll = _clean_id_token(rec.get("roll_number", ""))
        if roll in ("G", "NA", "N/A", "-"):
            roll = ""
        if not name or not klass:
            logger.warning(f"  BAD hub row {i}: name/class missing")
            bad += 1
            continue

        gfile_early = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
        if gfile_early:
            already = None
            for prev in pending:
                if prev.get("gfile") == gfile_early and prev.get("uid"):
                    already = prev.get("uid")
                    break
            if already:
                logger.info("  SKIP same drive file already has UID %s: %s", already, name)
                skipped += 1
                continue
        pkey = _person_key(name, rec.get("father_name", ""), klass)
        photo_now = str(rec.get("STUDENT_PHOTO_PATH") or "")
        needs_photo = bool(gfile_early) and not photo_now.lower().startswith(("d:\\", "d:/"))
        held = person_uid.get(pkey, "")
        if pkey in existing_people and not needs_photo and not gfile_early:
            logger.info(f"  SKIP already enrolled, no new photo: {name} / {klass}")
            skipped += 1
            continue
        if held and needs_photo:
            logger.info(f"  LATEST UPDATE {name} / {klass} â€” same UID {held}")
        if is_official_photo_uid(school_code, form_uid) and form_uid in existing and not needs_photo:
            logger.info(f"  SKIP already has official UID {form_uid}")
            skipped += 1
            continue

        if held:
            uid = held
        elif is_official_photo_uid(school_code, form_uid):
            uid = form_uid
        else:
            uid = next_official_uid(school_code, klass, existing)
            logger.info(f"  NEW UID {uid} â† form_id={form_uid or '-'} roll={roll} class={klass}")
        existing.add(uid)
        existing_people.add(pkey)

        gfile = _drive_file_id(rec.get("GOOGLE_FILE_ID")) or _drive_file_id(rec.get("STUDENT_PHOTO_PATH"))
        raw_path = None
        if gfile and uid:
            raw_path = raw_dir / f"{uid}.jpg"
            try:
                _download_drive_file(creds, gfile, raw_path)
                raw_ok += 1
                logger.info(f"  RAW â†“ {uid}  ({gfile[:8]}â€¦)")
            except Exception as e:
                logger.warning(f"  RAW download fail {uid}: {e}")
                raw_path = None

        pending.append({
            "row": rec.get("_sheet_row", i),
            "uid": uid,
            "name": name,
            "klass": klass,
            "roll": roll,
            "gfile": gfile,
            "raw_path": raw_path,
            "father": clean_for_display(rec.get("father_name", "")),
            "mother": clean_for_display(rec.get("mother_name", "")),
            "mobile": fix_mobile(rec.get("mob_number", "")),
            "address": clean_for_display(rec.get("address", "")),
            "form_photo": str(rec.get("STUDENT_PHOTO_PATH") or ""),
            "school": school_code,
        })

    logger.info(f"Rows ready: {len(pending)} | RAW downloaded: {raw_ok}")

    if raw_ok:
        logger.info("=== MODE E: Photo AI Lab (unprocessed â†’ finished) ===")
        step2_run_pipeline(bg_color=bg_color, school_code=school_code, source_folder=raw_dir)
        if auto:
            logger.info("Night mode: photo check skip, RAW/processed dono sheet par lagenge")
        else:
            try:
                input("\n>>> OUTPUT folder mein processed photos CHECK karo, phir ENTER <<<\n")
            except Exception:
                pass

    template_row = max(2, sheet.max_row)
    photos_done = uploaded = 0

    def _set_hub(row_i, colname, val):
        c = hidx.get(colname)
        if c:
            hub.update_cell(row_i, c, val)

    for item in pending:
        uid = item["uid"]
        gfile = item["gfile"]
        processed = None
        if uid:
            cand = PIPELINE_OUTPUT / f"{uid}.jpg"
            if cand.exists() and cand.stat().st_size > 0:
                processed = cand
        if processed is None and item["raw_path"] and item["raw_path"].exists():
            logger.warning(f"  NO processed file for {uid} â€” RAW photo library me save, AI baad me")

        local_lib = ""
        status = "ENROLLED_WAITING_PHOTO"
        if processed is None and item.get("raw_path") and item["raw_path"].exists():
            dest_raw = school_lib / f"{uid}.jpg"
            if not dest_raw.exists() or dest_raw.stat().st_size == 0:
                shutil.copy2(item["raw_path"], dest_raw)
            local_lib = str(dest_raw.resolve())
            status = "ENROLLED_PHOTO_RAW"
            photos_done += 1
            logger.info(f"  RAW library {dest_raw.name}")
        if processed is not None:
            dest_lib = school_lib / f"{uid}.jpg"
            shutil.copy2(processed, dest_lib)
            local_lib = str(dest_lib.resolve())
            status = "ENROLLED_PHOTO_OK"
            write_enroll_to_local_xlsx(item)
            photos_done += 1
        patch = {
            "timestamp": datetime.now().isoformat(),
            "student_name": item["name"],
            "class": item["klass"],
            "school_code": school_code,
            "mob_number": item["mobile"],
            "address": item["address"],
            "father_name": item["father"],
            "mother_name": item["mother"],
            "student_unique_id": uid,
            "roll_number": item["roll"],
            "GOOGLE_FILE_ID": gfile,
            "STUDENT_PHOTO_PATH": local_lib,  # processed only
            "source": "enroll_sheet",
        }
        if uid and uid in existing:
            # existing row update â€” fill photo path
            for r in range(2, sheet.max_row + 1):
                sc = str(sheet.cell(r, school_col).value or "").strip().upper()
                u = str(sheet.cell(r, uid_col).value or "").strip().upper()
                if sc == school_code.upper() and u == uid:
                    write_by_name(sheet, r, hmap, {
                        "STUDENT_PHOTO_PATH": local_lib,
                        "GOOGLE_FILE_ID": gfile,
                    }, template_row)
                    break
        else:
            write_by_name(sheet, sheet.max_row + 1, hmap, patch, template_row)
            if uid:
                existing.add(uid)

        _set_hub(item["row"], "STATUS", status)
        _set_hub(item["row"], "PHOTO_NO", uid)
        _set_hub(item["row"], "ENROLLMENT_NO", uid)
        _set_hub(item["row"], "LOCAL_PHOTO_PATH", local_lib)
        if gfile and "GOOGLE_FILE_ID" in hidx:
            _set_hub(item["row"], "GOOGLE_FILE_ID", gfile)

        enrolled += 1
        logger.info(f"  OK {uid or '(no uid)'} | {item['name']} | {item['klass']} | {status}")
        item["uid"] = uid
        item["sheet_photo"] = local_lib
        item["status_final"] = status
        if saini_db is not None and uid:
            try:
                saini_db.upsert(BASE_PROJECT, item)
            except Exception as e:
                logger.warning(f"saini.db upsert fail {uid}: {e}")
        if night_cards is not None and uid and local_lib:
            night_cards.append({
                "uid": uid,
                "name": item.get("name") or "",
                "father": item.get("father") or "",
                "klass": item.get("klass") or "",
                "school": school_code,
                "photo": local_lib,
            })

    sheet_updates = [
        {
            "name": it["name"],
            "father": it["father"],
            "klass": it["klass"],
            "uid": it.get("uid"),
            "photo": it.get("sheet_photo") or "",
            "gfile": it.get("gfile") or "",
            "mobile": it.get("mobile") or "",
        }
        for it in pending if it.get("uid")
    ]
    try:
        nsheet = _write_uids_to_school_google_sheet(gc, school_code, creds, sheet_updates)
        logger.info(f"Google school sheet UID write: {nsheet}")
    except Exception as e:
        logger.error(f"Google school sheet UID write fail: {e}")

    try:
        book.save(master)
    except PermissionError:
        logger.error("student_data.xlsx Excel mein khuli hai. Band karke dubara chalao.")
        return 0

    logger.info("-" * 60)
    logger.info(f"{school_code} enrolled     : {enrolled}")
    logger.info(f"RAW downloaded            : {raw_ok}")
    logger.info(f"AI processed â†’ library    : {photos_done}")
    logger.info(f"Drive original replaced   : {uploaded}")
    logger.info(f"Already done              : {skipped}")
    logger.info(f"Garbage school codes      : {garbage}")
    logger.info(f"Bad rows                  : {bad}")
    logger.info("ID CARD sirf PHOTO_LIBRARY processed files se banega.")
    if saini_db is not None:
        logger.info(f"saini.db master count: {saini_db.count(BASE_PROJECT)}")
    logger.info("-" * 60)
    try:
        status_mark(school_code, "enrolled", done=enrolled > 0, count=enrolled,
                    note=f"{photos_done} processed, {uploaded} drive replaced")
    except Exception:
        pass
    return enrolled



def _compose_night_sheets(cards: list, out_dir: Path) -> Path:
    """A4 par 10 ID card, saare schools ek PDF."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cards:
        return out_dir / "EMPTY.txt"
    font_b = get_font(36)
    font_s = get_font(26)
    font_t = get_font(22)
    # 2 col x 5 row, card ~ CR80 on A4 @ 300dpi
    cw, ch = 1010, 600
    gap_x, gap_y = 40, 28
    ox = (PAGE_W - (2 * cw + gap_x)) // 2
    oy = (PAGE_H - (5 * ch + 4 * gap_y)) // 2
    pages = []
    for start in range(0, len(cards), 10):
        batch = cards[start:start + 10]
        page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
        draw = ImageDraw.Draw(page)
        for i, card in enumerate(batch):
            col, row = i % 2, i // 2
            x = ox + col * (cw + gap_x)
            y = oy + row * (ch + gap_y)
            draw.rectangle([x, y, x + cw, y + ch], outline=(0, 0, 0), width=3)
            px, py = x + 24, y + 70
            draw.rectangle([px, py, px + 280, py + 350], outline=(0, 0, 0), width=2)
            photo = card.get("photo") or ""
            if photo and Path(photo).exists():
                try:
                    im = Image.open(photo).convert("RGB")
                    im = im.resize((280, 350), Image.Resampling.LANCZOS)
                    page.paste(im, (px, py))
                except Exception as e:
                    logger.warning(f"card photo fail {card.get('uid')}: {e}")
            tx = px + 300
            draw.text((tx, y + 24), str(card.get("school") or ""), fill=(0, 0, 0), font=font_b)
            draw.text((tx, y + 80), str(card.get("uid") or ""), fill=(0, 0, 0), font=font_b)
            draw.text((tx, y + 150), str(card.get("name") or "")[:28], fill=(0, 0, 0), font=font_s)
            draw.text((tx, y + 200), "F: " + str(card.get("father") or "")[:26], fill=(0, 0, 0), font=font_t)
            draw.text((tx, y + 250), "CLASS " + str(card.get("klass") or ""), fill=(0, 0, 0), font=font_s)
        pages.append(page)
    pdf = out_dir / f"ALL_SCHOOLS_10UP_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=300.0)
    logger.info(f"Night print PDF: {pdf} pages={len(pages)} cards={len(cards)}")
    return pdf


def stepN_night_all(bg_color: str = "W") -> int:
    """Ek command: saare schools enroll + combined A4 10-up ready folder."""
    logger.info("=== NIGHT: ALL SCHOOLS → combined A4 ===")
    try:
        gc, creds = _gspread_client()
    except Exception as e:
        logger.error(f"Google login fail: {e}")
        return -1
    rows = _load_hub_rows_via_drive(creds)
    schools = []
    seen = set()
    for rec in rows:
        sc = str(rec.get("school_code") or "").strip().upper()
        if not sc or sc in seen or _is_garbage_school_code(sc):
            continue
        if len(sc) > 12 or " " in sc:
            continue
        seen.add(sc)
        schools.append(sc)
    try:
        master_rows = _xlsx_tab_records(creds, HUB_SHEET_ID, SCHOOL_MASTER_TAB)
        for rec in master_rows:
            sc = str(rec.get("SCHOOL_CODE") or "").strip().upper()
            if sc and sc not in seen and not _is_garbage_school_code(sc) and len(sc) <= 12:
                seen.add(sc)
                schools.append(sc)
    except Exception as e:
        logger.warning(f"SCHOOL_MASTER list skip: {e}")
    schools.sort()
    logger.info(f"Schools in night run: {len(schools)}")
    night_cards = []
    out = BASE_PROJECT / "NIGHT_PRINT" / datetime.now().strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    for sc in schools:
        logger.info(f"--- NIGHT SCHOOL {sc} ---")
        try:
            stepE_enroll_from_sheet(sc, bg_color=bg_color, auto=True, shared_rows=rows, night_cards=night_cards)
        except Exception as e:
            logger.exception(f"Night school fail {sc}: {e}")
    pdf = _compose_night_sheets(night_cards, out)
    (out / "READ_ME.txt").write_text(
        f"cards={len(night_cards)}\nfile={pdf}\nprinter par isi PDF ko do.\n",
        encoding="utf-8",
    )
    logger.info(f"SUBAH PRINT FOLDER: {out}")
    return len(night_cards)


def clean_photo_lab_folders():
    """Mode M must not blanket-delete INPUT or OUTPUT. MIX originals stay untouched."""
    logger.info("Mode M: blanket INPUT/OUTPUT cleanup is disabled.")
    return 0


def stepM_combo_process(school_code: str, bg_color: str = "W") -> int:
    """
    Mode M development boundary.
    Temporary 50xxx IDs stay temporary.
    Reassign, Step 6, Step 7, Step 7B and the card generator are not called.
    """
    logger.info("=== MODE M: Combo MIX Photos (safe development) ===")
    school_code = school_code.strip().upper()
    dev_dir = Path(__file__).resolve().parent
    if str(dev_dir) not in sys.path:
        sys.path.insert(0, str(dev_dir))
    import mode_m_safety

    batch_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    journal_root = Path(os.environ.get("MODE_M_JOURNAL_ROOT", str(BASE_PROJECT / "MODE_M_JOURNAL")))
    gate = mode_m_safety.begin_batch(school_code, journal_root / "locks", batch_id)
    if not gate.ok:
        logger.error("Mode M fail closed: %s", gate.reason)
        return 0

    renamed = 0
    old_base = os.environ.get("SAINI_BASE_PROJECT")
    try:
        clean_photo_lab_folders()
        mix_folder = INPUT_WHATSAP / "MIX"
        if not mix_folder.is_dir():
            logger.error(f"MIX folder not found: {mix_folder}")
            return 0

        _, range_start, range_end = CLASS_RANGES["MIX"]
        highest = range_start - 1
        school_lib = PHOTO_LIBRARY / school_code
        safe_makedirs(school_lib)

        def extract_mix_num(stem: str):
            stem = stem.upper()
            if stem.startswith(school_code):
                num_str = "".join(ch for ch in stem[len(school_code):] if ch.isdigit())
                try:
                    return int(num_str) if num_str else None
                except Exception:
                    return None
            return None

        for folder in (school_lib, RENAME_OUTPUT):
            if folder.exists():
                for photo in folder.glob("*.jpg"):
                    number = extract_mix_num(photo.stem)
                    if number is not None and range_start <= number <= range_end:
                        highest = max(highest, number)

        next_num = highest + 1
        backup_dir = INPUT_WHATSAP / f"{school_code}_MIX_UNCROPPED_{batch_id}"
        safe_makedirs(backup_dir)
        files = sorted(f for f in mix_folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if not files:
            logger.info("MIX folder empty. No photos to process.")
            return 0

        assignments = []
        for src_file in files:
            placed = False
            while next_num <= range_end:
                new_name = f"{school_code}{next_num:05d}.jpg"
                next_num += 1
                status = mode_m_safety.copy_no_clobber(
                    src_file, RENAME_OUTPUT / new_name, {"library_owner": True}
                )
                if status != "COPIED":
                    logger.warning("Mode M review, destination not replaced: %s", new_name)
                    break
                slip_status = mode_m_safety.copy_no_clobber(
                    src_file, backup_dir / new_name, {"library_owner": True}
                )
                if slip_status != "COPIED":
                    logger.warning("Mode M review, uncropped copy not stored: %s", new_name)
                    break
                assignments.append((src_file, new_name))
                renamed += 1
                placed = True
                break
            if not placed:
                logger.warning("Mode M review, no free temporary name: %s", src_file.name)
        logger.info("Mode M Step-A done: %s temporary IDs. MIX originals kept.", renamed)
        if renamed == 0:
            return 0

        logger.info("Mode M: Running AI Lab pipeline...")
        step2_run_pipeline(bg_color=bg_color, school_code=school_code, source_folder=RENAME_OUTPUT)

        slip_dir = RETURNED_SLIPS / school_code
        safe_makedirs(slip_dir)
        for _src, new_name in assignments:
            mode_m_safety.copy_no_clobber(backup_dir / new_name, slip_dir / new_name, {"library_owner": True})

        os.environ["SAINI_BASE_PROJECT"] = str(BASE_PROJECT)
        from slip_ocr import list_scans, ocr_image, clean_name, clean_mob

        master = STUDENT_DATABASE
        if not master.exists():
            logger.error("student_data.xlsx missing")
            return renamed
        proposals = []
        for path in list_scans(school_code):
            try:
                data = ocr_image(path)
                students = data.get("students") or []
                if not students:
                    continue
                student = students[0]
                proposals.append({
                    "photo_sha256": mode_m_safety.sha256_file(path),
                    "temp_uid": path.stem.upper(),
                    "student_name": clean_name(student.get("student_name", "")),
                    "father_name": clean_name(student.get("father_name", "")),
                    "class": clean_name(student.get("class", "")),
                    "address": clean_name(student.get("address", "")),
                    "mob_number": clean_mob(student.get("mob_number", "")),
                })
            except Exception as exc:
                logger.warning("Mode M OCR review %s: %s", path.name, exc)
        result = mode_m_safety.commit_updates(
            master,
            school_code,
            batch_id,
            proposals,
            journal_root,
            journal_root / "photo_registry.json",
        )
        logger.info("Mode M excel state=%s written=%s reason=%s", result.state, result.written_rows, result.reason)
        if not result.ok:
            return renamed

        copied_final = 0
        for src_folder in (PIPELINE_OUTPUT, RENAME_OUTPUT):
            if not src_folder.exists():
                continue
            for photo in src_folder.glob("*.jpg"):
                status = mode_m_safety.copy_no_clobber(
                    photo, school_lib / photo.name, {"library_owner": True}
                )
                if status == "COPIED":
                    copied_final += 1
                elif status == "REVIEW":
                    logger.warning("Mode M library review, existing file kept: %s", photo.name)
        logger.info("Mode M library copies: %s", copied_final)
        logger.info("Mode M STOP before reassign. Temporary UIDs kept. Final UID conversion is not done.")
        return renamed
    finally:
        if old_base is None:
            os.environ.pop("SAINI_BASE_PROJECT", None)
        else:
            os.environ["SAINI_BASE_PROJECT"] = old_base
        mode_m_safety.end_batch(gate)


# ====================== MAIN ======================
def main():
    logger.info("=" * 70)
    logger.info("SAINI SCHOOL MASTER PROCESSOR - PERFECTED v2.0")
    logger.info("=" * 70)

    parser = argparse.ArgumentParser(description="Saini School ID Card Master Processor")
    parser.add_argument("--school", help="School code (e.g. STVN)")
    parser.add_argument("--dashboard", action="store_true", help="Print live status of all schools and exit")
    parser.add_argument("--status", metavar="CODE", help="Print one school status and exit")
    parser.add_argument("--skip", nargs="*", default=[], help="Skip steps by number, e.g. --skip 2 8")
    parser.add_argument("--no-launch", action="store_true", help="Do not open ID card generator (preview/stop)")
    parser.add_argument("--cutoff", default=None, help="Enroll only rows after YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--mode", choices=["A", "B", "C", "D", "E", "R", "N", "M"], help="A=Full, B=Data+cards, C=Returned slips, D=Correction, E=Enroll sheet, R=Reassign MIX, N=Night all schools, M=Combo MIX photos (A+C+R one shot)")
    args = parser.parse_args()

    if args.dashboard:
        print(dashboard_text())
        return
    if args.status:
        print(school_detail(args.status))
        return
    if args.mode == "N":
        n = stepN_night_all("W")
        logger.info(f"Night cards ready: {n}")
        logger.info(f"Folder: {BASE_PROJECT / 'NIGHT_PRINT'}")
        return

    school_code = (args.school or input("Enter School Code (e.g. STVN, JPSD, DCMD): ")).strip().upper()
    if not school_code:
        logger.error("School code is required.")
        return

    if args.mode:
        choice = args.mode
    else:
        print("\nWhat do you want to do?")
        print("A → New photos arrived → Full Process (Steps 1-5 + data sync + ID cards)")
        print("B → Only update data + sync photos + launch ID card generator")
        print("C → Teacher slips wapas aayi → scan OCR → Excel/Google update → ID cards")
        print("D → Correction slips wapas aayi → RIGHT values se Excel update → ID cards")
        print("E → Google Sheet ENROLL → RAW Drive download → AI Lab → processed Drive wapas → ID cards")
        print("R → MIX photos को Fully Automatic Reassign करो")
        print("N → RAAT: saare schools, subah combined A4 10 card/sheet")
        print("M → Combo MIX photos (photo + data slip) → Full A+C+R one shot")
        while True:
            choice = input("\nYour choice (A / B / C / D / E / R / N / M): ").strip().upper()
            if choice in ("A", "B", "C", "D", "E", "R", "N", "M"):
                break
            print("Enter only A, B, C, D, E, R, N or M")

    mode_name = {
        "A": "FULL PROCESS",
        "B": "DATA + SYNC + GENERATOR",
        "C": "RETURNED SLIPS OCR",
        "D": "CORRECTION SLIPS OCR",
        "E": "ENROLL FROM GOOGLE SHEET",
        "R": "REASSIGN MIXED PHOTOS",
        "N": "NIGHT ALL SCHOOLS PRINT",
        "M": "COMBO MIX PHOTOS (A+C+R ONE SHOT)",
    }
    logger.info(f"School: {school_code} | Mode: {mode_name.get(choice, choice)}")

    if choice == "N":
        n = stepN_night_all("W")
        logger.info(f"Night cards ready: {n}")
        logger.info(f"Folder: {BASE_PROJECT / 'NIGHT_PRINT'}")
        return

    # Ensure folders
    for p in [RENAME_OUTPUT, PIPELINE_OUTPUT, PRINT_SHEETS_FOLDER,
              PHOTO_LIBRARY / school_code, RETURNED_SLIPS / school_code,
              RETURNED_CORRECTIONS / school_code, CORRECTION_SLIPS]:
        safe_makedirs(p)

    if choice == "A":
        print("\nBackground Color Options:")
        print("  W  = White")
        print("  R  = Red")
        print("  B  = Blue")
        print("  G  = Green")
        print("  LG = Light Green")
        print("  LB = Light Blue")
        bg_input = input("Background color [W]: ").strip().upper() or "W"
        logger.info(f"Selected Background: {bg_input}")

        skip = {str(s) for s in (args.skip or [])}
        renamed = 0 if "1" in skip else step1_smart_rename(school_code)
        if renamed > 0:
            if "2" not in skip:
                step2_run_pipeline(bg_color=bg_input, school_code=school_code)
            input("\n>>> CHECK & FIX photos in OUTPUT folder if needed, then press ENTER to continue... <<<")
            if "3" not in skip:
                step3_copy_to_library(school_code)
            if "4" not in skip:
                step4_update_photo_db(school_code)
            if "5" not in skip:
                step5_generate_print_sheets(school_code)
        else:
            logger.info("No new photos processed in Step 1. Skipping to data merge.")

    n = -1
    if choice == "E":
        print("\nBackground Color (AI Lab / processed photo):")
        print("  W=White  R=Red  B=Blue  G=Green  LG=Light Green  LB=Light Blue")
        bg_e = input("Background color [W]: ").strip().upper() or "W"
        n = stepE_enroll_from_sheet(school_code, bg_color=bg_e, cutoff=_parse_enroll_ts(getattr(args, 'cutoff', None)))
        if n < 0:
            logger.error("Mode E band: Google Sheet API fail. 1 minute baad dubara E chalao.")
            input("\nSheet nahi khuli. Press Enter to exit...")
            return
        if n == 0:
            logger.info("Is school ke liye koi NEW row nahi mili (ya garbage code skip ho gaya).")

    if choice == "C":
        n = step5c_process_returned_slips(school_code)
        if n == 0:
            logger.info("Koi naya slip data nahi mila. Folder check karo.")
        # after OCR, still merge + sync + cards

    if choice == "D":
        n = step5d_process_corrections(school_code)
        if n == 0:
            logger.info("Koi naya correction data nahi mila. Folder check karo.")

    if choice in ("C", "D") and n == 0:
        logger.warning("No OCR records were approved in audio verification. Stopping: merge, sync, and ID card generation are blocked.")
        input("Verification pending/rejected. Press Enter to exit...")
        return
    if choice == "R":
        step_reassign_mixed(school_code)
        # Reassign के बाद photo path update भी कर दो
        step7b_update_photo_path(school_code)

    if choice == "M":
        print("\nBackground Color for AI Lab (combo photos):")
        print("  W=White  R=Red  B=Blue  G=Green  LG=Light Green  LB=Light Blue")
        bg_m = input("Background color [W]: ").strip().upper() or "W"
        logger.info(f"Mode M selected Background: {bg_m}")
        n_m = stepM_combo_process(school_code, bg_color=bg_m)
        if n_m == 0:
            logger.info("Mode M: कोई photo process नहीं हुई। MIX folder check करो।")
        else:
            logger.info(f"Mode M: {n_m} combo photos processed successfully.")
        logger.info("Mode M STOP: Step 6, Step 7, Step 7B and the card generator are not called.")
        return

    # Always run these for B/C and after A / M
    skip = {str(s) for s in (args.skip or [])}
    if "6" not in skip:
        step6_data_merge(school_code)
    if "7" not in skip:
        step7_sync_photos(school_code)
        step7b_update_photo_path(school_code)
    logger.info("\n--- SCHOOL STATUS ---\n" + school_detail(school_code))
    src, day, mode = prepare_id_source(school_code)
    if args.no_launch or "8" in skip:
        logger.info("ID card generator skipped (preview / --no-launch).")
    else:
        if mode == "xlsx":
            print(f"\nID card source: PRIMARY local Excel â†’ {src.name}")
        elif mode == "csv":
            print(f"\nID card source: CSV fallback â†’ {src}")
        else:
            print("\nID card source: koi file nahi mili")
        go = input("Launch ID card generator? [Y/n]: ").strip().lower()
        if go in ("", "y", "yes"):
            step8_launch_id_card(school_code, workflow_mode=choice)
        else:
            logger.info("Generator not launched.")

    logger.info("\n" + "=" * 70)
    logger.info("Workflow ended. Review per-step logs; Mode B uses master-roster authorization, while OCR modes retain Option C Gate verification.")
    logger.info(f"Log file: {LOGS_DIR}")
    logger.info("=" * 70)
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Exiting cleanly.")
    except Exception as e:
        logger.exception(f"Unexpected fatal error: {e}")
        input("\nAn error occurred. Check log file. Press Enter to exit...")