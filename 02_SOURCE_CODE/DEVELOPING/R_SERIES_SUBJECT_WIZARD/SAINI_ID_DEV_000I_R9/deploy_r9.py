# -*- coding: utf-8 -*-
"""Install the approved BSM template only after the live hashes match. Does not generate a card."""
import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

PRODUCTION_ROOT = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels")
PACKAGE = Path(__file__).resolve().parent
CLEAN_SOURCE = PACKAGE / "payload" / "BSM_PUBLIC_SCHOOL_CLEAN.png"
EXPECTED = {
    "SAINI_ID_CARD.py": "08F68584254CE7E016BCB075EE25F59EEB94803550F82D8FF4BFF844453CB0E1",
    "school_config_front.xlsx": "8E774A9754CB0A1CA0ED4099C721052FD416476770EA4BDD28C8E8FCA07BE7EF",
    "ID_CARD_PROJECT/templates/IDCARD/BSM.png": "FE644757E1F23AAAB47C46AE2880F8DFD4CCDE63B645C50B6C10B7C855151B73",
}
CLEAN_SHA = "B4CEC57AF02B6CB92CDF2EB7262EB5E3F5582207BC23A29D578BA694D707E956"
EDITOR_F_HASH = "2684F6C2475F645401E61F0532724C6146C9DF98D2BDA239A2B0D2FD80273216"
EDITOR_D_HASH = "3047D7B56096D1CF31C277A61BDFE1C0FF20FA02B16BFD71F27D218A1425A225"
F_LINE = 'EXCEL_CONFIG = r"F:\\SHRI_JAI_SHRI_RAM\\project_panels\\school_config_front.xlsx"'
D_LINE = 'EXCEL_CONFIG = r"D:\\SHRI_JAI_SHRI_RAM\\project_panels\\school_config_front.xlsx"'
OLD_HOOK = (
    "            config = config_row.iloc[0]\n"
    "            template_path = str(config.get('template', '')).strip()\n"
    "\n"
    "            if not template_path or not os.path.exists(template_path):\n"
    "                continue\n"
    "\n"
    "            school_dir = os.path.join(OUTPUT_DIR, school, \"FRONT\")\n"
)
NEW_HOOK = (
    "            config = config_row.iloc[0]\n"
    "            template_path = str(config.get('template', '')).strip()\n"
    "            if str(school).strip().upper() == \"BSM\":\n"
    "                from bsm_front_gate import require_approved_front\n"
    "                template_path, bsm_error = require_approved_front(EXCEL_CONFIG)\n"
    "                if bsm_error:\n"
    "                    messagebox.showerror(\"BSM Config\", bsm_error)\n"
    "                    return\n"
    "            elif not template_path or not os.path.exists(template_path):\n"
    "                continue\n"
    "\n"
    "            if not template_path or not os.path.exists(template_path):\n"
    "                messagebox.showerror(\"BSM Config\", \"Approved template is missing. Generation stopped.\")\n"
    "                return\n"
    "\n"
    "            school_dir = os.path.join(OUTPUT_DIR, school, \"FRONT\")\n"
)
MODULES = (
    "bsm_config_loader.py",
    "config_validator.py",
    "template_identity.py",
    "bsm_front_gate.py",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


STATE = {"backup": None, "root": None}


def fail(message):
    print("DEPLOYMENT_BLOCKED")
    print(message)
    if STATE["backup"] is not None:
        from rollback_r9 import rollback
        rollback(STATE["root"], STATE["backup"])
    raise SystemExit(2)


def snapshot_workbook(path):
    book = load_workbook(path)
    try:
        sheet = book["Sheet1"]
        values = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
        merged = [str(item) for item in sheet.merged_cells.ranges]
        widths = {key: item.width for key, item in sheet.column_dimensions.items()}
        return values, merged, widths
    finally:
        book.close()


def install(root, backup_root):
    root = Path(root)
    if not root.is_dir():
        fail(f"project root is not available: {root}")
    if sha256(CLEAN_SOURCE) != CLEAN_SHA:
        fail("approved template payload hash mismatch")
    for relative, expected in EXPECTED.items():
        source = root / relative
        if not source.is_file() or sha256(source) != expected:
            fail(f"live hash mismatch, file left untouched: {relative}")
    editor = root / "config_editor.py"
    editor_hash = sha256(editor) if editor.is_file() else ""
    if editor.is_file() and editor_hash not in {EDITOR_F_HASH, EDITOR_D_HASH}:
        fail("config_editor.py hash is not one of the two known copies")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(backup_root) / f"TASK_000I_R9_{stamp}"
    backup.mkdir(parents=True)
    manifest = ["SOURCE_HASHES"]
    for relative in EXPECTED:
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
        if sha256(target) != sha256(root / relative):
            fail(f"backup verification failed: {relative}")
        manifest.append(f"{relative}|{sha256(root / relative)}")
    if editor.is_file():
        copied = backup / "config_editor.py"
        shutil.copy2(editor, copied)
        if sha256(copied) != editor_hash:
            fail("config editor backup verification failed")
        manifest.append(f"config_editor.py|{editor_hash}")
    (backup / "SHA256_MANIFEST.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    STATE["backup"] = backup
    STATE["root"] = root

    before_values, before_merged, before_widths = snapshot_workbook(root / "school_config_front.xlsx")
    row13 = before_values[12]
    if str(row13[0] or "").strip().upper() != "BSM":
        fail("Excel row 13 is not BSM")
    header = list(before_values[0])
    name_at = header.index("SCHOOLNAME")
    template_at = header.index("template")
    card_at = header.index("CARD")
    type_at = header.index("CARD_TYPE")
    if row13[card_at] != "IDCARD" or str(row13[type_at]).lower() != "single":
        fail("row 13 CARD settings are not the expected ID card settings")

    destination = root / "ID_CARD_PROJECT" / "templates" / "IDCARD" / "BSM_PUBLIC_SCHOOL_CLEAN.png"
    if destination.exists() and sha256(destination) != CLEAN_SHA:
        fail("a different file already uses the clean template name")
    shutil.copy2(CLEAN_SOURCE, destination)
    if sha256(destination) != CLEAN_SHA or sha256(root / "ID_CARD_PROJECT/templates/IDCARD/BSM.png") != EXPECTED["ID_CARD_PROJECT/templates/IDCARD/BSM.png"]:
        fail("template copy verification failed")

    workbook_path = root / "school_config_front.xlsx"
    book = load_workbook(workbook_path)
    try:
        sheet = book["Sheet1"]
        sheet.cell(13, name_at + 1).value = "BSM PUBLIC SCHOOL"
        sheet.cell(13, template_at + 1).value = str(destination)
        book.save(workbook_path)
    finally:
        book.close()
    after_values, after_merged, after_widths = snapshot_workbook(workbook_path)
    if after_merged != before_merged or after_widths != before_widths or len(after_values) != len(before_values):
        fail("workbook structure changed")
    for index, (old, new) in enumerate(zip(before_values, after_values), start=1):
        if old == new:
            continue
        if index != 13:
            fail(f"unexpected workbook row changed: {index}")
        for column, (left, right) in enumerate(zip(old, new)):
            if left != right and column not in {name_at, template_at}:
                fail(f"unexpected row 13 column changed: {header[column]}")
    reopened = after_values[12]
    if reopened[name_at] != "BSM PUBLIC SCHOOL" or reopened[template_at] != str(destination):
        fail("row 13 verification failed")
    for excel_row in (83, 130, 215):
        if after_values[excel_row - 1] != before_values[excel_row - 1]:
            fail(f"BSM row {excel_row} changed")

    for name in MODULES:
        shutil.copy2(PACKAGE / "install_modules" / name, root / name)
    generator = root / "SAINI_ID_CARD.py"
    source = generator.read_text(encoding="utf-8")
    if OLD_HOOK not in source or source.count(OLD_HOOK) != 1:
        fail("generator hook point was not found exactly once")
    generator.write_text(source.replace(OLD_HOOK, NEW_HOOK, 1), encoding="utf-8")
    if "require_approved_front" not in generator.read_text(encoding="utf-8"):
        fail("generator hook was not written")

    if editor.is_file() and editor_hash == EDITOR_F_HASH:
        editor_text = editor.read_text(encoding="utf-8")
        if editor_text.count(F_LINE) != 1:
            fail("known config editor does not contain the expected F: path")
        editor.write_text(editor_text.replace(F_LINE, D_LINE, 1), encoding="utf-8")
        if D_LINE not in editor.read_text(encoding="utf-8"):
            fail("config editor path was not updated")

    sys.path.insert(0, str(root))
    from bsm_front_gate import require_approved_front
    approved, error = require_approved_front(workbook_path)
    if error or Path(approved) != destination:
        fail(error or "loader did not select the installed template")
    print("BACKUP", backup)
    print("TEMPLATE", destination)
    print("TEMPLATE_SHA", CLEAN_SHA)
    print("WORKBOOK_SHA", sha256(workbook_path))
    print("GENERATOR_SHA", sha256(generator))
    print("ORIGINAL_BSM_PNG", sha256(root / "ID_CARD_PROJECT/templates/IDCARD/BSM.png"))
    print("NO_CARD_GENERATED")
    if root.resolve() == PRODUCTION_ROOT.resolve() and PRODUCTION_ROOT.exists():
        print("DEPLOYED_TESTS_PASSED_FIRST_CARD_PENDING")
    else:
        print("SANDBOX_REHEARSAL_OK")
    return backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(PRODUCTION_ROOT))
    parser.add_argument("--backup-root", default=r"D:\SHRI_JAI_SHRI_RAM\BACKUPS")
    args = parser.parse_args()
    install(args.root, args.backup_root)


if __name__ == "__main__":
    main()
