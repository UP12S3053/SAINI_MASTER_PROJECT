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

from legacy_guard import LegacyEntryBlocked
from teacher_trial import TeacherTrial


class R233TeacherTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / "photos"
        self.photos.mkdir()
        Image.new("RGB", (10, 10), "green").save(self.photos / "good.jpg", "JPEG")
        (self.photos / "bad.jpg").write_bytes(b"this-is-not-a-photo")
        self.table = self.root / "students.xlsx"
        self._write_table(self.table)
        self.trial = TeacherTrial(self.root / "workspace")

    def tearDown(self):
        self.trial.close()
        self.temp.cleanup()

    def test_required_trial_scenarios(self):
        first = self.trial.start(self.table, self.photos, "1", "2026_27")
        enrolled = [item for item in first if item.get("visible_id")]
        self.assertEqual(enrolled[0]["visible_id"], "ABC1001")
        self.assertEqual(enrolled[0]["message"], "नामांकन हो गया।")
        self.assertIn("2026_27", enrolled[0]["photo_path"])
        self.assertTrue(enrolled[0]["photo_path"].endswith("ABC1001.jpg"))
        skipped = [item for item in first if item.get("skipped")]
        self.assertTrue(skipped)
        sixth = [item for item in self.trial.start(self.table, self.photos, "VI", "2026_27") if item.get("visible_id")]
        self.assertEqual(sixth[0]["visible_id"], "ABC6015")

        before_retry = self.trial.engine.count_identities()
        original = Path(enrolled[0]["photo_path"]).read_bytes()
        retry = [item for item in self.trial.start(self.table, self.photos, "1", "2026_27") if item.get("visible_id")]
        self.assertEqual(retry[0]["message"], "यह छात्र पहले से दर्ज है। नया रिकॉर्ड नहीं बना।")
        self.assertEqual(self.trial.engine.count_identities(), before_retry)
        self.assertEqual(Path(enrolled[0]["photo_path"]).read_bytes(), original)

        duplicate = self.trial.start(self.root / "duplicate.xlsx", self.photos, "I", "2026_27")
        self.assertFalse(duplicate[0]["ok"])
        self.assertIn("रोल", duplicate[0]["message"])
        self.assertIn("आईडी", duplicate[0]["message"])

        pending = self.trial.start(self.table, self.photos, "NUR", "2026_27")
        self.assertEqual(pending[0]["code"], "roll_limit_pending_user_approval")
        self.assertIn("बंद", pending[0]["message"])

        missing = self.trial.start(self.root / "missing.xlsx", self.photos, "III", "2026_27")
        self.assertEqual(missing[0]["code"], "photo_source_missing")
        self.assertFalse((self.trial.workspace / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC3003.jpg").exists())

        invalid = self.trial.start(self.root / "invalid.xlsx", self.photos, "IV", "2026_27")
        self.assertEqual(invalid[0]["code"], "photo_invalid")
        self.assertEqual(self._count_for("ABC4001"), 0)

        promoted = self.trial.promote("ABC", "2026_27", "ABC1001", "II", 4)
        changed = self.trial.change_roll("ABC", "2026_27", promoted["visible_id"], 5)
        self.assertEqual(promoted["visible_id"], "ABC2004")
        self.assertEqual(changed["visible_id"], "ABC2005")
        self.assertEqual(changed["history"], ["ABC1001", "ABC2004", "ABC2005"])
        secret = self.trial.engine._current_visible("ABC", "2026_27", "ABC2005")["permanent_key"]
        self.assertEqual(self.trial.engine.history("ABC", "2026_27", "ABC1001")[0]["permanent_key"], secret)

        spelling = self.trial.start(self.root / "spelling.xlsx", self.photos, "V", "2026_27")
        keys = {
            self.trial.engine._current_visible("ABC", "2026_27", item["visible_id"])["permanent_key"]
            for item in spelling
            if item.get("visible_id")
        }
        self.assertEqual(len(keys), 2)

        occupied = self.trial.engine.photo_path("ABC", "2026_27", "ABC7001")
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_bytes(b"keep-this-photo")
        blocked = self.trial.start(self.root / "occupied.xlsx", self.photos, "VII", "2026_27")
        self.assertEqual(blocked[0]["code"], "photo_exists")
        self.assertEqual(occupied.read_bytes(), b"keep-this-photo")
        self.assertEqual(self._count_for("ABC7001"), 0)

        shown = json.dumps(first + sixth + [promoted, changed] + spelling, ensure_ascii=False)
        self.assertNotIn(secret, shown)
        self.assertNotIn("permanent_key", shown)

        with self.assertRaises(LegacyEntryBlocked):
            self.trial.start(self.table, self.photos, "I", "2026_27", entry=ROOT / "baseline" / "MAIN_ASSISTANT.py")

    def _count_for(self, visible_student_id):
        return self.trial.engine._conn.execute(
            "SELECT COUNT(*) FROM identities WHERE visible_id=?",
            (visible_student_id,),
        ).fetchone()[0]

    def _write_table(self, path):
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
        sheet.append(["ABC", "2026_27", "I", 1, "TRIAL CHILD A", "TRIAL FATHER A", "good.jpg"])
        sheet.append(["ABC", "2026_27", "VI", 15, "TRIAL CHILD B", "TRIAL FATHER B", "good.jpg"])
        book.save(path)
        book.close()
        self._sheet(self.root / "duplicate.xlsx", ["ABC", "2026_27", "I", 1, "TRIAL CHILD C", "TRIAL FATHER C", "good.jpg"])
        self._sheet(self.root / "missing.xlsx", ["ABC", "2026_27", "III", 3, "TRIAL CHILD D", "TRIAL FATHER D", "missing.jpg"])
        self._sheet(self.root / "invalid.xlsx", ["ABC", "2026_27", "IV", 4, "TRIAL CHILD E", "TRIAL FATHER E", "bad.jpg"])
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
        sheet.append(["ABC", "2026_27", "V", 1, "Ram Kumar", "TRIAL FATHER F", "good.jpg"])
        sheet.append(["ABC", "2026_27", "V", 2, "RAM KUMAR", "TRIAL FATHER F", "good.jpg"])
        book.save(self.root / "spelling.xlsx")
        book.close()
        self._sheet(self.root / "occupied.xlsx", ["ABC", "2026_27", "VII", 1, "TRIAL CHILD G", "TRIAL FATHER G", "good.jpg"])

    def _sheet(self, path, row):
        book = Workbook()
        sheet = book.active
        sheet.append(["school_code", "session", "class", "roll_number", "student_name", "father_name", "photo_file"])
        sheet.append(row)
        book.save(path)
        book.close()


if __name__ == "__main__":
    unittest.main()
