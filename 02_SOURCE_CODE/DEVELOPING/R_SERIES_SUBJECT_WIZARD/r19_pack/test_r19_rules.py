# -*- coding: utf-8 -*-
"""R19 development rules. Synthetic files only. These are not the original R4 or R14 tests."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from bsm_selector import ConfigSelectionError, select_bsm_row
from saini_config_path import DEFAULT_CONFIG_WORKBOOK, ConfigPathError, require_config_workbook, resolve_config_workbook

LIVE = r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
OPTION_C = {
    "gate.py": "0EEB0EA1FEE4520A3E91B59E16D8C1BCF2F4B2B1DC1A7C4C5C10C7F60E1D51EA",
    "identity.py": "10FFD0C9A91DB42D5904255FD41CB307A458FC02F33378073A875C6C2CC0F112",
    "journal.py": "5A908C6BED369B597FC92D64BE27CF0444C0076B33A839D8D5E77523E43BF361",
    "safety.py": "42BDEFA0ECD3C2EA21490B39542E7ECFE0A8FA06EF4C73CED53BFB2FF8EE6F2E",
    "sink_verifier.py": "C274F2D0A214EDB95FF609FC10D1BEF6B3BBDC4240D543ADDA0F6CA8C44F78AC",
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def touch(folder, name):
    path = Path(folder) / name
    path.write_bytes(b"synthetic-template-not-a-card")
    return path


class R19RuleTests(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get("SAINI_DEV_CONFIG_XLSX")
        os.environ.pop("SAINI_DEV_CONFIG_XLSX", None)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("SAINI_DEV_CONFIG_XLSX", None)
        else:
            os.environ["SAINI_DEV_CONFIG_XLSX"] = self.old

    def test_01_generator_and_editor_share_one_path(self):
        generator = (ROOT / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        editor = (ROOT / "config_editor.py").read_text(encoding="utf-8")
        self.assertIn("require_config_workbook()", generator)
        self.assertIn("require_config_workbook()", editor)
        self.assertEqual(resolve_config_workbook(), DEFAULT_CONFIG_WORKBOOK)
        self.assertEqual(resolve_config_workbook(), r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19\school_config_front.xlsx")

    def test_02_legacy_f_path_is_rejected(self):
        os.environ["SAINI_DEV_CONFIG_XLSX"] = r"F:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
        with self.assertRaises(ConfigPathError) as caught:
            resolve_config_workbook()
        self.assertIn("F:", str(caught.exception))
        self.assertIn("No other workbook", str(caught.exception))

    def test_03_missing_workbook_fails_closed(self):
        missing = r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19\missing_synthetic_config.xlsx"
        os.environ["SAINI_DEV_CONFIG_XLSX"] = missing
        with self.assertRaises(ConfigPathError) as caught:
            require_config_workbook()
        self.assertIn("missing", str(caught.exception))
        self.assertIn("No fallback", str(caught.exception))
        self.assertNotEqual(resolve_config_workbook(), LIVE)

    def test_04_empty_school_name_is_rejected(self):
        data = pd.DataFrame([{"school_code": "BSM", "SCHOOLNAME": None, "template": "UNUSED"}])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("SCHOOLNAME", str(caught.exception))

    def test_05_whitespace_school_name_is_rejected(self):
        for value in ("", " ", "  ", "\t", "\n", " \t\n "):
            data = pd.DataFrame([{"school_code": "BSM", "SCHOOLNAME": value, "template": "UNUSED"}])
            with self.assertRaises(ConfigSelectionError):
                select_bsm_row(data)

    def test_06_first_eligible_row_is_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            later = touch(folder, "later.txt")
            chosen = touch(folder, "chosen.txt")
            data = pd.DataFrame([
                {"school_code": "BSM", "SCHOOLNAME": "   ", "template": str(chosen), "MARKER": "BLANK"},
                {"school_code": "BSM", "SCHOOLNAME": "SYNTHETIC SCHOOL", "template": str(chosen), "MARKER": "FIRST"},
                {"school_code": "BSM", "SCHOOLNAME": "OTHER SYNTHETIC", "template": str(later), "MARKER": "LATER"},
            ])
            row = select_bsm_row(data)
            self.assertEqual(row["MARKER"], "FIRST")
            self.assertEqual(row["template"], str(chosen))

    def test_07_all_fields_come_from_the_same_row(self):
        with tempfile.TemporaryDirectory() as folder:
            chosen = touch(folder, "chosen.txt")
            other = touch(folder, "other.txt")
            data = pd.DataFrame([
                {"school_code": "BSM", "SCHOOLNAME": "SYNTHETIC SCHOOL", "template": str(chosen), "CARD": "IDCARD", "MARKER": "ROW-A"},
                {"school_code": "BSM", "SCHOOLNAME": "OTHER SYNTHETIC", "template": str(other), "CARD": "ADMITCARD", "MARKER": "ROW-B"},
            ])
            row = select_bsm_row(data)
            self.assertEqual(row["CARD"], "IDCARD")
            self.assertEqual(row["MARKER"], "ROW-A")
            self.assertEqual(row["template"], str(chosen))

    def test_08_no_field_is_taken_from_a_later_row(self):
        with tempfile.TemporaryDirectory() as folder:
            chosen = touch(folder, "chosen.txt")
            other = touch(folder, "other.txt")
            data = pd.DataFrame([
                {"school_code": "BSM", "SCHOOLNAME": "SYNTHETIC SCHOOL", "template": str(chosen), "EXTRA": None, "MARKER": "ROW-A"},
                {"school_code": "BSM", "SCHOOLNAME": "OTHER SYNTHETIC", "template": str(other), "EXTRA": "DO-NOT-BORROW", "MARKER": "ROW-B"},
            ])
            row = select_bsm_row(data)
            self.assertEqual(row["MARKER"], "ROW-A")
            self.assertTrue(pd.isna(row["EXTRA"]))
            self.assertNotEqual(row["template"], str(other))

    def test_09_no_eligible_row_fails_closed(self):
        data = pd.DataFrame([
            {"school_code": "NBFP", "SCHOOLNAME": "OTHER SCHOOL", "template": "OTHER"},
            {"school_code": "BSM", "SCHOOLNAME": " \n", "template": "BLANK"},
        ])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("No template fallback", str(caught.exception))

    def test_10_duplicate_school_code_header_is_rejected(self):
        data = pd.DataFrame([["BSM", "BSM", "NAME", "T"]], columns=["school_code", "School_Code", "SCHOOLNAME", "template"])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("school_code", str(caught.exception))

    def test_11_duplicate_school_name_header_is_rejected(self):
        data = pd.DataFrame([["BSM", "ONE", "TWO", "T"]], columns=["school_code", "SCHOOLNAME", "SCHOOLNAME.1", "template"])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("SCHOOLNAME", str(caught.exception))

    def test_12_duplicate_template_header_is_rejected(self):
        data = pd.DataFrame([["BSM", "NAME", "ONE", "TWO"]], columns=["school_code", "SCHOOLNAME", "template", " template "])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("template", str(caught.exception))

    def test_13_missing_template_is_rejected(self):
        data = pd.DataFrame([{
            "school_code": "BSM",
            "SCHOOLNAME": "SYNTHETIC SCHOOL",
            "template": r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19\missing_template.png",
        }])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("template", str(caught.exception))
        self.assertIn("No cross-row fallback", str(caught.exception))

    def test_14_existing_template_file_is_not_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            chosen = touch(folder, "chosen.txt")
            before = sha(chosen)
            data = pd.DataFrame([{"school_code": "BSM", "SCHOOLNAME": "SYNTHETIC SCHOOL", "template": str(chosen)}])
            row = select_bsm_row(data)
            self.assertEqual(row["template"], str(chosen))
            self.assertEqual(sha(chosen), before)
            self.assertEqual(chosen.read_bytes(), b"synthetic-template-not-a-card")

    def test_15_synthetic_workbook_structure_is_not_changed(self):
        from openpyxl import Workbook, load_workbook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic_config.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(["school_code", "SCHOOLNAME", "template", "FATHER_X", "FATHER_X"])
            sheet.append(["BSM", "SYNTHETIC SCHOOL", "T", 1, 2])
            book.save(path)
            before = sha(path)
            loaded = pd.read_excel(path)
            with self.assertRaises(ConfigSelectionError):
                select_bsm_row(loaded)
            self.assertEqual(sha(path), before)
            again = load_workbook(path, read_only=True, data_only=True)
            try:
                headers = [cell.value for cell in next(again.active.iter_rows(max_row=1))]
            finally:
                again.close()
            self.assertEqual(headers, ["school_code", "SCHOOLNAME", "template", "FATHER_X", "FATHER_X"])

    def test_16_option_c_modules_are_unchanged(self):
        for name, digest in OPTION_C.items():
            self.assertEqual(sha(ROOT / "option_c_modules" / name), digest, name)

    def test_17_live_workbook_path_is_not_a_fallback(self):
        os.environ["SAINI_DEV_CONFIG_XLSX"] = LIVE
        with self.assertRaises(ConfigPathError) as caught:
            resolve_config_workbook()
        self.assertIn("live production", str(caught.exception))
        source = (ROOT / "saini_config_path.py").read_text(encoding="utf-8")
        self.assertNotIn("student_data.xlsx", source)
        self.assertNotIn(".to_excel(", source)
        self.assertNotIn("PHOTO_LIBRARY", source)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
