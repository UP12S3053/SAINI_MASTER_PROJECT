# -*- coding: utf-8 -*-
"""Correct School Master field names. The installer shifted them."""
import re
from pathlib import Path

DESK = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_master_desk.py")
FIELDS = '''FIELDS = {
    "code": "school_code",
    "name": "school_name",
    "mobile": "mobile",
    "principal": "principal",
    "address": "address",
}
'''
BUTTONS = '''BUTTONS = {"validate": "validate", "save": "save"}
'''


def main():
    text = DESK.read_text(encoding="utf-8")
    text, n1 = re.subn(r"FIELDS = \{.*?\}\n", FIELDS, text, count=1, flags=re.S)
    text, n2 = re.subn(r"BUTTONS = \{.*?\}\n", BUTTONS, text, count=1, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise SystemExit("ABORT block missing")
    DESK.write_text(text, encoding="utf-8")
    print("FIELD code school_code")
    print("FIELD name school_name")
    print("FIELD mobile mobile")
    print("FIELD principal principal")
    print("FIELD address address")
    print("SCHOOL_FIELDS_FIXED")


if __name__ == "__main__":
    main()
