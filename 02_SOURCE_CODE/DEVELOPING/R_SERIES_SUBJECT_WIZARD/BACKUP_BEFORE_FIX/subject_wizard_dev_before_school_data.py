from flask import Flask, render_template_string, request, jsonify, send_file, session, redirect, url_for
import sqlite3
import json
import os
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from openpyxl import load_workbook

app = Flask(__name__)

# Trial-only storage: every writable data path stays beside this copied app.
TRIAL_DIR = Path(__file__).resolve().parent
EXCEL_PATH = TRIAL_DIR / "PAPER.xlsx"
SHEET_NAME = "SCHOOL MASTER"
DB_PATH = TRIAL_DIR / "paper_bank.db"
OUTPUT_DIR = TRIAL_DIR / "output_shortlisting_v2"
OUTPUT_DIR.mkdir(exist_ok=True)
TRIAL_START_FILE = TRIAL_DIR / ".saini_trial_started_utc"
TRIAL_DAYS = 7
app.secret_key = os.environ.get("SAINI_SESSION_SECRET", "")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SAINI_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

LOGIN_HTML = """<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Saini Teacher Trial Login</title><style>body{font-family:Arial,sans-serif;max-width:420px;margin:12vh auto;padding:20px;background:#f5f7fa}form{background:white;padding:24px;border-radius:12px;box-shadow:0 2px 12px #0001}input,button{box-sizing:border-box;width:100%;padding:12px;margin-top:12px;font-size:16px}button{background:#17365d;color:white;border:0;border-radius:6px}p{color:#a00}</style></head><body><form method=\"post\"><h2>Saini Paper System</h2><p>Teacher Trial — Login Required</p>{% if error %}<p>{{ error }}</p>{% endif %}<label for=\"password\">Trial password</label><input id=\"password\" name=\"password\" type=\"password\" required autocomplete=\"current-password\"><button type=\"submit\">Login</button></form></body></html>"""

def _trial_started_at():
    # Trial clock starts only on first request; file lives in the trial folder.
    try:
        raw = TRIAL_START_FILE.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(raw)
    except FileNotFoundError:
        started = datetime.now(timezone.utc)
        try:
            with TRIAL_START_FILE.open("x", encoding="utf-8") as f:
                f.write(started.isoformat())
            return started
        except FileExistsError:
            return datetime.fromisoformat(TRIAL_START_FILE.read_text(encoding="utf-8").strip())

def _trial_expired():
    started = _trial_started_at()
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= started + timedelta(days=TRIAL_DAYS)

@app.before_request
def _require_trial_login():
    if request.path in ("/school-login", "/school-logout", "/portal"):
        return None
    if not os.environ.get("SAINI_TRIAL_PASSWORD") or not app.secret_key:
        return ("Trial setup incomplete. Set SAINI_TRIAL_PASSWORD and SAINI_SESSION_SECRET in the server environment, then restart.", 503)
    if request.endpoint == "trial_login" or request.endpoint == "static":
        return None
    if _trial_expired():
        session.clear()
        return ("This 7-day teacher trial has expired. Contact the administrator.", 403)
    if not session.get("saini_teacher_authenticated"):
        return redirect(url_for("trial_login", next=request.path))
    return None

@app.route("/login", methods=["GET", "POST"])
def trial_login():
    if not os.environ.get("SAINI_TRIAL_PASSWORD") or not app.secret_key:
        return ("Trial setup incomplete. Set SAINI_TRIAL_PASSWORD and SAINI_SESSION_SECRET in the server environment, then restart.", 503)
    if _trial_expired():
        return ("This 7-day teacher trial has expired. Contact the administrator.", 403)
    error = None
    if request.method == "POST":
        submitted = request.form.get("password", "")
        expected = os.environ.get("SAINI_TRIAL_PASSWORD", "")
        if hmac.compare_digest(submitted, expected):
            session.clear()
            session.permanent = True
            session["saini_teacher_authenticated"] = True
            target = request.args.get("next", "/")
            if not target.startswith("/") or target.startswith("//"):
                target = "/"
            return redirect(target)
        error = "Incorrect trial password. Please try again."
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout", methods=["POST"])
def trial_logout():
    session.clear()
    return redirect(url_for("trial_login"))

