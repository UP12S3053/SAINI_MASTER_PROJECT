# -*- coding: utf-8 -*-
"""Read-only Task 000-I-R4 compatibility checks. No workbook save. No generation."""
import ast
import hashlib
import inspect
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path("/workspace/SAINI_ID_DEV_000I_R4")
LIVE = ROOT / "live_root"
V5 = ROOT / "reference_v5_release"
GUARDED = ROOT / "reference_guarded"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def public_signatures(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            kw = [a.arg for a in node.args.kwonlyargs]
            found[node.name] = (tuple(args), tuple(kw))
    return found


class CompatibilityTests(unittest.TestCase):
    def test_recorded_hashes_unchanged(self):
        recorded = {}
        for line in (ROOT / "SHA256.txt").read_text(encoding="utf-8").splitlines():
            digest, _size, rel = line.split()
            recorded[rel] = digest
        self.assertEqual(sha(LIVE / "option_c_modules/journal.py"), "5A908C6BED369B597FC92D64BE27CF0444C0076B33A839D8D5E77523E43BF361")
        self.assertEqual(sha(V5 / "journal.py"), recorded["reference_v5_release/journal.py"])
        self.assertEqual(sha(LIVE / "school_config_front.xlsx"), "466E0EE1BF63698DC300A50BF07451F53889A1EE7B37A2C6E460D9551FC772F0")
        self.assertEqual(sha(LIVE / "ID_CARD_PROJECT/templates/IDCARD/BSM.png"), "FE644757E1F23AAAB47C46AE2880F8DFD4CCDE63B645C50B6C10B7C855151B73")

    def test_v5_journal_and_gate_match_live(self):
        self.assertEqual((LIVE / "option_c_modules/journal.py").read_bytes(), (V5 / "journal.py").read_bytes())
        self.assertEqual((LIVE / "option_c_modules/gate.py").read_bytes(), (V5 / "gate.py").read_bytes())
        self.assertNotEqual((LIVE / "option_c_modules/safety.py").read_bytes(), (V5 / "safety.py").read_bytes())
        self.assertNotEqual((LIVE / "option_c_modules/sink_verifier.py").read_bytes(), (V5 / "sink_verifier.py").read_bytes())

    def test_public_call_signatures_stay_compatible(self):
        live_safety = public_signatures(LIVE / "option_c_modules/safety.py")
        v5_safety = public_signatures(V5 / "safety.py")
        for name in ("school_batch_lock", "recovery_school_batch_lock", "make_approval", "validate_approval"):
            self.assertEqual(live_safety[name], v5_safety[name])
        self.assertNotIn("_school_admission_guard", live_safety)
        self.assertIn("_school_admission_guard", v5_safety)
        live_sink = public_signatures(LIVE / "option_c_modules/sink_verifier.py")
        v5_sink = public_signatures(V5 / "sink_verifier.py")
        self.assertEqual(live_sink["verify_sinks"], v5_sink["verify_sinks"])
        self.assertEqual(live_sink["verify_sinks"], (( "config",), ()))
        live_journal = public_signatures(LIVE / "option_c_modules/journal.py")
        guarded_journal = public_signatures(GUARDED / "journal.py")
        for name in ("create_journal", "complete_journal", "load_journal", "update_journal", "mark_recovery_required"):
            self.assertEqual(live_journal[name], guarded_journal[name])
        self.assertNotIn("complete_recovered_journal", live_journal)
        self.assertIn("complete_recovered_journal", guarded_journal)
        gate = public_signatures(LIVE / "option_c_modules/gate.py")["authorize"]
        self.assertEqual(gate, (("journal_path",), ("expected_batch_id", "expected_school_code", "expected_fingerprint")))

    def test_callers_pass_gate_keywords(self):
        card = (LIVE / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        ocr = (LIVE / "slip_ocr.py").read_text(encoding="utf-8")
        self.assertIn("expected_batch_id=batch_id", card)
        self.assertIn("expected_school_code=school_code", card)
        self.assertIn("expected_fingerprint=fingerprint", card)
        self.assertIn("from gate import authorize", card)
        self.assertIn("from journal import create_journal, complete_journal, mark_recovery_required, load_journal, update_journal", ocr)
        self.assertIn("from safety import make_approval, validate_approval, school_batch_lock, recovery_school_batch_lock", ocr)
        self.assertIn("gate_authorize(", ocr)
        self.assertNotIn("complete_recovered_journal", ocr)
        self.assertNotIn("import identity", ocr)
        self.assertNotIn("verify_sinks", ocr)

    def test_first_bsm_row_only(self):
        frame = pd.read_excel(LIVE / "school_config_front.xlsx", sheet_name="Sheet1")
        matches = frame[frame["school_code"].astype(str).str.strip() == "BSM"]
        self.assertEqual(len(matches), 4)
        first = matches.iloc[0]
        self.assertEqual(int(matches.index[0]) + 2, 13)
        self.assertEqual(first["school_code"], "BSM")
        self.assertEqual(str(first["ACTIVE"]).strip().upper(), "YES")
        self.assertEqual(first["template"], r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\templates\IDCARD\BSM.png")
        self.assertEqual(first["CARD"], "IDCARD")
        self.assertTrue(pd.isna(first["SCHOOLNAME"]))
        later = matches.iloc[1:]
        self.assertTrue(set(later["template"]) == {"D:/ID_CARD_PROJECT/templates/BSM_F.png"})
        self.assertNotIn("BSM_F.png", str(first["template"]))
        # pandas keeps the first FATHER_* header and hides the second copy.
        self.assertEqual(int(first["FATHER_X"]), 265)
        self.assertEqual(int(first["FATHER_SHOW"]), 1)
        self.assertIn("FATHER_X.1", frame.columns)
        self.assertTrue(pd.isna(first["FATHER_X.1"]))
        self.assertIn("M", frame.columns)
        self.assertTrue(any(str(name).startswith("Unnamed:") for name in frame.columns))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompatibilityTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
