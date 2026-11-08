# -*- coding: utf-8 -*-
"""Confirm the development package is complete and refuse a live destination."""

import hashlib
from pathlib import Path

from identity_engine import IdentityError, assert_development_path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "open_launcher.py",
    "Open_Enrollment.bat",
    "src/trial_window.py",
    "src/teacher_trial.py",
    "src/identity_engine.py",
    "src/development_launcher.py",
    "src/active_writers.py",
    "src/legacy_guard.py",
    "R23_3A_TEACHER_TRIAL_PACK/README.txt",
    "R23_3A_TEACHER_TRIAL_PACK/01_valid_class_1/students.xlsx",
    "R23_3A_TEACHER_TRIAL_PACK/01_valid_class_1/students.csv",
    "R23_3A_TEACHER_TRIAL_PACK/01_valid_class_1/photos/good.jpg",
    "R23_3A_TEACHER_TRIAL_PACK/02_valid_class_6/students.xlsx",
    "R23_3A_TEACHER_TRIAL_PACK/03_duplicate_roll/students.xlsx",
    "R23_3A_TEACHER_TRIAL_PACK/04_missing_photo/students.xlsx",
    "R23_3A_TEACHER_TRIAL_PACK/05_invalid_photo/students.xlsx",
    "PRESERVED_R23_3A_REPORTS/R23_3A_HINDI_TEACHER_GUIDE.txt",
    "PRESERVED_R23_3A_REPORTS/R23_3A_ENGLISH_TEACHER_GUIDE.txt",
)


def refuse_live_destination(destination):
    assert_development_path(destination)
    text = str(destination).replace("/", "\\").upper()
    if text.endswith("\\MAIN_ASSISTANT.PY") or text.endswith("\\SAINI_ID_CARD.PY"):
        raise IdentityError("live_path_refused")


def inspect_package(root=ROOT):
    root = Path(root)
    refuse_live_destination(root)
    missing = [item for item in REQUIRED if not (root / item).is_file()]
    launcher = (root / "open_launcher.py").read_text(encoding="utf-8")
    window = (root / "src" / "trial_window.py").read_text(encoding="utf-8")
    problems = []
    if "open_window" not in launcher:
        problems.append("entry_missing")
    if "filedialog.askopenfilename" not in window or "filedialog.askdirectory" not in window:
        problems.append("picker_missing")
    if "generate_front_card" in window or "saini_db" in window:
        problems.append("unsafe_call")
    return {
        "root": str(root),
        "missing": missing,
        "problems": problems,
        "ready": not missing and not problems,
        "launcher_sha256": hashlib.sha256((root / "open_launcher.py").read_bytes()).hexdigest().upper(),
    }
