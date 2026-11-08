# -*- coding: utf-8 -*-
"""Apply class and subject from the link, then copy the saved Word file."""
import hashlib
import py_compile
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
LOAD = "document.addEventListener('DOMContentLoaded', function() { loadQuestions(); });"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    raw = APP.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if any("_sainiParams" in line for line in lines):
        print("ABORT")
        print("reason=ALREADY")
        return
    loads = [i for i, line in enumerate(lines) if line.strip() == LOAD]
    if len(loads) != 1:
        print("ABORT")
        print("reason=LOAD")
        print("count=%s" % len(loads))
        return
    actual = [i for i, line in enumerate(lines) if line == '        fname = f"ACTUAL_{code}.docx"']
    if len(actual) != 1 or lines[actual[0] + 1] != "        fpath = OUTPUT_DIR / fname":
        print("ABORT")
        print("reason=SAVE_ANCHOR")
        print("count=%s" % len(actual))
        return
    saves = [j for j in range(actual[0] + 1, min(actual[0] + 80, len(lines))) if lines[j].strip() == "doc.save(fpath)"]
    if len(saves) != 1:
        print("ABORT")
        print("reason=SAVE_CALL")
        print("count=%s" % len(saves))
        return
    pad = indent_of(lines[loads[0]])
    js = [
        pad + "document.addEventListener('DOMContentLoaded', function() {",
        pad + "    try {",
        pad + "        var _sainiParams = new URLSearchParams(window.location.search);",
        pad + '        var _sainiClass = _sainiParams.get("class_level");',
        pad + '        var _sainiSubject = _sainiParams.get("subject");',
        pad + '        if (_sainiClass) document.getElementById("class_level").value = _sainiClass;',
        pad + '        if (_sainiSubject) document.getElementById("subject").value = _sainiSubject;',
        pad + "    } catch (e) {}",
        pad + "    loadQuestions();",
        pad + "});",
    ]
    gap = indent_of(lines[saves[0]])
    py = [
        gap + "try:",
        gap + "    import shutil as _shutil",
        gap + '    _school_name = (request.form.get("school_code") or session.get("portal_school") or "SCHOOL").strip().upper()[:20]',
        gap + '    _job_root = TRIAL_DIR / "production_jobs"',
        gap + "    _picked = None",
        gap + "    if _job_root.is_dir():",
        gap + '        _cands = [p for p in _job_root.iterdir() if p.is_dir() and p.name.startswith("JOB-")]',
        gap + "        _cands.sort(key=lambda p: p.name)",
        gap + "        if len(_cands) == 1:",
        gap + "            _picked = _cands[0]",
        gap + "    if _picked is None:",
        gap + '        _picked = _job_root / "INBOX" / _school_name',
        gap + "    _picked.mkdir(parents=True, exist_ok=True)",
        gap + "    _shutil.copy2(fpath, _picked / fname)",
        gap + "except Exception:",
        gap + "    pass",
    ]
    updated = []
    for i, line in enumerate(lines):
        if i == loads[0]:
            updated.extend(js)
            continue
        updated.append(line)
        if i == saves[0]:
            updated.extend(py)
    newline = "\r\n" if b"\r\n" in raw else "\n"
    new_app = newline.join(updated)
    if raw.endswith(b"\n"):
        new_app += newline
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / "subject_wizard_dev_before_class_link.py"
    stamp = 2
    while bak.exists():
        bak = BACKUP_DIR / ("subject_wizard_dev_before_class_link_%s.py" % stamp)
        stamp += 1
    bak.write_bytes(raw)
    tmp = APP.with_name(APP.name + ".class_tmp")
    chk = APP.with_name(APP.name + ".class_check.pyc")
    try:
        tmp.write_bytes(new_app.encode("utf-8"))
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        chk.unlink(missing_ok=True)
    tmp.replace(APP)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    text = APP.read_text(encoding="utf-8")
    if text.count("_sainiParams") != 3 or text.count("_shutil.copy2(fpath, _picked / fname)") != 1:
        APP.write_bytes(raw)
        raise SystemExit("ABORT VERIFY")
    print("PATCH_OK")
    print("class_from_link=yes")
    print("job_copy=yes")
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("printer=not_started")


if __name__ == "__main__":
    main()
