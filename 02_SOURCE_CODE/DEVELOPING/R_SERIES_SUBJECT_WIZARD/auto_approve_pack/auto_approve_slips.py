# -*- coding: utf-8 -*-
"""Auto-approve slip audio when SAINI_AUTO_APPROVE=1."""
from pathlib import Path

ROOTS = [
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels"),
    Path(r"D:\SAINI_TEACHER_TRIAL"),
]
OLD = '''        print(f"\\nPRIYAMVADA voice audio ready for {kind_label}:")
        print(audio_file)
        print("Please listen to the complete audio and verify this batch before approving.")
        choice = input(f"Approve this {kind_label} batch after listening? [Y/N]: ").strip().upper()
        if choice != "Y":'''
NEW = '''        print(f"\\nPRIYAMVADA voice audio ready for {kind_label}:")
        print(audio_file)
        if __import__("os").environ.get("SAINI_AUTO_APPROVE") == "1":
            print("AUTO APPROVE on. Barrier skipped.")
            choice = "Y"
        else:
            print("Please listen to the complete audio and verify this batch before approving.")
            choice = input(f"Approve this {kind_label} batch after listening? [Y/N]: ").strip().upper()
        if choice != "Y":'''


def main():
    hits = []
    for root in ROOTS:
        if root.is_dir():
            hits.extend(root.rglob("slip_ocr_OPTION_C_CANDIDATE.py"))
    if not hits:
        raise SystemExit("ABORT file missing")
    changed = 0
    for path in hits:
        text = path.read_text(encoding="utf-8")
        if "SAINI_AUTO_APPROVE" in text:
            print("ALREADY", path)
            continue
        if OLD not in text:
            print("SKIP", path)
            continue
        path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
        print("AUTO_OK", path)
        changed += 1
    if changed == 0:
        raise SystemExit("ABORT nothing patched")
    print("DONE")


if __name__ == "__main__":
    main()
