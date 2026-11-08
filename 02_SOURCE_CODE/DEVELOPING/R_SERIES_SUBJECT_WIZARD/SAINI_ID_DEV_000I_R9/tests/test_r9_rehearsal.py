# -*- coding: utf-8 -*-
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

PACKAGE = Path("/workspace/SAINI_ID_DEV_000I_R9")
SOURCE = Path("/workspace/SAINI_ID_DEV_000I_R4/live_root")
EDITOR = Path("/workspace/SAINI_ID_DEV_000I_R4/reference_config_editors/config_editor_PROJECT_ROOT.py")
EXPECTED = {
    "SAINI_ID_CARD.py": "08F68584254CE7E016BCB075EE25F59EEB94803550F82D8FF4BFF844453CB0E1",
    "school_config_front.xlsx": "466E0EE1BF63698DC300A50BF07451F53889A1EE7B37A2C6E460D9551FC772F0",
    "ID_CARD_PROJECT/templates/IDCARD/BSM.png": "FE644757E1F23AAAB47C46AE2880F8DFD4CCDE63B645C50B6C10B7C855151B73",
}
CLEAN = "B4CEC57AF02B6CB92CDF2EB7262EB5E3F5582207BC23A29D578BA694D707E956"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def run(args):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project_panels"
        self.backups = Path(self.temp.name) / "BACKUPS"
        for relative in EXPECTED:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / relative, target)
        shutil.copy2(EDITOR, self.root / "config_editor.py")
        option = self.root / "option_c_modules" / "gate.py"
        option.parent.mkdir(parents=True)
        option.write_text("SENTINEL\n", encoding="utf-8")
        self.option_hash = sha256(option)

    def tearDown(self):
        self.temp.cleanup()

    def test_rehearsal_then_rollback(self):
        result = run([
            str(PACKAGE / "deploy_r9.py"),
            "--root", str(self.root),
            "--backup-root", str(self.backups),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SANDBOX_REHEARSAL_OK", result.stdout)
        self.assertIn("NO_CARD_GENERATED", result.stdout)
        self.assertNotIn("DEPLOYED_TESTS_PASSED_FIRST_CARD_PENDING", result.stdout)
        self.assertEqual(sha256(self.root / "ID_CARD_PROJECT/templates/IDCARD/BSM.png"), EXPECTED["ID_CARD_PROJECT/templates/IDCARD/BSM.png"])
        clean = self.root / "ID_CARD_PROJECT/templates/IDCARD/BSM_PUBLIC_SCHOOL_CLEAN.png"
        self.assertEqual(sha256(clean), CLEAN)
        self.assertEqual(sha256(self.root / "option_c_modules/gate.py"), self.option_hash)
        book = load_workbook(self.root / "school_config_front.xlsx", read_only=True, data_only=True)
        try:
            rows = {index: row for index, row in enumerate(book["Sheet1"].iter_rows(values_only=True), start=1)}
        finally:
            book.close()
        self.assertEqual(rows[13][1], "BSM PUBLIC SCHOOL")
        self.assertEqual(rows[13][3], str(clean))
        self.assertIsNone(rows[83][1])
        self.assertIsNone(rows[130][1])
        self.assertIsNone(rows[215][1])
        generator = (self.root / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        self.assertIn("require_approved_front", generator)
        self.assertNotIn("generate_front_card(", generator.split("require_approved_front", 1)[1][:400])
        editor = (self.root / "config_editor.py").read_text(encoding="utf-8")
        self.assertIn(r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx", editor)
        self.assertNotIn(r"F:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx", editor)
        backup = next(self.backups.glob("TASK_000I_R9_*"))
        restored = run([
            str(PACKAGE / "rollback_r9.py"),
            "--root", str(self.root),
            "--backup", str(backup),
        ])
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assertIn("ROLLED_BACK", restored.stdout)
        for relative, expected in EXPECTED.items():
            self.assertEqual(sha256(self.root / relative), expected)
        self.assertFalse((self.root / "bsm_front_gate.py").exists())
        self.assertEqual(sha256(SOURCE / "school_config_front.xlsx"), EXPECTED["school_config_front.xlsx"])

    def test_wrong_live_hash_stops_before_changes(self):
        workbook = self.root / "school_config_front.xlsx"
        workbook.write_bytes(workbook.read_bytes() + b" ")
        before = {relative: sha256(self.root / relative) for relative in EXPECTED}
        result = run([
            str(PACKAGE / "deploy_r9.py"),
            "--root", str(self.root),
            "--backup-root", str(self.backups),
        ])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("DEPLOYMENT_BLOCKED", result.stdout)
        self.assertFalse((self.root / "ID_CARD_PROJECT/templates/IDCARD/BSM_PUBLIC_SCHOOL_CLEAN.png").exists())
        for relative, expected in before.items():
            self.assertEqual(sha256(self.root / relative), expected)

    def test_missing_production_root_is_blocked(self):
        result = run([str(PACKAGE / "deploy_r9.py"), "--root", r"D:\SHRI_JAI_SHRI_RAM\project_panels"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("DEPLOYMENT_BLOCKED", result.stdout)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RehearsalTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
