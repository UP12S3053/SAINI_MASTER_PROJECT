# -*- coding: utf-8 -*-
"""Turn Make paper into a link that opens the existing Paper Setter."""
import hashlib
import py_compile
from pathlib import Path

DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
APP = DEV / "app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py"
DATA = DEV / "school_data.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
OLD = """        if str(row[0]).upper() in online_names:
            action_cell = (
                '<form method="post"><input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
                + '<input type="hidden" name="action" value="makepaper">'
                + '<input type="hidden" name="class_name" value="' + _esc(row[0]) + '">'
                + '<input type="hidden" name="subject" value="' + _esc(row[1]) + '">'
                + '<input name="sheets" value="5" inputmode="numeric" style="width:80px" required>'
                + '<button type="submit">Make paper</button></form>'
            )"""
NEW = """        if str(row[0]).upper() in online_names:
            action_cell = (
                '<a href="/paper?class_level=' + _esc(row[0]) + '&subject=' + _esc(row[1]) + '">Make paper</a>'
            )"""
ANCHOR = '    if request.path in ("/school-login", "/school-logout", "/portal", "/portal/data"):'
EXTRA = [
    '    if session.get("portal_school") and (',
    '        request.path == "/paper"',
    '        or request.path in ("/generate", "/get_questions", "/save", "/validate")',
    '        or request.path.startswith("/question_image/")',
    '        or request.path.startswith("/actual/")',
    '        or request.path.startswith("/download/")',
    "    ):",
    "        return None",
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    data = DATA.read_text(encoding="utf-8")
    if 'session.get("portal_school")' not in data:
        print("ABORT")
        print("reason=SESSION")
        return
    if data.count(OLD) != 1:
        print("ABORT")
        print("reason=BUTTON")
        print("count=%s" % data.count(OLD))
        return
    raw = APP.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if any('request.path == "/paper"' in line for line in lines):
        print("ABORT")
        print("reason=ALREADY")
        return
    hits = [index for index, line in enumerate(lines) if line == ANCHOR]
    if len(hits) != 1 or lines[hits[0] + 1] != "        return None":
        print("ABORT")
        print("reason=GUARD")
        print("count=%s" % len(hits))
        return
    at = hits[0] + 2
    updated = lines[:at] + EXTRA + lines[at:]
    newline = "\r\n" if b"\r\n" in raw else "\n"
    new_app = newline.join(updated)
    if raw.endswith(b"\n"):
        new_app += newline
    new_data = data.replace(OLD, NEW, 1)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    app_bak = BACKUP_DIR / "subject_wizard_dev_before_open_setter.py"
    data_bak = BACKUP_DIR / "school_data_before_open_setter.py"
    stamp = 2
    while app_bak.exists():
        app_bak = BACKUP_DIR / ("subject_wizard_dev_before_open_setter_%s.py" % stamp)
        data_bak = BACKUP_DIR / ("school_data_before_open_setter_%s.py" % stamp)
        stamp += 1
    app_bak.write_bytes(raw)
    data_bak.write_bytes(DATA.read_bytes())
    app_tmp = APP.with_name(APP.name + ".open_tmp")
    data_tmp = DATA.with_name(DATA.name + ".open_tmp")
    app_chk = APP.with_name(APP.name + ".open_check.pyc")
    data_chk = DATA.with_name(DATA.name + ".open_check.pyc")
    try:
        app_tmp.write_bytes(new_app.encode("utf-8"))
        data_tmp.write_bytes(new_data.encode("utf-8"))
        py_compile.compile(str(app_tmp), cfile=str(app_chk), doraise=True)
        py_compile.compile(str(data_tmp), cfile=str(data_chk), doraise=True)
    except Exception as exc:
        app_tmp.unlink(missing_ok=True)
        data_tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        app_chk.unlink(missing_ok=True)
        data_chk.unlink(missing_ok=True)
    app_tmp.replace(APP)
    data_tmp.replace(DATA)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        DATA.write_bytes(data_bak.read_bytes())
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("setter=opens_from_school_login")
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("printer=not_started")


if __name__ == "__main__":
    main()
