# -*- coding: utf-8 -*-
"""R13 synthetic tests. No live workbook, no student data, no card generation."""
import ast
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from bsm_selector import ConfigSelectionError, select_bsm_row
from saini_config_path import DEFAULT_CONFIG_WORKBOOK, resolve_config_workbook

BASELINE = {
    "SAINI_ID_CARD.py": "08F68584254CE7E016BCB075EE25F59EEB94803550F82D8FF4BFF844453CB0E1",
    "config_editor.py": "2684F6C2475F645401E61F0532724C6146C9DF98D2BDA239A2B0D2FD80273216",
    "gate.py": "0EEB0EA1FEE4520A3E91B59E16D8C1BCF2F4B2B1DC1A7C4C5C10C7F60E1D51EA",
    "identity.py": "10FFD0C9A91DB42D5904255FD41CB307A458FC02F33378073A875C6C2CC0F112",
    "journal.py": "5A908C6BED369B597FC92D64BE27CF0444C0076B33A839D8D5E77523E43BF361",
    "safety.py": "42BDEFA0ECD3C2EA21490B39542E7ECFE0A8FA06EF4C73CED53BFB2FF8EE6F2E",
    "sink_verifier.py": "C274F2D0A214EDB95FF609FC10D1BEF6B3BBDC4240D543ADDA0F6CA8C44F78AC",
}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def frame(rows):
    return pd.DataFrame(rows)


class BsmSelectionTests(unittest.TestCase):
    def test_a_both_known_empty_rows_fail_closed(self):
        data = frame([
            {"school_code": "BSM", "SCHOOLNAME": None, "template": r"T13", "excel_row": 13},
            {"school_code": "BSM", "SCHOOLNAME": None, "template": r"T82", "excel_row": 82},
        ])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("No eligible BSM row", str(caught.exception))
        self.assertNotIn("T13", str(caught.exception))
        self.assertNotIn("T82", str(caught.exception))

    def test_b_whitespace_only_names_are_rejected(self):
        for value in ("", " ", "  ", "\t", "\n", " \t\n "):
            with self.subTest(value=repr(value)):
                data = frame([
                    {"school_code": "BSM", "SCHOOLNAME": value, "template": "REJECTED"},
                ])
                with self.assertRaises(ConfigSelectionError):
                    select_bsm_row(data)

    def test_c_first_eligible_row_top_to_bottom(self):
        data = frame([
            {"school_code": "BSM", "SCHOOLNAME": "   ", "template": "T13", "excel_row": 13},
            {"school_code": "BSM", "SCHOOLNAME": "BSM PUBLIC SCHOOL", "template": "T82", "excel_row": 82},
            {"school_code": "BSM", "SCHOOLNAME": "ANOTHER SCHOOL", "template": "T129", "excel_row": 129},
        ])
        row = select_bsm_row(data)
        self.assertEqual(row["excel_row"], 82)
        self.assertEqual(row["SCHOOLNAME"], "BSM PUBLIC SCHOOL")
        self.assertEqual(row["template"], "T82")

    def test_d_every_field_comes_from_the_same_row(self):
        data = frame([
            {"school_code": "BSM", "SCHOOLNAME": None, "template": "T13", "CARD": "IDCARD", "ACTIVE": "YES", "MARKER": "ROW13"},
            {"school_code": "BSM", "SCHOOLNAME": "BSM PUBLIC SCHOOL", "template": "T82", "CARD": "IDCARD", "ACTIVE": "YES", "MARKER": "ROW82"},
            {"school_code": "BSM", "SCHOOLNAME": "ANOTHER SCHOOL", "template": "T129", "CARD": "ADMITCARD", "ACTIVE": "NO", "MARKER": "ROW129"},
        ])
        row = select_bsm_row(data)
        self.assertEqual(row["template"], "T82")
        self.assertEqual(row["CARD"], "IDCARD")
        self.assertEqual(row["ACTIVE"], "YES")
        self.assertEqual(row["MARKER"], "ROW82")
        self.assertNotEqual(row["template"], "T129")
        self.assertNotEqual(row["MARKER"], "ROW129")
        self.assertNotEqual(row["MARKER"], "ROW13")

    def test_e_no_eligible_row_has_no_template_fallback(self):
        data = frame([
            {"school_code": "BSM", "SCHOOLNAME": "", "template": "DO-NOT-USE"},
            {"school_code": "BSM", "SCHOOLNAME": "\t\n", "template": "ALSO-DO-NOT-USE"},
        ])
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(data)
        self.assertIn("No template fallback", str(caught.exception))

    def test_f_other_schools_are_not_selected_as_bsm(self):
        data = frame([
            {"school_code": "NBFP", "SCHOOLNAME": "NEW BRIGHT FUTURE", "template": "NBFP-TEMPLATE"},
            {"school_code": "BSM", "SCHOOLNAME": " ", "template": "BSM-BLANK"},
        ])
        with self.assertRaises(ConfigSelectionError):
            select_bsm_row(data)
        data = frame([
            {"school_code": "NBFP", "SCHOOLNAME": "NEW BRIGHT FUTURE", "template": "NBFP-TEMPLATE"},
            {"school_code": "BSM", "SCHOOLNAME": "BSM PUBLIC SCHOOL", "template": "BSM-TEMPLATE"},
        ])
        row = select_bsm_row(data)
        self.assertEqual(str(row["school_code"]).strip().upper(), "BSM")
        self.assertEqual(row["template"], "BSM-TEMPLATE")
        self.assertNotEqual(row["template"], "NBFP-TEMPLATE")

    def test_g_duplicate_required_headers_fail_closed(self):
        mangled = pd.DataFrame(
            [["BSM", "REAL NAME", "FIRST-TEMPLATE", "SECOND NAME", "SECOND-TEMPLATE"]],
            columns=["school_code", "SCHOOLNAME", "template", "SCHOOLNAME.1", "template.1"],
        )
        with self.assertRaises(ConfigSelectionError) as caught:
            select_bsm_row(mangled)
        self.assertIn("duplicated", str(caught.exception))

        raw = pd.DataFrame(
            [["BSM", "REAL NAME", "FIRST-TEMPLATE", "OTHER NAME"]],
            columns=["school_code", "SCHOOLNAME", "template", "SCHOOLNAME"],
        )
        with self.assertRaises(ConfigSelectionError):
            select_bsm_row(raw)

    def test_g_unrelated_duplicate_father_header_does_not_change_row(self):
        data = pd.DataFrame(
            [["BSM", "BSM PUBLIC SCHOOL", "T82", 10, 99]],
            columns=["school_code", "SCHOOLNAME", "template", "FATHER_X", "FATHER_X.1"],
        )
        row = select_bsm_row(data)
        self.assertEqual(row["template"], "T82")
        self.assertEqual(row["SCHOOLNAME"], "BSM PUBLIC SCHOOL")

    def test_g_synthetic_workbook_duplicate_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic_config.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(["school_code", "SCHOOLNAME", "template", "SCHOOLNAME"])
            sheet.append(["BSM", "BSM PUBLIC SCHOOL", "T-FIRST", "OTHER"])
            book.save(path)
            loaded = pd.read_excel(path)
            with self.assertRaises(ConfigSelectionError):
                select_bsm_row(loaded)
            self.assertFalse(path.name.startswith("student_data"))


class PathAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get("SAINI_DEV_CONFIG_XLSX")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("SAINI_DEV_CONFIG_XLSX", None)
        else:
            os.environ["SAINI_DEV_CONFIG_XLSX"] = self.old

    def test_default_path_matches_generator_workbook(self):
        os.environ.pop("SAINI_DEV_CONFIG_XLSX", None)
        self.assertEqual(
            resolve_config_workbook(),
            r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx",
        )
        self.assertEqual(resolve_config_workbook(), DEFAULT_CONFIG_WORKBOOK)

    def test_editor_and_generator_call_the_same_resolver(self):
        generator = ast.parse((ROOT / "SAINI_ID_CARD.py").read_text(encoding="utf-8"))
        editor = ast.parse((ROOT / "config_editor.py").read_text(encoding="utf-8"))
        def calls(tree):
            found = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    found.append(node.func.id)
            return found
        self.assertIn("resolve_config_workbook", calls(generator))
        self.assertIn("resolve_config_workbook", calls(editor))
        editor_text = (ROOT / "config_editor.py").read_text(encoding="utf-8")
        self.assertNotIn("F:\\SHRI_JAI_SHRI_RAM", editor_text)
        self.assertNotIn("F:/SHRI_JAI_SHRI_RAM", editor_text)
        self.assertNotIn("EXCEL_CONFIG =", editor_text)

    def test_temporary_override_is_shared_and_not_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / "synthetic_school_config.xlsx")
            os.environ["SAINI_DEV_CONFIG_XLSX"] = target
            self.assertEqual(resolve_config_workbook(), target)
            self.assertFalse(Path(target).exists())

    def test_legacy_f_path_is_refused_without_opening_it(self):
        os.environ["SAINI_DEV_CONFIG_XLSX"] = r"F:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
        with self.assertRaises(RuntimeError) as caught:
            resolve_config_workbook()
        self.assertIn("F:", str(caught.exception))
        source = (ROOT / "saini_config_path.py").read_text(encoding="utf-8")
        self.assertNotIn("open(", source)
        self.assertNotIn("exists(", source)

    def test_bsm_selector_is_wired_and_non_bsm_branch_remains(self):
        text = (ROOT / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        self.assertIn("from bsm_selector import ConfigSelectionError, select_bsm_row", text)
        self.assertEqual(text.count("select_bsm_row(self.config_df)"), 1)
        self.assertIn("config_row = self.config_df[self.config_df['school_code'].astype(str).str.strip() == school]", text)
        self.assertIn("config = self.config_df[self.config_df['school_code'] == school].iloc[0]", text)
        self.assertNotIn("write_by_name", text)


class ProtectionTests(unittest.TestCase):
    def test_baseline_matches_recorded_live_hashes(self):
        for name, expected in BASELINE.items():
            self.assertEqual(sha(ROOT / "baseline" / name), expected, name)

    def test_option_c_modules_were_not_modified(self):
        for name in ("gate.py", "identity.py", "journal.py", "safety.py", "sink_verifier.py"):
            self.assertEqual((ROOT / "option_c_modules" / name).read_bytes(), (ROOT / "baseline" / name).read_bytes())

    def test_development_sources_do_not_reference_photo_library(self):
        for name in ("bsm_selector.py", "saini_config_path.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("PHOTO_LIBRARY", text)
            self.assertNotIn("student_data.xlsx", text)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
