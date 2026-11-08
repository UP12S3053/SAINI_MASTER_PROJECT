# -*- coding: utf-8 -*-
"""Regression tests for the three R23.4C defects. Dummy data only."""

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from development_launcher import DevelopmentLauncher
from identity_engine import IdentityEngine, IdentityError
from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE, _is_reparse_point
import path_guard
from teacher_trial import TeacherTrial


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)


def _install_photo_fail(mode):
    original = IdentityEngine.__init__

    def wrapped(self, db_path, photo_root):
        original(self, db_path, photo_root)
        self.photo_fail = mode

    IdentityEngine.__init__ = wrapped
    return original


class RemediationTest(unittest.TestCase):
    def setUp(self):
        _clean()

    def tearDown(self):
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_photo_failure_modes_leave_no_student_or_attempt_file(self):
        decoy = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "KEEP" / "keep.jpg"
        decoy.parent.mkdir(parents=True)
        decoy.write_bytes(b"pre-existing-keep")
        for mode, code in (
            ("database", "photo_database_failed"),
            ("stage", "photo_stage_failed"),
            ("finalize", "photo_finalize_failed"),
        ):
            original = _install_photo_fail(mode)
            trial = TeacherTrial(TRIAL_WORKSPACE)
            try:
                results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
                self.assertEqual(results[0]["code"], code)
                self.assertEqual(trial.engine.count_identities(), 0)
                self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg").exists())
                self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg.staging").exists())
                self.assertEqual(decoy.read_bytes(), b"pre-existing-keep")
            finally:
                IdentityEngine.__init__ = original
                trial.close()

    def test_preexisting_and_replaced_photos_are_not_deleted(self):
        target = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"different-preexisting-photo")
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(results[0]["code"], "photo_exists")
            self.assertEqual(target.read_bytes(), b"different-preexisting-photo")
            self.assertEqual(trial.engine.count_identities(), 0)
        finally:
            trial.close()
        _clean()
        original = IdentityEngine.assign_photo

        def write_other_bytes(self, school, session, visible_student_id, source_path):
            path = self.photo_path(school, session, visible_student_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"replaced-after-create")
            raise IdentityError("photo_database_failed")

        IdentityEngine.assign_photo = write_other_bytes
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(results[0]["code"], "photo_database_failed")
            self.assertEqual(trial.engine.count_identities(), 0)
            replaced = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
            self.assertEqual(replaced.read_bytes(), b"replaced-after-create")
        finally:
            IdentityEngine.assign_photo = original
            trial.close()

    def test_legacy_launcher_methods_create_no_files(self):
        launcher = DevelopmentLauncher(TRIAL_WORKSPACE)
        try:
            for call in (
                lambda: launcher.visible_history("ABC", "2026_27", "ABC1001"),
                lambda: launcher.enroll_table(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS),
                lambda: launcher.promote("ABC", "2026_27", "ABC1001", "II", 2),
                lambda: launcher.run_legacy_baseline("teacher_trial.py"),
                lambda: launcher._enroll_row({}, TEST_PHOTOS),
                lambda: launcher._success({}, {}),
                lambda: launcher._engine(),
            ):
                with self.assertRaises(IdentityError):
                    call()
            launcher.close()
            self.assertIsNone(launcher.engine)
            self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
            self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())
        finally:
            launcher.close()

    def test_reparse_check_failure_is_not_treated_as_safe(self):
        sample = TEST_PHOTOS / "dummy_a.jpg"
        self.assertFalse(_is_reparse_point(sample, "excel_path_refused", platform="posix"))
        original = path_guard._windows_reparse_attribute

        def broken(_path):
            raise OSError("reparse_check_indeterminate")

        path_guard._windows_reparse_attribute = broken
        try:
            with self.assertRaises(IdentityError) as caught:
                _is_reparse_point(sample, "excel_path_refused", platform="nt")
            self.assertEqual(caught.exception.code, "excel_path_refused")
        finally:
            path_guard._windows_reparse_attribute = original


if __name__ == "__main__":
    unittest.main()
