# -*- coding: utf-8 -*-
"""R23.4F junction cleanup. A failed removal is a failure, never a skip or a pass."""

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
    remove_directory_junction,
)
from symlink_setup import require_symlink


class JunctionCleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="saini_r23_4f_"))
        self.outside = self.temp / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_bytes(b"synthetic-not-a-student")

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_successful_symlink_removal_does_not_delete_the_target(self):
        link = self.temp / "link"
        require_symlink(link, self.outside, target_is_directory=True)
        remove_directory_junction(link)
        self.assertFalse(link.exists())
        self.assertFalse(link.is_symlink())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), b"synthetic-not-a-student")

    def test_successful_rmdir_result_removes_only_the_link(self):
        link = self.temp / "link"
        require_symlink(link, self.outside, target_is_directory=True)

        def rmdir(path):
            Path(path).unlink()
            return 0, ""

        remove_directory_junction(link, rmdir_func=rmdir)
        self.assertFalse(link.exists())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), b"synthetic-not-a-student")

    def test_rmdir_failure_is_a_failure_not_a_skip(self):
        link = self.temp / "link"
        require_symlink(link, self.outside, target_is_directory=True)

        def rmdir(_path):
            return 1, "access denied"

        try:
            remove_directory_junction(link, rmdir_func=rmdir)
            status = "passed"
        except JunctionCleanupError as exc:
            status = "failed"
            self.assertIn("rmdir returned 1", str(exc))
            self.assertIn("access denied", str(exc))
        except JunctionUnavailable:
            status = "skipped"
        self.assertEqual(status, "failed")
        self.assertTrue(link.is_symlink())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), b"synthetic-not-a-student")

    def test_real_directory_is_not_recursively_deleted(self):
        folder = self.temp / "real"
        folder.mkdir()
        (folder / "keep.txt").write_bytes(b"keep")
        with self.assertRaises(JunctionCleanupError):
            remove_directory_junction(folder)
        self.assertEqual((folder / "keep.txt").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
