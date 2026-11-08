# -*- coding: utf-8 -*-
"""R23.4D: a pre-existing staging file must stop enrollment before any student row."""

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from teacher_trial import TeacherTrial

STAGING_BYTES = b"pre-existing-staging-do-not-touch"
TARGET_BYTES = b"pre-existing-target-do-not-touch"


def _clean():
    database = TRIAL_WORKSPACE / "identity.sqlite"
    library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
    if database.exists():
        database.unlink()
    if library.exists():
        shutil.rmtree(library)


class StagingGuardTest(unittest.TestCase):
    def setUp(self):
        _clean()

    def tearDown(self):
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_preexisting_staging_file_blocks_enrollment_and_stays_unchanged(self):
        staging = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg.staging"
        staging.parent.mkdir(parents=True)
        staging.write_bytes(STAGING_BYTES)
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(results[0]["code"], "photo_staging_exists")
            self.assertEqual(staging.read_bytes(), STAGING_BYTES)
            self.assertFalse((staging.parent / "ABC1001.jpg").exists())
            self.assertEqual(trial.engine.count_identities(), 0)
        finally:
            trial.close()

    def test_normal_enrollment_works_without_a_staging_file(self):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertTrue(results[0]["ok"])
            self.assertEqual(results[0]["visible_id"], "ABC1001")
            photo = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
            self.assertTrue(photo.is_file())
            self.assertFalse(photo.with_name(photo.name + ".staging").exists())
            self.assertEqual(trial.engine.count_identities(), 1)
        finally:
            trial.close()

    def test_preexisting_target_photo_behavior_is_unchanged(self):
        target = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
        target.parent.mkdir(parents=True)
        target.write_bytes(TARGET_BYTES)
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            results = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")
            self.assertEqual(results[0]["code"], "photo_exists")
            self.assertEqual(target.read_bytes(), TARGET_BYTES)
            self.assertFalse(target.with_name(target.name + ".staging").exists())
            self.assertEqual(trial.engine.count_identities(), 0)
        finally:
            trial.close()


if __name__ == "__main__":
    unittest.main()
