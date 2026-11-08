# -*- coding: utf-8 -*-
"""Add the ID Cards button to the development paper system. Run once."""
import hashlib
import py_compile
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
HERE = Path(__file__).resolve().parent
MODULE = HERE / "idcard_desk.py"
BACKUP = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
HOOK = "\nimport idcard_desk as _idcard_desk\n_idcard_desk.attach(app)\n"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def originals_untouched():
    if ORIG.is_file() and sha256(ORIG) != ORIG_APP_HASH:
        raise SystemExit("ABORT original app changed")
    if ORIG_DB.is_file() and sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT original database changed")
    print("ORIGINAL untouched")


def home_button(text):
    if "/saini/idcard" in text:
        print("HOME already")
        return text
    marker = "Complete paper order"
    pos = text.find(marker)
    if pos < 0:
        print("HOME missing")
        return text
    start = text.rfind("<", 0, pos)
    end = text.find(">", pos)
    if start < 0 or end < 0 or "/saini/order" not in text[start:end + 1]:
        print("HOME missing")
        return text
    tag = text[start:end + 1]
    added = tag.replace("/saini/order", "/saini/idcard", 1).replace(marker, "ID Cards", 1)
    print("HOME yes")
    return text[:end + 1] + added + text[end + 1:]


def attach_hook(text):
    if "_idcard_desk.attach(app)" in text:
        print("HOOK already")
        return text
    for marker in ('if __name__ == "__main__":', "if __name__ == '__main__':"):
        at = text.find(marker)
        if at >= 0:
            print("HOOK yes")
            return text[:at] + HOOK + text[at:]
    print("HOOK end")
    return text + HOOK


def main():
    if not MODULE.is_file():
        raise SystemExit("ABORT missing idcard_desk.py")
    if not APP.is_file():
        raise SystemExit("ABORT missing " + str(APP))
    originals_untouched()
    py_compile.compile(str(MODULE), doraise=True)
    shutil.copy2(MODULE, APP.parent / "idcard_desk.py")
    BACKUP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(APP, BACKUP / ("subject_wizard_dev_before_idcard_%s.py" % stamp))
    text = attach_hook(home_button(APP.read_text(encoding="utf-8")))
    APP.write_text(text, encoding="utf-8")
    py_compile.compile(str(APP), doraise=True)
    originals_untouched()
    print("IDCARD_OK")
    print("page=/saini/idcard")


if __name__ == "__main__":
    main()
