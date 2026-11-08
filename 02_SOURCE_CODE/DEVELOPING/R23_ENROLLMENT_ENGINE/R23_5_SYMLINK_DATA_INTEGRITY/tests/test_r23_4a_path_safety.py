# -*- coding: utf-8 -*-
"""Path allowlist tests for the R23.4A safety patch.

These tests use the dummy files shipped in this package.
They must not create a trial database.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from identity_engine import IdentityError, visible_id
from path_guard import (
    TEST_EXCEL,
    TEST_PHOTOS,
    TRIAL_WORKSPACE,
    preflight_photo_names,
    require_excel,
    require_photo_dir,
    require_workspace,
)
from teacher_trial import main
from trial_window import EnrollmentScreen

import openpyxl


def _files(root):
    return sorted(
        path.relative_to(root).as_posix()
        for path in Path(root).rglob("*")
        if path.is_file()
    )


def _workbook(path, photo_name):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
    sheet.append(["ABC", "2026_27", "I", 1, "DUMMY STUDENT A", "DUMMY FATHER A", photo_name])
    book.save(path)
    book.close()


class PathSafetyTest(unittest.TestCase):
    def setUp(self):
        self.package_before = _files(ROOT)
        self.workspace_before = _files(TRIAL_WORKSPACE)

    def tearDown(self):
        self.assertEqual(self.workspace_before, _files(TRIAL_WORKSPACE))
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_visible_id_rule_is_unchanged(self):
        self.assertEqual(visible_id("ABC", "I", 1), "ABC1001")
        self.assertEqual(visible_id("ABC", "VI", 15), "ABC6015")

    def test_valid_test_excel_path(self):
        selected = require_excel(TEST_EXCEL / "TEST_CLASS_1.xlsx")
        self.assertEqual(selected, (TEST_EXCEL / "TEST_CLASS_1.xlsx").resolve())
        self.assertTrue(str(selected).startswith(str(TEST_EXCEL.resolve())))

    def test_external_excel_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.xlsx"
            _workbook(outside, "dummy_a.jpg")
            with self.assertRaises(IdentityError) as caught:
                require_excel(outside)
            self.assertEqual(caught.exception.code, "excel_path_refused")
            self.assertFalse((Path(temp) / "identity.sqlite").exists())

    def test_valid_test_photos_path(self):
        selected = require_photo_dir(TEST_PHOTOS)
        self.assertEqual(selected, TEST_PHOTOS.resolve())
        self.assertTrue((TEST_PHOTOS / "dummy_a.jpg").is_file())

    def test_external_photo_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(IdentityError) as caught:
                require_photo_dir(temp)
            self.assertEqual(caught.exception.code, "photo_dir_refused")

    def test_parent_filename_is_rejected(self):
        with self.assertRaises(IdentityError) as caught:
            preflight_photo_names(TEST_PHOTOS, [{"photo_file": "../dummy_a.jpg"}])
        self.assertEqual(caught.exception.code, "photo_name_refused")

    def test_absolute_photo_path_is_rejected(self):
        with self.assertRaises(IdentityError) as caught:
            preflight_photo_names(TEST_PHOTOS, [{"photo_file": str(TEST_PHOTOS / "dummy_a.jpg")}])
        self.assertEqual(caught.exception.code, "photo_name_refused")

    def test_symlink_escape_is_rejected_where_supported(self):
        link = TEST_PHOTOS / "escape.jpg"
        created = TEST_EXCEL / "SYMLINK_CASE.xlsx"
        try:
            with tempfile.TemporaryDirectory() as temp:
                secret = Path(temp) / "secret.jpg"
                secret.write_bytes(b"not a student")
                try:
                    os.symlink(secret, link)
                except OSError as exc:
                    self.skipTest(f"symlink not supported: {exc}")
                _workbook(created, "escape.jpg")
                code, output = self._cli(created, TEST_PHOTOS, TRIAL_WORKSPACE)
                self.assertEqual(code, 1)
                self.assertIn("photo_name_refused", output)
                self.assertFalse((Path(temp) / "identity.sqlite").exists())
        finally:
            if link.is_symlink() or link.exists():
                link.unlink()
            if created.exists():
                created.unlink()

    def test_external_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(IdentityError) as caught:
                require_workspace(temp)
            self.assertEqual(caught.exception.code, "workspace_refused")
            self.assertFalse((Path(temp) / "identity.sqlite").exists())

    def test_cli_bypass_is_rejected_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.xlsx"
            _workbook(outside, "dummy_a.jpg")
            before = _files(ROOT)
            code, output = self._cli(outside, TEST_PHOTOS, TRIAL_WORKSPACE)
            self.assertEqual(code, 1)
            self.assertIn("excel_path_refused", output)
            code, output = self._cli(TEST_EXCEL / "TEST_CLASS_1.xlsx", temp, TRIAL_WORKSPACE)
            self.assertEqual(code, 1)
            self.assertIn("photo_dir_refused", output)
            code, output = self._cli(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, temp)
            self.assertEqual(code, 1)
            self.assertIn("workspace_refused", output)
            self.assertEqual(before, _files(ROOT))
            self.assertFalse((Path(temp) / "identity.sqlite").exists())

    def test_gui_rejects_external_paths_before_start(self):
        screen = EnrollmentScreen(
            open_file=lambda: str(TEST_EXCEL / "TEST_CLASS_1.xlsx"),
            open_folder=lambda: str(TEST_PHOTOS),
        )
        self.assertEqual(screen.choose_file(), "selected")
        self.assertEqual(screen.choose_folder(), "selected")
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.xlsx"
            _workbook(outside, "dummy_a.jpg")
            blocked = EnrollmentScreen(open_file=lambda: str(outside), open_folder=lambda: temp)
            self.assertEqual(blocked.choose_file(), "blocked")
            self.assertEqual(blocked.table, "")
            self.assertEqual(blocked.choose_folder(), "blocked")
            self.assertEqual(blocked.photos, "")
            blocked.table = str(outside)
            blocked.photos = str(TEST_PHOTOS)
            blocked.session = "2026_27"
            blocked.selected_class = "I"
            self.assertEqual(blocked.start(), "blocked")
            self.assertFalse((Path(temp) / "identity.sqlite").exists())

    def _cli(self, table, photos, workspace):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "--workspace", str(workspace),
                "--table", str(table),
                "--photos", str(photos),
                "--class", "I",
                "--session", "2026_27",
            ])
        return code, buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
