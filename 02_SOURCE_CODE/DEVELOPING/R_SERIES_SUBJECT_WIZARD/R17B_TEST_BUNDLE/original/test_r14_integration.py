# -*- coding: utf-8 -*-
"""R14 integration checks. Synthetic images only. No live project access."""
import hashlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bsm_selector import ConfigSelectionError, select_bsm_row

BASELINE = {
    "gate.py": "0EEB0EA1FEE4520A3E91B59E16D8C1BCF2F4B2B1DC1A7C4C5C10C7F60E1D51EA",
    "identity.py": "10FFD0C9A91DB42D5904255FD41CB307A458FC02F33378073A875C6C2CC0F112",
    "journal.py": "5A908C6BED369B597FC92D64BE27CF0444C0076B33A839D8D5E77523E43BF361",
    "safety.py": "42BDEFA0ECD3C2EA21490B39542E7ECFE0A8FA06EF4C73CED53BFB2FF8EE6F2E",
    "sink_verifier.py": "C274F2D0A214EDB95FF609FC10D1BEF6B3BBDC4240D543ADDA0F6CA8C44F78AC",
}
R13_PATCHED = {
    "SAINI_ID_CARD.py": "EA1E637CD5FABF2E122BD84FCF275908D41B5A2929908D823A3C518FED95D187",
    "config_editor.py": "FE3C8090698A491EDB6C6E7AC943AF853832E074F394090D787A0282F0328A0E",
    "bsm_selector.py": "3B58769CBE08B36B30FE8536BEA9391FEE6640A10F4545D43215E62E3F6B891C",
    "saini_config_path.py": "A1EEA7A6233C9DF6B28123E70DB69A28E14112C36D8D69FDFE900D74E8EAF550",
}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_generator():
    tk = types.ModuleType("tkinter")
    tk.messagebox = types.ModuleType("tkinter.messagebox")
    tk.ttk = types.ModuleType("tkinter.ttk")
    sys.modules.setdefault("tkinter", tk)
    sys.modules.setdefault("tkinter.messagebox", tk.messagebox)
    sys.modules.setdefault("tkinter.ttk", tk.ttk)
    calendar = types.ModuleType("tkcalendar")
    calendar.DateEntry = object
    sys.modules.setdefault("tkcalendar", calendar)
    spec = importlib.util.spec_from_file_location("saini_id_card_r14", ROOT / "SAINI_ID_CARD.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class R14IntegrationTests(unittest.TestCase):
    def test_copied_patch_hashes_match_r13(self):
        for name, digest in R13_PATCHED.items():
            self.assertEqual(sha(ROOT / name), digest, name)

    def test_option_c_modules_match_baseline(self):
        for name, digest in BASELINE.items():
            self.assertEqual(sha(ROOT / "option_c_modules" / name), digest, name)
            self.assertEqual((ROOT / "option_c_modules" / name).read_bytes(), (ROOT / "baseline" / name).read_bytes())

    def test_gate_calls_remain_and_non_bsm_branch_remains(self):
        text = (ROOT / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
        self.assertIn("from gate import authorize", text)
        self.assertIn("return authorize(", text)
        self.assertIn("expected_school_code=school_code", text)
        self.assertNotIn("write_by_name", text)
        self.assertIn("config = self.config_df[self.config_df['school_code'] == school].iloc[0]", text)
        editor = (ROOT / "config_editor.py").read_text(encoding="utf-8")
        self.assertNotIn("F:\\SHRI_JAI_SHRI_RAM", editor)
        self.assertNotIn("F:/SHRI_JAI_SHRI_RAM", editor)

    def test_synthetic_render_uses_only_the_selected_row(self):
        import pandas as pd
        out_dir = ROOT / "synthetic_output"
        out_dir.mkdir(exist_ok=True)
        template = out_dir / "synthetic_template.png"
        photo = out_dir / "synthetic_color_block.png"
        output = out_dir / "synthetic_front.png"
        rejected = out_dir / "rejected_template.png"
        Image.new("RGB", (320, 200), (10, 40, 90)).save(template)
        Image.new("RGB", (40, 50), (200, 160, 20)).save(photo)
        Image.new("RGB", (30, 30), (255, 0, 0)).save(rejected)
        frame = pd.DataFrame([
            {"school_code": "BSM", "SCHOOLNAME": " \n\t ", "template": str(rejected), "CARD": "IDCARD"},
            {
                "school_code": "BSM",
                "SCHOOLNAME": "BSM PUBLIC SCHOOL",
                "template": str(template),
                "CARD": "IDCARD",
                "STUDENT_PHOTO_X": 20,
                "STUDENT_PHOTO_Y": 30,
                "STUDENT_PHOTO_W": 40,
                "STUDENT_PHOTO_H": 50,
                "PHOTO_RADIUS": 0,
            },
            {"school_code": "NBFP", "SCHOOLNAME": "OTHER SCHOOL", "template": str(rejected), "CARD": "IDCARD"},
        ])
        with self.assertRaises(ConfigSelectionError):
            select_bsm_row(frame.iloc[0:1])
        row = select_bsm_row(frame)
        self.assertEqual(row["template"], str(template))
        self.assertNotEqual(row["template"], str(rejected))
        module = load_generator()
        if output.exists():
            output.unlink()
        ok = module.generate_front_card(
            row["template"],
            str(output),
            {"student_name": "SYNTHETIC", "STUDENT_PHOTO_PATH": str(photo)},
            row,
        )
        self.assertTrue(ok)
        self.assertTrue(output.is_file())
        self.assertGreater(output.stat().st_size, 0)
        with Image.open(output) as rendered:
            self.assertEqual(rendered.size, (320, 200))
            self.assertEqual(rendered.getpixel((25, 35)), (200, 160, 20))
        self.assertFalse(module.generate_front_card(str(out_dir / "missing_template.png"), str(out_dir / "must_not_exist.png"), {}, row))
        self.assertFalse((out_dir / "must_not_exist.png").exists())


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
