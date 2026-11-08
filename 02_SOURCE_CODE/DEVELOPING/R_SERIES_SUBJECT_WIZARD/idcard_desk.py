# -*- coding: utf-8 -*-
"""ID card page for the development portal. No separate command window."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ASSISTANT = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\MAIN_ASSISTANT.py")
CANDIDATE = Path(
    r"D:\SHRI_JAI_SHRI_RAM\project_panels"
    r"\OPTION_C_V5_RELEASE_CANDIDATE_20261028_0655"
    r"\slip_ocr_OPTION_C_CANDIDATE.py"
)
ID_PROJECT = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT")
AUDIO_ROOT = ID_PROJECT / "WHATSAP" / "SLIP_AUDIO"
JOBS = Path(__file__).resolve().parent / "idcard_jobs"
MODES = [
    ("B", "B — data ready, ID card generator"),
    ("A", "A — new photos, full process"),
    ("C", "C — teacher slips, Option C OCR"),
    ("D", "D — correction slips"),
    ("E", "E — Google Sheet enroll"),
    ("R", "R — MIX photos reassign"),
    ("M", "M — combo MIX photos"),
    ("N", "N — night run, all schools"),
]
COLORS = ["W", "R", "B", "G", "LG", "LB"]


def _job_dir(job_id):
    if not re.fullmatch(r"[a-f0-9]{16}", job_id or ""):
        raise ValueError("Unknown job")
    folder = JOBS / job_id
    if not folder.is_dir():
        raise ValueError("Unknown job")
    return folder


def _read(path, limit=12000):
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def _auto_answer(prompt, job):
    text = (prompt or "").lower()
    if "background color" in text:
        return job.get("bg") or "W"
    if "launch id card generator" in text:
        return "y" if job.get("launch") else "n"
    if "press enter to exit" in text or "an error occurred" in text:
        return ""
    if "sheet nahi khuli" in text or "verification pending" in text:
        return ""
    return None


def _load_candidate():
    os.environ["SAINI_BASE_PROJECT"] = str(ID_PROJECT)
    if not CANDIDATE.is_file():
        raise FileNotFoundError("Option C slip OCR missing: " + str(CANDIDATE))
    spec = importlib.util.spec_from_file_location("slip_ocr", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["slip_ocr"] = module
    spec.loader.exec_module(module)


def run_job(folder):
    folder = Path(folder)
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    log_path = folder / "log.txt"
    waiting = folder / "waiting.txt"
    answer = folder / "answer.txt"
    log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_handle
    sys.stderr = log_handle

    def gui_input(prompt=""):
        print(prompt, flush=True)
        known = _auto_answer(prompt, job)
        if known is not None:
            print(">> " + known, flush=True)
            return known
        waiting.write_text(prompt, encoding="utf-8")
        while True:
            if (folder / "stop.txt").is_file():
                raise KeyboardInterrupt
            if answer.is_file():
                typed = answer.read_text(encoding="utf-8", errors="replace")
                answer.unlink(missing_ok=True)
                waiting.write_text("", encoding="utf-8")
                print(">> " + typed.rstrip("\n"), flush=True)
                return typed.rstrip("\n")
            time.sleep(0.4)

    import builtins
    builtins.input = gui_input
    try:
        if not ASSISTANT.is_file():
            raise FileNotFoundError("MAIN_ASSISTANT.py missing: " + str(ASSISTANT))
        print("Loading Option C slip OCR", flush=True)
        _load_candidate()
        print("Starting MAIN_ASSISTANT", job.get("school"), "mode", job.get("mode"), flush=True)
        sys.argv = [str(ASSISTANT), "--school", job.get("school") or "BSM", "--mode", job.get("mode") or "B"]
        import runpy
        runpy.run_path(str(ASSISTANT), run_name="__main__")
        (folder / "status.txt").write_text("done", encoding="utf-8")
        print("ID card process finished.", flush=True)
    except KeyboardInterrupt:
        (folder / "status.txt").write_text("stopped", encoding="utf-8")
        print("Stopped from the page.", flush=True)
    except Exception as error:
        (folder / "status.txt").write_text("error", encoding="utf-8")
        print("ERROR: " + str(error), flush=True)
    finally:
        waiting.write_text("", encoding="utf-8")
        log_handle.close()


def _audio_in_log(log_text):
    found = []
    for line in log_text.splitlines():
        candidate = line.strip().strip('"')
        path = Path(candidate)
        if path.suffix.lower() in (".mp3", ".wav") and path.is_file():
            try:
                path.resolve().relative_to(AUDIO_ROOT.resolve())
            except Exception:
                continue
            found.append(path)
    return found[-1] if found else None


def _page(token, notice, job_id=""):
    options = "".join(
        '<option value="%s">%s</option>' % (code, label) for code, label in MODES
    )
    colors = "".join('<option>%s</option>' % color for color in COLORS)
    log = ""
    waiting = ""
    audio = ""
    running = False
    if job_id:
        folder = _job_dir(job_id)
        log = _read(folder / "log.txt")
        waiting = _read(folder / "waiting.txt", 2000).strip()
        status = _read(folder / "status.txt", 40).strip()
        running = not status and not waiting
        clip = _audio_in_log(log)
        if clip and waiting:
            audio = '<audio controls src="/saini/idcard/audio?job=%s"></audio>' % job_id
    refresh = '<meta http-equiv="refresh" content="4">' if running else ""
    answer_box = ""
    if waiting:
        answer_box = (
            '<h2>Program is waiting</h2><pre>%s</pre>'
            '<form method="post"><input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="action" value="answer">'
            '<input type="hidden" name="job" value="%s">'
            '<input name="typed" size="48" placeholder="Type the answer shown above">'
            '<button type="submit">Send answer</button>'
            '<button name="quick" value="Y" type="submit">Haan</button>'
            '<button name="quick" value="N" type="submit">Nahi</button>'
            '<button name="quick" value="ENTER" type="submit">Enter</button></form>%s'
        ) % (_esc(waiting), token, job_id, audio)
    stop = ""
    if job_id and (running or waiting):
        stop = (
            '<form method="post"><input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="action" value="stop">'
            '<input type="hidden" name="job" value="%s">'
            '<button type="submit">Stop</button></form>'
        ) % (token, job_id)
    return """<!doctype html><html><head><meta charset="utf-8"><title>ID Cards</title>%s
