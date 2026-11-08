# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deploy_check import inspect_package, refuse_live_destination
from identity_engine import IdentityError


class R233CDeploymentTests(unittest.TestCase):
    def test_package_is_complete_and_live_destination_is_refused(self):
        report = inspect_package(ROOT)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["problems"], [])
        self.assertTrue(report["ready"])
        bat = (ROOT / "Open_Enrollment.bat").read_text(encoding="utf-8")
        self.assertNotIn("MAIN_ASSISTANT", bat)
        self.assertNotIn("SHRI_JAI_SHRI_RAM", bat)
        self.assertIn("open_launcher.py", bat)
        with self.assertRaises(IdentityError):
            refuse_live_destination(r"D:\SHRI_JAI_SHRI_RAM\project_panels\MAIN_ASSISTANT.py")
        with self.assertRaises(IdentityError):
            refuse_live_destination(r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx")


if __name__ == "__main__":
    unittest.main()
