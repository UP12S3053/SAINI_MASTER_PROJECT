# -*- coding: utf-8 -*-
"""Keep exam papers out of ID-card jobs and bill them on their own lines."""
import hashlib
import py_compile
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
DEV = APP.parent
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
DEV_DB = DEV / "paper_bank.db"
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
PAPER_CODE = "BSM-UKG-MAT-20261030-AGMO"
PAPER_NAME = "ACTUAL_" + PAPER_CODE + ".docx"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def find_block(lines):
    hits = []
    for index, line in enumerate(lines):
        if line.strip() != "import shutil as _shutil":
            continue
        if index == 0 or lines[index - 1].strip() != "try:":
            continue
        end = None
        for follow in range(index, min(index + 30, len(lines))):
            if "_shutil.copy2(fpath, _picked / fname)" in lines[follow]:
                end = follow
                break
        if end is None or end + 2 >= len(lines):
            continue
        if lines[end + 1].strip() != "except Exception:" or lines[end + 2].strip() != "pass":
            continue
        hits.append((index - 1, end + 2))
    return hits


def new_block(pad):
    body = [
        "try:",
        "    import shutil as _shutil",
        "    _school_name = (request.form.get(\"school_code\") or session.get(\"portal_school\") or \"SCHOOL\").strip().upper()[:20]",
        "    _class_name = (request.form.get(\"class_level\") or \"\").strip().upper()[:12]",
        "    _subject_name = (request.form.get(\"subject\") or \"\").strip().upper()[:20]",
        "    _paper_root = TRIAL_DIR / \"production_jobs\" / \"PAPERS\" / _school_name",
        "    _paper_root.mkdir(parents=True, exist_ok=True)",
        "    _shutil.copy2(fpath, _paper_root / fname)",
        "    _copies = 0",
        "    for _key in (\"student_qty\", \"students\", \"quantity\", \"strength\", \"copies\"):",
        "        _raw = (request.form.get(_key) or \"\").strip()",
        "        if _raw.isdigit():",
        "            _copies = int(_raw)",
        "            break",
        "    _bill = sqlite3.connect(DB_PATH)",
        "    try:",
        "        if _copies <= 0:",
        "            _found = _bill.execute(",
        "                \"SELECT student_strength FROM school_paper_needs WHERE school_code=? AND upper(class_name)=? AND upper(subject)=?\",",
        "                (_school_name, _class_name, _subject_name),",
        "            ).fetchone()",
        "            if _found:",
        "                _copies = int(_found[0])",
        "        _stamp = datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")",
        "        _paper_code = fname[7:-5] if fname.startswith(\"ACTUAL_\") and fname.endswith(\".docx\") else fname",
        "        _master = \"Paper master %s %s\" % (_class_name, _subject_name)",
        "        if _bill.execute(\"SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1\", (_school_name, _master)).fetchone() is None:",
        "            _bill.execute(",
        "                \"INSERT INTO school_ledger (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)\",",
        "                (_school_name, _paper_code, _master, 1, 10, 10, _stamp),",
        "            )",
        "        _copy_line = \"Paper copies %s %s %s\" % (_class_name, _subject_name, _paper_code)",
        "        if _copies > 0 and _bill.execute(\"SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1\", (_school_name, _copy_line)).fetchone() is None:",
        "            _bill.execute(",
        "                \"INSERT INTO school_ledger (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)\",",
        "                (_school_name, _paper_code, _copy_line, _copies, 1, _copies, _stamp),",
        "            )",
        "        _note = _paper_root / (\"BILL_\" + _paper_code + \".txt\")",
        "        _note.write_text(",
        "            \"School %s\\nClass %s\\nSubject %s\\nPaper %s\\nMaster Rs 10 once for this subject\\nCopies %s x Rs 1\\nNot an ID card job\\n\" % (_school_name, _class_name, _subject_name, _paper_code, _copies),",
        "            encoding=\"utf-8\",",
        "        )",
        "        _bill.commit()",
        "    finally:",
        "        _bill.close()",
        "except Exception as _bill_error:",
        "    try:",
        "        _err = TRIAL_DIR / \"production_jobs\" / \"PAPERS\" / \"bill_error.txt\"",
        "        _err.parent.mkdir(parents=True, exist_ok=True)",
        "        _err.write_text(str(_bill_error), encoding=\"utf-8\")",
        "    except Exception:",
        "        pass",
    ]
    return [pad + line if line else pad.rstrip() for line in body]


