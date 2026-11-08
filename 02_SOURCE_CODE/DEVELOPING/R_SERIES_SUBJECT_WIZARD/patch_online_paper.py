import base64, hashlib, json, py_compile, zlib
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py")
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ODB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
MODULE = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\online_paper.py")
OA = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
OD = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BLOB = "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"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if sha(ORIG) != OA or sha(ODB) != OD:
        raise SystemExit("ABORT ORIGINAL")
    data = json.loads(zlib.decompress(base64.b64decode(BLOB)).decode("utf-8"))
    text = DEV.read_text(encoding="utf-8")
    updated = text
    for index, pair in enumerate(data["pairs"]):
        old, new = pair
        if updated.count(old) != 1:
            print("ABORT")
            print("reason=ANCHOR_%s" % index)
            print("count=%s" % updated.count(old))
            return
        updated = updated.replace(old, new, 1)
    BAK.mkdir(parents=True, exist_ok=True)
    backup = BAK / "school_data_before_online_paper.py"
    stamp = 2
    while backup.exists():
        backup = BAK / ("school_data_before_online_paper_%s.py" % stamp)
        stamp += 1
    raw = DEV.read_bytes()
    backup.write_bytes(raw)
    tmp = DEV.with_name("school_data.online_tmp")
    chk = DEV.with_name("school_data.online_check.pyc")
    mod_tmp = MODULE.with_name("online_paper.online_tmp")
    mod_chk = MODULE.with_name("online_paper.online_check.pyc")
    try:
        tmp.write_text(updated, encoding="utf-8")
        mod_tmp.write_text(data["module"], encoding="utf-8")
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
        py_compile.compile(str(mod_tmp), cfile=str(mod_chk), doraise=True)
        tmp.replace(DEV)
        mod_tmp.replace(MODULE)
    except Exception as exc:
        DEV.write_bytes(raw)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        for path in (tmp, chk, mod_tmp, mod_chk):
            if path.exists():
                path.unlink()
    if sha(ORIG) != OA or sha(ODB) != OD:
        DEV.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("backup=%s" % backup)
    print("module=%s" % MODULE)
    print("original_app=%s" % sha(ORIG))
    print("original_db=%s" % sha(ODB))
    print("printer=not_started")
    print("class_3_to_12=not_used")

if __name__ == "__main__":
    main()
