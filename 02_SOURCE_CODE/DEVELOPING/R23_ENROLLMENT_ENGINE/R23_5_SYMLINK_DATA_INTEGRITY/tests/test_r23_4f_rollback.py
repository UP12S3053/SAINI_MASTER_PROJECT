# -*- coding: utf-8 -*-
"""R23.4F: an OSError during photo assignment rolls back only the new student."""

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from identity_engine import IdentityEngine
from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from teacher_trial import TeacherTrial

SENTINEL = b"pre-existing-sentinel-do-not-touch"


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)


def _row(roll, photo):
    return {
        "school_code": "ABC",
        "session": "2026_27",
        "class": "I",
        "roll_number": roll,
        "student_name": "DUMMY STUDENT",
        "father_name": "DUMMY FATHER",
        "photo_file": photo,
    }


class RollbackTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_assign = IdentityEngine.assign_photo

    def tearDown(self):
        IdentityEngine.assign_photo = self.original_assign
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def _fail_with(self, method):
        IdentityEngine.assign_photo = method
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(result["code"], "photo_io_failed")
            self.assertNotIn("permanent_key", json.dumps(result))
            self.assertNotIn("secret", json.dumps(result))
            self.assertEqual(trial.engine.count_identities(), 0)
            return trial
        finally:
            trial.close()

    def test_oserror_before_staging_leaves_no_student(self):
        def assign(self, school, session, visible_id, source):
            raise OSError("before-staging-secret")

        self._fail_with(assign)
        library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
        self.assertFalse(library.exists() and any(library.rglob("*.jpg")))
        self.assertFalse(library.exists() and any(library.rglob("*.staging")))

    def test_oserror_during_staging_removes_only_owned_bytes(self):
        def assign(self, school, session, visible_id, source):
            payload = Path(source).read_bytes()
            target = self.photo_path(school, session, visible_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = target.with_name(target.name + ".staging")
            staging.write_bytes(payload)
            raise OSError("during-staging-secret")

        self._fail_with(assign)
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg.staging").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg").exists())

    def test_oserror_during_final_photo_creation_leaves_no_student(self):
        def assign(self, school, session, visible_id, source):
            payload = Path(source).read_bytes()
            target = self.photo_path(school, session, visible_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            raise OSError("during-final-secret")

        self._fail_with(assign)
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg").exists())

    def test_oserror_during_linking_leaves_no_student(self):
        original = self.original_assign
        original_link = IdentityEngine._link_verified_photo

        def assign(self, school, session, visible_id, source):
            def boom(*_args, **_kwargs):
                raise OSError("during-link-secret")

            IdentityEngine._link_verified_photo = boom
            try:
                return original(self, school, session, visible_id, source)
            finally:
                IdentityEngine._link_verified_photo = original_link

        self._fail_with(assign)
        folder = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27"
        self.assertFalse((folder / "ABC1001.jpg").exists())
        self.assertFalse((folder / "ABC1001.jpg.staging").exists())

    def test_unproven_partial_file_is_left_untouched(self):
        def assign(self, school, session, visible_id, source):
            target = self.photo_path(school, session, visible_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = target.with_name(target.name + ".staging")
            staging.write_bytes(b"partial-not-owned")
            raise OSError("partial-secret")

        self._fail_with(assign)
        staging = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg.staging"
        self.assertEqual(staging.read_bytes(), b"partial-not-owned")

    def test_existing_student_and_files_survive_a_failed_new_enrollment(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            first = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertTrue(first["ok"])
            photo = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
            before_photo = photo.read_bytes()
            sentinel = photo.parent / "sentinel.bin"
            sentinel.write_bytes(SENTINEL)

            def assign(self, school, session, visible_id, source):
                raise OSError("second-secret")

            IdentityEngine.assign_photo = assign
            failed = trial._one(_row(2, "dummy_b.jpg"), TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(failed["code"], "photo_io_failed")
            self.assertNotIn("second-secret", json.dumps(failed))
            self.assertNotIn("permanent_key", json.dumps(failed))
            self.assertEqual(trial.engine.count_identities(), 1)
            self.assertEqual(photo.read_bytes(), before_photo)
            self.assertEqual(sentinel.read_bytes(), SENTINEL)
            self.assertFalse((photo.parent / "ABC1002.jpg").exists())
        finally:
            trial.close()

    def test_unexpected_exception_is_not_swallowed_and_new_row_is_removed(self):
        def assign(self, school, session, visible_id, source):
            raise RuntimeError("unexpected-secret")

        IdentityEngine.assign_photo = assign
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            with self.assertRaises(RuntimeError) as caught:
                trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertIn("unexpected-secret", str(caught.exception))
            self.assertEqual(trial.engine.count_identities(), 0)
        finally:
            trial.close()


if __name__ == "__main__":
    unittest.main()
