# -*- coding: utf-8 -*-
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from development_launcher import DevelopmentLauncher
from identity_engine import IdentityError
from legacy_guard import LegacyEntryBlocked


class R232EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / "incoming"
        self.photos.mkdir()
        Image.new("RGB", (12, 8), "blue").save(self.photos / "face.jpg", "JPEG")
        self.launcher = DevelopmentLauncher(self.root / "workspace")

    def tearDown(self):
        self.launcher.close()
        self.temp.cleanup()

    def test_excel_and_csv_enrollment_reaches_generator_input(self):
        workbook = self.root / "students.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file", "mob_number", "address", "legacy_uid"])
        sheet.append(["ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal", "face.jpg", "9999999999", "Synthetic Lane", "ABC9999"])
        sheet.append(["ABC", "2026_27", "I", 1, "Other Child", "Other Father", "face.jpg", "", "", "ABC1000"])
        sheet.append(["ABC", "2026_27", "NUR", 1, "Small Child", "Small Father", "face.jpg", "", "", ""])
        sheet.append(["ABC", "2026_27", "II", 2, "Missing Photo", "Missing Father", "missing.jpg", "", "", ""])
        sheet.append(["ABC", "2026_27", "VI", 15, "Geeta", "Ramesh", "face.jpg", "", "", ""])
        book.save(workbook)
        book.close()

        results = self.launcher.enroll_table(workbook, self.photos)
        self.assertEqual([item["ok"] for item in results], [True, False, False, False, True])
        self.assertEqual(results[0]["visible_id"], "ABC1001")
        self.assertNotEqual(results[0]["visible_id"], "ABC9999")
        self.assertEqual(results[1]["code"], "duplicate_identity")
        self.assertIn("रोल", results[1]["message"])
        self.assertEqual(results[2]["code"], "roll_limit_pending_user_approval")
        self.assertEqual(results[3]["code"], "photo_source_missing")
        self.assertEqual(results[4]["visible_id"], "ABC6015")
        self.assertEqual(self.launcher.engine.count_identities(), 2)

        photo = Path(results[0]["photo_path"])
        self.assertTrue(photo.is_file())
        self.assertIn("2026_27", str(photo))
        self.assertTrue(str(photo).endswith("ABC1001.jpg"))
        self.assertEqual(results[0]["generator_consumed"]["student_unique_id"], "ABC1001")
        self.assertEqual(results[0]["generator_consumed"]["photo_size"], (12, 8))
        self.assertEqual(results[0]["generator_input"]["mob_number"], "9999999999")

        promoted = self.launcher.promote("ABC", "2026_27", "ABC1001", "II", 4)
        self.assertTrue(promoted["ok"])
        self.assertEqual(promoted["visible_id"], "ABC2004")
        self.assertEqual(promoted["history"], ["ABC1001", "ABC2004"])
        secret = self.launcher.engine._current_visible("ABC", "2026_27", "ABC2004")["permanent_key"]
        first_key = self.launcher.engine.history("ABC", "2026_27", "ABC1001")[0]["permanent_key"]
        self.assertEqual(secret, first_key)
        blob = json.dumps(results + [promoted], ensure_ascii=False)
        self.assertNotIn(secret, blob)
        self.assertNotIn("permanent_key", blob)

        csv_path = self.root / "more.csv"
        csv_path.write_text(
            "school_code,session,class,roll_number,student_name,father_name,photo_file\n"
            "XYZ,2026_27,X,1,Card Child,Card Father,face.jpg\n",
            encoding="utf-8",
        )
        csv_result = self.launcher.enroll_table(csv_path, self.photos)[0]
        self.assertEqual(csv_result["visible_id"], "XYZX001")
        self.assertTrue(Path(csv_result["photo_path"]).is_file())

    def test_legacy_baseline_is_blocked_and_direct_call_stays_outside(self):
        before = self.launcher.engine.count_identities()
        with self.assertRaises(LegacyEntryBlocked):
            self.launcher.run_legacy_baseline(ROOT / "baseline" / "MAIN_ASSISTANT.py")
        self.assertEqual(self.launcher.engine.count_identities(), before)
        launcher_source = (ROOT / "src" / "development_launcher.py").read_text(encoding="utf-8")
        self.assertNotIn("saini_db", launcher_source)
        self.assertNotIn("MAIN_ASSISTANT", launcher_source)
        legacy_id = isolated_legacy_uid(self.root / "legacy_scan")
        self.assertEqual(legacy_id, "ABC1000")
        self.assertNotEqual(legacy_id, "ABC1001")

    def test_failed_row_does_not_leave_a_photo_or_database_row(self):
        before = self.launcher.engine.count_identities()
        csv_path = self.root / "bad.csv"
        csv_path.write_text(
            "school_code,session,class,roll_number,student_name,father_name,photo_file\n"
            "ABC,2026_27,UKG,4,Tiny Child,Tiny Father,face.jpg\n",
            encoding="utf-8",
        )
        result = self.launcher.enroll_table(csv_path, self.photos)[0]
        self.assertFalse(result["ok"])
        self.assertEqual(self.launcher.engine.count_identities(), before)
        self.assertFalse((self.launcher.workspace / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC30004.jpg").exists())


def isolated_legacy_uid(folder):
    """Execute only the preserved old allocator against an empty temporary folder."""
    source = (ROOT / "baseline" / "MAIN_ASSISTANT.py").read_text(encoding="utf-8")
    start = source.index("def next_official_uid")
    end = source.index("\ndef normalize_class_name")
    namespace = {
        "PHOTO_LIBRARY": folder / "lib",
        "RENAME_OUTPUT": folder / "rename",
        "PIPELINE_OUTPUT": folder / "pipe",
        "GOOGLE_DRIVE_PHOTOS": folder / "drive",
        "CLASS_RANGES": {"I": ("I", 1000, 1999), "MIX": ("MIX", 50000, 59999)},
        "extract_class_number": lambda _stem, _school, _cls: None,
        "logger": type("Logger", (), {"warning": staticmethod(lambda *_args, **_kwargs: None)})(),
    }
    exec(source[start:end], namespace)
    return namespace["next_official_uid"]("ABC", "I", set())


if __name__ == "__main__":
    unittest.main()
