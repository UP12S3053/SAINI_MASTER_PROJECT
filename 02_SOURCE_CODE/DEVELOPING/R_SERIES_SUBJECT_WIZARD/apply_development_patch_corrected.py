"""Create an isolated DEVELOPMENT copy with the Subject Enrollment Wizard.

Usage: python apply_development_patch.py --project-root PATH_TO_EXTRACTED_SAINI_TEACHER_TRIAL
The source app and source database are read only; all edits happen in a new sibling folder.
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

APP_NAME = "app_phase2_shortlisting_v2_trial_secure.py"
DEV_APP_NAME = "app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py"

HOME_LINK = '<a href="/admin/subjects">Subject Enrollment Wizard (DEVELOPMENT)</a>'

ROUTES = r'''

# ---------------- DEVELOPMENT-ONLY SUBJECT ENROLLMENT WIZARD ----------------
from secrets import token_urlsafe
from subject_wizard_core import (
    ALLOWED_CLASSES, ALLOWED_SUBJECTS, ALLOWED_CONTENT_TYPES,
    ALLOWED_TEMPLATE_POLICIES, ensure_schema, create_draft_enrollment,
    write_template_scaffold,
)

SUBJECT_WIZARD_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Subject Enrollment Wizard — DEVELOPMENT</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}
main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}
label{display:block;font-weight:bold;margin-top:14px}select,input,button{box-sizing:border-box;width:100%;padding:11px;margin-top:6px;font-size:16px}
button{background:#17365d;color:white;border:0;border-radius:6px;margin-top:20px;cursor:pointer}
.note{padding:12px;background:#fff5d6;border:1px solid #efd58a;border-radius:8px}.ok{background:#e8f7eb;padding:12px;border-radius:8px}.err{background:#fde8e8;padding:12px;border-radius:8px}
a{color:#17365d}
</style></head><body><main>
<p><a href="/">← Home</a></p><h1>Subject Enrollment Wizard</h1>
<div class="note"><b>DEVELOPMENT ONLY.</b> New enrollments are saved as DRAFT and remain inactive. This page does not add questions or activate a subject.</div>
{% if message %}<p class="ok">{{ message }}</p>{% endif %}{% if error %}<p class="err">{{ error }}</p>{% endif %}
<form method="post" action="/admin/subjects">
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
<label for="board_code">Board</label><select id="board_code" name="board_code" required>{% for b in boards %}<option value="{{ b['code'] }}" {% if b['code']=='HR' %}selected{% endif %}>{{ b['code'] }} — {{ b['name'] }}</option>{% endfor %}</select>
<label for="class_level">Class</label><select id="class_level" name="class_level" required>{% for c in classes %}<option value="{{ c }}" {% if c=='UKG' %}selected{% endif %}>{{ c }}</option>{% endfor %}</select>
<label for="subject">Subject</label><select id="subject" name="subject" required>{% for s in subjects %}<option value="{{ s }}" {% if s=='ENGLISH' %}selected{% endif %}>{{ s }}</option>{% endfor %}</select>
<label for="content_type">Content type</label><select id="content_type" name="content_type" required><option value="worksheet_images" selected>Worksheet images</option><option value="text_questions">Text questions</option><option value="mixed">Mixed questions and images</option></select>
<label for="template_policy">Template policy</label><select id="template_policy" name="template_policy" required><option value="separate_master" selected>Separate master template</option><option value="reuse_approved">Reuse an approved template (requires separate review)</option></select>
<button type="submit">Create DRAFT Enrollment</button></form>
<h2>Existing enrollments</h2><table><tr><th>Code</th><th>Board</th><th>Status</th><th>Activated</th></tr>{% for e in enrollments %}<tr><td>{{e['subject_code']}}</td><td>{{e['board_code']}}</td><td>{{e['status']}}</td><td>{{'YES' if e['activated'] else 'NO'}}</td></tr>{% endfor %}</table>
<p><small>Activation is intentionally not implemented in this patch. Add approved images/template and pass validation before a separately reviewed activation change.</small></p>
</main></body></html>"""

