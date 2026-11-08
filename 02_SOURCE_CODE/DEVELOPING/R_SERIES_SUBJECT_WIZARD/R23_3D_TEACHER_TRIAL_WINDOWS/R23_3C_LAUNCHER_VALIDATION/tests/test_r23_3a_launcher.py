# -*- coding: utf-8 -*-
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trial_window import CLASS_CODES, EnrollmentScreen


class R233ALauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / "photos"
        self.photos.mkdir()
        Image.new("RGB", (8, 8), "blue").save(self.photos / "good.jpg", "JPEG")
        (self.photos / "bad.jpg").write_bytes(b"not-a-real-photo")
        self.table = self.root / "students.xlsx"
        self._sheet(self.table, ["ABC", "2026_27", "I", 1, "TRIAL CHILD A", "TRIAL FATHER A", "good.jpg"])
        self.screen = EnrollmentScreen(
            workspace=self.root / "workspace",
            open_file=lambda: str(self.table),
            open_folder=lambda: str(self.photos),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_pickers_validation_cancel_privacy_and_double_start(self):
        source = (ROOT / "src" / "trial_window.py").read_text(encoding="utf-8")
        self.assertIn("filedialog.askopenfilename", source)
        self.assertIn("filedialog.askdirectory", source)
        self.assertEqual(self.screen.table, "")
        self.assertEqual(self.screen.photos, "")
        self.assertEqual(self.screen.choose_file(), "selected")
        self.assertEqual(Path(self.screen.table).name, "students.xlsx")
        self.assertEqual(self.screen.choose_folder(), "selected")
        self.assertEqual(Path(self.screen.photos).name, "photos")

        invalid = EnrollmentScreen(self.root / "workspace", open_file=lambda: str(self._text()), open_folder=lambda: "")
        self.assertEqual(invalid.choose_file(), "invalid")
        self.assertEqual(invalid.table, "")
        missing_file = EnrollmentScreen(self.root / "workspace", open_file=lambda: str(self.root / "missing.xlsx"), open_folder=lambda: "")
        self.assertEqual(missing_file.choose_file(), "missing")
        missing_folder = EnrollmentScreen(self.root / "workspace", open_file=lambda: "", open_folder=lambda: str(self.root / "missing-folder"))
        self.assertEqual(missing_folder.choose_folder(), "missing")
        blocked = EnrollmentScreen(
            self.root / "workspace",
            open_file=lambda: r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx",
            open_folder=lambda: "",
        )
        self.assertEqual(blocked.choose_file(), "blocked")
        self.assertEqual(blocked.table, "")

        self.assertEqual(self.screen.cancel(), "cancelled")
        self.assertFalse((self.root / "workspace" / "identity.sqlite").exists())
        self.assertEqual(self.screen.exit(), "exited")
        self.assertEqual(self.screen.start(), "exited")

        fresh = self._ready_screen()
        second = []
        original = fresh._progress

        def progress(index, total):
            original(index, total)
            second.append(fresh.start())

        fresh._progress = progress
        self.assertEqual(fresh.start(), "completed")
        self.assertEqual(second, ["already_running"])
        self.assertEqual(fresh.summary[0].split(" — ")[0], "ABC1001")
        self.assertIn("नामांकन हो गया", fresh.summary[0])
        secret = fresh_secret(fresh)
        self.assertNotIn(secret, "\n".join(fresh.summary))
        self.assertNotIn("permanent_key", "\n".join(fresh.summary))
        self.assertEqual(fresh.status, "पूरा / Completed")

    def test_duplicate_missing_invalid_and_pack(self):
        duplicate = self.root / "duplicate.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
        sheet.append(["ABC", "2026_27", "I", 1, "TRIAL CHILD A", "TRIAL FATHER A", "good.jpg"])
        sheet.append(["ABC", "2026_27", "I", 1, "TRIAL CHILD OTHER", "TRIAL FATHER OTHER", "good.jpg"])
        book.save(duplicate)
        book.close()
        screen = self._ready_screen(duplicate)
        self.assertEqual(screen.start(), "completed")
        self.assertIn("रोल", screen.summary[1])

        missing = self.root / "missing.xlsx"
        self._sheet(missing, ["ABC", "2026_27", "III", 3, "TRIAL CHILD D", "TRIAL FATHER D", "absent.jpg"])
        missing_screen = self._ready_screen(missing, "III")
        self.assertEqual(missing_screen.start(), "completed")
        self.assertIn("फोटो", missing_screen.summary[0])

        invalid = self.root / "invalid.xlsx"
        self._sheet(invalid, ["ABC", "2026_27", "IV", 4, "TRIAL CHILD E", "TRIAL FATHER E", "bad.jpg"])
        invalid_screen = self._ready_screen(invalid, "IV")
        self.assertEqual(invalid_screen.start(), "completed")
        self.assertIn("खुल नहीं", invalid_screen.summary[0])

        pack = ROOT / "R23_3A_TEACHER_TRIAL_PACK"
        self.assertTrue((pack / "README.txt").read_text(encoding="utf-8").find("artificial") >= 0)
        class_one = EnrollmentScreen(
            self.root / "pack-workspace",
            open_file=lambda: str(pack / "01_valid_class_1" / "students.xlsx"),
            open_folder=lambda: str(pack / "01_valid_class_1" / "photos"),
        )
        class_one.choose_file()
        class_one.choose_folder()
        class_one.session = "2026_27"
        class_one.selected_class = "I"
        self.assertEqual(class_one.start(), "completed")
        self.assertTrue(class_one.summary[0].startswith("ABC1001"))
        self.assertIn("I", CLASS_CODES)
        self.assertNotIn("NUR", CLASS_CODES)

    def test_previous_packages_were_not_overwritten(self):
        self.assertEqual(digest("/workspace/R23_2_DEVELOPMENT/src/identity_engine.py"), "E7D9B3626986E5AA287480BA9DE5F2BB5D0D9EFDBDF81EE9B9EAF633490910D2")
        self.assertEqual(digest("/workspace/R23_3_TEACHER_TRIAL/src/teacher_trial.py"), "25B2B894674C3F0F88B6DF2B1CF654F1C2E00C61954F45A7F8985A4969AE8EF1")
        self.assertEqual(digest("/workspace/R23_3A_TEACHER_PREPARATION/baseline/MAIN_ASSISTANT.py"), "D155AB4AA029415A45C01350B586303A19D280BB5C2CC8DD21D9E3257433FD5A")
        launcher = (ROOT / "src" / "trial_window.py").read_text(encoding="utf-8")
        self.assertNotIn("saini_db", launcher)
        self.assertNotIn("generate_front_card", launcher)
        self.assertNotIn("MAIN_ASSISTANT", launcher)

    def _ready_screen(self, table=None, selected_class="I"):
        screen = EnrollmentScreen(
            workspace=self.root / f"workspace-{selected_class}-{Path(table).stem if table else 'main'}",
            open_file=lambda: str(table or self.table),
            open_folder=lambda: str(self.photos),
        )
        screen.choose_file()
        screen.choose_folder()
        screen.session = "2026_27"
        screen.selected_class = selected_class
        return screen

    def _sheet(self, path, row):
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
        sheet.append(row)
        book.save(path)
        book.close()

    def _text(self):
        path = self.root / "notes.txt"
        path.write_text("not a table", encoding="utf-8")
        return path


def fresh_secret(screen):
    from identity_engine import IdentityEngine
    engine = IdentityEngine(Path(screen.workspace) / "identity.sqlite", Path(screen.workspace) / "PHOTO_LIBRARY")
    try:
        return engine._current_visible("ABC", "2026_27", "ABC1001")["permanent_key"]
    finally:
        engine.close()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


if __name__ == "__main__":
    unittest.main()