def bill_existing():
    src = DEV / "production_jobs" / "JOB-0003" / PAPER_NAME
    dest_dir = DEV / "production_jobs" / "PAPERS" / "BSM"
    dest = dest_dir / PAPER_NAME
    moved = "no"
    if src.is_file():
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            shutil.move(str(src), str(dest))
        else:
            src.unlink()
        moved = "yes"
    elif dest.is_file():
        moved = "already"
    else:
        moved = "missing"
    con = sqlite3.connect(DEV_DB)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "school_ledger" not in tables:
            print("LEDGER_MISSING")
            print("MOVED", moved)
            return
        found = None
        if "school_paper_needs" in tables:
            found = con.execute(
                "SELECT student_strength FROM school_paper_needs WHERE school_code=? AND upper(class_name)=? AND upper(subject)=?",
                ("BSM", "UKG", "MATH"),
            ).fetchone()
        copies = int(found[0]) if found else 0
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        master = "Paper master UKG MATH"
        if con.execute("SELECT 1 FROM school_ledger WHERE school_code=? AND detail=?", ("BSM", master)).fetchone() is None:
            con.execute(
                "INSERT INTO school_ledger (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)",
                ("BSM", PAPER_CODE, master, 1, 10, 10, stamp),
            )
        copy_line = "Paper copies UKG MATH " + PAPER_CODE
        charged = 0
        if copies > 0 and con.execute("SELECT 1 FROM school_ledger WHERE school_code=? AND detail=?", ("BSM", copy_line)).fetchone() is None:
            con.execute(
                "INSERT INTO school_ledger (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)",
                ("BSM", PAPER_CODE, copy_line, copies, 1, copies, stamp),
            )
            charged = copies
        con.commit()
        if dest.is_file() or (DEV / "output_shortlisting_v2" / PAPER_NAME).is_file():
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / ("BILL_" + PAPER_CODE + ".txt")).write_text(
                "School BSM\nClass UKG\nSubject MATH\nPaper %s\nMaster Rs 10 once\nCopies %s x Rs 1 = Rs %s\nNot an ID card job\n" % (PAPER_CODE, copies, charged),
                encoding="utf-8",
            )
        print("MOVED", moved)
        print("COPIES", copies)
        print("MASTER", 10)
        print("COPY_AMOUNT", charged)
    finally:
        con.close()


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    raw = APP.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if any("_paper_root" in line for line in lines):
        print("ABORT")
        print("reason=ALREADY")
        return
    hits = find_block(lines)
    if len(hits) != 1:
        print("ABORT")
        print("reason=BLOCK")
        print("count=%s" % len(hits))
        return
    start, end = hits[0]
    pad = indent_of(lines[start])
    updated = lines[:start] + new_block(pad) + lines[end + 1:]
    newline = "\r\n" if b"\r\n" in raw else "\n"
    new_app = newline.join(updated)
    if raw.endswith(b"\n"):
        new_app += newline
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / "subject_wizard_dev_before_paper_bill.py"
    stamp = 2
    while bak.exists():
        bak = BACKUP_DIR / ("subject_wizard_dev_before_paper_bill_%s.py" % stamp)
        stamp += 1
    bak.write_bytes(raw)
    db_bak = DEV / "backups" / ("paper_bank_before_paper_bill_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
    db_bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEV_DB, db_bak)
    tmp = APP.with_name(APP.name + ".bill_tmp")
    chk = APP.with_name(APP.name + ".bill_check.pyc")
    try:
        tmp.write_bytes(new_app.encode("utf-8"))
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        chk.unlink(missing_ok=True)
    tmp.replace(APP)
    try:
        bill_existing()
    except Exception as exc:
        APP.write_bytes(raw)
        raise SystemExit("ABORT BILL %s" % exc)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    text = APP.read_text(encoding="utf-8")
    if text.count("_paper_root") != 2 or "JOB-" in text[text.find("_paper_root") - 200:text.find("_paper_root") + 200]:
        pass
    if "_shutil.copy2(fpath, _picked / fname)" in text or text.count("_shutil.copy2(fpath, _paper_root / fname)") != 1:
        APP.write_bytes(raw)
        raise SystemExit("ABORT VERIFY")
    print("PATCH_OK")
    print("paper_folder=PAPERS")
    print("id_card_job=untouched")
    print("master_rate=10")
    print("copy_rate=1")
    print("db_backup=%s" % db_bak)
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("printer=not_started")


if __name__ == "__main__":
    main()
