import hashlib
import py_compile
from pathlib import Path

DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py")
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX\school_data_before_final_output.py")
APP = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BANK = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
PAIRS = [
(
'if part not in ("paper", "id", "result"):',
'if part not in ("paper", "id", "result", "output"):',
),
(
'{"paper": "Paper data", "id": "ID card data", "result": "Result data"}',
'{"paper": "Paper data", "id": "ID card data", "result": "Result data", "output": "Final output"}',
),
(
"""            + '<button type="submit">Save marks</button></form>'
        )
    else:""",
"""            + '<button type="submit">Save marks</button></form>'
        )
    elif part == "output":
        student_count = conn.execute(
            "SELECT COUNT(*) FROM school_students WHERE school_code=?", (school_code,)
        ).fetchone()[0]
        mark_count = conn.execute(
            "SELECT COUNT(*) FROM school_marks WHERE school_code=?", (school_code,)
        ).fetchone()[0]
        body = (
            head
            + "<p>Preview only for " + _esc(school_code) + ". No PDF, no print, and no approval. Status stays DRAFT.</p>"
            + "<table><tr><th>Item</th><th>Count</th></tr>"
            + "<tr><td>Paper plans</td><td>" + str(len(papers)) + "</td></tr>"
            + "<tr><td>ID card students</td><td>" + str(student_count) + "</td></tr>"
            + "<tr><td>Result marks</td><td>" + str(mark_count) + "</td></tr></table>"
            + "<h2>Paper plans</h2><table><tr><th>Class</th><th>Subject</th><th>Strength</th><th>Max</th></tr>"
            + paper_rows + "</table>"
        )
    else:""",
),
(
"""            + '<a class="go" href="/portal/data?part=result">3. Result data</a>'
        )""",
"""            + '<a class="go" href="/portal/data?part=result">3. Result data</a>'
            + '<a class="go" href="/portal/data?part=output">4. Final output</a>'
        )""",
),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sha(ORIG) != APP or sha(DB) != BANK:
        raise SystemExit("ABORT ORIGINAL")
    text = DEV.read_text(encoding="utf-8")
    for old, _new in PAIRS:
        if text.count(old) != 1:
            raise SystemExit("ABORT MATCH " + str(text.count(old)))
    updated = text
    for old, new in PAIRS:
        updated = updated.replace(old, new, 1)
    if updated.count("part=output") != 1 or "Preview only" not in updated:
        raise SystemExit("ABORT OUTPUT")
    temporary = DEV.with_name(DEV.name + ".output_tmp")
    compiled = DEV.with_name(DEV.name + ".output_check.pyc")
    temporary.write_text(updated, encoding="utf-8", newline="\n")
    try:
        py_compile.compile(str(temporary), cfile=str(compiled), doraise=True)
    finally:
        if compiled.exists():
            compiled.unlink()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    BAK.write_bytes(DEV.read_bytes())
    DEV.write_text(updated, encoding="utf-8", newline="\n")
    temporary.unlink()
    if sha(ORIG) != APP or sha(DB) != BANK:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("final_output=preview")
    print("approval=locked")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")


if __name__ == "__main__":
    main()
