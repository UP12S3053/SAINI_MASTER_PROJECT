# -*- coding: utf-8 -*-
import hashlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
BASELINE = Path(__file__).resolve().parents[1] / "baseline"
sys.path.insert(0, str(SRC))

from controlled_writers import WRITER_CONTROL, legacy_next_official_uid
from controlled_writers import IdentityBypassError, enroll
from generator_contract import baseline_generator_text, generator_reads_prepared_fields
from identity_engine import IdentityEngine, IdentityError, visible_id


def engine_in(root):
    return IdentityEngine(root / "synthetic.sqlite", root / "photos")


class R23EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = engine_in(self.root)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_formula_for_every_approved_class(self):
        expected = {
            ("NUR", 1): "ABC10001",
            ("LKG", 1): "ABC20001",
            ("UKG", 1): "ABC30001",
            ("I", 1): "ABC1001",
            ("1", 1): "ABC1001",
            ("II", 1): "ABC2001",
            ("III", 1): "ABC3001",
            ("IV", 1): "ABC4001",
            ("V", 1): "ABC5001",
            ("VI", 15): "ABC6015",
            ("VII", 1): "ABC7001",
            ("VIII", 1): "ABC8001",
            ("IX", 1): "ABC9001",
            ("X", 1): "ABCX001",
            ("XI", 1): "ABCXI001",
            ("XII", 1): "ABCXII001",
        }
        for (klass, roll), identifier in expected.items():
            self.assertEqual(visible_id("ABC", klass, roll), identifier)

    def test_numeric_and_roman_issue_and_pending_primary_classes(self):
        created = self.engine.create_student("ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal")
        self.assertEqual(created["visible_id"], "ABC1001")
        sixth = self.engine.create_student("ABC", "2026_27", "VI", 15, "Geeta", "Ramesh")
        self.assertEqual(sixth["visible_id"], "ABC6015")
        tenth = self.engine.create_student("ABC", "2026_27", "X", 1, "A.B. Sharma", "Suresh")
        self.assertEqual(tenth["visible_id"], "ABCX001")
        eleventh = self.engine.create_student("ABC", "2026_27", "XI", 1, "AB Sharma", "Suresh")
        self.assertEqual(eleventh["visible_id"], "ABCXI001")
        self.assertNotEqual(tenth["permanent_key"], eleventh["permanent_key"])
        twelfth = self.engine.create_student("ABC", "2026_27", "XII", 1, "Meena", "Ravi")
        self.assertEqual(twelfth["visible_id"], "ABCXII001")
        before = self.engine.count_identities()
        for klass in ("NUR", "LKG", "UKG"):
            with self.assertRaises(IdentityError) as caught:
                self.engine.create_student("ABC", "2026_27", klass, 1, "New Child", "New Father")
            self.assertEqual(caught.exception.code, "roll_limit_pending_user_approval")
        self.assertEqual(self.engine.count_identities(), before)

    def test_duplicate_roll_and_visible_id_write_nothing(self):
        self.engine.create_student("ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal")
        before = self.engine.count_identities()
        with self.assertRaises(IdentityError) as caught:
            self.engine.create_student("ABC", "2026_27", "I", 1, "Other Child", "Other Father")
        self.assertEqual(caught.exception.code, "duplicate_identity")
        self.assertEqual(self.engine.count_identities(), before)

    def test_roll_change_and_promotion_keep_key_and_history(self):
        created = self.engine.create_student("ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal")
        promoted = self.engine.promote("ABC", created["permanent_key"], "2026_27", "VI", 1)
        changed = self.engine.change_roll("ABC", created["permanent_key"], "2026_27", 15)
        self.assertEqual(promoted["visible_id"], "ABC6001")
        self.assertEqual(changed["visible_id"], "ABC6015")
        self.assertEqual(changed["permanent_key"], created["permanent_key"])
        old = [item["visible_id"] for item in self.engine.history("ABC", "2026_27", "ABC6015")]
        self.assertEqual(old, ["ABC1001", "ABC6001", "ABC6015"])
        self.assertTrue(all(item["permanent_key"] == created["permanent_key"] for item in self.engine.history("ABC", "2026_27", "ABC6015")))

    def test_same_session_reentry_and_session_gap(self):
        created = self.engine.create_student("ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal")
        again = self.engine.reenter("ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal")
        self.assertEqual(again["permanent_key"], created["permanent_key"])
        self.assertEqual(self.engine.count_identities(), 1)
        consecutive = self.engine.reenter("ABC", "2027_28", "I", 4, "Ram Kumar", "Mohan Lal")
        self.assertEqual(consecutive["permanent_key"], created["permanent_key"])
        self.assertEqual(consecutive["visible_id"], "ABC1004")
        returned = self.engine.reenter("ABC", "2029_30", "I", 2, "Ram Kumar", "Mohan Lal")
        self.assertNotEqual(returned["permanent_key"], created["permanent_key"])
        self.assertFalse(returned["previous_key_linked"])
        self.assertEqual(returned["visible_id"], "ABC1002")

    def test_exact_spelling_does_not_merge(self):
        first = self.engine.create_student("ABC", "2026_27", "II", 1, "Ram Kumar", "Mohan Lal")
        pairs = [
            ("Ramkumar", "Mohan Lal", 2),
            ("RAM KUMAR", "Mohan Lal", 3),
            ("Ram  Kumar", "Mohan Lal", 4),
            ("A.B. Sharma", "Suresh", 5),
        ]
        keys = {first["permanent_key"]}
        for name, father, roll in pairs:
            created = self.engine.create_student("ABC", "2026_27", "II", roll, name, father)
            keys.add(created["permanent_key"])
        separate = self.engine.create_student("ABC", "2026_27", "III", 1, "AB Sharma", "Suresh")
        keys.add(separate["permanent_key"])
        self.assertEqual(len(keys), 6)

    def test_explicit_correction_keeps_key(self):
        created = self.engine.create_student("ABC", "2026_27", "IV", 8, "Ram Kumar", "Mohan Lal")
        corrected = self.engine.correct_name(
            "ABC", created["permanent_key"], "2026_27", student_name="Ram Kumar."
        )
        self.assertEqual(corrected["permanent_key"], created["permanent_key"])
        self.assertEqual(corrected["visible_id"], "ABC4008")
        self.assertEqual(corrected["student_name"], "Ram Kumar.")

    def test_photo_collision_and_existing_file_are_preserved(self):
        created = self.engine.create_student("ABC", "2026_27", "V", 3, "Photo Child", "Photo Father")
        source = self.root / "synthetic.jpg"
        source.write_bytes(b"synthetic-face")
        saved = self.engine.assign_photo("ABC", "2026_27", created["visible_id"], source)
        target = Path(saved["photo_path"])
        self.assertEqual(target, self.engine.photo_path("ABC", "2026_27", "ABC5003"))
        self.assertEqual(target.read_bytes(), b"synthetic-face")
        source.write_bytes(b"different-face")
        with self.assertRaises(IdentityError):
            self.engine.assign_photo("ABC", "2026_27", created["visible_id"], source)
        self.assertEqual(target.read_bytes(), b"synthetic-face")
        other = self.engine.create_student("ABC", "2026_27", "V", 4, "Second Child", "Second Father")
        occupied = self.engine.photo_path("ABC", "2026_27", other["visible_id"])
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_bytes(b"already-there")
        with self.assertRaises(IdentityError) as caught:
            self.engine.assign_photo("ABC", "2026_27", other["visible_id"], source)
        self.assertEqual(caught.exception.code, "photo_exists")
        self.assertEqual(occupied.read_bytes(), b"already-there")

    def test_same_visible_id_in_another_session_has_a_separate_photo(self):
        first = self.engine.create_student("ABC", "2024_25", "I", 1, "Old Student", "Old Father")
        second = self.engine.create_student("ABC", "2026_27", "I", 1, "New Student", "New Father")
        self.assertEqual(first["visible_id"], second["visible_id"])
        self.assertNotEqual(first["permanent_key"], second["permanent_key"])
        source = self.root / "face.jpg"
        source.write_bytes(b"new-face")
        saved = self.engine.assign_photo("ABC", "2026_27", second["visible_id"], source)
        self.assertIn("2026_27", saved["photo_path"])
        self.assertFalse(self.engine.photo_path("ABC", "2024_25", "ABC1001").exists())

    def test_invalid_roll_does_not_truncate_or_write(self):
        before = self.engine.count_identities()
        for klass, roll in (("I", 0), ("I", 1000), ("I", 1001), ("X", 1000), ("XI", 1000)):
            with self.assertRaises(IdentityError) as caught:
                self.engine.create_student("ABC", "2026_27", klass, roll, "Bad Roll", "Bad Father")
            self.assertEqual(caught.exception.code, "roll_out_of_range")
        with self.assertRaises(IdentityError):
            visible_id("ABC", "X", 1000)
        self.assertEqual(self.engine.count_identities(), before)

    def test_concurrent_duplicate_enrollment(self):
        barrier = threading.Barrier(2)
        results = []

        def attempt(student_name):
            local = engine_in(self.root)
            try:
                barrier.wait()
                enroll(local, "ABC", "2026_27", "VIII", 9, student_name, "Father")
                results.append("created")
            except IdentityError as exc:
                results.append(exc.code)
            finally:
                local.close()

        first = threading.Thread(target=attempt, args=("Concurrent One",))
        second = threading.Thread(target=attempt, args=("Concurrent Two",))
        first.start()
        second.start()
        first.join()
        second.join()
        self.assertEqual(sorted(results), ["created", "duplicate_identity"])
        self.assertEqual(self.engine.count_identities(), 1)

    def test_legacy_allocator_and_live_paths_are_blocked(self):
        with self.assertRaises(IdentityBypassError):
            legacy_next_official_uid("ABC", "I", set())
        with self.assertRaises(IdentityError) as caught:
            IdentityEngine(r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx", self.root / "photos")
        self.assertEqual(caught.exception.code, "live_path_refused")
        with self.assertRaises(IdentityError) as caught:
            self.engine.create_student("BSM", "2026_27", "I", 1, "Live School", "Father")
        self.assertEqual(caught.exception.code, "live_school_refused")

    def test_writer_inventory_matches_baseline_and_engine_has_no_r22_fields(self):
        baseline = "\n".join(path.read_text(encoding="utf-8") for path in BASELINE.glob("*.py"))
        for name in WRITER_CONTROL:
            self.assertIn(f"def {name}", baseline)
        engine_source = (SRC / "identity_engine.py").read_text(encoding="utf-8")
        controlled = (SRC / "controlled_writers.py").read_text(encoding="utf-8")
        self.assertNotIn("next_official_uid", engine_source)
        self.assertNotIn("normalize_key", engine_source + controlled)
        self.assertNotIn("clean_for_display", engine_source + controlled)
        for header in ("FATHER_X", "ADDR_COLOR", "FATHER_PREFIX"):
            self.assertNotIn(header, engine_source + controlled)
        workbook = self.root / "duplicate_headers.txt"
        workbook.write_text("FATHER_X,FATHER_X,M,M\n", encoding="utf-8")
        digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
        self.engine.create_student("XYZ", "2026_27", "IX", 2, "Synthetic", "Father")
        self.assertEqual(hashlib.sha256(workbook.read_bytes()).hexdigest(), digest)

    def test_generator_contract_and_baseline_hash(self):
        text = baseline_generator_text()
        self.assertTrue(generator_reads_prepared_fields(text))
        self.assertEqual(
            hashlib.sha256((BASELINE / "SAINI_ID_CARD.py").read_bytes()).hexdigest().upper(),
            "EA1E637CD5FABF2E122BD84FCF275908D41B5A2929908D823A3C518FED95D187",
        )
        created = self.engine.create_student("XYZ", "2026_27", "I", 7, "Card Child", "Card Father")
        source = self.root / "card-face.jpg"
        source.write_bytes(b"card-face")
        self.engine.assign_photo("XYZ", "2026_27", created["visible_id"], source)
        row = self.engine.generator_row("XYZ", "2026_27", "XYZ1007")
        self.assertEqual(row["student_unique_id"], "XYZ1007")
        self.assertTrue(row["STUDENT_PHOTO_PATH"].endswith("XYZ1007.jpg"))
        self.assertNotIn("permanent_key", row)


if __name__ == "__main__":
    unittest.main()
