# -*- coding: utf-8 -*-
import hashlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import active_writers
from active_writers import (
    ACTIVE_IDENTITY_WRITERS,
    _delete,
    _save_edit,
    _write_uids_to_school_google_sheet,
    step1_smart_rename,
    step3_copy_to_library,
    step4_update_photo_db,
    step6_data_merge,
    step7_sync_photos,
    step7b_update_photo_path,
    stepE_enroll_from_sheet,
    step_reassign_mixed,
    update_student_excel,
    write_by_name,
    write_enroll_to_local_xlsx,
    write_school_csv,
)
from identity_engine import IdentityEngine, IdentityError


def new_engine(root):
    return IdentityEngine(root / "synthetic.sqlite", root / "photos")


class R231IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = new_engine(self.root)
        self.face = self.root / "face.jpg"
        self.face.write_bytes(b"synthetic-face")

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_active_enrollment_paths_use_the_engine_and_hide_the_key(self):
        enrolled = stepE_enroll_from_sheet(
            self.engine, "ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal"
        )
        self.assertEqual(enrolled["visible_id"], "ABC1001")
        self.assertNotIn("permanent_key", enrolled)
        linked = step4_update_photo_db(self.engine, "ABC", "2026_27", "ABC1001", self.face)
        self.assertTrue(linked["photo_path"].endswith("ABC1001.jpg"))
        confirmed = step7b_update_photo_path(self.engine, "ABC", "2026_27", "ABC1001", linked["photo_path"])
        self.assertEqual(confirmed["photo_path"], linked["photo_path"])
        renamed = step1_smart_rename(
            self.engine, "ABC", "2026_27", "II", 2, "Geeta", "Ramesh", self.face
        )
        self.assertEqual(renamed["visible_id"], "ABC2002")
        self.assertNotIn("permanent_key", renamed)
        pending = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "III", 3, "Third Child", "Third Father")
        copied = step3_copy_to_library(self.engine, "ABC", "2026_27", pending["visible_id"], self.face)
        self.assertIn("2026_27", copied["photo_path"])
        another = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "IV", 4, "Fourth Child", "Fourth Father")
        synced = step7_sync_photos(self.engine, "ABC", "2026_27", another["visible_id"], self.face)
        self.assertIn(another["visible_id"], synced["photo_path"])
        merged = step6_data_merge(self.engine, "ABC", "2026_27", "ABC1001", student_name="Ram Kumar.")
        self.assertEqual(merged["student_name"], "Ram Kumar.")
        self.assertNotIn("permanent_key", merged)
        local_row = write_enroll_to_local_xlsx(self.engine, "ABC", "2026_27", "ABC1001")
        sheet = _write_uids_to_school_google_sheet(self.engine, "ABC", "2026_27", "ABC1001")
        self.assertEqual(local_row["student_unique_id"], "ABC1001")
        self.assertEqual(sheet["network"], "not_used")
        self.assertNotIn("permanent_key", local_row)
        self.assertNotIn("permanent_key", sheet)
        corrected = update_student_excel(self.engine, "ABC", "2026_27", "ABC2002", father_name="Ramesh Lal")
        self.assertEqual(corrected["father_name"], "Ramesh Lal")
        destination = self.root / "teacher.csv"
        write_school_csv(self.engine, "ABC", "2026_27", destination)
        text = destination.read_text(encoding="utf-8")
        self.assertNotIn("permanent_key", text)
        self.assertNotIn(self._secret("ABC1001"), text)

    def test_legacy_allocator_is_not_used_by_active_paths(self):
        source = (SRC / "active_writers.py").read_text(encoding="utf-8")
        engine_source = (SRC / "identity_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("next_official_uid(", source)
        self.assertNotIn("next_official_uid(", engine_source)
        for name in ACTIVE_IDENTITY_WRITERS:
            self.assertIn(f"def {name}", source)
        before = self.engine.count_identities()
        sheet = {}
        write_by_name(sheet, 2, {"student_unique_id": 1}, {"student_unique_id": "ABC9999"})
        self.assertEqual(sheet[2][1], "ABC9999")
        self.assertEqual(self.engine.count_identities(), before)
        with self.assertRaises(IdentityError) as caught:
            step4_update_photo_db(self.engine, "ABC", "2026_27", "ABC9999", self.face)
        self.assertEqual(caught.exception.code, "identity_not_found")
        self.assertEqual(self.engine.count_identities(), before)

    def test_reassignment_preserves_key_and_existing_photo(self):
        enrolled = stepE_enroll_from_sheet(
            self.engine, "ABC", "2026_27", "I", 1, "Ram Kumar", "Mohan Lal", self.face
        )
        secret = self._secret(enrolled["visible_id"])
        photo = Path(enrolled["photo_path"])
        original = photo.read_bytes()
        promoted = step_reassign_mixed(self.engine, "ABC", "2026_27", "ABC1001", "VI", 15)
        self.assertEqual(promoted["visible_id"], "ABC6015")
        self.assertNotIn("permanent_key", promoted)
        self.assertEqual(self._secret("ABC6015"), secret)
        self.assertEqual(photo.read_bytes(), original)
        changed = step_reassign_mixed(self.engine, "ABC", "2026_27", "ABC6015", "VI", 16)
        self.assertEqual(changed["visible_id"], "ABC6016")
        self.assertEqual(self._secret("ABC6016"), secret)
        self.assertEqual(photo.read_bytes(), original)

    def test_exact_match_duplicates_and_pending_limits(self):
        stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "III", 1, "Ram Kumar", "Mohan Lal")
        other = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "III", 2, "RAM KUMAR", "Mohan Lal")
        spaced = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "III", 3, "Ram  Kumar", "Mohan Lal")
        dotted = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "IV", 1, "A.B. Sharma", "Suresh")
        plain = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "IV", 2, "AB Sharma", "Suresh")
        secrets = {self._secret(item["visible_id"]) for item in (other, spaced, dotted, plain)}
        secrets.add(self._secret("ABC3001"))
        self.assertEqual(len(secrets), 5)
        before = self.engine.count_identities()
        with self.assertRaises(IdentityError) as caught:
            stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "III", 1, "Other Child", "Other Father")
        self.assertEqual(caught.exception.code, "duplicate_identity")
        for klass in ("NUR", "LKG", "UKG"):
            with self.assertRaises(IdentityError) as caught:
                step1_smart_rename(self.engine, "ABC", "2026_27", klass, 1, "Small Child", "Father", self.face)
            self.assertEqual(caught.exception.code, "roll_limit_pending_user_approval")
        self.assertEqual(self.engine.count_identities(), before)

    def test_teacher_outputs_and_errors_do_not_contain_the_key(self):
        enrolled = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "V", 5, "Card Child", "Card Father", self.face)
        secret = self._secret(enrolled["visible_id"])
        self.assertTrue(secret)
        destination = self.root / "rows.csv"
        write_school_csv(self.engine, "ABC", "2026_27", destination)
        visible_history = [self.engine.teacher_view(item) for item in self.engine.history("ABC", "2026_27", "ABC5005")]
        log_line = "enrolled " + enrolled["visible_id"]
        blob = "\n".join([
            str(enrolled),
            destination.read_text(encoding="utf-8"),
            str(visible_history),
            str(self.engine.generator_row("ABC", "2026_27", "ABC5005")),
            log_line,
            "duplicate_identity",
        ])
        self.assertNotIn(secret, blob)
        self.assertNotIn("permanent_key", blob)
        with self.assertRaises(IdentityError) as caught:
            _save_edit(self.engine, "ABC", "2026_27", "ABC5005", new_class="VI")
        self.assertNotIn(secret, caught.exception.code)
        with self.assertRaises(IdentityError) as caught:
            _delete(self.engine, "ABC", "ABC5005")
        self.assertEqual(caught.exception.code, "delete_not_exposed")
        self.assertEqual(self.engine.count_identities(), 1)

    def test_photo_failure_recovery_never_overwrites(self):
        enrolled = stepE_enroll_from_sheet(self.engine, "ABC", "2026_27", "VII", 1, "Photo Child", "Photo Father")
        target = self.engine.photo_path("ABC", "2026_27", enrolled["visible_id"])
        self.engine.photo_fail = "stage"
        with self.assertRaises(IdentityError) as caught:
            self.engine.assign_photo("ABC", "2026_27", enrolled["visible_id"], self.face)
        self.assertEqual(caught.exception.code, "photo_stage_failed")
        self.assertFalse(target.exists())
        self.engine.photo_fail = "finalize"
        with self.assertRaises(IdentityError) as caught:
            self.engine.assign_photo("ABC", "2026_27", enrolled["visible_id"], self.face)
        self.assertEqual(caught.exception.code, "photo_finalize_failed")
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + ".staging").exists())
        self.engine.photo_fail = "database"
        with self.assertRaises(IdentityError) as caught:
            self.engine.assign_photo("ABC", "2026_27", enrolled["visible_id"], self.face)
        self.assertEqual(caught.exception.code, "photo_database_failed")
        self.assertEqual(target.read_bytes(), b"synthetic-face")
        self.assertEqual(self.engine.generator_row("ABC", "2026_27", enrolled["visible_id"])["STUDENT_PHOTO_PATH"], "")
        self.engine.photo_fail = None
        different = self.root / "other.jpg"
        different.write_bytes(b"other-face")
        with self.assertRaises(IdentityError) as caught:
            self.engine.assign_photo("ABC", "2026_27", enrolled["visible_id"], different)
        self.assertEqual(caught.exception.code, "photo_exists")
        self.assertEqual(target.read_bytes(), b"synthetic-face")
        recovered = self.engine.assign_photo("ABC", "2026_27", enrolled["visible_id"], self.face)
        self.assertEqual(Path(recovered["photo_path"]).read_bytes(), b"synthetic-face")
        self.assertEqual(self.engine.generator_row("ABC", "2026_27", enrolled["visible_id"])["STUDENT_PHOTO_PATH"], str(target))

    def test_generator_reads_recorded_path_and_r22_file_stays_unchanged(self):
        enrolled = stepE_enroll_from_sheet(
            self.engine, "XYZ", "2026_27", "X", 1, "Card Child", "Card Father", self.face
        )
        row = self.engine.generator_row("XYZ", "2026_27", enrolled["visible_id"])
        generator = (ROOT / "baseline" / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        self.assertIn("STUDENT_PHOTO_PATH", generator)
        self.assertEqual(row["student_unique_id"], "XYZX001")
        self.assertTrue(Path(row["STUDENT_PHOTO_PATH"]).is_file())
        workbook = self.root / "r22_headers.txt"
        workbook.write_text("FATHER_X,FATHER_X,BSM\n", encoding="utf-8")
        digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
        stepE_enroll_from_sheet(self.engine, "XYZ", "2026_27", "XI", 2, "Another Child", "Another Father")
        self.assertEqual(hashlib.sha256(workbook.read_bytes()).hexdigest(), digest)
        self.assertEqual(
            hashlib.sha256((ROOT / "baseline" / "SAINI_ID_CARD.py").read_bytes()).hexdigest().upper(),
            "EA1E637CD5FABF2E122BD84FCF275908D41B5A2929908D823A3C518FED95D187",
        )

    def test_concurrent_active_enrollment_has_one_identity(self):
        barrier = threading.Barrier(2)
        results = []

        def attempt(student_name):
            local = new_engine(self.root)
            try:
                barrier.wait()
                stepE_enroll_from_sheet(local, "ABC", "2026_27", "VIII", 9, student_name, "Father")
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

    def _secret(self, visible_student_id):
        row = self.engine._current_visible("ABC" if visible_student_id.startswith("ABC") else "XYZ", "2026_27", visible_student_id)
        return row["permanent_key"]


if __name__ == "__main__":
    unittest.main()
