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
MODULE = Path(__file__).with_name("school_registry.py")
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
ROUTE = '''
@app.route("/admin/schools", methods=["GET", "POST"])
def school_registration():
    import school_registry
    return school_registry.handle(get_db, request, session)


'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if sha256(ORIG) != ORIG_APP_HASH:
        raise SystemExit("ABORT ORIGINAL_APP")
    if sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL_DB")
    if not MODULE.is_file():
        raise SystemExit("ABORT MODULE_MISSING")
    raw = DEV.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    if "/admin/schools" in text or "school_registration" in text:
        raise SystemExit("ABORT ALREADY_PATCHED")
    lines = text.splitlines()
    matches = [
        index
        for index, line in enumerate(lines)
        if 'href="/admin/subjects"' in line
        and "Subject Enrollment Wizard (DEVELOPMENT)" in line
    ]
    if len(matches) != 1:
        shown = [
            line
            for line in lines
            if "admin/subjects" in line or "Enrollment Wizard" in line
        ]
        raise SystemExit(
            "ABORT HOME_LINK_COUNT %s\n%s" % (len(matches), "\n".join(shown[:12]))
        )
    marker = 'if __name__ == "__main__":'
    if text.count(marker) != 1:
        raise SystemExit("ABORT MAIN_COUNT")
    cloned = (
        lines[matches[0]]
        .replace('href="/admin/subjects"', 'href="/admin/schools"', 1)
        .replace(
            "Subject Enrollment Wizard (DEVELOPMENT)",
            "School Registration (DEVELOPMENT)",
            1,
        )
    )
    lines.insert(matches[0] + 1, cloned)
    updated = newline.join(lines)
    if not updated.endswith(newline):
        updated += newline
    route = ROUTE.replace("\n", newline)
    updated = updated.replace(marker, route + marker, 1)
    target = DEV.parent / "school_registry.py"
    temporary = DEV.with_name(DEV.name + ".school_tmp")
    compiled = DEV.with_name(DEV.name + ".school_check.pyc")
    temporary.write_bytes(updated.encode("utf-8"))
    try:
        py_compile.compile(str(temporary), cfile=str(compiled), doraise=True)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        if compiled.exists():
            compiled.unlink()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / "subject_wizard_dev_before_school_registry.py"
    stamp = 2
    while backup.exists():
        backup = BACKUP_DIR / (
            "subject_wizard_dev_before_school_registry_%s.py" % stamp
        )
        stamp += 1
    backup.write_bytes(raw)
    shutil.copy2(MODULE, target)
    temporary.replace(DEV)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        DEV.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("backup=%s" % backup)
    print("module=%s" % target)
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("activation_changed=no")


if __name__ == "__main__":
    main()
