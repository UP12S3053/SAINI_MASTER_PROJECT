# -*- coding: utf-8 -*-
"""R23.5: prove junction cleanup on Windows. A symlink skip is not a pass."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from junction_probe import (
    JunctionCleanupError,
    JunctionUnavailable,
    classify_junction_attempt,
    create_directory_junction,
    remove_directory_junction,
)
from symlink_setup import require_symlink

UNVERIFIED = (
    "Windows junction data-integrity check was not executed on this Linux runner. "
    "Status: UNVERIFIED."
)
SECRET = b"synthetic-not-a-student"


class DataIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="saini_r23_5_"))
        self.outside = self.temp / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_bytes(SECRET)
        self.link = self.temp / "link"

    def tearDown(self):
        if os.name == "nt" and (self.link.exists() or self.link.is_symlink()):
            remove_directory_junction(self.link)
        shutil.rmtree(self.temp)

    def test_windows_junction_removal_keeps_the_target(self):
        if os.name != "nt":
            self.skipTest(UNVERIFIED)
        create_directory_junction(self.link, self.outside)
        remove_directory_junction(self.link)
        self.assertFalse(self.link.exists())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), SECRET)

    def test_windows_rmdir_failure_is_a_failure_not_a_skip(self):
        if os.name != "nt":
            self.skipTest(UNVERIFIED)
        create_directory_junction(self.link, self.outside)

        def refuse(_path):
            return 1, "access denied"

        with self.assertRaises(JunctionCleanupError) as caught:
            remove_directory_junction(self.link, rmdir_func=refuse)
        self.assertIn("rmdir returned 1", str(caught.exception))
        self.assertIn("access denied", str(caught.exception))
        self.assertTrue(self.link.exists())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), SECRET)

    def test_real_directory_is_not_deleted(self):
        folder = self.temp / "real"
        folder.mkdir()
        (folder / "keep.txt").write_bytes(SECRET)
        with self.assertRaises(JunctionCleanupError):
            remove_directory_junction(folder)
        self.assertEqual((folder / "keep.txt").read_bytes(), SECRET)

    def test_junction_creation_failure_is_not_a_pass(self):
        def fail():
            raise JunctionUnavailable("junction creation failed: synthetic privilege denied")

        status, reason = classify_junction_attempt(fail)
        self.assertEqual(status, "skipped")
        self.assertNotEqual(status, "passed")
        self.assertIn("synthetic privilege denied", reason)

    def test_uncreated_symlink_skip_is_not_a_pass(self):
        def refuse(self, target, target_is_directory=False):
            error = OSError(13, "A required privilege is not held by the client")
            error.winerror = 1314
            raise error

        original = Path.symlink_to
        Path.symlink_to = refuse
        try:
            with self.assertRaises(unittest.SkipTest) as caught:
                require_symlink(self.temp / "absent", self.outside, target_is_directory=True)
        finally:
            Path.symlink_to = original
        self.assertIn("SKIPPED, not passed", str(caught.exception))
        self.assertNotIn("PASS", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
