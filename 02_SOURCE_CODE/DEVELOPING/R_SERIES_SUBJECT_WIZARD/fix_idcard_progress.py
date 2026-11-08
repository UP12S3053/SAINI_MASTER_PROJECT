# -*- coding: utf-8 -*-
from pathlib import Path
PATH = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\idcard_desk.py")
START = "def _progress(log, running):"
END = "\ndef _page("
CALL_OLD = "    percent, label = _progress(log, running)\n"
CALL_NEW = (
    "        started = (folder / \"job.json\").stat().st_mtime\n"
    "        percent, label = _progress(log, running, folder / \"log.txt\", started)\n"
    "    else:\n"
    "        percent, label = 0, \"\"\n"
)
NEW = r'''def _scan_log(path):
    found = {"whatsapp": 0, "ocr": 0, "slips": 0, "voice": None, "klass": "", "last_id": ""}
    if not path.is_file():
        return found
    voice_re = re.compile(r"generated\s+(\d+)/(\d+)\s+student clips")
    slip_re = re.compile(r"extracted\s+(\d+)\s+slips")
    class_re = re.compile(r"Processing Class:\s*(\S+)")
    id_re = re.compile(r"\b([A-Z]{2,8}\d{3,})\.(?:jpg|jpeg|png)", re.I)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "WhatsApp Image" in line:
                found["whatsapp"] += 1
            if "OCR: Image" in line:
                found["ocr"] += 1
            slip = slip_re.search(line)
            if slip:
                found["slips"] += int(slip.group(1))
            voice = voice_re.search(line)
            if voice:
                found["voice"] = (int(voice.group(1)), int(voice.group(2)))
            klass = class_re.search(line)
            if klass:
                found["klass"] = klass.group(1)
            card = id_re.search(line)
            if card:
                found["last_id"] = card.group(1)
    return found


def _clock(seconds):
    seconds = max(0, int(seconds))
    return "%d:%02d" % (seconds // 60, seconds % 60)


def _progress(log, running, path=None, started=None):
    found = _scan_log(path) if path else {
        "whatsapp": (log or "").count("WhatsApp Image"),
        "ocr": (log or "").count("OCR: Image"),
        "slips": 0, "voice": None, "klass": "", "last_id": "",
    }
    elapsed = (time.time() - started) if started else 0
    percent = 0
    label = "Waiting to start"
    if found["voice"]:
        done, total = found["voice"]
        percent = int(done * 100 / total) if total else 0
        label = "Voice %s / %s | %s" % (done, total, _clock(elapsed))
    elif found["slips"]:
        percent = min(90, 10 + found["ocr"])
        label = "OCR slips %s | images %s | %s" % (found["slips"], found["ocr"], _clock(elapsed))
    elif found["whatsapp"] or found["ocr"]:
        count = found["whatsapp"] or found["ocr"]
        percent = min(95, 8 + count)
        label = "Images %s" % count
        if found["klass"]:
            label += " | Class " + found["klass"]
        if found["last_id"]:
            label += " | " + found["last_id"]
        if elapsed >= 15 and count:
            label += " | %s | about %s/min" % (_clock(elapsed), max(1, int(count * 60 / elapsed)))
    elif running and (log or "").strip():
        percent = 6
        label = "Process running | " + _clock(elapsed)
    if not running and "finished" in (log or "").lower():
        percent = 100
        label = "Finished | " + _clock(elapsed)
    return percent, label


'''

def main():
    text = PATH.read_text(encoding="utf-8")
    if "def _scan_log(" in text:
        print("ALREADY")
        return
    at = text.find(START)
    end = text.find(END, at)
    if at < 0 or end < 0:
        raise SystemExit("ABORT progress block missing")
    text = text[:at] + NEW + text[end + 1:]
    if CALL_OLD not in text:
        raise SystemExit("ABORT call missing")
    text = text.replace(CALL_OLD, CALL_NEW, 1)
    compile(text, str(PATH), "exec")
    PATH.write_text(text, encoding="utf-8")
    print("PROGRESS_OK")

if __name__ == "__main__":
    main()
