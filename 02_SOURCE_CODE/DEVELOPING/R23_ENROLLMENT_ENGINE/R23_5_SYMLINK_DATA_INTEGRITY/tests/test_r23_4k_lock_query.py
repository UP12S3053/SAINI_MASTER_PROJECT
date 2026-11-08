# -*- coding: utf-8 -*-
"""R23.4K: a lock probe must not signal, kill, or outlive the caller."""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import teacher_trial
from identity_engine import IdentityError
from path_guard import TRIAL_WORKSPACE
from teacher_trial import CrossProcessPhotoLock, _owner_from_identity, _windows_identity_from_probe


def _clean():
    for relative in ("identity.sqlite", "PHOTO_LIBRARY", "enrollment_locks"):
        path = TRIAL_WORKSPACE / relative
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


class LockQueryTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_name = teacher_trial.os.name
        self.original_kill = teacher_trial.os.kill
        self.original_query = teacher_trial._windows_process_identity

    def tearDown(self):
        teacher_trial.os.name = self.original_name
        teacher_trial.os.kill = self.original_kill
        teacher_trial._windows_process_identity = self.original_query
        os.environ.pop("SAINI_PHOTO_LOCK_TIMEOUT", None)
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_confirmed_dead_owner_is_not_alive(self):
        self.assertFalse(_owner_from_identity("stamp", None))
        self.assertFalse(_owner_from_identity("", None))

    def test_indeterminate_owner_stays_alive(self):
        self.assertTrue(_owner_from_identity("stamp", "unknown"))
        self.assertTrue(_owner_from_identity("", "unknown"))

    def test_creation_mismatch_is_a_different_process(self):
        self.assertFalse(_owner_from_identity("first", "second"))

    def test_matching_creation_is_alive(self):
        self.assertTrue(_owner_from_identity("stamp", "stamp"))
        self.assertTrue(_owner_from_identity("", "stamp"))

    def test_windows_probe_mapping_fails_closed(self):
        self.assertIsNone(_windows_identity_from_probe(False, None, None, 87))
        self.assertEqual(_windows_identity_from_probe(False, None, None, 5), "unknown")
        self.assertEqual(_windows_identity_from_probe(True, None, None, 0), "unknown")
        self.assertIsNone(_windows_identity_from_probe(True, 0, 10, 0))
        self.assertEqual(_windows_identity_from_probe(True, 259, 10, 0), "10")

    def test_windows_owner_check_does_not_signal_or_kill(self):
        calls = []

        def forbid_kill(*_args):
            calls.append("kill")
            raise AssertionError("os.kill must not run on Windows")

        teacher_trial.os.name = "nt"
        teacher_trial.os.kill = forbid_kill
        teacher_trial._windows_process_identity = lambda _pid: "stamp"
        self.assertTrue(teacher_trial._owner_alive({"pid": 4321, "start": "stamp"}))
        teacher_trial._windows_process_identity = lambda _pid: None
        self.assertFalse(teacher_trial._owner_alive({"pid": 4321, "start": "stamp"}))
        teacher_trial._windows_process_identity = lambda _pid: "unknown"
        self.assertTrue(teacher_trial._owner_alive({"pid": 4321, "start": "stamp"}))
        teacher_trial._windows_process_identity = lambda _pid: "other"
        self.assertFalse(teacher_trial._owner_alive({"pid": 4321, "start": "stamp"}))
        self.assertEqual(calls, [])

    def test_live_owner_timeout_preserves_staging_and_this_process(self):
        os.environ["SAINI_PHOTO_LOCK_TIMEOUT"] = "0.2"
        library = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27"
        library.mkdir(parents=True)
        staging = library / "ABC1001.jpg.staging"
        staging.write_bytes(b"other-process")
        lock_dir = TRIAL_WORKSPACE / "enrollment_locks"
        lock_dir.mkdir()
        (lock_dir / "ABC_2026_27_ABC1001.lock").write_text(json.dumps({
            "pid": os.getpid(),
            "token": "this-process",
            "start": teacher_trial._process_start(os.getpid()),
        }), encoding="utf-8")
        lock = CrossProcessPhotoLock(TRIAL_WORKSPACE, "ABC", "2026_27", "ABC1001")
        started = time.monotonic()
        with self.assertRaises(IdentityError) as caught:
            lock.acquire()
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, "photo_lock_busy")
        self.assertGreaterEqual(elapsed, 0.15)
        self.assertLess(elapsed, 2)
        self.assertEqual(staging.read_bytes(), b"other-process")
        self.assertTrue(lock.path.is_file())
        self.assertEqual(os.getpid(), json.loads(lock.path.read_text(encoding="utf-8"))["pid"])

    def test_timeout_child_is_not_left_running(self):
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            process.communicate(timeout=0.2)
            self.fail("sleeping child returned early")
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
        self.assertIsNotNone(process.poll())


if __name__ == "__main__":
    unittest.main()