HOME_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Saini Paper System</title>
<style>
body { font-family: Arial; max-width: 600px; margin: 60px auto; text-align: center; }
a { display: block; margin: 20px; padding: 20px; background: #27ae60; color: white; text-decoration: none; font-size: 20px; border-radius: 8px; }
a:hover { background: #219a52; }
</style>
</head>
<body>
<h1>Saini Paper System</h1>
<a href="/school">School Master</a>
<a href="/paper">Paper Setter</a>
<a href="/admin/subjects">Subject Enrollment Wizard (DEVELOPMENT)</a>
<a href="/admin/schools">School Registration (DEVELOPMENT)</a>
<a href="/school-login">School Portal (DEVELOPMENT)</a>
</body>
</html>"""

SCHOOL_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>School Master</title>
<style>
body { font-family: Arial; max-width: 600px; margin: 40px auto; padding: 20px; }
label { display: block; margin-top: 15px; font-weight: bold; }
input, select, button { width: 100%; padding: 10px; margin-top: 5px; font-size: 16px; box-sizing: border-box; }
button { background: #27ae60; color: white; border: none; cursor: pointer; margin-top: 20px; }
.msg { padding: 10px; margin-top: 15px; border-radius: 4px; }
.success { background: #d4edda; color: #155724; }
.error { background: #f8d7da; color: #721c24; }
a { display: inline-block; margin-top: 20px; }
</style>
</head>
<body>
<a href="/">Back</a>
<h2>School Master</h2>
<form method="POST" action="/save">
<label>School Code</label>
<input name="school_code" id="school_code" placeholder="BSM">
<button type="button" onclick="validate()">Validate</button>
<div id="msg"></div>
<label>School Name</label>
<input name="school_name" id="school_name">
<label>Mobile</label>
<input name="mobile" id="mobile">
<label>Principal</label>
<input name="principal" id="principal">
<label>School Address</label>
<input name="address" id="address" placeholder="School Address">
<button type="submit">Save to Excel</button>
</form>
<script>
function calcTotal() {
    var total = 0;
    for (var i = 1; i <= 15; i++) {
        var v = parseInt(document.getElementById('q' + i + '_marks').value) || 0;
        total += v;
    }
    document.getElementById('total_marks').innerText = total;
}
document.querySelectorAll('input[type=number]').forEach(function(el) {
    el.addEventListener('input', calcTotal);
});
function validate() {
    var code = document.getElementById('school_code').value.trim();
    if (!code) { alert('School Code daalo'); return; }
    fetch('/validate?code=' + encodeURIComponent(code))
    .then(r => r.json())
    .then(data => {
        var msg = document.getElementById('msg');
        if (data.found) {
            msg.innerHTML = '<div class="msg success">Found: ' + data.name + '</div>';
            document.getElementById('school_name').value = data.name || '';
            document.getElementById('mobile').value = data.mobile || '';
            document.getElementById('principal').value = data.principal || '';
            document.getElementById('address').value = data.address || '';
            for (var i = 1; i <= 15; i++) {
                var el = document.getElementById('q' + i + '_marks');
                if (el && data['q' + i]) el.value = data['q' + i];
            }
            calcTotal();
        } else {
            msg.innerHTML = '<div class="msg error">Not found. Fill new data.</div>';
        }
    });
}
</script>
</body>
</html>"""

PAPER_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Paper Setter</title>
<style>
body { font-family: Arial; max-width: 800px; margin: 20px auto; padding: 15px; }
label { display: block; margin-top: 12px; font-weight: bold; }
select, input, button { width: 100%; padding: 12px; margin-top: 5px; font-size: 16px; box-sizing: border-box; border-radius: 4px; }
button { background: #27ae60; color: white; border: none; cursor: pointer; margin-top: 15px; }
.row { display: flex; gap: 10px; flex-wrap: wrap; }
.row > div { flex: 1; min-width: 140px; }
a { display: inline-block; margin-top: 15px; }
.qbox { margin-top: 15px; border: 1px solid #ddd; padding: 12px; border-radius: 5px; }
#question_bank {
    max-height: 520px;
    overflow-y: auto;
    overflow-x: hidden;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 8px;
    margin-top: 10px;
}
#question_bank .qbox {
    margin-top: 8px;
}

@media (max-width: 600px) { body { margin: 10px; padding: 10px; } .row { flex-direction: column; } }
</style>
</head>
<body>
<a href="/">Back</a>
<h2>Paper Setter</h2>
<label>School Code</label>
<input id="school_code" value="BSM" placeholder="BSM">
<label>Board</label>
<select id="board_id" onchange="loadQuestions()">
{% for b in boards %}
<option value="{{ b.id }}">{{ b.name }}</option>
{% endfor %}
</select>
<div class="row">
<div>
<label>Class</label>
<select id="class_level" onchange="loadQuestions()">
<option selected>LKG</option>
<option>UKG</option>
<option>I</option>
<option>II</option>
<option>III</option>
<option>IV</option>
<option>V</option>
<option>VI</option>
<option>VII</option>
<option>VIII</option>
</select>
</div>
<div>
<label>Student Quantity</label>
<input id="student_qty" type="number" value="40">
</div>
</div>
<label>Subject</label>
<select id="subject" onchange="loadQuestions()">
<option>MATH</option>
<option>HINDI</option>
<option>ENGLISH</option>
<option>SCIENCE</option>
<option>SST</option>
</select>
<label>Total Photostat</label>
<input id="photostat" type="number" value="45">
<button type="button" onclick="loadQuestions()">सवाल दिखाओ</button>
<h3>Question Bank ? Checkbox Shortlist (Maximum 20)</h3>
<p>Selected: <b><span id="shortlist_count">0</span>/20</b></p>
<div id="question_bank"></div>
<p><b>Total Max Marks: <span id="paper_total_marks">0</span></b></p>
<button type="button" onclick="previewPaper()" style="background:#6c5ce7">Preview Paper</button>
<button type="button" id="generate_paper_button" onclick="generatePaper()" style="background:#d35400;font-weight:bold;">Generate Question Paper + Code</button>
<div id="paper_preview" style="display:none;margin-top:20px;"></div>
<div id="result" aria-live="polite"></div>
<script>
function updatePaperTotal() {
    var total = 0;
    shortlistIds.forEach(function(id) {
        total += parseInt(marksByQuestionId[String(id)] || '1', 10) || 0;
    });
    document.getElementById('paper_total_marks').textContent = total;
}
var questionBank = [];
var shortlistIds = [];
var marksByQuestionId = {};

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderQuestionBank() {
    var host = document.getElementById('question_bank');
    if (!questionBank.length) {
        host.innerHTML = '<p>No questions found for this Board/Class/Subject.</p>';
        updatePaperTotal();
        return;
    }

    var html = '';
    questionBank.forEach(function(q) {
        var id = Number(q.id);
        var checked = shortlistIds.indexOf(id) !== -1;
        var markValue = String(marksByQuestionId[String(id)] || '1');

        html += '<div class="qbox" style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;">';
        html += '<div style="flex:1;min-width:240px;">';
        html += '<label style="display:flex;gap:8px;align-items:flex-start;margin-top:0;">';
        html += '<input type="checkbox" style="width:auto;flex:0 0 auto;margin-top:4px;"'
             + (checked ? ' checked' : '')
             + ' onchange="toggleShortlist(' + id + ',this.checked)">';
        html += '<span><b>ID ' + id + ':</b> ' + escapeHtml(q.stem)
             + '<br><small>Merit selections: ' + Number(q.merit || 0)
             + (q.last_selected_at
                 ? ' | Last selected: ' + escapeHtml(q.last_selected_at)
                 : ' | Not selected in recorded history')
             + '</small></span></label></div>';

        html += '<div style="width:130px;flex:0 0 130px;">';
        html += '<label for="marks_' + id + '" style="margin-top:0;">Marks</label>';
        html += '<select id="marks_' + id + '" style="width:100%;padding:8px;margin-top:4px;"'
             + ' onchange="setQuestionMarks(' + id + ',this.value)">';
        for (var m = 1; m <= 20; m++) {
            html += '<option value="' + m + '"' + (String(m) === markValue ? ' selected' : '')
                 + '>' + m + (m === 1 ? ' Mark' : ' Marks') + '</option>';
        }
        html += '</select></div>';

        if (q.image) {
            html += '<div style="flex-basis:100%;padding-left:28px;">'
                 + '<img src="/question_image/' + id + '" alt="Question ' + id + ' preview" '
                 + 'loading="lazy" style="max-width:100%;height:auto;max-height:180px;'
                 + 'object-fit:contain;border:1px solid #ddd;"></div>';
        }
        html += '</div>';
    });
    host.innerHTML = html;
}

function setQuestionMarks(id, value) {
    marksByQuestionId[String(Number(id))] = String(parseInt(value, 10) || 1);
    updatePaperTotal();
}

function toggleShortlist(id, checked) {
    id = Number(id);
    if (checked && shortlistIds.indexOf(id) === -1) {
        if (shortlistIds.length >= 20) {
            alert('Maximum 20 questions can be selected.');
            renderQuestionBank();
            return;
        }
        shortlistIds.push(id);
        if (!marksByQuestionId[String(id)]) marksByQuestionId[String(id)] = '1';
    } else if (!checked) {
        shortlistIds = shortlistIds.filter(function(x) { return Number(x) !== id; });
    }

    document.getElementById('shortlist_count').textContent = shortlistIds.length;
    updatePaperTotal();
}

function loadQuestions() {
    var board = document.getElementById('board_id').value;
    var cls = document.getElementById('class_level').value;
    var sub = document.getElementById('subject').value;
    document.getElementById('question_bank').innerHTML = '<p>Loading questions...</p>';
    shortlistIds = [];
    questionBank = [];
    marksByQuestionId = {};
    document.getElementById('shortlist_count').textContent = '0';

    fetch('/get_questions?board=' + encodeURIComponent(board)
        + '&class=' + encodeURIComponent(cls)
        + '&subject=' + encodeURIComponent(sub), {cache: 'no-store'})
    .then(async function(r) {
        var body = await r.text();
        if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + body.slice(0, 250));
        try { return JSON.parse(body); }
        catch (e) { throw new Error('Server returned invalid JSON: ' + body.slice(0, 250)); }
    })
    .then(function(data) {
        if (!Array.isArray(data)) throw new Error(data.error || 'Unexpected question response');
        questionBank = data;
        renderQuestionBank();
        updatePaperTotal();
    })
    .catch(function(err) {
        document.getElementById('question_bank').innerHTML =
            '<p style="color:#b91c1c;white-space:pre-wrap">Question loading error: '
            + escapeHtml(err.message || err) + '</p>';
    });
}

function previewPaper() {
    var school = document.getElementById('school_code').value.trim();
    var cls = document.getElementById('class_level').value;
    var sub = document.getElementById('subject').value;
    var selected = [];

    for (var i = 0; i < shortlistIds.length; i++) {
        var id = Number(shortlistIds[i]);
        var q = questionBank.find(function(item) {
            return Number(item.id) === id;
        });
        if (q) selected.push({
            id: id,
            stem: q.stem,
            marks: parseInt(marksByQuestionId[String(id)] || '1', 10) || 1,
            image: !!q.image
        });
    }

    var host = document.getElementById('paper_preview');
    if (!selected.length) {
        host.style.display = 'block';
        host.innerHTML = '<p>Please shortlist at least one question first.</p>';
        return;
    }

    var total = selected.reduce(function(sum, q) { return sum + q.marks; }, 0);
    var html = '<div style="background:white;color:#111;padding:28px;'
        + 'border:1px solid #bbb;max-width:800px;margin:auto;'
        + 'font-family:Arial,sans-serif;">';
    html += '<div style="text-align:center;border-bottom:2px solid #222;'
        + 'padding-bottom:12px;margin-bottom:16px;">';
    html += '<h2 style="margin:0;">' + escapeHtml(school || 'School Name') + '</h2>';
    html += '<h3>' + escapeHtml(cls) + ' ? ' + escapeHtml(sub) + '</h3>';
    html += '<p>Student Quantity: ' + escapeHtml(document.getElementById('student_qty').value)
        + ' | Total Marks: ' + total + '</p></div>';

    selected.forEach(function(q, index) {
        html += '<div style="margin:18px 0;page-break-inside:avoid;">';
        if (q.image) {
            html += '<div style="position:relative;width:100%;line-height:0;margin:8px 0;">';
            html += '<img src="/question_image/' + q.id + '" alt="Worksheet Q' + (index + 1) + '" style="display:block;width:100%;height:auto;">';
            html += '<span style="position:absolute;left:2.2%;top:8%;width:6.3%;height:19%;display:flex;align-items:center;justify-content:center;line-height:1;font-family:Bookman Old Style,serif;font-size:17pt;font-weight:bold;color:#111;text-align:center;pointer-events:none;">Q' + (index + 1) + '</span>';
            html += '<span style="position:absolute;right:3.5%;top:6%;width:13%;height:15%;display:flex;align-items:center;justify-content:center;line-height:1.05;font-family:Bookman Old Style,serif;font-size:17pt;font-weight:bold;color:#111;text-align:center;white-space:nowrap;pointer-events:none;">' + q.marks + (q.marks === 1 ? ' Mark' : ' Marks') + '</span>';
            html += '</div>';
        } else {
            html += '<p style="font-family:Bookman Old Style,serif;font-size:17pt;"><b>Q' + (index + 1) + '.</b> ' + escapeHtml(q.stem) + ' <span style="float:right;">' + q.marks + (q.marks === 1 ? ' Mark' : ' Marks') + '</span></p>';
        }
        html += '</div>';
    });

    html += '<p style="text-align:center;border-top:1px solid #aaa;padding-top:12px;">'
        + '? End of Paper ?</p></div>';
    host.innerHTML = html;
    host.style.display = 'block';
    host.scrollIntoView({behavior:'smooth', block:'start'});
}

function generatePaper() {
    var result = document.getElementById('result');
    var school = document.getElementById('school_code').value.trim();
    var board = document.getElementById('board_id').value;
    var cls = document.getElementById('class_level').value;
    var sub = document.getElementById('subject').value;
    var qty = document.getElementById('student_qty').value;
    var photo = document.getElementById('photostat').value;

    // Use the actual checkbox shortlist and marks controls shown in this Paper Setter.
    var selected = shortlistIds.map(function(id) {
        return {
            id: Number(id),
            marks: parseInt(marksByQuestionId[String(Number(id))] || '1', 10) || 1
        };
    });

    if (!school) {
        result.textContent = 'Please enter the School Code first.';
        return;
    }
    if (!selected.length) {
        result.textContent = 'Please shortlist at least one question first.';
        return;
    }
    if (selected.length > 20) {
        result.textContent = 'Maximum 20 questions can be selected.';
        return;
    }

    var button = document.getElementById('generate_paper_button');
    if (button) {
        button.disabled = true;
        button.textContent = 'Generating paper… please wait';
    }
    result.innerHTML = '<p>Creating demo, generating unique code, and preparing the actual Word paper…</p>';

    var form = new FormData();
    form.append('school_code', school);
    form.append('board_id', board);
    form.append('class_level', cls);
    form.append('subject', sub);
    form.append('student_qty', qty);
    form.append('photostat', photo);
    form.append('question_selection', JSON.stringify(selected));

    fetch('/generate', {method: 'POST', body: form})
    .then(async function(response) {
        var body = await response.text();
        var data;
        try { data = JSON.parse(body); }
        catch (e) { throw new Error('Demo-generation endpoint returned an unexpected response: ' + body.slice(0, 250)); }
        if (!response.ok || !data.code || !data.file) {
            throw new Error(data.error || 'Demo paper or unique code could not be created.');
        }
        return data;
    })
    .then(function(data) {
        var code = data.code;
        // The actual route returns an HTML download link when successful.
        return fetch('/actual/' + encodeURIComponent(code), {cache: 'no-store'})
        .then(async function(response) {
            var body = await response.text();
            if (!response.ok) {
                var errorMessage = body;
                try {
                    var errorData = JSON.parse(body);
                    errorMessage = errorData.error || body;
                    if (errorData.details) errorMessage += ' ' + errorData.details.join(' ');
                } catch (e) {}
                throw new Error('Unique code ' + code + ' was created, but actual paper generation failed: ' + errorMessage);
            }
            var contentType = response.headers.get('content-type') || '';
            if (contentType.indexOf('application/json') !== -1) {
                var errorData = JSON.parse(body);
                throw new Error(errorData.error || 'Actual Word paper generation failed.');
            }
            var safeCode = escapeHtml(code);
            var safeDemo = escapeHtml(data.file);
            result.innerHTML =
                '<div style="border:1px solid #b7dfc5;background:#f0fff4;padding:14px;border-radius:6px;">' +
                '<h3 style="margin-top:0;">Question paper generated successfully</h3>' +
                '<p><b>Unique Paper Code:</b> <code>' + safeCode + '</code></p>' +
                '<p><a href="/download/' + encodeURIComponent(data.file) + '">Download Demo Paper (.docx)</a></p>' +
                '<p><a href="/download/ACTUAL_' + encodeURIComponent(code) + '.docx" style="display:inline-block;background:#27ae60;color:white;padding:12px 16px;border-radius:5px;text-decoration:none;font-weight:bold;">Download Actual Question Paper (.docx)</a></p>' +
                '<p><a href="https://wa.me/?text=' + encodeURIComponent('Paper Code: ' + code) + '" target="_blank" rel="noopener" style="display:inline-block;background:#25D366;color:white;padding:10px 16px;border-radius:5px;text-decoration:none;">Share Code on WhatsApp</a></p>' +
                '</div>';
        });
    })
    .catch(function(error) {
        result.innerHTML = '<p style="color:#b91c1c;white-space:pre-wrap;"><b>Generation failed:</b> ' +
            escapeHtml(error.message || error) + '</p>';
    })
    .finally(function() {
        if (button) {
            button.disabled = false;
            button.textContent = 'Generate Question Paper + Code';
        }
    });
}
document.addEventListener('DOMContentLoaded', function() { loadQuestions(); });
</script>
</body>
</html>"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_excel():
    if not EXCEL_PATH.exists():
        return None, None
    wb = load_workbook(EXCEL_PATH)
    if SHEET_NAME not in wb.sheetnames:
        return wb, None
    return wb, wb[SHEET_NAME]

def log_paper_register(code, school, cls, subject, paper_date, student_qty, status):
    """Write the seven agreed fields to the staging workbook's PAPER REGISTER."""
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Staging Excel not found: {EXCEL_PATH}")
    wb = load_workbook(EXCEL_PATH)
    sheet_name = "PAPER REGISTER"
    headers = ["Paper Date", "Paper Code", "School Code", "School Name", "Class", "Subject", "Student Quantity"]
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Migrate any earlier candidate register layout to the agreed seven-column layout,
        # preserving known values and dropping unneeded fields (Board ID, Photostat, Status, Total Marks).
        old_headers = [str(ws.cell(1, c).value or "").strip() for c in range(1, ws.max_column + 1)]
        old_rows = []
        for r in range(2, ws.max_row + 1):
            old_rows.append({old_headers[c-1]: ws.cell(r, c).value for c in range(1, len(old_headers) + 1) if c <= ws.max_column})
        ws.delete_rows(1, ws.max_row)
        ws.append(headers)
        for old in old_rows:
            ws.append([
                old.get("Paper Date"), old.get("Paper Code"), old.get("School Code"),
                old.get("School Name"), old.get("Class"), old.get("Subject"),
                old.get("Student Quantity")
            ])
    else:
        ws = wb.create_sheet(sheet_name)
        ws.append(headers)

    # Look up school name from SCHOOL MASTER by the School Code header position.
    school_name = school
    try:
        master = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else None
        if master:
            header_map = {str(master.cell(1, c).value or "").strip().casefold(): c for c in range(1, master.max_column + 1)}
            code_col = header_map.get("school code", 1)
            name_col = header_map.get("school name", 2)
            for r in range(2, master.max_row + 1):
                if str(master.cell(r, code_col).value or "").strip().upper() == school.upper():
                    school_name = master.cell(r, name_col).value or school
                    break
    except Exception:
        pass

    # Update by Paper Code; None values preserve already-recorded date/quantity on status updates.
    row_num = None
    for r in range(2, ws.max_row + 1):
        if str(ws.cell(r, 2).value or "").strip() == code:
            row_num = r
            break
    is_new_row = row_num is None
    if row_num is None:
        row_num = ws.max_row + 1
    values = [paper_date, code, school, school_name, cls, subject, student_qty]
    for col, value in enumerate(values, 1):
        if value is not None or is_new_row:
            ws.cell(row=row_num, column=col, value=value)
    wb.save(EXCEL_PATH)

@app.route("/")
def home():
    return render_template_string(HOME_HTML)

@app.route("/school")
def school():
    return render_template_string(SCHOOL_HTML)

@app.route("/validate")
def validate():
    code = request.args.get("code", "").strip().upper()
    wb, ws = load_excel()
    if ws is None:
        return jsonify({"found": False})
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and str(row[0]).strip().upper() == code:
            result = {
                "found": True,
                "name": row[1] or "",
                "mobile": row[2] or "",
                "principal": row[3] or "",
                "address": row[4] or ""
            }
            return jsonify(result)
    return jsonify({"found": False})

@app.route("/save", methods=["POST"])
def save():
    code = request.form.get("school_code", "").strip().upper()
    name = request.form.get("school_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    principal = request.form.get("principal", "").strip()
    address = request.form.get("address", "").strip()
    if not code or not name:
        return "<p>School Code and Name required.</p><a href='/school'>Back</a>"
    wb, ws = load_excel()
    if wb is None:
        return "<p>Excel not found.</p><a href='/school'>Back</a>"
    if ws is None:
        ws = wb.create_sheet(SHEET_NAME)
        headers = ["School Code", "School Name", "Mobile", "Principal", "Address"] + [f"Q{i}" for i in range(1, 16)] + ["Total"]
        ws.append(headers)
    found = False
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if row[0].value and str(row[0].value).strip().upper() == code:
            row[1].value = name
            row[2].value = mobile
            row[3].value = principal
            row[4].value = address
            found = True
            break
    if not found:
        ws.append([code, name, mobile, principal, address])
    wb.save(EXCEL_PATH)
    return "<p>Saved: " + code + "</p><a href='/school'>Back</a>"

@app.route("/paper")
def paper():
    try:
        conn = get_db()
        boards = conn.execute("SELECT id, name FROM boards WHERE active=1").fetchall()
        conn.close()
    except:
        boards = [{"id": 1, "name": "Haryana Board"}]
    return render_template_string(PAPER_HTML, boards=boards)

@app.route("/get_questions")
def get_questions():
    board = request.args.get("board", 1)
    cls = request.args.get("class", "III")
    sub = request.args.get("subject", "MATH")
    conn = None
    try:
        conn = get_db()
        rows = conn.execute(
            """SELECT q.id, q.content_json, q.image_path,
                      COALESCE(h.successful_selection_count, 0) AS merit,
                      h.last_selected_at
               FROM questions q
               LEFT JOIN question_history h ON h.question_id=q.id
               WHERE q.board_id=? AND q.class_level=? AND q.subject=?
               ORDER BY merit DESC, h.last_selected_at DESC, q.id ASC""",
            (board, cls, sub)
        ).fetchall()

        result = []
        for r in rows:
            try:
                c = json.loads(r["content_json"])
                stem = c.get("stem", "")
                has_image = bool(r["image_path"] or c.get("image"))
            except Exception:
                stem = str(r["content_json"])[:100]
                has_image = bool(r["image_path"])

            result.append({
                "id": int(r["id"]),
                "stem": stem,
                "image": has_image,
                "merit": int(r["merit"] or 0),
                "last_selected_at": r["last_selected_at"]
            })
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Question bank loading failed")
        return jsonify({"error": "Question bank loading failed: " + str(e)}), 500
    finally:
        if conn is not None:
            conn.close()


@app.route("/question_image/<int:qid>")
def question_image(qid):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT image_path, content_json FROM questions WHERE id=?",
            (qid,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Question not found"}), 404

    try:
        c = json.loads(row["content_json"] or "{}")
    except Exception:
        c = {}

    stored = row["image_path"] or c.get("image", "")
    if not stored:
        return jsonify({"error": "Question has no image"}), 404

    root = Path(__file__).parent.resolve()
    image_root = (Path(r"D:\SAINI_TEACHER_TRIAL") / "images").resolve()
    raw_path = Path(stored)
    img_path = (Path(r"D:\SAINI_TEACHER_TRIAL") / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()

    if image_root not in img_path.parents or not img_path.is_file():
        return jsonify({"error": "Image missing or invalid path"}), 404

    return send_file(img_path, conditional=True)


@app.route("/generate", methods=["POST"])
def generate():
    try:
        import random, string
        from datetime import datetime
        school = request.form.get("school_code", "SCHOOL001")
        cls = request.form.get("class_level", "III")
        subject = request.form.get("subject", "MATH")
        student_qty = request.form.get("student_qty", "40")
        photostat = request.form.get("photostat", "45")
        selection_raw = request.form.get("question_selection", "")
        qids = request.form.get("qids", "")
        board_id = request.form.get("board_id", "1")

        # Fail closed on invalid form values before writing to the database or files.
        school = school.strip().upper()
        cls = cls.strip()
        subject = subject.strip().upper()
        try:
            student_qty_int = int(student_qty)
            photostat_int = int(photostat)
            board_id_int = int(board_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Board, student quantity, and photostat must be valid numbers."}), 400
        if not school or not cls or not subject:
            return jsonify({"error": "School code, class, and subject are required."}), 400
        if student_qty_int < 1 or student_qty_int > 10000:
            return jsonify({"error": "Student quantity must be between 1 and 10000."}), 400
        if photostat_int < 1 or photostat_int > 100000:
            return jsonify({"error": "Photostat quantity must be between 1 and 100000."}), 400
        import json
        selected = []
        try:
            if selection_raw:
                parsed = json.loads(selection_raw)
                if not isinstance(parsed, list): raise ValueError
                for item in parsed:
                    qid, marks = int(item["id"]), int(item["marks"])
                    if qid <= 0 or marks < 0 or marks > 20: raise ValueError
                    selected.append({"id": qid, "marks": marks})
                ids = [item["id"] for item in selected]
            else:
                ids = [int(x.strip()) for x in qids.split(",") if x.strip()]
                selected = [{"id": qid, "marks": 1} for qid in ids]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return jsonify({"error": "Question selection or marks are invalid."}), 400
        if not ids:
            return jsonify({"error": "Please select at least one question."}), 400
        if len(ids) > 20:
            return jsonify({"error": "Maximum 20 questions can be selected."}), 400
        if len(ids) != len(set(ids)):
            return jsonify({"error": "The same question cannot be selected more than once."}), 400
        selected_payload = json.dumps({"version": 2, "questions": selected}, ensure_ascii=False)

        date_str = datetime.now().strftime("%Y%m%d")
        rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        unique_code = f"{school}-{cls}-{subject[:3].upper()}-{date_str}-{rand}"

        conn = get_db()
        placeholders = ",".join(["?"] * len(ids))
        valid_rows = conn.execute(
            f"SELECT id FROM questions WHERE id IN ({placeholders}) AND board_id=? AND class_level=? AND subject=?",
            (*ids, board_id_int, cls, subject)
        ).fetchall()
        valid_ids = {int(r["id"]) for r in valid_rows}
        if valid_ids != set(ids):
            conn.close()
            return jsonify({"error": "One or more selected questions do not belong to the chosen board, class, and subject."}), 400
        conn.execute(
            "INSERT INTO selections (school_code, board_id, class_level, subject, selected_slots_json, review_status, generated_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (school, board_id_int, cls, subject, selected_payload, "demo_pending", unique_code)
        )
        conn.commit()
        conn.close()

        from docx import Document
        from docx.shared import RGBColor, Pt
        doc = Document()
        # Unformatted plain text
        p = doc.add_paragraph()
        run = p.add_run(f"DEMO {school} {cls} {subject}")
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(150, 150, 150)
        doc.add_paragraph(f"code {unique_code}")
        doc.add_paragraph(f"students {student_qty_int}")
        # Watermark
        header = doc.sections[0].header
        header_para = header.paragraphs[0]
        header_para.alignment = 1
        run = header_para.add_run("DEMO ONLY NOT FOR PRINT")
        run.font.size = Pt(28)
        run.font.color.rgb = RGBColor(230, 230, 230)
        ids = [item["id"] for item in selected]
        conn = get_db()
        placeholders = ",".join(["?"] * len(ids))
        rows = conn.execute(f"SELECT id, content_json FROM questions WHERE id IN ({placeholders})", ids).fetchall()
        by_id = {int(row["id"]): row for row in rows}
        conn.close()
        for i, item in enumerate(selected, 1):
            q = by_id.get(item["id"])
            if not q: continue
            try:
                c = json.loads(q["content_json"])
                stem = c.get("stem", "")
                opts = c.get("options", [])
                p = doc.add_paragraph()
                run = p.add_run(f"{i}. {stem} [{item['marks']}]")
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(170, 170, 170)
                if opts:
                    p2 = doc.add_paragraph()
                    run2 = p2.add_run(" ".join(opts))
                    run2.font.size = Pt(7)
                    run2.font.color.rgb = RGBColor(170, 170, 170)
            except Exception:
                doc.add_paragraph(str(q["content_json"])[:50])
        footer = doc.sections[0].footer
        footer.paragraphs[0].text = unique_code
        fname = f"DEMO_{unique_code}.docx"
        fpath = OUTPUT_DIR / fname
        doc.save(fpath)

        # Record paper date/code and batch details in a dedicated register in the staging workbook.
        try:
            board_row = conn = get_db()
            try:
                board_rec = board_row.execute("SELECT name FROM boards WHERE id=?", (board_id_int,)).fetchone()
                board_label = board_rec["name"] if board_rec else str(board_id_int)
            finally:
                board_row.close()
            log_paper_register(
                unique_code, school, cls, subject,
                datetime.now().strftime("%d-%m-%Y"), student_qty_int,
                "demo_pending"
            )
        except Exception as log_error:
            # The demo file exists, but clearly report that the register write failed.
            return jsonify({"error": f"Demo file created ({fname}), but PAPER REGISTER could not be updated: {log_error}", "file": fname, "code": unique_code}), 500

        # Log to Excel
        try:
            from openpyxl import Workbook, load_workbook
            log_path = Path(__file__).parent / "CODES.xlsx"
            if log_path.exists():
                wb = load_workbook(log_path)
                ws = wb.active
            else:
                wb = Workbook()
                ws = wb.active
                ws.append(["Code", "School", "Class", "Subject", "Date", "Status"])
            ws.append([unique_code, school, cls, subject, date_str, "demo"])
            wb.save(log_path)
            # Teacher-trial safety: intentionally no Google Drive writes.
        except:
            pass

        # Backup DB
        try:
            import shutil
            from datetime import datetime as dt
            bak = Path(__file__).parent / f"backup_{dt.now().strftime('%Y%m%d')}.db"
            if not bak.exists():
                shutil.copy(DB_PATH, bak)
        except:
            pass

        return jsonify({"file": fname, "code": unique_code})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/actual/<code>")
def actual(code):
    try:
        code = code.strip()
        conn = get_db()
        row = conn.execute(
            "SELECT school_code, class_level, subject, selected_slots_json FROM selections WHERE generated_path=? LIMIT 1",
            (code,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Code not found"})
        school, cls, subject, stored_selection = row["school_code"], row["class_level"], row["subject"], row["selected_slots_json"]
        conn.close()
        import json
        try:
            decoded = json.loads(stored_selection or "")
            if isinstance(decoded, dict) and isinstance(decoded.get("questions"), list):
                selected = [{"id": int(x["id"]), "marks": int(x.get("marks", 1))} for x in decoded["questions"]]
            else:
                selected = [{"id": int(x), "marks": 1} for x in str(stored_selection or "").split(",") if x]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            selected = [{"id": int(x), "marks": 1} for x in str(stored_selection or "").split(",") if x.strip().isdigit()]
        ids = [item["id"] for item in selected]
        qids = ",".join(str(qid) for qid in ids)
        from datetime import datetime
        date_str = datetime.now().strftime("%d-%m-%Y")
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.oxml.ns import qn
        import json

        # School identity comes from School Master; question marks come from this paper's selections.
        q_marks = [str(item["marks"]) for item in selected]
        school_full_name = school
        try:
            wb, ws = load_excel()
            if ws:
                for school_row in ws.iter_rows(min_row=2, values_only=True):
                    if school_row[0] and str(school_row[0]).strip().upper() == school.upper():
                        school_full_name = school_row[1] or school
                        break
        except Exception:
            pass

        doc = Document()
        # A4 narrow margins
        section = doc.sections[0]
        section.page_width = Pt(595)
        section.page_height = Pt(842)
        section.left_margin = Pt(36)
        section.right_margin = Pt(36)
        section.top_margin = Pt(36)
        section.bottom_margin = Pt(36)

        # Page border 1cm inside
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        pgBorders = OxmlElement('w:pgBorders')
        pgBorders.set(qn('w:offsetFrom'), 'page')
        for border_name in ['top', 'left', 'bottom', 'right']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '12')
            border.set(qn('w:space'), '28')
            border.set(qn('w:color'), '000000')
            pgBorders.append(border)
        section._sectPr.append(pgBorders)

        style = doc.styles['Normal']
        style.font.name = 'Bookman Old Style'
        style.font.size = Pt(17)
        style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Bookman Old Style')

        # School name large, full width
        p = doc.add_paragraph()
        p.alignment = 1
        run = p.add_run(school_full_name)
        run.font.name = 'Bookman Old Style'
        run.font.size = Pt(22)
        run.bold = True
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0

        # Time | Class(Subject) | Total Marks
        total_m = 0
        n_qs = len(selected)
        for m in q_marks[:n_qs]:
            try:
                total_m += int(m or 0)
            except:
                total_m += 1

        hdr = doc.add_table(rows=1, cols=3)
        hdr.columns[0].width = Pt(150)
        hdr.columns[1].width = Pt(250)
        hdr.columns[2].width = Pt(150)
        c0 = hdr.cell(0, 0)
        c1 = hdr.cell(0, 1)
        c2 = hdr.cell(0, 2)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run("Time: 1 Hour")
        r0.font.name = 'Bookman Old Style'
        r0.font.size = Pt(14)
        p1 = c1.paragraphs[0]
        p1.alignment = 1
        r1 = p1.add_run(f"{cls}({subject})")
        r1.font.name = 'Bookman Old Style'
        r1.font.size = Pt(18)
        r1.bold = True
        p2 = c2.paragraphs[0]
        p2.alignment = 2
        r2 = p2.add_run(f"Total Marks: {total_m}")
        r2.font.name = 'Bookman Old Style'
        r2.font.size = Pt(14)
        r2.bold = True

        # Double solid line full width
        p_line = doc.add_paragraph()
        p_line.paragraph_format.space_before = Pt(0)
        p_line.paragraph_format.space_after = Pt(3)
        p_line.paragraph_format.line_spacing = Pt(2)
        p_line.paragraph_format.keep_together = True
        p_line.paragraph_format.keep_with_next = True
        p_line.paragraph_format.widow_control = False
        p_line.paragraph_format.left_indent = Pt(0)
        p_line.paragraph_format.right_indent = Pt(0)
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        pPr = p_line._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        for edge in ('top', 'bottom'):
            border = OxmlElement(f'w:{edge}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '8')
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), '000000')
            pBdr.append(border)
        pPr.append(pBdr)
        tiny_run = p_line.add_run(' ')
        tiny_run.font.size = Pt(1)
        tiny_run.font.name = 'Bookman Old Style'
        if qids:
            ids = [int(x) for x in qids.split(",") if x]
            if ids:
                conn = get_db()
                placeholders = ",".join(["?"] * len(ids))
                rows = conn.execute(f"SELECT id, content_json, image_path FROM questions WHERE id IN ({placeholders})", ids).fetchall()
                by_id = {int(row["id"]): row for row in rows}
                qs = [by_id[qid] for qid in ids if qid in by_id]
                conn.close()
                if len(qs) != len(ids):
                    return jsonify({"error": "A selected question is missing from the question bank; paper was not marked generated."}), 409
                image_errors = []
                for i, q in enumerate(qs, 1):
                    marks = q_marks[i-1] if i <= len(q_marks) else "1"
                    try:
                        c = json.loads(q["content_json"])
                        stem = c.get("stem", "")
                        opts = c.get("options", [])
                        img_name = c.get("image", "")
                        # For LKG/UKG worksheet images, permanently render
                        # this paper's question number and marks into a copy.
                        is_worksheet_image = (
                            cls.upper() in ("LKG", "UKG")
                            and bool(q["image_path"] or img_name)
                        )

                        if is_worksheet_image:
                            from PIL import Image, ImageDraw, ImageFont

                            image_root = (Path(r"D:\SAINI_TEACHER_TRIAL") / "images").resolve()
                            stored_path = q["image_path"] or ("images/" + img_name)
                            img_path = (Path(r"D:\SAINI_TEACHER_TRIAL") / stored_path).resolve()

                            if image_root not in img_path.parents or not img_path.is_file():
                                image_errors.append(
                                    f"Question ID {q['id']}: image missing or outside the images folder"
                                )
                            else:
                                try:
                                    font_candidates = [
                                        Path(r"C:\\Windows\\Fonts\\BOOKOSB.TTF"),
                                        Path(r"C:\\Windows\\Fonts\\BOOKOS.TTF"),
                                    ]
                                    font_path = next(
                                        (fp for fp in font_candidates if fp.is_file()),
                                        None
                                    )
                                    if font_path is None:
                                        raise FileNotFoundError(
                                            "Bookman Old Style font not found."
                                        )

                                    with Image.open(img_path) as original:
                                        original.load()
                                        canvas = original.convert("RGB")
                                        width, height = canvas.size
                                        draw = ImageDraw.Draw(canvas)

                                        # Scale from the approved Q001 layout
                                        # (2172 x 598); never resize the worksheet.
                                        q_font_size = max(12, round(width * 90 / 2172))
                                        marks_font_size = max(12, round(width * 71 / 2172))
                                        q_font = ImageFont.truetype(
                                            str(font_path), q_font_size
                                        )
                                        marks_font = ImageFont.truetype(
                                            str(font_path), marks_font_size
                                        )

                                        draw.text(
                                            (round(width * 170 / 2172),
                                             round(height * 123 / 598)),
                                            f"Q{i}",
                                            font=q_font,
                                            fill=(0, 0, 0),
                                            anchor="mm"
                                        )

                                        marks_number = int(marks)
                                        marks_label = (
                                            f"{marks_number} Mark"
                                            if marks_number == 1
                                            else f"{marks_number} Marks"
                                        )
                                        draw.text(
                                            (round(width * 1935 / 2172),
                                             round(height * 105 / 598)),
                                            marks_label,
                                            font=marks_font,
                                            fill=(0, 0, 0),
                                            anchor="mm"
                                        )

                                        composite_dir = (
                                            OUTPUT_DIR / "composite_images" / str(code)
                                        )
                                        composite_dir.mkdir(
                                            parents=True, exist_ok=True
                                        )
                                        composite_path = composite_dir / (
                                            f"{i:02d}_Q{q['id']}_NUMBERED.png"
                                        )
                                        canvas.save(
                                            composite_path,
                                            format="PNG",
                                            dpi=(300, 300)
                                        )

                                        # Fail closed if dimensions changed.
                                        with Image.open(composite_path) as verify:
                                            if verify.size != original.size:
                                                raise RuntimeError(
                                                    "Composite dimensions changed."
                                                )

                                    doc.add_picture(
                                        str(composite_path), width=Inches(7.1)
                                    )

                                except Exception as image_exc:
                                    image_errors.append(
                                        f"Question ID {q['id']}: composite image failed ({image_exc})"
                                    )
                        else:
                            # Preserve existing text-question behaviour.
                            table = doc.add_table(rows=1, cols=2)
                            table.columns[0].width = Pt(450)
                            table.columns[1].width = Pt(80)
                            cell0 = table.cell(0, 0)
                            cell1 = table.cell(0, 1)
                            p = cell0.paragraphs[0]
                            run = p.add_run(f"Q{i}. {stem}")
                            run.font.name = 'Bookman Old Style'
                            run.font.size = Pt(17)
                            p1 = cell1.paragraphs[0]
                            p1.alignment = 2
                            run1 = p1.add_run(f"[{marks}]")
                            run1.font.name = 'Bookman Old Style'
                            run1.font.size = Pt(17)
                            run1.bold = True

                            if opts:
                                opt_text = "   ".join(
                                    [f"{chr(65+j)}) {o}" for j, o in enumerate(opts)]
                                )
                                p2 = doc.add_paragraph()
                                run2 = p2.add_run(opt_text)
                                run2.font.name = 'Bookman Old Style'
                                run2.font.size = Pt(17)
                    except:
                        p = doc.add_paragraph()
                        run = p.add_run(f"Q{i}. {q['content_json']}")
                        run.font.name = 'Bookman Old Style'
                        run.font.size = Pt(17)
        if image_errors:
            return jsonify({
                "error": "Paper was not saved because one or more selected images could not be embedded.",
                "details": image_errors
            }), 409

        fname = f"ACTUAL_{code}.docx"
        fpath = OUTPUT_DIR / fname

        # Footer
        footer = section.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0]
        fp.clear()
        # Left: Date/Code
        run_l = fp.add_run(f"{date_str} | {code}")
        run_l.font.name = 'Bookman Old Style'
        run_l.font.size = Pt(10)
        run_l.add_tab()
        # Center: Page X of Y
        run_c = fp.add_run("Page ")
        run_c.font.name = 'Bookman Old Style'
        run_c.font.size = Pt(10)
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')
        instrText = OxmlElement('w:instrText')
        instrText.text = "PAGE"
        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'end')
        run_c._r.append(fldChar1)
        run_c._r.append(instrText)
        run_c._r.append(fldChar2)
        run_c2 = fp.add_run(" of ")
        run_c2.font.name = 'Bookman Old Style'
        run_c2.font.size = Pt(10)
        fldChar3 = OxmlElement('w:fldChar')
        fldChar3.set(qn('w:fldCharType'), 'begin')
        instrText2 = OxmlElement('w:instrText')
        instrText2.text = "NUMPAGES"
        fldChar4 = OxmlElement('w:fldChar')
        fldChar4.set(qn('w:fldCharType'), 'end')
        run_c2._r.append(fldChar3)
        run_c2._r.append(instrText2)
        run_c2._r.append(fldChar4)
        run_c2.add_tab()
        # Right: SAINI_ID_CARD
        run_r = fp.add_run("SAINI_ID_CARD: 8059058868")
        run_r.font.name = 'Bookman Old Style'
        run_r.font.size = Pt(10)

        doc.save(fpath)

        # Record merit only after DOCX save, atomically with final status.
        status_conn = get_db()
        try:
            status_conn.execute("BEGIN IMMEDIATE")
            current = status_conn.execute(
                "SELECT review_status FROM selections WHERE generated_path=? LIMIT 1",
                (code,)
            ).fetchone()

            if not current:
                raise RuntimeError("Selection record disappeared before history update")

            # A paper code already marked actual_generated must not earn merit twice.
            if current["review_status"] != "actual_generated":
                generated_at = datetime.now().isoformat(timespec="seconds")
                for item in selected:
                    qid = int(item["id"])
                    event = status_conn.execute(
                        """INSERT OR IGNORE INTO question_generation_events
                           (selection_code, question_id, generated_at)
                           VALUES (?, ?, ?)""",
                        (code, qid, generated_at)
                    )

                    if event.rowcount == 1:
                        status_conn.execute(
                            """INSERT INTO question_history
                               (question_id, successful_selection_count, last_selected_at)
                               VALUES (?, 1, ?)
                               ON CONFLICT(question_id) DO UPDATE SET
                                   successful_selection_count =
                                       successful_selection_count + 1,
                                   last_selected_at = excluded.last_selected_at""",
                            (qid, generated_at)
                        )

                status_conn.execute(
                    "UPDATE selections SET review_status='actual_generated' WHERE generated_path=?",
                    (code,)
                )

            status_conn.commit()
        except Exception:
            status_conn.rollback()
            raise
        finally:
            status_conn.close()

        # Update the corresponding PAPER REGISTER row after the actual DOCX has saved.
        try:
            log_paper_register(
                code, school, cls, subject, date_str,
                None, "actual_generated"
            )
        except Exception as log_error:
            # Keep the generated paper, but make the register failure visible.
            return jsonify({"error": f"Actual paper created ({fname}), but PAPER REGISTER update failed: {log_error}", "file": fname, "code": code}), 500

        # Update Google Sheet
        try:
            import requests
            sheet_url = "https://docs.google.com/spreadsheets/d/1TTMQxpsBArUtZiH3TShJVDNrX0as1OLaNx1I2FXg3TY/edit"
            # Note: Full API needs service account. For now, log locally.
            gs_log = Path(__file__).parent / "google_sheet_log.csv"
            with open(gs_log, "a") as f:
                f.write(f"{code},{school},{cls},{subject},{date_str},actual\n")
        except:
            pass

        # Update Excel log
        try:
            log_path = Path(__file__).parent / "CODES.xlsx"
            if log_path.exists():
                from openpyxl import load_workbook
                wb = load_workbook(log_path)
                ws = wb.active
                for row in ws.iter_rows(min_row=2):
                    if row[0].value == code:
                        row[5].value = "actual"
                        break
                wb.save(log_path)
        except:
            pass

        # Update School Master with paper code
        try:
            wb, ws = load_excel()
            if ws:
                for row in ws.iter_rows(min_row=2):
                    if row[0].value and str(row[0].value).strip().upper() == school.upper():
                        # Add paper code in a notes column or append
                        if len(row) > 21:
                            existing = str(row[21].value or "")
                            row[21].value = existing + f", {code}" if existing else code
                        break
                wb.save(EXCEL_PATH)
        except:
            pass

        return f'<p>Paper ready: <a href="/download/{fname}">{fname}</a></p>'
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/download/<filename>")
def download(filename):
    # Never allow path traversal outside the configured output directory.
    if Path(filename).name != filename or filename in {".", ".."}:
        return jsonify({"error": "Invalid filename."}), 400
    target = (OUTPUT_DIR / filename).resolve()
    if target.parent != OUTPUT_DIR.resolve() or not target.is_file():
        return jsonify({"error": "File not found."}), 404
    return send_file(target, as_attachment=True)



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



@app.route("/admin/schools", methods=["GET", "POST"])
def school_registration():
    import school_registry
    return school_registry.handle(get_db, request, session)



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


if __name__ == "__main__":
    if not os.environ.get("SAINI_TRIAL_PASSWORD") or not app.secret_key:
        raise SystemExit("Set SAINI_TRIAL_PASSWORD and SAINI_SESSION_SECRET before starting the teacher trial.")
    print("Saini Teacher Trial is running on http://127.0.0.1:5001")
    print("A login is required. Trial ends 7 days after the first request.")
    app.run(host="127.0.0.1", port=5001, debug=False)
