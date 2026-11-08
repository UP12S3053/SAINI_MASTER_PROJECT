# -*- coding: utf-8 -*-
"""R23.4H: separate processes must not take each other's files, and a linked photo stays."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from identity_engine import IdentityEngine
from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from teacher_trial import TeacherTrial

WORKER = ROOT / "tests" / "process_attempt.py"
PHOTO = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg"
STAGING = PHOTO.with_name(PHOTO.name + ".staging")


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


def _run(command, extra_env=None, args=()):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(
        [sys.executable, str(WORKER), command, *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(timeout=30)
    except BaseException:
        process.kill()
        process.communicate(timeout=5)
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


class CrossProcessTest(unittest.TestCase):
    def setUp(self):
        _clean()
        self.original_view = IdentityEngine.teacher_view
        self.original_public = TeacherTrial._public_result

    def tearDown(self):
        IdentityEngine.teacher_view = self.original_view
        TeacherTrial._public_result = self.original_public
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_matching_bytes_without_ownership_are_not_deleted(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        PHOTO.parent.mkdir(parents=True)
        PHOTO.write_bytes(payload)
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            trial._remove_attempt_file(PHOTO, payload, False, False)
            self.assertEqual(PHOTO.read_bytes(), payload)
        finally:
            trial.close()

    def test_stale_lock_does_not_delete_another_staging_file(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            trial._engine()
            STAGING.parent.mkdir(parents=True, exist_ok=True)
            STAGING.write_bytes(payload)
            lock_dir = TRIAL_WORKSPACE / "enrollment_locks"
            lock_dir.mkdir(parents=True, exist_ok=True)
            (lock_dir / "ABC_2026_27_ABC1001.lock").write_text(
                json.dumps({"pid": 2147483646, "token": "dead-owner", "start": "1"}),
                encoding="utf-8",
            )
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(result["code"], "photo_staging_exists")
            self.assertEqual(STAGING.read_bytes(), payload)
            self.assertFalse(PHOTO.exists())
            self.assertEqual(trial.engine.count_identities(), 0)
        finally:
            trial.close()

    def test_two_processes_with_the_same_photo_keep_one_linked_file(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        first = subprocess.Popen(
            [sys.executable, str(WORKER), "enroll"],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        second = subprocess.Popen(
            [sys.executable, str(WORKER), "enroll"],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        first_out, first_err = first.communicate(timeout=30)
        second_out, second_err = second.communicate(timeout=30)
        self.assertEqual(first.returncode, 0, first_err)
        self.assertEqual(second.returncode, 0, second_err)
        results = [json.loads(first_out), json.loads(second_out)]
        self.assertTrue(any(item.get("ok") for item in results))
        self.assertNotIn("permanent_key", json.dumps(results))
        self.assertEqual(PHOTO.read_bytes(), payload)
        self.assertFalse(STAGING.exists())
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            rows = trial._engine()._conn.execute(
                "SELECT photo_path FROM identities WHERE visible_id='ABC1001' AND status='current'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(Path(rows[0]["photo_path"]).read_bytes(), payload)
        finally:
            trial.close()

    def test_a_failed_process_does_not_remove_the_other_process_staging_file(self):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp) / "ready"
            release = Path(temp) / "release"
            holder = subprocess.Popen(
                [sys.executable, str(WORKER), "hold", str(ready), str(release)],
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(200):
                    if ready.exists():
                        break
                    if holder.poll() is not None:
                        break
                    time_sleep()
                self.assertTrue(ready.exists(), holder.stderr.read() if holder.poll() is not None else "holder not ready")
                failed = _run("enroll", {"SAINI_PHOTO_LOCK_TIMEOUT": "1"})
                self.assertEqual(failed.returncode, 0, failed.stderr)
                result = json.loads(failed.stdout)
                self.assertEqual(result["code"], "photo_lock_busy")
                self.assertNotIn("permanent_key", json.dumps(result))
                self.assertEqual(STAGING.read_bytes(), payload)
            finally:
                release.write_text("go", encoding="utf-8")
                try:
                    holder.communicate(timeout=10)
                except BaseException:
                    holder.kill()
                    holder.communicate(timeout=5)
                    raise
                if holder.poll() is None:
                    holder.kill()
                    holder.communicate(timeout=5)

    def test_teacher_view_failure_after_link_keeps_the_photo(self):
        self._presentation_failure(IdentityEngine, "teacher_view", "view-secret")

    def test_public_result_failure_after_link_keeps_the_photo(self):
        def boom(self, created, message):
            raise RuntimeError("public-secret")

        TeacherTrial._public_result = boom
        self._expect_photo_kept("public-secret")

    def _presentation_failure(self, owner, name, secret):
        def boom(self, *args, **kwargs):
            raise RuntimeError(secret)

        setattr(owner, name, boom)
        self._expect_photo_kept(secret)

    def _expect_photo_kept(self, secret):
        payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
        trial = TeacherTrial(TRIAL_WORKSPACE)
        try:
            result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
            self.assertEqual(result["code"], "photo_saved")
            self.assertTrue(result["ok"])
            self.assertNotIn(secret, json.dumps(result))
            self.assertNotIn("permanent_key", json.dumps(result))
            self.assertEqual(PHOTO.read_bytes(), payload)
            row = trial.engine._conn.execute(
                "SELECT photo_path FROM identities WHERE visible_id='ABC1001' AND status='current'"
            ).fetchone()
            self.assertIsNotNone(row["photo_path"])
            self.assertEqual(Path(row["photo_path"]).read_bytes(), payload)
        finally:
            trial.close()


def time_sleep():
    import time
    time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
