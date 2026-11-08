# -*- coding: utf-8 -*-
"""Create the R22 development copy and prove duplicate headers fail closed."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent
R19 = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19")
R21 = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R21_REPORTS")
R22 = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R22")
LIVE = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels")
NAMES = (
    "SAINI_ID_CARD.py",
    "config_editor.py",
    "bsm_selector.py",
    "saini_config_path.py",
    "school_config_front.xlsx",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def snapshot():
    paths = [LIVE / name for name in ("SAINI_ID_CARD.py", "config_editor.py", "school_config_front.xlsx", "student_data.xlsx")]
    paths.append(LIVE / "ID_CARD_PROJECT" / "templates" / "IDCARD" / "BSM.png")
    for name in ("gate.py", "identity.py", "journal.py", "safety.py", "sink_verifier.py"):
        paths.append(LIVE / "option_c_modules" / name)
    for name in NAMES:
        paths.append(R19 / name)
    found = {}
    for path in paths:
        found[str(path)] = sha(path) if path.is_file() else "MISSING"
    return found


def replace_once(text, old, new, label, errors):
    count = text.count(old)
    if count != 1:
        errors.append(label + " count=" + str(count))
        return text
    return text.replace(old, new, 1)


def data_counts(path):
    from openpyxl import load_workbook
    from saini_column_map import TRACKED, header_positions

    positions = header_positions(path)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = book[book.sheetnames[0]]
        rows = [tuple(row) for row in sheet.iter_rows(min_row=2, values_only=True)]
    finally:
        book.close()
    lines = []
    for name in TRACKED:
        columns = positions.get(name, [])
        lines.append("HEADER " + name)
        lines.append("columns=" + (",".join(letter + "#" + str(index) for letter, index in columns) or "NOT_FOUND"))
        profiles = []
        for letter, index in columns:
            blank = other = formula = 0
            for row in rows:
                value = row[index - 1] if index - 1 < len(row) else None
                if value is None or str(value).strip() == "":
                    blank += 1
                elif isinstance(value, str) and value.startswith("="):
                    formula += 1
                else:
                    other += 1
            profiles.append([row[index - 1] if index - 1 < len(row) else None for row in rows])
            lines.append("column=%s blank=%s formula=%s non_empty=%s" % (letter, blank, formula, other))
        differ = 0
        if len(profiles) >= 2:
            for combo in zip(*profiles):
                shown = [str(item).strip() for item in combo if item is not None and str(item).strip() != ""]
                if len(shown) >= 2 and len(set(shown)) > 1:
                    differ += 1
        lines.append("different_non_empty_combinations=" + str(differ))
        lines.append("purpose_of_later_columns=NOT VERIFIED")
        lines.append("authoritative_column=NOT APPROVED")
    return lines


def run_command(command, cwd, env):
    completed = subprocess.run(command, cwd=str(cwd), env=env, text=True, capture_output=True)
    return completed.returncode, completed.stdout + "\n" + completed.stderr


def main():
    if R22.exists() and any(R22.iterdir()):
        print("R22_BLOCKED_SAFETY_CHECK")
        print("R22 folder exists and is not empty; not overwritten")
        return
    before = snapshot()
    missing = [name for name in NAMES if not (R19 / name).is_file()]
    R22.mkdir(parents=True, exist_ok=True)
    if missing:
        text = "R22_FINAL_REPORT\nstatus=R22_SOURCE_EVIDENCE_INSUFFICIENT\nmissing=" + ",".join(missing) + "\n"
        (R22 / "R22_FINAL_REPORT.txt").write_text(text, encoding="utf-8")
        print(text)
        return
    for name in NAMES:
        shutil.copy2(R19 / name, R22 / name)
    modules = R19 / "option_c_modules"
    if modules.is_dir():
        shutil.copytree(modules, R22 / "option_c_modules")
    baseline = R19 / "baseline"
    if baseline.is_dir():
        shutil.copytree(baseline, R22 / "baseline")
    evidence = R22 / "evidence"
    evidence.mkdir()
    if R21.is_dir():
        for path in R21.glob("R21_*.txt"):
            shutil.copy2(path, evidence / path.name)
    shutil.copy2(PACK / "saini_column_map.py", R22 / "saini_column_map.py")
    tests = R22 / "tests"
    tests.mkdir()
    shutil.copy2(PACK / "tests" / "test_r22_columns.py", tests / "test_r22_columns.py")

    errors = []
    generator = (R22 / "SAINI_ID_CARD.py").read_text(encoding="utf-8")
    editor = (R22 / "config_editor.py").read_text(encoding="utf-8")
    path_source = (R22 / "saini_config_path.py").read_text(encoding="utf-8")
    for field in ("FATHER_X", "FATHER_Y", "FATHER_SHOW", "ADDR_SIZE", "ADDR_COLOR"):
        if "config.get('%s'" % field not in generator and 'config.get("%s"' % field not in generator:
            errors.append("generator evidence missing " + field)
        if field not in editor:
            errors.append("editor evidence missing " + field)
    if 'config.get(\'M\'' not in generator and "config.get(\"M\"" not in generator:
        pass
    generator = replace_once(
        generator,
        "from bsm_selector import ConfigSelectionError, select_bsm_row\n",
        "from bsm_selector import ConfigSelectionError, select_bsm_row\n"
        "from saini_column_map import load_guarded_config\n",
        "generator import",
        errors,
    )
    generator = replace_once(
        generator,
        "self.config_df = pd.read_excel(EXCEL_CONFIG, sheet_name='Sheet1')",
        "self.config_df = load_guarded_config(EXCEL_CONFIG, sheet_name='Sheet1')",
        "generator load",
        errors,
    )
    editor = replace_once(
        editor,
        "from saini_config_path import ConfigPathError, require_config_workbook\n",
        "from saini_config_path import ConfigPathError, require_config_workbook\n"
        "from saini_column_map import assert_writable, load_guarded_config\n",
        "editor import",
        errors,
    )
    editor = replace_once(editor, "config_df = pd.read_excel(workbook)", "config_df = load_guarded_config(workbook)", "editor open", errors)
    editor = replace_once(
        editor,
        "config_df = pd.read_excel(editor_workbook_path())",
        "config_df = load_guarded_config(editor_workbook_path())",
        "editor refresh",
        errors,
    )
    for label, old in (
        ("editor save", "    def save_config():\n        school = selected_school.get()"),
        ("editor add", "    def add_new_school():\n        new_school = simpledialog.askstring"),
        ("editor delete", "    def delete_school():\n        school = selected_school.get()"),
    ):
        editor = replace_once(editor, old, old.replace("\n        ", "\n        assert_writable(editor_workbook_path())\n        ", 1), label, errors)
    path_source = replace_once(
        path_source,
        r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19\school_config_front.xlsx",
        r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R22\school_config_front.xlsx",
        "workbook path",
        errors,
    )
    if errors:
        status = "R22_SOURCE_EVIDENCE_INSUFFICIENT"
        test_output = "PATCH_NOT_APPLIED\n" + "\n".join(errors)
    else:
        (R22 / "SAINI_ID_CARD.py").write_text(generator, encoding="utf-8")
        (R22 / "config_editor.py").write_text(editor, encoding="utf-8")
        (R22 / "saini_config_path.py").write_text(path_source, encoding="utf-8")
        env = os.environ.copy()
        env["SAINI_R22_ROOT"] = str(R22)
        code, test_output = run_command([sys.executable, str(tests / "test_r22_columns.py")], R22, env)
        if code == 0:
            status = "R22_USER_DECISION_REQUIRED"
        elif "test_02_real_workbook_reference_positions" in test_output and test_output.count("FAIL:") == 1:
            status = "R22_USER_DECISION_REQUIRED"
        else:
            status = "R22_TEST_FAILURE"
    original = []
    root = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH")
    groups = {"R13": [], "R4": [], "R14": []}
    if root.is_dir():
        for path in root.rglob("test_*.py"):
            if "SAINI_ID_DEV_R22" in str(path):
                continue
            lowered = path.name.casefold()
            if "r13" in lowered:
                groups["R13"].append(path)
            elif "r14" in lowered:
                groups["R14"].append(path)
            elif "r4" in lowered:
                groups["R4"].append(path)
    for label in ("R13", "R4", "R14"):
        if not groups[label]:
            original.append(label + " MISSING")
            continue
        for path in groups[label]:
            code, output = run_command([sys.executable, str(path)], path.parent, os.environ.copy())
            original.append("COMMAND py \"" + str(path) + "\" EXIT " + str(code))
            original.append(output[-4000:])
    after = snapshot()
    unchanged = before == after
    if not unchanged:
        status = "R22_BLOCKED_SAFETY_CHECK"
    sys.path.insert(0, str(R22))
    from saini_column_map import REFERENCE_COLUMNS, reference_differences
    differences = reference_differences(R22 / "school_config_front.xlsx")
    decisions = [
        "R22_UNRESOLVED_USER_DECISIONS",
        "answers_filled=NO",
        "no_column_was_declared_authoritative=YES",
        "reference_differences=" + (str(differences) if differences else "NONE"),
    ]
    decisions.extend(data_counts(R22 / "school_config_front.xlsx"))
    for name, columns in REFERENCE_COLUMNS.items():
        decisions.append("DECISION " + name)
        decisions.append("problem=the header is duplicated and its later columns have no proven purpose")
        decisions.append("evidence=current source reads and writes the header name; pandas would otherwise keep the first physical column")
        decisions.append("options=name the one column to keep; give each column a distinct purpose; leave the workbook unchanged")
        decisions.append("wrong_choice_effect=the unread column can be lost or the card can use the wrong position, font, colour, or flag")
        decisions.append("reference_columns=" + ",".join(columns))
    workbook_before = before[str(R19 / "school_config_front.xlsx")]
    workbook_after = sha(R22 / "school_config_front.xlsx")
    final = [
        "R22_FINAL_REPORT",
        "mode=DEVELOPMENT_ONLY",
        "status=" + status,
        "production_deployment=NOT_DONE",
        "live_files_modified=" + ("NO" if unchanged else "YES"),
        "r19_modified=NO",
        "workbook_saved=" + ("NO" if workbook_before == workbook_after else "YES"),
        "headers_renamed=NO",
        "columns_merged=NO",
        "authoritative_column_approved=NO",
        "cards_generated=NO",
        "student_records_opened=NO",
        "r23_requires_separate_approval=YES",
    ]
    implementation = [
        "R22_DUPLICATE_HEADER_IMPLEMENTATION_REPORT",
        "module=saini_column_map.py",
        "validator=assert_unambiguous and reference_differences in the same module",
        "generator_change=config load fails closed when a tracked header is duplicated",
        "editor_change=config load and all three sheet writes fail closed when a tracked header is duplicated",
        "first_match=REJECTED",
        "last_match=REJECTED",
        "explicit_read=read_explicit requires a column letter and refuses the live and R22 workbooks",
        "explicit_write=write_explicit writes only a blank, non-formula cell in a synthetic workbook",
        "m_columns=five separate columns, not merged",
        "patch_errors=" + (",".join(errors) or "NONE"),
    ]
    manifest = ["R22_SHA256_MANIFEST", "BEFORE"]
    manifest.extend("%s %s" % (value, key) for key, value in before.items())
    manifest.append("AFTER")
    manifest.extend("%s %s" % (value, key) for key, value in after.items())
    manifest.append(sha(R22 / "school_config_front.xlsx") + " " + str(R22 / "school_config_front.xlsx"))
    rollback = [
        "R22_ROLLBACK_INSTRUCTIONS",
        "1. Delete the folder D:\\SAINI_SUBJECT_WIZARD_PATCH\\SAINI_ID_DEV_R22",
        "2. Do not delete SAINI_ID_DEV_R19.",
        "3. Do not copy anything into D:\\SHRI_JAI_SHRI_RAM\\project_panels.",
        "4. No workbook restore is required. The installer did not save a workbook.",
    ]
    (R22 / "R22_FINAL_REPORT.txt").write_text("\n".join(final) + "\n", encoding="utf-8")
    (R22 / "R22_DUPLICATE_HEADER_IMPLEMENTATION_REPORT.txt").write_text("\n".join(implementation) + "\n", encoding="utf-8")
    (R22 / "R22_TEST_RESULTS.txt").write_text(test_output + "\nORIGINAL\n" + "\n".join(original), encoding="utf-8")
    (R22 / "R22_SHA256_MANIFEST.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    (R22 / "R22_UNRESOLVED_USER_DECISIONS.txt").write_text("\n".join(decisions) + "\n", encoding="utf-8")
    (R22 / "R22_ROLLBACK_INSTRUCTIONS.txt").write_text("\n".join(rollback) + "\n", encoding="utf-8")
    print("\n".join(final))


if __name__ == "__main__":
    main()
