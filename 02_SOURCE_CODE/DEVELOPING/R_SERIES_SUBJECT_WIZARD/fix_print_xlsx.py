# -*- coding: utf-8 -*-
from pathlib import Path

DESK = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\order_desk.py")
text = DESK.read_text(encoding="utf-8")
old = (
    '    target = folder / "production_jobs" / "PAPERS" / school / "PAPER_PRINT.xlsx"\n'
    "    return write_xlsx(target, table)\n"
)
new = (
    '    target = folder / "production_jobs" / "PAPERS" / school / "PAPER_PRINT.xlsx"\n'
    "    write_xlsx(target, table)\n"
    '    official = PRINT_SCRIPT.parent / "PRINT.xlsx"\n'
    "    write_xlsx(official, table)\n"
    "    return official\n"
)
if "official = PRINT_SCRIPT.parent" in text:
    print("ALREADY")
elif old not in text:
    raise SystemExit("ABORT print excel block missing")
else:
    text = text.replace(old, new, 1)
    text = text.replace(">Print complete order<", ">Make PRINT.xlsx and print<", 1)
    DESK.write_text(text, encoding="utf-8")
    print("PRINT_XLSX_OK")
