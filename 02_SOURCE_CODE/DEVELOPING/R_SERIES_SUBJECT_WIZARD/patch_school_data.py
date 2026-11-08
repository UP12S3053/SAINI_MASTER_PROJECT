import hashlib
import py_compile
import shutil
from pathlib import Path

DEV = Path(
    r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD"
    r"\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py"
)
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
MODULE = Path(__file__).with_name("school_data.py")
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
GUARD = 'if request.path in ("/school-login", "/school-logout", "/portal"):'
GUARD_NEW = 'if request.path in ("/school-login", "/school-logout", "/portal", "/portal/data"):'
PORTAL_MARK = "Papers, ID cards, and printing stay closed while this school is DRAFT.</p>"
PORTAL_LINK = PORTAL_MARK + '\n<p><a href="/portal/data">School data</a></p>'
ROUTE = '''
@app.route("/portal/data", methods=["GET", "POST"])
def school_data_page():
    import school_data
    return school_data.handle(get_db, request, session)


'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    if not MODULE.is_file():
        raise SystemExit("ABORT MODULE_MISSING")
    portal = DEV.parent / "school_portal.py"
    raw = DEV.read_bytes()
    portal_raw = portal.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    portal_text = portal_raw.decode("utf-8")
    if "/portal/data" in text or "school_data_page" in text:
        raise SystemExit("ABORT ALREADY_PATCHED")
    if text.count(GUARD) != 1:
        raise SystemExit("ABORT GUARD_COUNT %s" % text.count(GUARD))
    if portal_text.count(PORTAL_MARK) != 1:
        raise SystemExit("ABORT PORTAL_MARK")
    marker = 'if __name__ == "__main__":'
    if text.count(marker) != 1:
        raise SystemExit("ABORT MAIN_COUNT")
    updated = text.replace(GUARD, GUARD_NEW, 1)
    updated = updated.replace(marker, ROUTE.replace("\n", newline) + marker, 1)
    portal_updated = portal_text.replace(PORTAL_MARK, PORTAL_LINK, 1)
    if updated.count('"/portal/data"') != 2:
        raise SystemExit("ABORT ROUTE_COUNT")
    temporary = DEV.with_name(DEV.name + ".data_tmp")
    compiled = DEV.with_name(DEV.name + ".data_check.pyc")
    temporary.write_bytes(updated.encode("utf-8"))
    try:
        py_compile.compile(str(temporary), cfile=str(compiled), doraise=True)
        py_compile.compile(str(MODULE), doraise=True)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        if compiled.exists():
            compiled.unlink()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / "subject_wizard_dev_before_school_data.py"
    stamp = 2
    while backup.exists():
        backup = BACKUP_DIR / ("subject_wizard_dev_before_school_data_%s.py" % stamp)
        stamp += 1
    backup.write_bytes(raw)
    portal_backup = BACKUP_DIR / "school_portal_before_school_data.py"
    portal_backup.write_bytes(portal_raw)
    shutil.copy2(MODULE, DEV.parent / "school_data.py")
    portal.write_bytes(portal_updated.encode("utf-8"))
    temporary.replace(DEV)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        DEV.write_bytes(raw)
        portal.write_bytes(portal_raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("backup=%s" % backup)
    print("module=%s" % (DEV.parent / "school_data.py"))
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("paper_login_changed=no")
    print("activation_changed=no")


if __name__ == "__main__":
    main()
