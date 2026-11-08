# -*- coding: utf-8 -*-
"""R23.4L: the worker result must survive a Windows cp1252 console."""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tests" / "process_attempt.py"
sys.path.insert(0, str(ROOT / "src"))

from path_guard import TRIAL_WORKSPACE


def _clean():
    for relative in ("identity.sqlite", "PHOTO_LIBRARY", "enrollment_locks"):
        path = TRIAL_WORKSPACE / relative
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


class WorkerIoTest(unittest.TestCase):
    def setUp(self):
        _clean()

    def tearDown(self):
        _clean()
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_enroll_json_survives_cp1252_stdout(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "cp1252"
        env["PYTHONUTF8"] = "0"
        completed = subprocess.run(
            [sys.executable, str(WORKER), "enroll"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("cp1252", "replace"))
        text = completed.stdout.decode("cp1252")
        self.assertTrue(text.isascii())
        result = json.loads(text)
        self.assertTrue(result["ok"])
        self.assertEqual(result["visible_id"], "ABC1001")
        self.assertNotIn("permanent_key", text)


if __name__ == "__main__":
    unittest.main()