@app.route("/admin/subjects", methods=["GET", "POST"])
def subject_enrollment_wizard():
    # This app copy is the DEVELOPMENT environment. The explicit migration must run first.
    conn = None
    try:
        conn = get_db()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "subject_enrollments" not in tables:
            return ("Subject Wizard schema is missing. Run migrate_subject_enrollment.py against the DEVELOPMENT database first.", 503)
        message = None
        error = None
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not token or not hmac.compare_digest(token, session.get("subject_wizard_csrf", "")):
                error = "Security token expired. Reload the page and try again."
            else:
                try:
                    enrollment = create_draft_enrollment(
                        conn,
                        board_code=request.form.get("board_code", ""),
                        class_level=request.form.get("class_level", ""),
                        subject=request.form.get("subject", ""),
                        content_type=request.form.get("content_type", "worksheet_images"),
                        template_policy=request.form.get("template_policy", "separate_master"),
                        template_root="subject_templates",
                        created_by="authenticated_trial_admin",
                    )
                    template_root = TRIAL_DIR / "subject_templates"
                    try:
                        metadata = write_template_scaffold(template_root, enrollment)
                    except Exception:
                        conn.execute("DELETE FROM subject_enrollments WHERE id=? AND status='DRAFT' AND activated=0", (enrollment["id"],))
                        conn.commit()
                        raise
                    message = f"Created {enrollment['subject_code']} as DRAFT (inactive). Metadata: {metadata.relative_to(TRIAL_DIR)}"
                except sqlite3.IntegrityError:
                    error = "This board/class/subject enrollment already exists. No duplicate was created."
                except (ValueError, OSError, FileExistsError) as exc:
                    error = str(exc)
        boards = conn.execute("SELECT code,name FROM boards WHERE active=1 ORDER BY name").fetchall()
        enrollments = conn.execute("""SELECT e.subject_code,b.code AS board_code,e.status,e.activated
            FROM subject_enrollments e JOIN boards b ON b.id=e.board_id
            ORDER BY e.created_at DESC,e.id DESC""").fetchall()
        session["subject_wizard_csrf"] = token_urlsafe(32)
        return render_template_string(SUBJECT_WIZARD_HTML, boards=boards,
            classes=ALLOWED_CLASSES, subjects=ALLOWED_SUBJECTS,
            enrollments=enrollments, message=message, error=error,
            csrf_token=session["subject_wizard_csrf"])
    finally:
        if conn is not None:
            conn.close()
# -----------------------------------------------------------------------------
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", required=True, type=Path, help="Extracted SAINI_TEACHER_TRIAL directory")
    args = p.parse_args()
    src = args.project_root.resolve()
    if not src.is_dir(): raise SystemExit(f"Project folder not found: {src}")
    app_src = src / APP_NAME
    db_src = src / "paper_bank.db"
    if not app_src.is_file() or not db_src.is_file():
        raise SystemExit("Required app script or paper_bank.db is missing from project root")
    dev = src / "DEVELOPMENT_SUBJECT_WIZARD"
    if dev.exists():
        raise SystemExit(f"Refusing to overwrite existing folder: {dev}\nRename or back it up manually first.")
    dev.mkdir()
    try:
        # Copy only the files needed to run the app; originals are never edited.
        for name in (APP_NAME, "paper_bank.db", "PAPER.xlsx", "CODES.xlsx", "google_sheet_log.csv", ".saini_trial_started_utc", "worksheet_resizer.py"):
            item = src / name
            if item.is_file(): shutil.copy2(item, dev / name)
        if (src / "images").is_dir(): shutil.copytree(src / "images", dev / "images")
        # Include the new helper module required by the patched app.
        shutil.copy2(Path(__file__).resolve().parent / "subject_wizard_core.py", dev / "subject_wizard_core.py")
        # Use an independent DB copy and app path in the development folder.
        text = (dev / APP_NAME).read_text(encoding="utf-8")
        _saini_paper_setter_anchor = '<a href="/paper">Paper Setter</a>'
        _saini_anchor_count = text.count(_saini_paper_setter_anchor)
        _saini_home_count = text.count(HOME_LINK)
        if _saini_home_count > 1:
            raise SystemExit(
                "Home Link appears " + str(_saini_home_count) + " times; refusing to continue"
            )
        elif _saini_home_count == 0:
            if _saini_anchor_count != 1:
                raise SystemExit(
                    "Paper Setter anchor count is " + str(_saini_anchor_count) + ", expected 1; refusing to continue"
                )
            text = text.replace(
                _saini_paper_setter_anchor,
                _saini_paper_setter_anchor + "\n" + HOME_LINK,
                1,
            )
            if text.count(HOME_LINK) != 1 or text.count(_saini_paper_setter_anchor) != 1:
                raise SystemExit(
                    "Home Link insertion verification failed; refusing to continue"
                )
        elif _saini_home_count != 1:
            raise SystemExit(
                "Home Link count is " + str(_saini_home_count) + "; refusing to continue"
            )
        if "def subject_enrollment_wizard():" in text:
            raise SystemExit("Unexpected: source app already contains the wizard route")
        marker = 'if __name__ == "__main__":'
        if text.count(marker) != 1:
            raise SystemExit(
                "Startup marker count is " + str(text.count(marker)) + ", expected 1; refusing to continue"
            )
        if "def subject_enrollment_wizard(" in text:
            raise SystemExit(
                "subject_enrollment_wizard route already exists; refusing to continue"
            )
        if marker not in text: raise SystemExit("Cannot find app startup marker; no development app was written")
        text = text.replace(marker, ROUTES + "\n\n" + marker, 1)
        (dev / DEV_APP_NAME).write_text(text, encoding="utf-8")
        (dev / APP_NAME).unlink()  # avoid accidentally launching the unpatched name from the dev folder
        print("DEVELOPMENT COPY CREATED")
        print(f"Path: {dev}")
        print(f"Patched app: {DEV_APP_NAME}")
        print("Original app and original database were not modified.")
        print("Next: run the explicit migration command shown in README_DEVELOPMENT.md")
    except Exception:
        # Keep partial evidence rather than delete files silently; report exact folder.
        raise

if __name__ == "__main__": main()