<style>
body{font-family:Arial;margin:0;background:#f4f7fb;color:#172033}
main{max-width:980px;margin:24px auto;background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}
button.go{background:#1f9d55;color:white;border:0;border-radius:8px;padding:12px 16px;font-size:16px}
input,select,button{font:16px Arial;padding:8px;margin:4px 4px 4px 0}
pre{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:12px;border-radius:8px;max-height:360px;overflow:auto}
.note{background:#e8f6ee;padding:10px;border-radius:8px}
</style></head><body><main>
<p><a href="/">Home</a></p>
<h1>ID Cards</h1>
<p>School code, mode, then Start. MAIN_ASSISTANT and Option C slip OCR run from this page. Approval is never automatic.</p>
<p class="note">%s</p>
<form method="post">
<input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="start">
<input name="school" value="BSM" size="8" required>
<select name="mode">%s</select>
<select name="bg">%s</select>
<label><input type="checkbox" name="launch" value="1" checked> Open ID card generator at the end</label>
<button class="go" type="submit">Start</button>
</form>
%s%s
<h2>Log</h2>
<pre>%s</pre>
</main></body></html>""" % (
        refresh, _esc(notice), token, options, colors, answer_box, stop, _esc(log or "No job yet."),
    )


def _esc(value):
    return (
        str(value)
        .replace("&", "&")
        .replace("<", "<")
        .replace(">", ">")
    )


def _start(form):
    school = (form.get("school") or "").strip().upper()
    mode = (form.get("mode") or "").strip().upper()
    bg = (form.get("bg") or "W").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,12}", school):
        raise ValueError("School code must be 2 to 12 letters or digits")
    if mode not in {code for code, _label in MODES}:
        raise ValueError("Unknown mode")
    if bg not in COLORS:
        raise ValueError("Unknown background")
    JOBS.mkdir(parents=True, exist_ok=True)
    import secrets
    job_id = secrets.token_hex(8)
    folder = JOBS / job_id
    folder.mkdir()
    job = {"school": school, "mode": mode, "bg": bg, "launch": form.get("launch") == "1"}
    (folder / "job.json").write_text(json.dumps(job), encoding="utf-8")
    (folder / "log.txt").write_text("", encoding="utf-8")
    (folder / "waiting.txt").write_text("", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--run-job", str(folder)],
        cwd=str(ASSISTANT.parent),
        creationflags=flags,
    )
    (folder / "pid.txt").write_text(str(process.pid), encoding="utf-8")
    return job_id


def _answer(form):
    folder = _job_dir(form.get("job"))
    if not _read(folder / "waiting.txt", 2000).strip():
        raise ValueError("The program is not waiting for an answer")
    quick = form.get("quick") or ""
    text = "" if quick == "ENTER" else (quick or form.get("typed") or "")
    if len(text) > 200:
        raise ValueError("Answer is too long")
    temporary = folder / "answer.tmp"
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, folder / "answer.txt")
    return folder.name


def _stop(form):
    folder = _job_dir(form.get("job"))
    (folder / "stop.txt").write_text("1", encoding="utf-8")
    pid_text = _read(folder / "pid.txt", 20).strip()
    if pid_text.isdigit():
        try:
            os.kill(int(pid_text), 15)
        except Exception:
            pass
    return folder.name


def attach(app):
    if "saini_idcard" in getattr(app, "view_functions", {}):
        return

    def _csrf(session):
        import secrets
        token = session.get("idcard_csrf")
        if not token:
            token = secrets.token_hex(16)
            session["idcard_csrf"] = token
        return token

    def _posted(request, session):
        import hmac
        sent = request.form.get("csrf") or ""
        stored = session.get("idcard_csrf") or ""
        if not stored or not hmac.compare_digest(sent, stored):
            raise ValueError("Reload the page and try again")

    @app.route("/saini/idcard", methods=["GET", "POST"])
    def saini_idcard():
        from flask import redirect, request, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/saini/idcard"))
        notice = ""
        job_id = (request.values.get("job") or "").strip()
        if request.method == "POST":
            try:
                _posted(request, session)
                action = request.form.get("action")
                if action == "start":
                    job_id = _start(request.form)
                    return redirect("/saini/idcard?job=" + job_id)
                if action == "answer":
                    job_id = _answer(request.form)
                    notice = "Answer sent."
                elif action == "stop":
                    job_id = _stop(request.form)
                    notice = "Stop sent."
                else:
                    notice = "Unknown action"
            except Exception as error:
                notice = str(error)
        try:
            if job_id:
                _job_dir(job_id)
        except Exception:
            job_id = ""
            notice = notice or "Unknown job"
        return _page(_csrf(session), notice, job_id)

    @app.route("/saini/idcard/audio")
    def saini_idcard_audio():
        from flask import redirect, request, send_file, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/saini/idcard"))
        folder = _job_dir(request.args.get("job"))
        clip = _audio_in_log(_read(folder / "log.txt"))
        if clip is None:
            raise ValueError("No audio for this job")
        return send_file(clip)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-job":
        run_job(sys.argv[2])
