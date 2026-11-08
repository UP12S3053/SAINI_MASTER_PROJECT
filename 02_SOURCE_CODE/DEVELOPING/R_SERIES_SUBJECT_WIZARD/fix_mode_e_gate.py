# -*- coding: utf-8 -*-
"""Mode E uses local Excel. Option C stays only for slip OCR modes."""
from pathlib import Path

ROOTS = [
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels"),
    Path(r"D:\SAINI_TEACHER_TRIAL"),
]
OLD = 'if str(workflow_mode or "").strip().upper() == "B":'
NEW = 'if str(workflow_mode or "").strip().upper() in ("B", "E"):'
NOTE = "Mode B/E authorization: hash-bound Local Excel master roster; Option C stays for slip OCR only."


def main():
    hits = []
    for root in ROOTS:
        if root.is_dir():
            hits.extend(root.rglob("MAIN_ASSISTANT.py"))
    if not hits:
        raise SystemExit("ABORT MAIN_ASSISTANT.py not found")
    changed = 0
    for path in hits:
        text = path.read_text(encoding="utf-8")
        if 'in ("B", "E")' in text:
            print("ALREADY", path)
            continue
        if OLD not in text:
            print("SKIP", path)
            continue
        text = text.replace(OLD, NEW, 1)
        text = text.replace(
            "Mode B authorization: hash-bound Local Excel master roster; Option C/D Gate unchanged.",
            NOTE,
            1,
        )
        path.write_text(text, encoding="utf-8")
        changed += 1
        print("MODE_E_OK", path)
    if changed == 0:
        raise SystemExit("ABORT no file patched")
    print("DONE")


if __name__ == "__main__":
    main()
