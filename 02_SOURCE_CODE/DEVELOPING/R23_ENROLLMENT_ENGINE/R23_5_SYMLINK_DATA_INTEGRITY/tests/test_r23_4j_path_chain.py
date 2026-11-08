# -*- coding: utf-8 -*-
"""R23.4J: a parent reparse point must never make reconciliation return verified."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import teacher_trial
from identity_engine import IdentityEngine, IdentityError
from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from symlink_setup import require_symlink
from teacher_trial import TeacherTrial

PHOTO = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
UNVERIFIED = "Windows junction verification was not executed on this Linux runner. Status: UNVERIFIED."


def _clean():
    for relative in ("identity.sqlite", "PHOTO_LIBRARY", "enrollment_locks"):
        path = TRIAL_WORKSPACE / relative
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


class PathChainTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_assign = IdentityEngine.assign_photo
        self.original_reparse = teacher_trial._is_reparse_point

    def tearDown(self):
        IdentityEngine.assign_photo = self.original_assign
        teacher_trial._is_reparse_point = self.original_reparse
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def _payload(self):
        return (TEST_PHOTOS / "dummy_a.jpg").read_bytes()

    def _plant(self, photo_path):
        trial = TeacherTrial(TRIAL_WORKSPACE)
        created = trial._engine().create_student(
            "ABC", "2026_27", "I", 1, "DUMMY STUDENT A", "DUMMY FATHER A"
        )
        trial.engine._conn.execute(
            "UPDATE identities SET photo_path=? WHERE permanent_key=?",
            (str(photo_path), created["permanent_key"]),
        )
        trial.engine._conn.commit()
        return trial

    def _state(self, trial, photo_path, payload):
        return trial._reconcile_committed_target(
            trial.engine, "ABC", "2026_27", "ABC1001", photo_path, payload
        )

    def test_normal_committed_photo_is_verified(self):
        payload = self._payload()
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertTrue(result["ok"])
            self.assertEqual(self._state(trial, PHOTO, payload), "verified")
            self.assertEqual(PHOTO.read_bytes(), payload)
        finally:
            trial.close()

    def test_oserror_after_commit_preserves_photo(self):
        self._error_after_commit(OSError("after-os-secret"), "after-os-secret")

    def test_runtime_error_after_commit_preserves_photo(self):
        self._error_after_commit(RuntimeError("after-runtime-secret"), "after-runtime-secret")

    def _error_after_commit(self, error, secret):
        payload = self._payload()
        original = self.original_assign

        def assign(self, school, session, visible_id, source):
            original(self, school, session, visible_id, source)
            raise error

        IdentityEngine.assign_photo = assign
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(result["code"], "photo_saved")
            self.assertNotIn(secret, json.dumps(result))
            self.assertEqual(PHOTO.read_bytes(), payload)
            self.assertEqual(self._state(trial, PHOTO, payload), "verified")
        finally:
            trial.close()

    def test_missing_committed_photo_fails_closed(self):
        payload = self._payload()
        PHOTO.parent.mkdir(parents=True)
        trial = self._plant(PHOTO)
        try:
            self.assertEqual(self._state(trial, PHOTO, payload), "broken")
            self.assertFalse(PHOTO.exists())
            self.assertEqual(trial.engine.count_identities(), 1)
        finally:
            trial.close()

    def test_different_photo_bytes_fail_closed(self):
        PHOTO.parent.mkdir(parents=True)
        PHOTO.write_bytes(b"different-bytes")
        trial = self._plant(PHOTO)
        try:
            self.assertEqual(self._state(trial, PHOTO, self._payload()), "broken")
            self.assertEqual(PHOTO.read_bytes(), b"different-bytes")
        finally:
            trial.close()

    def test_target_file_symlink_is_rejected(self):
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.jpg"
            outside.write_bytes(payload)
            PHOTO.parent.mkdir(parents=True)
            require_symlink(PHOTO, outside)
            trial = self._plant(PHOTO)
            try:
                self.assertEqual(self._state(trial, PHOTO, payload), "broken")
                self.assertEqual(outside.read_bytes(), payload)
                trial._remove_attempt_file(PHOTO, payload, False, True)
                self.assertEqual(outside.read_bytes(), payload)
            finally:
                trial.close()

    def test_parent_directory_symlink_is_rejected(self):
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temp:
            outside_dir = Path(temp) / "outside"
            outside = outside_dir / "ABC1001.jpg"
            outside.parent.mkdir()
            outside.write_bytes(payload)
            parent = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC"
            parent.parent.mkdir(parents=True, exist_ok=True)
            require_symlink(parent, outside_dir, target_is_directory=True)
            photo = parent / "ABC1001.jpg"
            trial = self._plant(photo)
            try:
                self.assertEqual(self._state(trial, photo, payload), "broken")
                self.assertEqual(outside.read_bytes(), payload)
                trial._remove_attempt_file(photo, payload, False, True)
                self.assertEqual(outside.read_bytes(), payload)
            finally:
                trial.close()

    def test_windows_directory_junction_is_rejected(self):
        if os.name != "nt":
            self.skipTest(UNVERIFIED)
        self._reject_windows_junction(nested=False)

    def test_nested_windows_junction_is_rejected(self):
        if os.name != "nt":
            self.skipTest(UNVERIFIED)
        self._reject_windows_junction(nested=True)

    def _reject_windows_junction(self, nested):
        from junction_probe import create_directory_junction, remove_directory_junction
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside"
            photo_outside = outside / "ABC1001.jpg"
            outside.mkdir()
            photo_outside.write_bytes(payload)
            library = TRIAL_WORKSPACE / "PHOTO_LIBRARY"
            library.mkdir(parents=True, exist_ok=True)
            first = library / "ABC"
            create_directory_junction(first, outside)
            photo = first / "ABC1001.jpg"
            second = None
            try:
                if nested:
                    second = library / "NEST"
                    create_directory_junction(second, first)
                    photo = second / "ABC1001.jpg"
                trial = self._plant(photo)
                try:
                    self.assertEqual(self._state(trial, photo, payload), "broken")
                    self.assertEqual(photo_outside.read_bytes(), payload)
                finally:
                    trial.close()
            finally:
                if second is not None:
                    remove_directory_junction(second)
                remove_directory_junction(first)

    def test_unreadable_reparse_attributes_fail_closed(self):
        payload = self._payload()
        PHOTO.parent.mkdir(parents=True)
        PHOTO.write_bytes(payload)

        def indeterminate(path, code, platform=None):
            raise IdentityError("photo_reconcile_failed")

        teacher_trial._is_reparse_point = indeterminate
        trial = self._plant(PHOTO)
        try:
            self.assertEqual(self._state(trial, PHOTO, payload), "broken")
            trial._remove_attempt_file(PHOTO, payload, False, True)
            self.assertEqual(PHOTO.read_bytes(), payload)
        finally:
            trial.close()

    def test_workspace_escape_is_rejected(self):
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "escape.jpg"
            outside.write_bytes(payload)
            escaped = self._lexical_escape()
            trial = self._plant(outside)
            try:
                self.assertEqual(self._state(trial, outside, payload), "broken")
                self.assertEqual(self._state(trial, escaped, payload), "broken")
                trial._remove_attempt_file(outside, payload, False, True)
                self.assertEqual(outside.read_bytes(), payload)
            finally:
                trial.close()

    def _lexical_escape(self):
        return TRIAL_WORKSPACE / "PHOTO_LIBRARY" / ".." / ".." / "escape.jpg"

    def test_validation_cleanup_race_does_not_delete_outside_file(self):
        payload = self._payload()
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "raced.jpg"
            outside.write_bytes(payload)
            PHOTO.parent.mkdir(parents=True)
            PHOTO.write_bytes(payload)
            trial = self._plant(PHOTO)
            try:
                self.assertEqual(self._state(trial, PHOTO, payload), "verified")
                PHOTO.unlink()
                require_symlink(PHOTO, outside)
                trial._remove_attempt_file(PHOTO, payload, False, True)
                self.assertTrue(outside.is_file())
                self.assertEqual(outside.read_bytes(), payload)
            finally:
                trial.close()


if __name__ == "__main__":
    unittest.main()
