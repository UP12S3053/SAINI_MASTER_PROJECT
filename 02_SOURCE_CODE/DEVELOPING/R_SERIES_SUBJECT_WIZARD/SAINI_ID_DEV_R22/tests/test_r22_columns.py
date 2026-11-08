# -*- coding: utf-8 -*-
"""R22 synthetic column-mapping tests. No live workbook and no student data."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(os.environ.get("SAINI_R22_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))

from saini_column_map import (
    LIVE_WORKBOOK,
    R22_WORKBOOK,
    TRACKED,
    AmbiguousHeaderError,
    ColumnMapError,
    ambiguous_headers,
    assert_unambiguous,
    assert_writable,
    load_guarded_config,
    read_explicit,
    reference_differences,
    reject_forbidden_path,
    write_explicit,
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def source(name):
    path = ROOT / name
    if not path.is_file():
        raise unittest.SkipTest(name + " is not in this workspace")
    return path.read_text(encoding="utf-8")


_HOLD = []


def workbook(headers, values, formula=None):
    folder = tempfile.TemporaryDirectory()
    _HOLD.append(folder)
    path = Path(folder.name) / "synthetic_config.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(list(headers))
    sheet.append(list(values))
    if formula:
        sheet.cell(2, formula[0]).value = formula[1]
    book.save(path)
    return path


class DuplicateHeaderTests(unittest.TestCase):
    def test_01_all_tracked_headers_are_in_scope(self):
        self.assertEqual(len(TRACKED), 10)
        self.assertIn("M", TRACKED)

    def test_02_real_workbook_reference_positions(self):
        path = Path(R22_WORKBOOK)
        if not path.is_file():
            self.skipTest("R22 workbook is not on this machine")
        differences = reference_differences(path)
        self.assertEqual(differences, [], differences)

    def test_03_generator_uses_guarded_loader(self):
        text = source("SAINI_ID_CARD.py")
        self.assertIn("load_guarded_config(EXCEL_CONFIG, sheet_name='Sheet1')", text)
        self.assertNotIn("pd.read_excel(EXCEL_CONFIG", text)

    def test_04_editor_uses_guarded_loader(self):
        text = source("config_editor.py")
        self.assertIn("load_guarded_config(workbook)", text)
        self.assertIn("load_guarded_config(editor_workbook_path())", text)
        self.assertNotIn("pd.read_excel(", text)

    def test_05_editor_write_is_guarded(self):
        text = source("config_editor.py")
        self.assertEqual(text.count("assert_writable(editor_workbook_path())"), 3)

    def test_06_first_match_is_rejected(self):
        path = workbook(["FATHER_X", "FATHER_X"], [1, 2])
        with self.assertRaises(AmbiguousHeaderError):
            load_guarded_config(path)
        self.assertNotEqual(read_explicit(path, 2, "FATHER_X", "A"), 2)

    def test_07_last_match_is_rejected(self):
        path = workbook(["FATHER_X", "FATHER_X"], [1, 2])
        with self.assertRaises(AmbiguousHeaderError):
            read_explicit(path, 2, "FATHER_X", "")
        self.assertEqual(read_explicit(path, 2, "FATHER_X", "B"), 2)

    def test_08_ambiguous_read_is_rejected(self):
        path = workbook(["ADDR_COLOR", "NOTE", "ADDR_COLOR"], ["#111111", "KEEP", "#222222"])
        with self.assertRaises(AmbiguousHeaderError):
            assert_unambiguous(path)

    def test_09_ambiguous_write_is_rejected(self):
        path = workbook(["FATHER_SIZE", "FATHER_SIZE"], [None, None])
        before = sha(path)
        with self.assertRaises(AmbiguousHeaderError):
            assert_writable(path)
        self.assertEqual(sha(path), before)

    def test_10_different_values_are_preserved(self):
        path = workbook(["FATHER_Y", "FATHER_Y"], [10, 90])
        before = sha(path)
        with self.assertRaises(ColumnMapError):
            write_explicit(path, 2, "FATHER_Y", 11, "A")
        self.assertEqual(read_explicit(path, 2, "FATHER_Y", "A"), 10)
        self.assertEqual(read_explicit(path, 2, "FATHER_Y", "B"), 90)
        self.assertEqual(sha(path), before)

    def test_11_both_columns_blank(self):
        path = workbook(["FATHER_FONT", "FATHER_FONT"], [None, None])
        self.assertIsNone(read_explicit(path, 2, "FATHER_FONT", "A"))
        self.assertIsNone(read_explicit(path, 2, "FATHER_FONT", "B"))
        with self.assertRaises(AmbiguousHeaderError):
            load_guarded_config(path)

    def test_12_one_column_populated_is_still_ambiguous(self):
        path = workbook(["FATHER_PREFIX", "FATHER_PREFIX"], ["S/O", None])
        with self.assertRaises(AmbiguousHeaderError):
            load_guarded_config(path)
        self.assertEqual(read_explicit(path, 2, "FATHER_PREFIX", "A"), "S/O")
        self.assertIsNone(read_explicit(path, 2, "FATHER_PREFIX", "B"))

    def test_13_different_populated_columns_are_not_merged(self):
        path = workbook(["FATHER_SHOW", "FATHER_SHOW"], [1, 0])
        self.assertEqual(ambiguous_headers(path), ["FATHER_SHOW"])
        self.assertNotEqual(read_explicit(path, 2, "FATHER_SHOW", "A"), read_explicit(path, 2, "FATHER_SHOW", "B"))

    def test_14_explicit_mapping_writes_only_the_blank_approved_cell(self):
        path = workbook(["FATHER_COLOR", "KEEP", "FATHER_COLOR"], [None, "UNTOUCHED", None])
        write_explicit(path, 2, "FATHER_COLOR", "#ABCDEF", "A")
        self.assertEqual(read_explicit(path, 2, "FATHER_COLOR", "A"), "#ABCDEF")
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=False)
        try:
            row = list(next(book.active.iter_rows(min_row=2, max_row=2, values_only=True)))
        finally:
            book.close()
        self.assertEqual(row, ["#ABCDEF", "UNTOUCHED", None])

    def test_15_wrong_column_is_rejected(self):
        path = workbook(["FATHER_X", "OTHER"], [1, 2])
        with self.assertRaises(ColumnMapError):
            read_explicit(path, 2, "FATHER_X", "B")

    def test_16_header_moved_to_another_column_fails_closed(self):
        path = workbook(["OTHER", "FATHER_X"], [1, 2])
        with self.assertRaises(ColumnMapError):
            read_explicit(path, 2, "FATHER_X", "A")

    def test_17_missing_header_fails_closed(self):
        path = workbook(["school_code"], ["BSM"])
        with self.assertRaises(ColumnMapError):
            read_explicit(path, 2, "ADDR_SIZE", "A")

    def test_18_legacy_f_path_is_rejected(self):
        with self.assertRaises(ColumnMapError):
            reject_forbidden_path(r"F:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx")

    def test_19_live_workbook_path_is_rejected(self):
        with self.assertRaises(ColumnMapError):
            reject_forbidden_path(LIVE_WORKBOOK)

    def test_20_generator_and_editor_share_the_r22_workbook(self):
        source_text = source("saini_config_path.py")
        generator = source("SAINI_ID_CARD.py")
        editor = source("config_editor.py")
        self.assertIn(R22_WORKBOOK, source_text)
        self.assertIn("require_config_workbook()", generator)
        self.assertIn("require_config_workbook()", editor)

    def test_21_existing_non_empty_cell_is_preserved(self):
        path = workbook(["ADDR_SIZE", "ADDR_SIZE"], [15, None])
        before = sha(path)
        with self.assertRaises(ColumnMapError):
            write_explicit(path, 2, "ADDR_SIZE", 18, "A")
        self.assertEqual(read_explicit(path, 2, "ADDR_SIZE", "A"), 15)
        self.assertEqual(sha(path), before)

    def test_22_blank_value_does_not_clear_data(self):
        path = workbook(["ADDR_COLOR", "ADDR_COLOR"], ["#000000", None])
        before = sha(path)
        with self.assertRaises(ColumnMapError):
            write_explicit(path, 2, "ADDR_COLOR", "   ", "A")
        self.assertEqual(sha(path), before)

    def test_23_formula_cell_is_preserved(self):
        path = workbook(["FATHER_SIZE", "FATHER_SIZE"], [None, None], formula=(1, "=1+1"))
        before = path.read_bytes()
        with self.assertRaises(ColumnMapError):
            write_explicit(path, 2, "FATHER_SIZE", 12, "A")
        self.assertEqual(path.read_bytes(), before)

    def test_24_m_columns_are_not_merged(self):
        path = workbook(["M", "M", "M", "M", "M"], [1, 2, 3, 4, 5])
        with self.assertRaises(AmbiguousHeaderError):
            load_guarded_config(path)
        self.assertEqual([read_explicit(path, 2, "M", letter) for letter in "ABCDE"], [1, 2, 3, 4, 5])

    def test_25_option_c_sources_match_their_baseline(self):
        modules = ROOT / "option_c_modules"
        baseline = ROOT / "baseline"
        if not modules.is_dir() or not baseline.is_dir():
            self.skipTest("Option C baseline copy is not in this workspace")
        for name in ("gate.py", "identity.py", "journal.py", "safety.py", "sink_verifier.py"):
            self.assertEqual((modules / name).read_bytes(), (baseline / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
