# -*- coding: utf-8 -*-
"""R23.4G: rollback may delete only a row this attempt conclusively created."""

import shutil
import sqlite3
import sys
import threading
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from identity_engine import IdentityEngine
from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from teacher_trial import TeacherTrial


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)


def _keys(engine):
    return {
        row["permanent_key"]
        for row in engine._conn.execute("SELECT permanent_key, photo_path FROM identities")
    }


def _photo_paths(engine):
    return {
        row["permanent_key"]: row["photo_path"] or ""
        for row in engine._conn.execute("SELECT permanent_key, photo_path FROM identities")
    }


def _insert_unrelated(database):
    key = str(uuid.uuid4())
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO students (permanent_key, school_code, created_session) VALUES (?, 'ABC', '2026_27')",
        (key,),
    )
    connection.execute(
        """
        INSERT INTO identities (
            permanent_key, school_code, session, visible_id, class_name,
            roll_number, student_name, father_name, photo_path, status
        ) VALUES (?, 'ABC', '2026_27', 'ABC1009', 'I', 9, 'DUMMY OTHER', 'DUMMY OTHER FATHER', NULL, 'current')
        """,
        (key,),
    )
    connection.commit()
    connection.close()
    return key


class OwnershipTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_assign = IdentityEngine.assign_photo

    def tearDown(self):
        IdentityEngine.assign_photo = self.original_assign
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_existing_photoless_student_survives_concurrent_insert_and_oserror(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            existing = trial._engine().create_student(
                "ABC", "2026_27", "I", 1, "DUMMY STUDENT A", "DUMMY FATHER A"
            )
            existing_key = existing["permanent_key"]

            def assign(engine, school, session, visible_id, source):
                _insert_unrelated(engine.db_path)
                raise OSError("concurrent-secret")

            IdentityEngine.assign_photo = assign
            failed = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(failed["code"], "photo_io_failed")
            self.assertNotIn("concurrent-secret", failed["message"])
            self.assertNotIn("permanent_key", failed["message"])
            keys = _keys(trial.engine)
            self.assertIn(existing_key, keys)
            self.assertEqual(_photo_paths(trial.engine)[existing_key], "")
            self.assertEqual(len(keys), 2)
        finally:
            trial.close()

    def test_existing_student_with_photo_is_unchanged_after_failed_attempt(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            first = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertTrue(first["ok"])
            photo = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
            before = photo.read_bytes()
            keys_before = _keys(trial.engine)

            def assign(self, school, session, visible_id, source):
                raise OSError("existing-secret")

            IdentityEngine.assign_photo = assign
            failed = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(failed["message"], "यह छात्र पहले से दर्ज है। नया रिकॉर्ड नहीं बना।")
            self.assertEqual(photo.read_bytes(), before)
            self.assertEqual(_keys(trial.engine), keys_before)
        finally:
            trial.close()

    def test_two_concurrent_attempts_do_not_delete_an_unrelated_student(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            bystander = trial._engine().create_student(
                "ABC", "2026_27", "I", 8, "DUMMY BYSTANDER", "DUMMY BYSTANDER FATHER"
            )
            bystander_key = bystander["permanent_key"]
            errors = []

            def assign(self, school, session, visible_id, source):
                raise OSError("race-secret")

            IdentityEngine.assign_photo = assign

            def attempt():
                try:
                    trial._one(
                        {
                            "school_code": "ABC",
                            "session": "2026_27",
                            "class": "I",
                            "roll_number": 1,
                            "student_name": "DUMMY STUDENT A",
                            "father_name": "DUMMY FATHER A",
                            "photo_file": "dummy_a.jpg",
                        },
                        TEST_PHOTOS,
                        "I",
                        "2026_27",
                    )
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=attempt), threading.Thread(target=attempt)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            keys = _keys(trial.engine)
            self.assertIn(bystander_key, keys)
            self.assertEqual(_photo_paths(trial.engine)[bystander_key], "")
            self.assertNotIn("ABC1001", {
                row["visible_id"]
                for row in trial.engine._conn.execute("SELECT visible_id FROM identities")
            })
        finally:
            trial.close()

    def test_only_the_new_failed_student_is_rolled_back(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            bystander = trial._engine().create_student(
                "ABC", "2026_27", "I", 8, "DUMMY BYSTANDER", "DUMMY BYSTANDER FATHER"
            )

            def assign(self, school, session, visible_id, source):
                raise OSError("new-secret")

            IdentityEngine.assign_photo = assign
            failed = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(failed["code"], "photo_io_failed")
            keys = _keys(trial.engine)
            self.assertEqual(keys, {bystander["permanent_key"]})
            self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg").exists())
        finally:
            trial.close()

    def test_uncertain_ownership_deletes_nothing(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            existing = trial._engine().create_student(
                "ABC", "2026_27", "I", 4, "DUMMY UNCERTAIN", "DUMMY UNCERTAIN FATHER"
            )
            key = existing["permanent_key"]
            trial._drop_new_without_photo(existing, set(), False, existing["visible_id"])
            trial._drop_new_without_photo(existing, {key}, True, existing["visible_id"])
            self.assertEqual(_keys(trial.engine), {key})
            self.assertEqual(_photo_paths(trial.engine)[key], "")
        finally:
            trial.close()


if __name__ == "__main__":
    unittest.main()
