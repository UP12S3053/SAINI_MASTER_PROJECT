# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trial_window import build_window


class R233BGuiRuntimeTests(unittest.TestCase):
    def test_open_launcher_process_opens_a_real_window(self):
        output = Path(tempfile.mkdtemp()) / "window.txt"
        env = os.environ.copy()
        env["SAINI_GUI_SELFTEST"] = "1"
        env["SAINI_GUI_SELFTEST_OUT"] = str(output)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "open_launcher.py")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        text = output.read_text(encoding="utf-8")
        self.assertIn("नामांकन", text)
        self.assertIn("Excel या CSV चुनें / Choose file", text)
        self.assertIn("फोटो फ़ोल्डर चुनें / Choose photo folder", text)
        self.assertIn("नामांकन शुरू करें / Start enrollment", text)
        self.assertIn("रद्द करें / Cancel", text)
        self.assertIn("बाहर निकलें / Exit", text)
        self.assertIn("कोई फ़ाइल नहीं / No file", text)
        self.assertIn("कोई फ़ोल्डर नहीं / No folder", text)

    def test_real_buttons_enroll_synthetic_pack_and_hide_the_key(self):
        import tkinter as tk
        pack = ROOT / "R23_3A_TEACHER_TRIAL_PACK"
        workspace = Path(tempfile.mkdtemp()) / "workspace"
        root = tk.Tk()
        root.update()
        parts = build_window(root)
        self.assertEqual(parts["screen"].table, "")
        self.assertEqual(parts["screen"].photos, "")
        parts["start_button"].invoke()
        root.update()
        self.assertIn("चुनें", parts["status"].get())

        parts["screen"].workspace = workspace
        parts["screen"].open_file = lambda: str(pack / "01_valid_class_1" / "students.xlsx")
        parts["screen"].open_folder = lambda: str(pack / "01_valid_class_1" / "photos")
        parts["file_button"].invoke()
        parts["folder_button"].invoke()
        root.update()
        self.assertEqual(parts["file_name"].get(), "students.xlsx")
        self.assertEqual(parts["folder_name"].get(), "photos")
        parts["session"].set("2026_27")
        parts["class_code"].set("I")
        parts["start_button"].invoke()
        root.update()
        shown = parts["summary"].get("1.0", "end")
        self.assertIn("ABC1001", shown)
        self.assertIn("नामांकन हो गया", shown)
        self.assertIn("पूरा", parts["status"].get())
        self.assertNotIn("permanent_key", shown)

        parts["screen"].open_file = lambda: str(pack / "02_valid_class_6" / "students.xlsx")
        parts["screen"].open_folder = lambda: str(pack / "02_valid_class_6" / "photos")
        parts["file_button"].invoke()
        parts["folder_button"].invoke()
        parts["class_code"].set("VI")
        parts["start_button"].invoke()
        root.update()
        shown = parts["summary"].get("1.0", "end")
        self.assertIn("ABC6015", shown)

        parts["screen"].open_file = lambda: str(pack / "03_duplicate_roll" / "students.xlsx")
        parts["screen"].open_folder = lambda: str(pack / "03_duplicate_roll" / "photos")
        parts["screen"].workspace = Path(tempfile.mkdtemp()) / "duplicate"
        parts["file_button"].invoke()
        parts["folder_button"].invoke()
        parts["class_code"].set("I")
        parts["start_button"].invoke()
        root.update()
        self.assertIn("रोल", parts["summary"].get("1.0", "end"))

        parts["screen"].open_file = lambda: str(pack / "04_missing_photo" / "students.xlsx")
        parts["screen"].open_folder = lambda: str(pack / "04_missing_photo" / "photos")
        parts["screen"].workspace = Path(tempfile.mkdtemp()) / "missing"
        parts["file_button"].invoke()
        parts["folder_button"].invoke()
        parts["class_code"].set("III")
        parts["start_button"].invoke()
        root.update()
        self.assertIn("फोटो", parts["summary"].get("1.0", "end"))

        parts["screen"].open_file = lambda: str(pack / "05_invalid_photo" / "students.xlsx")
        parts["screen"].open_folder = lambda: str(pack / "05_invalid_photo" / "photos")
        parts["screen"].workspace = Path(tempfile.mkdtemp()) / "invalid"
        parts["file_button"].invoke()
        parts["folder_button"].invoke()
        parts["class_code"].set("IV")
        parts["start_button"].invoke()
        root.update()
        self.assertIn("खुल नहीं", parts["summary"].get("1.0", "end"))
        self.assertNotIn("permanent_key", parts["summary"].get("1.0", "end"))
        parts["cancel_button"].invoke()
        root.update()
        self.assertIn("रद्द", parts["status"].get())
        root.destroy()


if __name__ == "__main__":
    unittest.main()
