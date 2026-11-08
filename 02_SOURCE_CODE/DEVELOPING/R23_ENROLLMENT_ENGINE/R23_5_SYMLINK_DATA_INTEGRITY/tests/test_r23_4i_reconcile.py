# -*- coding: utf-8 -*-
"""R23.4I: an exception after a committed photo link must not delete that photo."""

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

PHOTO = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
SENTINEL = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "sentinel.bin"


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    locks = TRIAL_WORKSPACE / "enrollment_locks"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)
    if locks.exists():
        shutil.rmtree(locks)


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_assign = IdentityEngine.assign_photo

    def tearDown(self):
        IdentityEngine.assign_photo = self.original_assign
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def _row(self, trial):
        return trial.engine._conn.execute(
            """
            SELECT photo_path FROM identities
            WHERE school_code='ABC' AND session='2026_27' AND visible_id='ABC1001' AND status='current'
            """
        ).fetchone()

    def _enroll(self, assign):
        IdentityEngine.assign_photo = assign
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            return result, self._row(trial), trial
        except Exception:
            trial.close()
            raise

    def test_oserror_after_commit_keeps_row_and_photo(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        original = self.original_assign

        def assign(self, school, session, visible_id, source):
            original(self, school, session, visible_id, source)
            raise OSError("after-commit-secret")

        result, row, trial = self._enroll(assign)
        try:
            self.assertEqual(result["code"], "photo_saved")
            self.assertNotIn("after-commit-secret", json.dumps(result))
            self.assertNotIn("permanent_key", json.dumps(result))
            self.assertIsNotNone(row)
            self.assertEqual(Path(row["photo_path"]).read_bytes(), payload)
            self.assertTrue(PHOTO.is_file())
        finally:
            trial.close()

    def test_runtime_error_after_commit_keeps_row_and_photo(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        original = self.original_assign

        def assign(self, school, session, visible_id, source):
            original(self, school, session, visible_id, source)
            raise RuntimeError("after-runtime-secret")

        result, row, trial = self._enroll(assign)
        try:
            self.assertEqual(result["code"], "photo_saved")
            self.assertNotIn("after-runtime-secret", json.dumps(result))
            self.assertEqual(Path(row["photo_path"]).read_bytes(), payload)
        finally:
            trial.close()

    def test_committed_link_with_missing_file_fails_closed(self):
        original = self.original_assign

        def assign(self, school, session, visible_id, source):
            updated = original(self, school, session, visible_id, source)
            SENTINEL.write_bytes(b"do-not-touch")
            Path(updated["photo_path"]).unlink()
            raise OSError("missing-secret")

        result, row, trial = self._enroll(assign)
        try:
            self.assertEqual(result["code"], "photo_reconcile_failed")
            self.assertNotIn("missing-secret", json.dumps(result))
            self.assertIsNotNone(row)
            self.assertTrue(row["photo_path"])
            self.assertFalse(PHOTO.exists())
            self.assertEqual(SENTINEL.read_bytes(), b"do-not-touch")
            self.assertEqual(trial.engine.count_identities(), 1)
        finally:
            trial.close()

    def test_committed_link_with_different_bytes_fails_closed(self):
        original = self.original_assign

        def assign(self, school, session, visible_id, source):
            updated = original(self, school, session, visible_id, source)
            Path(updated["photo_path"]).write_bytes(b"different-bytes")
            SENTINEL.write_bytes(b"do-not-touch")
            raise OSError("mismatch-secret")

        result, row, trial = self._enroll(assign)
        try:
            self.assertEqual(result["code"], "photo_reconcile_failed")
            self.assertNotIn("mismatch-secret", json.dumps(result))
            self.assertIsNotNone(row)
            self.assertEqual(PHOTO.read_bytes(), b"different-bytes")
            self.assertEqual(SENTINEL.read_bytes(), b"do-not-touch")
            self.assertEqual(trial.engine.count_identities(), 1)
        finally:
            trial.close()

    def test_oserror_before_commit_cleans_only_the_new_unlinked_attempt(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            bystander = trial._engine().create_student(
                "ABC", "2026_27", "I", 8, "DUMMY BYSTANDER", "DUMMY BYSTANDER FATHER"
            )
            SENTINEL.parent.mkdir(parents=True, exist_ok=True)
            SENTINEL.write_bytes(b"pre-existing")

            def assign(self, school, session, visible_id, source):
                raise OSError("before-commit-secret")

            IdentityEngine.assign_photo = assign
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(result["code"], "photo_io_failed")
            self.assertNotIn("before-commit-secret", json.dumps(result))
            self.assertIsNone(self._row(trial))
            self.assertFalse(PHOTO.exists())
            keys = {
                row["permanent_key"]
                for row in trial.engine._conn.execute("SELECT permanent_key FROM identities")
            }
            self.assertEqual(keys, {bystander["permanent_key"]})
            self.assertEqual(SENTINEL.read_bytes(), b"pre-existing")
        finally:
            trial.close()


if __name__ == "__main__":
    unittest.main()
