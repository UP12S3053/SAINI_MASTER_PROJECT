# -*- coding: utf-8 -*-
"""Windows junction verification. Linux skips the live probe and does not call it a pass."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from identity_engine import IdentityError
from junction_probe import JunctionUnavailable, assert_junction_rejected, classify_junction_attempt
from path_guard import TEST_PHOTOS, TRIAL_WORKSPACE, _is_reparse_point, interpret_file_attributes


class JunctionVerificationTest(unittest.TestCase):
    def test_linux_skips_live_junction_without_passing_it(self):
        if sys.platform == "win32":
            try:
                assert_junction_rejected(TEST_PHOTOS, TRIAL_WORKSPACE)
            except JunctionUnavailable as exc:
                self.skipTest(str(exc))
            self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
            self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())
            return
        with self.assertRaises(JunctionUnavailable) as caught:
            assert_junction_rejected(TEST_PHOTOS, TRIAL_WORKSPACE)
        self.assertIn("UNVERIFIED", str(caught.exception))
        self.skipTest(str(caught.exception))

    def test_junction_creation_failure_is_skipped_not_passed(self):
        def fail():
            raise JunctionUnavailable("junction creation failed: synthetic permission denied")

        status, reason = classify_junction_attempt(fail)
        self.assertEqual(status, "skipped")
        self.assertNotEqual(status, "passed")
        self.assertEqual(reason, "junction creation failed: synthetic permission denied")
        self.assertFalse((TRIAL_WORKSPACE / "identity.sqlite").exists())
        self.assertFalse((TRIAL_WORKSPACE / "PHOTO_LIBRARY").exists())

    def test_indeterminate_windows_attributes_fail_closed(self):
        for value in (None, -1, 0xFFFFFFFF):
            with self.assertRaises(OSError):
                interpret_file_attributes(value)
        self.assertTrue(interpret_file_attributes(0x400))
        self.assertFalse(interpret_file_attributes(0x20))
        with self.assertRaises(IdentityError) as caught:
            original = sys.modules["path_guard"]._windows_reparse_attribute

            def broken(_path):
                raise OSError("reparse_check_indeterminate")

            sys.modules["path_guard"]._windows_reparse_attribute = broken
            try:
                _is_reparse_point(TEST_PHOTOS / "dummy_a.jpg", "photo_dir_refused", platform="nt")
            finally:
                sys.modules["path_guard"]._windows_reparse_attribute = original
        self.assertEqual(caught.exception.code, "photo_dir_refused")


if __name__ == "__main__":
    unittest.main()
