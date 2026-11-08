import ast
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
MODULE = Path(__file__).with_name("school_portal.py")
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
ROUTE = '''
@app.route("/school-login", methods=["GET", "POST"])
def school_portal_login():
    import school_portal
    return school_portal.portal_login(get_db, request, session)


@app.route("/portal", methods=["GET"])
def school_portal_home():
    import school_portal
    return school_portal.portal_home(get_db, request, session)


@app.route("/school-logout", methods=["POST"])
def school_portal_logout():
    import school_portal
    return school_portal.portal_logout(session, request)


'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decorator_name(node):
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def insert_guard(text):
    tree = ast.parse(text)
    guards = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        names = [decorator_name(item) for item in node.decorator_list]
        if "before_request" in names:
            guards.append(node)
    if len(guards) != 1:
        raise SystemExit("ABORT GUARD_COUNT %s" % len(guards))
    node = guards[0]
    if not node.body:
        raise SystemExit("ABORT GUARD_EMPTY")
    lines = text.splitlines()
    insert_at = node.body[0].lineno - 1
    indent = " " * node.body[0].col_offset
    snippet = [
        indent + 'if request.path in ("/school-login", "/school-logout", "/portal"):',
        indent + "    return None",
    ]
    for offset, line in enumerate(snippet):
        lines.insert(insert_at + offset, line)
    return lines


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
    if "/school-login" in text or "school_portal_login" in text:
        raise SystemExit("ABORT ALREADY_PATCHED")
    lines = insert_guard(text)
    matches = [
        index
        for index, line in enumerate(lines)
        if 'href="/admin/schools"' in line
        and "School Registration (DEVELOPMENT)" in line
    ]
    if len(matches) != 1:
        raise SystemExit("ABORT HOME_LINK_COUNT %s" % len(matches))
    marker = 'if __name__ == "__main__":'
    if text.count(marker) != 1:
        raise SystemExit("ABORT MAIN_COUNT")
    cloned = (
        lines[matches[0]]
        .replace('href="/admin/schools"', 'href="/school-login"', 1)
        .replace(
            "School Registration (DEVELOPMENT)",
            "School Portal (DEVELOPMENT)",
            1,
        )
    )
    lines.insert(matches[0] + 1, cloned)
    updated = newline.join(lines)
    if not updated.endswith(newline):
        updated += newline
    updated = updated.replace(marker, ROUTE.replace("\n", newline) + marker, 1)
    if updated.count('request.path in ("/school-login"') != 1:
        raise SystemExit("ABORT GUARD_INSERT")
    temporary = DEV.with_name(DEV.name + ".portal_tmp")
    compiled = DEV.with_name(DEV.name + ".portal_check.pyc")
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
    backup = BACKUP_DIR / "subject_wizard_dev_before_school_portal.py"
    stamp = 2
    while backup.exists():
        backup = BACKUP_DIR / ("subject_wizard_dev_before_school_portal_%s.py" % stamp)
        stamp += 1
    backup.write_bytes(raw)
    target = DEV.parent / "school_portal.py"
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
    print("paper_login_changed=no")
    print("activation_changed=no")


if __name__ == "__main__":
    main()
