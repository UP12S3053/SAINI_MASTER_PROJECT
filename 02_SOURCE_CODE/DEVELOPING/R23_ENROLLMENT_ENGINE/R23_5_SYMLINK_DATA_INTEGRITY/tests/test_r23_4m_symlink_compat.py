# -*- coding: utf-8 -*-
"""R23.4M: only an uncreated Windows privilege failure may skip."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from junction_probe import JunctionCleanupError, remove_directory_junction
from symlink_setup import require_symlink


def _privilege(winerror=1314):
    error = OSError(13, "A required privilege is not held by the client")
    error.winerror = winerror
    return error


class SymlinkCompatTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="saini_r23_4m_"))
        self.outside = self.temp / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_bytes(b"synthetic-not-a-student")
        self.original = Path.symlink_to

    def tearDown(self):
        Path.symlink_to = self.original
        shutil.rmtree(self.temp)

    def test_uncreated_privilege_failure_is_skipped_not_passed(self):
        def refuse(self, target, target_is_directory=False):
            raise _privilege()

        Path.symlink_to = refuse
        link = self.temp / "link"
        with self.assertRaises(unittest.SkipTest) as caught:
            require_symlink(link, self.outside, target_is_directory=True)
        reason = str(caught.exception)
        self.assertIn("SKIPPED, not passed", reason)
        self.assertIn("1314", reason)
        self.assertIn("not executed", reason)
        self.assertNotIn("PASS", reason)
        self.assertFalse(link.exists())

    def test_privilege_error_after_a_link_exists_is_a_failure(self):
        def partial(self, target, target_is_directory=False):
            self.mkdir()
            raise _privilege()

        Path.symlink_to = partial
        link = self.temp / "link"
        with self.assertRaises(OSError) as caught:
            require_symlink(link, self.outside, target_is_directory=True)
        self.assertNotIsInstance(caught.exception, unittest.SkipTest)
        self.assertTrue(link.exists())

    def test_other_windows_error_is_not_skipped(self):
        def denied(self, target, target_is_directory=False):
            error = OSError(5, "Access is denied")
            error.winerror = 5
            raise error

        Path.symlink_to = denied
        with self.assertRaises(OSError) as caught:
            require_symlink(self.temp / "link", self.outside, target_is_directory=True)
        self.assertEqual(caught.exception.winerror, 5)
        self.assertNotIsInstance(caught.exception, unittest.SkipTest)

    def test_cleanup_error_is_not_turned_into_a_skip(self):
        link = self.temp / "link"
        require_symlink(link, self.outside, target_is_directory=True)
        with self.assertRaises(JunctionCleanupError):
            remove_directory_junction(link, rmdir_func=lambda _path: (1, "access denied"))
        self.assertTrue(link.is_symlink())
        self.assertEqual((self.outside / "secret.txt").read_bytes(), b"synthetic-not-a-student")

    def test_successful_symlink_still_runs_the_assertion(self):
        link = self.temp / "link"
        require_symlink(link, self.outside, target_is_directory=True)
        self.assertTrue(link.is_symlink())
        self.assertEqual((link / "secret.txt").read_bytes(), b"synthetic-not-a-student")
        link.unlink()
        self.assertEqual((self.outside / "secret.txt").read_bytes(), b"synthetic-not-a-student")


if __name__ == "__main__":
    unittest.main()
