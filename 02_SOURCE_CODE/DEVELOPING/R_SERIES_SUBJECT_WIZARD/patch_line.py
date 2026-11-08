# -*- coding: utf-8 -*-
"""Add the desktop production line. Does not run any desktop program."""
import hashlib
import py_compile
import shutil
from pathlib import Path

DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
DATA = DEV / "school_data.py"
DELIVERY = DEV / "school_delivery.py"
MODULE = DEV / "production_queue.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
QUEUE_FILE = Path(__file__).with_name("production_queue.py")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def dump(text, newline):
    if not text.endswith("\n"):
        text += "\n"
    return text.replace("\n", newline).encode("utf-8")


def lines_of(text):
    return text.split("\n")


def one(lines, snippet, name):
    hits = [i for i, line in enumerate(lines) if snippet in line]
    if len(hits) != 1:
        print("ABORT")
        print("reason=" + name)
        print("count=%d" % len(hits))
        for i, line in enumerate(lines):
            if snippet[:24] in line or name.split("_")[0].lower() in line.lower():
                print("%d:%s" % (i + 1, line))
        raise SystemExit(2)
    return hits[0]


def next_else(lines, start, name):
    for offset in range(1, 8):
        index = start + offset
        if index >= len(lines):
            break
        if lines[index].strip().startswith("else:"):
            return index
    print("ABORT")
    print("reason=" + name + "_ELSE")
    raise SystemExit(2)


def patch_data(text):
    if "part=line" in text or 'action == "join"' in text:
        print("ABORT")
        print("reason=ALREADY_DATA")
        raise SystemExit(2)
    lines = lines_of(text)
    order = one(lines, "school_delivery.save_order(", "DATA_ORDER")
    else_at = next_else(lines, order, "DATA_ORDER")
    indent = lines[else_at][:len(lines[else_at]) - len(lines[else_at].lstrip())]
    lines[else_at:else_at] = [
        indent + 'elif action == "join":',
        indent + "    import production_queue",
        indent + '    notice = production_queue.join_line(conn, school_code, form.get("kind"))',
    ]
    joined = "\n".join(lines)
    old_part = 'if part not in ("paper", "id", "result", "output", "account", "shipping"):'
    new_part = 'if part not in ("paper", "id", "result", "output", "account", "shipping", "line"):'
    if joined.count(old_part) != 1:
        print("ABORT")
        print("reason=DATA_PART")
        print("count=%d" % joined.count(old_part))
        raise SystemExit(2)
    joined = joined.replace(old_part, new_part, 1)
    old_map = '"shipping": "shipping"'
    if joined.count(old_map) != 1:
        print("ABORT")
        print("reason=DATA_MAP")
        print("count=%d" % joined.count(old_map))
        for i, line in enumerate(joined.split("\n")):
            if "cardsheet" in line or "shipping" in line and "part" in line:
                print("%d:%s" % (i + 1, line))
        raise SystemExit(2)
    joined = joined.replace(old_map, '"shipping": "shipping", "join": "line"', 1)
    old_title = '"shipping": "Shipping address"'
    if joined.count(old_title) != 1:
        print("ABORT")
        print("reason=DATA_TITLE")
        print("count=%d" % joined.count(old_title))
        raise SystemExit(2)
    joined = joined.replace(old_title, '"shipping": "Shipping address", "line": "Production line"', 1)
    lines = joined.split("\n")
    ship = one(lines, "school_delivery.shipping_block(conn, school_code, token)", "DATA_SHIP")
    else_at = next_else(lines, ship, "DATA_SHIP")
    indent = lines[else_at][:len(lines[else_at]) - len(lines[else_at].lstrip())]
    lines[else_at:else_at] = [
        indent + 'elif part == "line":',
        indent + "    import production_queue",
        indent + "    body = head + production_queue.school_block(conn, school_code, token)",
    ]
    menu = one(lines, 'href="/portal/data?part=shipping">6. Shipping address</a>', "DATA_MENU")
    prefix = lines[menu][:lines[menu].index("+")]
    lines.insert(menu + 1, prefix + "+ '<a class=\"go\" href=\"/portal/data?part=line\">7. Production line</a>'")
    return "\n".join(lines)


