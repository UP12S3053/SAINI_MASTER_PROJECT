# -*- coding: utf-8 -*-
"""R23.4B safety tests. Dummy records only. No GUI launch."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import openpyxl

from active_writers import stepE_enroll_from_sheet, step_reassign_mixed
from controlled_writers import IdentityBypassError, enroll as controlled_enroll
from development_launcher import DevelopmentLauncher
from identity_engine import IdentityEngine, IdentityError, visible_id
from path_guard import (
    TEST_EXCEL,
    TEST_PHOTOS,
    TRIAL_WORKSPACE,
    junction_test_supported,
    require_excel,
    require_photo_dir,
    require_workspace,
)
from teacher_trial import TeacherTrial, main


def _files(root):
    return sorted(path.relative_to(root).as_posix() for path in Path(root).rglob("*") if path.is_file())


def _workbook(path, photo_name, roll=1, name="DUMMY STUDENT A", father="DUMMY FATHER A", klass="I"):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
    sheet.append(["ABC", "2026_27", klass, roll, name, father, photo_name])
    book.save(path)
    book.close()


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)


class SafetyReviewTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.package_before = _files(ROOT)

    def tearDown(self):
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())
        self.assertEqual(self.package_before, _files(ROOT))

    def test_excel_outside_package_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.xlsx"
            _workbook(outside, "dummy_a.jpg")
            with self.assertRaises(IdentityError) as caught:
                require_excel(outside)
            self.assertEqual(caught.exception.code, "excel_path_refused")
            self.assertEqual(_files(temp), ["outside.xlsx"])
            self.assertFalse((Path(temp) / "identity.sqlite").exists())

    def test_photo_dir_and_workspace_outside_create_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(IdentityError) as caught:
                require_photo_dir(temp)
            self.assertEqual(caught.exception.code, "photo_dir_refused")
            with self.assertRaises(IdentityError) as caught:
                require_workspace(temp)
            self.assertEqual(caught.exception.code, "workspace_refused")
            self.assertEqual([], _files(temp))

    def test_unc_paths_are_rejected_before_resolve(self):
        with self.assertRaises(IdentityError) as caught:
            require_excel("\\\\server\\share\\book.xlsx")
        self.assertEqual(caught.exception.code, "excel_path_refused")
        with self.assertRaises(IdentityError) as caught:
            require_photo_dir("//server/share/photos")
        self.assertEqual(caught.exception.code, "photo_dir_refused")

    def test_live_path_is_rejected(self):
        with self.assertRaises(IdentityError) as caught:
            require_excel("D:\\SHRI_JAI_SHRI_RAM\\student_data.xlsx")
        self.assertEqual(caught.exception.code, "live_path_refused")

    def test_dotdot_and_absolute_photo_names_create_no_database(self):
        created = TEST_EXCEL / "UNSAFE_NAME.xlsx"
        try:
            _workbook(created, "../dummy_a.jpg")
            code, output = self._cli(created)
            self.assertEqual(code, 1)
            self.assertIn("photo_name_refused", output)
            _workbook(created, str(TEST_PHOTOS / "dummy_a.jpg"))
            code, output = self._cli(created)
            self.assertEqual(code, 1)
            self.assertIn("photo_name_refused", output)
            self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        finally:
            if created.exists():
                created.unlink()

    def test_missing_required_photo_creates_no_database(self):
        created = TEST_EXCEL / "MISSING_PHOTO.xlsx"
        try:
            _workbook(created, "missing_dummy.jpg")
            code, output = self._cli(created)
            self.assertEqual(code, 1)
            self.assertIn("photo_source_missing", output)
            self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        finally:
            if created.exists():
                created.unlink()

    def test_corrupt_photo_creates_no_database(self):
        photo = TEST_PHOTOS / "corrupt.jpg"
        created = TEST_EXCEL / "CORRUPT_PHOTO.xlsx"
        try:
            photo.write_bytes(b"this is not a photograph")
            _workbook(created, "corrupt.jpg")
            code, output = self._cli(created)
            self.assertEqual(code, 1)
            self.assertIn("photo_invalid", output)
            self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        finally:
            if photo.exists():
                photo.unlink()
            if created.exists():
                created.unlink()

    def test_symlink_escape_creates_no_database(self):
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
                code, output = self._cli(created)
                self.assertEqual(code, 1)
                self.assertIn("photo_name_refused", output)
                self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
                self.assertFalse((Path(temp) / "identity.sqlite").exists())
        finally:
            if link.is_symlink() or link.exists():
                link.unlink()
            if created.exists():
                created.unlink()

    def test_windows_junction_is_reported_when_unsupported(self):
        if os.name != "nt":
            self.skipTest(
                "Windows junction verification was not executed on this Linux runner. Status: UNVERIFIED."
            )
        from junction_probe import JunctionUnavailable, assert_junction_rejected
        try:
            assert_junction_rejected(TEST_PHOTOS, TRIAL_WORKSPACE)
        except JunctionUnavailable as exc:
            self.skipTest(str(exc))

    def test_failed_photo_assignment_leaves_no_student_row(self):
        original = IdentityEngine.assign_photo

        def fail_photo(self, school, session, visible_student_id, source_path):
            raise IdentityError("photo_stage_failed")

        IdentityEngine.assign_photo = fail_photo
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(results[0]["code"], "photo_stage_failed")
            self.assertEqual(trial.engine.count_identities(), 0)
            self.assertNotIn("permanent_key", json.dumps(results))
        finally:
            IdentityEngine.assign_photo = original
            trial.close()

    def test_duplicate_enrollment_wrong_class_and_duplicate_roll(self):
        other = TEST_EXCEL / "DUP_ROLL.xlsx"
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            first = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            second = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            mixed = trial.start(TEST_EXCEL / "TEST_MIXED.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(first[0]["visible_id"], "ABC1001")
            self.assertEqual(first[0]["message"], "नामांकन हो गया।")
            self.assertEqual(second[0]["message"], "यह छात्र पहले से दर्ज है। नया रिकॉर्ड नहीं बना।")
            self.assertEqual(mixed[1]["message"], "यह पंक्ति चुनी हुई कक्षा या सेशन की नहीं है।")
            self.assertNotIn("permanent_key", json.dumps([first, second, mixed]))
            self.assertEqual(visible_id("ABC", "I", 1), "ABC1001")
            _workbook(other, "dummy_a.jpg", roll=1, name="DUMMY OTHER", father="DUMMY OTHER FATHER")
            duplicate_roll = trial.start(other, TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(duplicate_roll[0]["code"], "duplicate_identity")
            self.assertEqual(trial.engine.count_identities(), 1)
        finally:
            trial.close()
            if other.exists():
                other.unlink()

    def test_direct_old_writer_launcher_and_controlled_writer_do_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(IdentityError) as caught:
                DevelopmentLauncher(temp)
            self.assertEqual(caught.exception.code, "workspace_refused")
            self.assertEqual([], _files(temp))
        launcher = DevelopmentLauncher(TRIAL_WORKSPACE)
        try:
            with self.assertRaises(IdentityBypassError):
                launcher.enroll_table(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS)
            with self.assertRaises(IdentityBypassError):
                launcher.promote("ABC", "2026_27", "ABC1001", "II", 2)
            self.assertIsNone(launcher.engine)
        finally:
            launcher.close()
        with self.assertRaises(IdentityBypassError):
            stepE_enroll_from_sheet(None, "ABC", "2026_27", "I", 1, "DUMMY STUDENT A", "DUMMY FATHER A")
        with self.assertRaises(IdentityBypassError):
            step_reassign_mixed(None, "ABC", "2026_27", "ABC1001", "II", 2)
        with self.assertRaises(IdentityBypassError):
            controlled_enroll(None, "ABC", "2026_27", "I", 1, "DUMMY STUDENT A", "DUMMY FATHER A")
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())

    def test_promote_and_change_roll_are_not_exposed(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            with self.assertRaises(IdentityError) as caught:
                trial.promote("ABC", "2026_27", "ABC1001", "II", 2)
            self.assertEqual(caught.exception.code, "operation_not_exposed")
            with self.assertRaises(IdentityError) as caught:
                trial.change_roll("ABC", "2026_27", "ABC1001", 3)
            self.assertEqual(caught.exception.code, "operation_not_exposed")
            self.assertIsNone(trial.engine)
        finally:
            trial.close()

    def _cli(self, table):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "--workspace", str(TRIAL_WORKSPACE),
                "--table", str(table),
                "--photos", str(TEST_PHOTOS),
                "--class", "I",
                "--session", "2026_27",
            ])
        return code, buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
