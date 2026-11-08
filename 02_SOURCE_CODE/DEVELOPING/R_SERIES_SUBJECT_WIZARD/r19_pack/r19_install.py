# -*- coding: utf-8 -*-
"""Create the R19 development copy and verify it. Live files are only read."""
import hashlib
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

R13 = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_000I_R13")
DEST = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R19")
LIVE = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels")
PACK = Path(__file__).resolve().parent
R4_TEST = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\R17B_TEST_BUNDLE\original\test_compat_r4.py")
R4_BASE = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\R17B_TEST_BUNDLE\r4_baseline")
R14_TEST = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\R17B_TEST_BUNDLE\original\test_r14_integration.py")
LIVE_FILES = [
    LIVE / "SAINI_ID_CARD.py",
    LIVE / "school_config_front.xlsx",
    LIVE / "config_editor.py",
    LIVE / "ID_CARD_PROJECT" / "templates" / "IDCARD" / "BSM.png",
]
OPTION_C = ["gate.py", "identity.py", "journal.py", "safety.py", "sink_verifier.py"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def hashes(paths):
    found = {}
    for path in paths:
        found[str(path)] = sha(path) if Path(path).is_file() else "MISSING"
    return found


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit("PATCH_COUNT %s %s" % (path.name, text.count(old)))
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def live_snapshot():
    paths = list(LIVE_FILES)
    for name in OPTION_C:
        paths.append(LIVE / "option_c_modules" / name)
    return hashes(paths)


def run_py(args, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=merged)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def original_count(output):
    for line in output.splitlines():
        if line.startswith("Ran ") and " test" in line:
            return line
    return "count missing"


def bsm_and_headers(workbook):
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        sheet = book[book.sheetnames[0]]
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        book.close()
    headers = ["" if cell is None else str(cell) for cell in rows[0]]
    positions = defaultdict(list)
    for index, name in enumerate(headers, start=1):
        if name:
            positions[name].append(index)
    sources = []
    for name in ("SAINI_ID_CARD.py", "config_editor.py", "bsm_selector.py"):
        sources.append((name, (DEST / name).read_text(encoding="utf-8", errors="replace")))
    mapping = ["R19_DUPLICATE_HEADER_MAPPING", "schema_migration=NOT_DONE", "headers_were_not_changed=YES"]
    duplicates = [(name, places) for name, places in sorted(positions.items()) if len(places) > 1]
    if not duplicates:
        mapping.append("duplicate_headers=NONE")
    for name, places in duplicates:
        used = []
        for source_name, text in sources:
            if "'" + name + "'" in text or '"' + name + '"' in text:
                used.append(source_name)
        mapping.append("HEADER " + name)
        mapping.append("positions=" + ",".join(str(item) for item in places))
        mapping.append("source_usage=" + (",".join(used) if used else "NO_EXACT_STRING_MATCH"))
        mapping.append("ambiguity=pandas keeps the first column under this name and renames later copies")
        mapping.append("proposed_resolution=do not delete, rename, merge, or shift; user must choose the authoritative column")
        mapping.append("required_user_decision=YES")
    bsm = ["R19_BSM_VALIDATION_REPORT", "school_names_invented=NO", "templates_invented=NO", "workbook_modified=NO"]
    def hits_for(key):
        found = []
        for number, name in enumerate(headers):
            norm = "".join(name.split()).casefold()
            if norm == key or (norm.startswith(key + ".") and norm[len(key) + 1:].isdigit()):
                found.append(number)
        return found
    code_hits = hits_for("school_code")
    name_hits = hits_for("schoolname")
    template_hits = hits_for("template")
    ambiguous = len(code_hits) != 1 or len(name_hits) != 1 or len(template_hits) != 1
    bsm.append("required_header_ambiguity=" + ("YES" if ambiguous else "NO"))
    if not ambiguous:
        for number, values in enumerate(rows[1:], start=2):
            code = "" if values[code_hits[0]] is None else str(values[code_hits[0]]).strip().upper()
            if code != "BSM":
                continue
            raw_name = values[name_hits[0]]
            name_status = "BLANK" if raw_name is None or str(raw_name).strip() == "" else "PRESENT"
            raw_template = values[template_hits[0]]
            template = "" if raw_template is None else str(raw_template).strip()
            blocked = "PHOTO_LIBRARY" in template.upper()
            exists = False if blocked or not template else Path(template).is_file()
            reasons = []
            if name_status == "BLANK":
                reasons.append("SCHOOLNAME missing or whitespace-only")
            if not template:
                reasons.append("template path missing")
            elif blocked:
                reasons.append("template path was not opened")
            elif not exists:
                reasons.append("template file missing")
            eligible = "ELIGIBLE" if not reasons else "REJECTED"
            bsm.append(
                "row=%s SCHOOLNAME=%s template=%s exists=%s eligibility=%s reason=%s"
                % (number, name_status, template or "BLANK", exists, eligible, "; ".join(reasons) or "NONE")
            )
    else:
        bsm.append("row_evaluation=NOT_EVALUATED reason=required header is missing or duplicated")
    return mapping, bsm


def main():
    if DEST.exists() and any(DEST.iterdir()):
        print("R19_BLOCKED_SAFETY_CHECK")
        print("folder exists and is not empty; not overwritten")
        print(DEST)
        return
    if not R13.is_dir():
        print("R19_BLOCKED_SAFETY_CHECK")
        print("R13 development folder missing")
        return
    before_live = live_snapshot()
    r13_names = ["SAINI_ID_CARD.py", "config_editor.py", "bsm_selector.py", "saini_config_path.py", *["option_c_modules/" + name for name in OPTION_C]]
    before_r13 = hashes([R13 / name for name in r13_names])
    DEST.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(R13, DEST, dirs_exist_ok=True)
        for name in ("saini_config_path.py", "bsm_selector.py", "test_r19_rules.py"):
            target = DEST / ("tests" if name.startswith("test_") else "") / name
            if name.startswith("test_"):
                target = DEST / "tests" / name
            else:
                target = DEST / name
            shutil.copyfile(PACK / name, target)
        replace_once(
            DEST / "SAINI_ID_CARD.py",
            "from saini_config_path import resolve_config_workbook\n",
            "from saini_config_path import require_config_workbook\n",
        )
        replace_once(
            DEST / "SAINI_ID_CARD.py",
            "EXCEL_CONFIG = resolve_config_workbook()\n",
            "EXCEL_CONFIG = require_config_workbook()\n",
        )
        replace_once(
            DEST / "config_editor.py",
            "from saini_config_path import resolve_config_workbook\n",
            "from saini_config_path import ConfigPathError, require_config_workbook\n",
        )
        replace_once(
            DEST / "config_editor.py",
            "    return resolve_config_workbook()\n",
            "    return require_config_workbook()\n",
        )
        replace_once(
            DEST / "config_editor.py",
            "    workbook = editor_workbook_path()\n    if not os.path.exists(workbook):\n        messagebox.showerror(\"Error\", \"school_config_front.xlsx not found!\")\n        return\n",
            "    try:\n        workbook = editor_workbook_path()\n    except ConfigPathError as exc:\n        messagebox.showerror(\"Config workbook\", str(exc))\n        return\n",
        )
        workbook = LIVE / "school_config_front.xlsx"
        copied = DEST / "school_config_front.xlsx"
        if workbook.is_file():
            shutil.copyfile(workbook, copied)
        code, r19_output = run_py([str(DEST / "tests" / "test_r19_rules.py")])
        r13_test = R13 / "tests" / "test_r13_bsm_and_path.py"
        if r13_test.is_file():
            r13_code, r13_output = run_py([str(r13_test)])
            r13_state = "PASS" if r13_code == 0 else "FAIL"
        else:
            r13_code, r13_output, r13_state = 1, "", "MISSING"
        if R4_TEST.is_file() and R4_BASE.is_dir():
            mount = Path(r"C:\workspace\SAINI_ID_DEV_000I_R4")
            created_mount = False
            created_parent = False
            if not mount.exists():
                if not mount.parent.exists():
                    mount.parent.mkdir(parents=True)
                    created_parent = True
                subprocess.run(["cmd", "/c", "mklink", "/J", str(mount), str(R4_BASE)], check=True, capture_output=True, text=True)
                created_mount = True
            try:
                r4_code, r4_output = run_py([str(R4_TEST)])
            finally:
                if created_mount and mount.exists():
                    os.rmdir(mount)
                if created_parent and mount.parent.exists():
                    os.rmdir(mount.parent)
            r4_state = "PASS" if r4_code == 0 else "FAIL"
        else:
            r4_code, r4_output, r4_state = 1, "", "MISSING"
        if R14_TEST.is_file():
            view = DEST / "regression_r14_view"
            view.mkdir()
            (view / "tests").mkdir()
            shutil.copyfile(R14_TEST, view / "tests" / "test_r14_integration.py")
            for name in ("SAINI_ID_CARD.py", "config_editor.py", "bsm_selector.py", "saini_config_path.py"):
                shutil.copyfile(R13 / name, view / name)
            (view / "option_c_modules").mkdir()
            (view / "baseline").mkdir()
            for name in OPTION_C:
                shutil.copyfile(R13 / "option_c_modules" / name, view / "option_c_modules" / name)
                shutil.copyfile(R13 / "baseline" / name, view / "baseline" / name)
            for name in ("SAINI_ID_CARD.py", "config_editor.py"):
                shutil.copyfile(R13 / "baseline" / name, view / "baseline" / name)
            r14_code, r14_output = run_py([str(view / "tests" / "test_r14_integration.py")])
            r14_state = "PASS" if r14_code == 0 else "FAIL"
        else:
            r14_code, r14_output, r14_state = 1, "", "MISSING"
        after_live = live_snapshot()
        after_r13 = hashes([R13 / name for name in r13_names])
        mapping, bsm = ([], ["workbook_copy=MISSING"])
        if copied.exists():
            mapping, bsm = bsm_and_headers(copied)
        changed = {
            "SAINI_ID_CARD.py": sha(DEST / "SAINI_ID_CARD.py"),
            "config_editor.py": sha(DEST / "config_editor.py"),
            "bsm_selector.py": sha(DEST / "bsm_selector.py"),
            "saini_config_path.py": sha(DEST / "saini_config_path.py"),
        }
        manifest = ["R19_SHA256_MANIFEST", "R13_BEFORE"]
        manifest.extend("%s %s" % (value, key) for key, value in before_r13.items())
        manifest.append("R13_AFTER")
        manifest.extend("%s %s" % (value, key) for key, value in after_r13.items())
        manifest.append("R19_CHANGED")
        manifest.extend("%s %s" % (value, DEST / key) for key, value in changed.items())
        manifest.append("R19_NEW %s %s" % (sha(DEST / "tests" / "test_r19_rules.py"), DEST / "tests" / "test_r19_rules.py"))
        if copied.exists():
            manifest.append("R19_WORKBOOK_COPY %s %s" % (sha(copied), copied))
        manifest.append("LIVE_BEFORE")
        manifest.extend("%s %s" % (value, key) for key, value in before_live.items())
        manifest.append("LIVE_AFTER")
        manifest.extend("%s %s" % (value, key) for key, value in after_live.items())
        safe = before_live == after_live and before_r13 == after_r13
        if not safe:
            status = "R19_BLOCKED_SAFETY_CHECK"
        elif code != 0:
            status = "R19_TEST_FAILURE"
        elif r13_state == "FAIL" or r4_state == "FAIL" or r14_state == "FAIL":
            status = "R19_TEST_FAILURE"
        elif r13_state == "MISSING" or r4_state == "MISSING" or r14_state == "MISSING" or not copied.exists():
            status = "R19_PARTIALLY_VERIFIED"
        else:
            status = "R19_DEVELOPMENT_PATCH_VERIFIED"
        results = [
            "R19_TEST_RESULTS",
            "R19_RULES exit=%s %s" % (code, original_count(r19_output)),
            r19_output,
            "R13_ORIGINAL %s exit=%s %s" % (r13_state, r13_code, original_count(r13_output)),
            r13_output,
            "R4_ORIGINAL %s exit=%s %s" % (r4_state, r4_code, original_count(r4_output)),
            r4_output,
            "R14_ORIGINAL %s exit=%s %s" % (r14_state, r14_code, original_count(r14_output)),
            r14_output,
        ]
        plan = [
            "R19_PROPOSED_MIGRATION_PLAN",
            "migration_executed=NO",
            "production_deployment=NOT_DONE",
            "1. Keep every duplicate header until the user chooses the authoritative column.",
            "2. Do not invent SCHOOLNAME values for BSM rows.",
            "3. Do not invent or rewrite missing template paths.",
            "4. Deploy no R19 file to the live project until a separate approval.",
        ]
        final = [
            "R19_FINAL_REPORT",
            "mode=DEVELOPMENT_ONLY",
            "status=" + status,
            "production_deployment=NOT_DONE",
            "live_files_modified=" + ("NO" if before_live == after_live else "YES"),
            "r13_original_modified=" + ("NO" if before_r13 == after_r13 else "YES"),
            "workbook_saved=NO",
            "student_records_opened=NO",
            "photographs_opened=NO",
            "card_generated=NO",
            "schema_migration=NOT_DONE",
            "R19_RULES=" + ("PASS" if code == 0 else "FAIL"),
            "R13_ORIGINAL=" + r13_state,
            "R4_ORIGINAL=" + r4_state,
            "R14_ORIGINAL=" + r14_state,
        ]
        (DEST / "R19_SHA256_MANIFEST.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        (DEST / "R19_DUPLICATE_HEADER_MAPPING.txt").write_text("\n".join(mapping) + "\n", encoding="utf-8")
        (DEST / "R19_BSM_VALIDATION_REPORT.txt").write_text("\n".join(bsm) + "\n", encoding="utf-8")
        (DEST / "R19_TEST_RESULTS.txt").write_text("\n".join(results), encoding="utf-8")
        (DEST / "R19_PROPOSED_MIGRATION_PLAN.txt").write_text("\n".join(plan) + "\n", encoding="utf-8")
        (DEST / "R19_FINAL_REPORT.txt").write_text("\n".join(final) + "\n", encoding="utf-8")
        print("\n".join(final))
    except Exception as exc:
        print("R19_BLOCKED_SAFETY_CHECK")
        print(type(exc).__name__ + ": " + str(exc))
        raise


if __name__ == "__main__":
    main()