def patch_delivery(text):
    if "take_line" in text or "production_queue" in text:
        print("ABORT")
        print("reason=ALREADY_DELIVERY")
        raise SystemExit(2)
    lines = lines_of(text)
    start = one(lines, "def saini_queue(get_db, request, session):", "QUEUE_DEF")
    lines.insert(start + 1, "    import production_queue")
    notice = one(lines, "A job is never split.", "COMBINE")
    else_at = next_else(lines, notice, "COMBINE")
    indent = lines[else_at][:len(lines[else_at]) - len(lines[else_at].lstrip())]
    lines[else_at:else_at] = [
        indent + 'elif action == "take_line":',
        indent + "    notice = production_queue.take_next(conn)",
        indent + 'elif action == "finish_line":',
        indent + '    notice = production_queue.finish_current(conn, request.form.get("ok") == "1")',
    ]
    intro = one(lines, "Schools only request. Nothing is activated.", "QUEUE_INTRO")
    prefix = "        "
    lines.insert(intro + 1, prefix + "+ production_queue.saini_block(conn, token)")
    return "\n".join(lines)


def compile_text(text, path):
    path.write_bytes(text.encode("utf-8"))
    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        path.unlink(missing_ok=True)
        print("ABORT")
        print("reason=COMPILE")
        print(exc)
        raise SystemExit(2)
    path.unlink(missing_ok=True)


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        print("ABORT")
        print("reason=ORIGINAL_CHANGED")
        raise SystemExit(2)
    if not QUEUE_FILE.is_file():
        print("ABORT")
        print("reason=MODULE_MISSING")
        raise SystemExit(2)
    data_text, data_nl = load(DATA)
    delivery_text, delivery_nl = load(DELIVERY)
    updated_data = patch_data(data_text)
    updated_delivery = patch_delivery(delivery_text)
    if updated_data.count('action == "join"') != 1 or updated_data.count('part == "line"') != 1:
        print("ABORT")
        print("reason=DATA_COUNT")
        raise SystemExit(2)
    if updated_delivery.count('action == "take_line"') != 1 or updated_delivery.count("saini_block") != 1:
        print("ABORT")
        print("reason=DELIVERY_COUNT")
        raise SystemExit(2)
    compile_text(updated_data, DATA.with_name("school_data.line_check.py"))
    compile_text(updated_delivery, DELIVERY.with_name("school_delivery.line_check.py"))
    py_compile.compile(str(QUEUE_FILE), doraise=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    data_backup = BACKUP_DIR / "school_data_before_line.py"
    delivery_backup = BACKUP_DIR / "school_delivery_before_line.py"
    stamp = 2
    while data_backup.exists():
        data_backup = BACKUP_DIR / ("school_data_before_line_%d.py" % stamp)
        stamp += 1
    delivery_backup = BACKUP_DIR / data_backup.name.replace("school_data", "school_delivery")
    data_backup.write_bytes(DATA.read_bytes())
    delivery_backup.write_bytes(DELIVERY.read_bytes())
    DATA.write_bytes(dump(updated_data, data_nl))
    DELIVERY.write_bytes(dump(updated_delivery, delivery_nl))
    shutil.copy2(QUEUE_FILE, MODULE)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        DATA.write_bytes(data_backup.read_bytes())
        DELIVERY.write_bytes(delivery_backup.read_bytes())
        print("ABORT")
        print("reason=ORIGINAL_CHANGED")
        raise SystemExit(2)
    print("PATCH_OK")
    print("backup=%s" % data_backup)
    print("module=%s" % MODULE)
    print("school_uses_files=no")
    print("programs_started=no")
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("activation_changed=no")


if __name__ == "__main__":
    main()
