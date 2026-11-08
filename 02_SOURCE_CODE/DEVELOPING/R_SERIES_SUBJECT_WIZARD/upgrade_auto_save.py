# -*- coding: utf-8 -*-
"""Stop the file picker. PAPER.py output lands in the order folder."""
import py_compile
from pathlib import Path

DESK = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\order_desk.py")
PAPER = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\PAPER.py")
BLOCK = r'''

def _for_school(name, school):
    noise = set(ORDERED) | set(SUBJECTS) | set(SUBJECT_BIT.values()) | {
        "HM", "EM", "MEDIUM", "WORKSHEET", "PAPER", "ALL", "CHECK",
        "CLASS", "UNKNOWN", "SCHOOL", "DOCX", "PDF",
    }
    tokens = _tokens(name)
    if school in tokens:
        return True
    extra = [token for token in tokens if token.isalpha() and token not in noise and len(token) > 1]
    return not extra


def _output_files():
    if not PAPER_OUTPUT.is_dir():
        return []
    found = []
    for path in PAPER_OUTPUT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".docx", ".pdf"}:
            continue
        upper = path.name.upper()
        if "TEACHER_KEY" in upper or upper.startswith("DEMO_") or upper.endswith("_CHECK.DOCX"):
            continue
        if any(part.upper() in {"COMBINED_PDF", "BACKUPS"} for part in path.parts):
            continue
        found.append(path)
    found.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return found


def _take_generated(conn, folder, school, line, source):
    source = Path(source)
    detected = sheets_in_docx(source) if source.suffix.lower() == ".docx" else 0
    sheets = detected or int(line["sheets"] or 1)
    if sheets < 1 or sheets > 20:
        sheets = 1
    code = re.sub(r"[^A-Z0-9-]+", "-", source.stem.upper())[:80].strip("-") or "PAPER"
    target_dir = folder / "production_jobs" / "PAPERS" / school
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _safe(code + source.suffix.lower())
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        target.write_bytes(source.read_bytes())
    try:
        import document_archive
        document_archive.keep(folder, school, "paper", code, target)
    except Exception:
        pass
    master_amount, copy_amount = _bill(
        conn, school, line["class_name"], line["subject"], code, int(line["students"]), sheets,
    )
    conn.execute(
        """UPDATE paper_order_lines
        SET sheets=?, doc_code=?, filename=?, stored_path=? WHERE id=?""",
        (sheets, code, target.name, str(target), line["id"]),
    )
    conn.commit()
    return master_amount + copy_amount


def pull_generated(conn, folder, school):
    folder = root_of(folder)
    school = _school(school)
    ensure(conn)
    waiting = []
    for line in lines_for(conn, school):
        if line["lane"] != "legacy":
            continue
        if line["stored_path"] and Path(line["stored_path"]).is_file():
            continue
        waiting.append(line)
    placed = 0
    for source in _output_files():
        if not waiting:
            break
        for line in list(waiting):
            if not _matches(line, source.stem, source.name) or not _for_school(source.name, school):
                continue
            _take_generated(conn, folder, school, line, source)
            waiting.remove(line)
            placed += 1
            break
    return placed


def accept_generated(source):
    folder = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
    if not Path(source).is_file() or not folder.is_dir():
        return 0
    conn = connect(folder)
    try:
        schools = [row[0] for row in conn.execute("SELECT DISTINCT school_code FROM paper_order_lines")]
        total = 0
        for school in schools or ["BSM"]:
            total += pull_generated(conn, folder, school)
        return total
    finally:
        conn.close()

'''
HOOK = '''        export_to_ips_engine(row_data, page_texts, OUTPUT_FOLDER)
    try:
        import sys as _odsys
        _od = r"D:\\SAINI_TEACHER_TRIAL\\DEVELOPMENT_SUBJECT_WIZARD"
        if _od not in _odsys.path:
            _odsys.path.insert(0, _od)
        import order_desk as _oddesk
        _oddesk.accept_generated(output_path)
    except Exception as _oderr:
        print("  order folder skip:", _oderr)
    return output_path
'''


def once(text, old, new, label):
    if old not in text:
        if new.strip() in text or label == "hook" and "accept_generated(output_path)" in text:
            print(label, "already")
            return text
        raise SystemExit("ABORT missing " + label)
    print(label, "yes")
    return text.replace(old, new, 1)


def main():
    text = DESK.read_text(encoding="utf-8")
    if "def pull_generated" not in text:
        text = once(
            text,
            'r"D:\\SHRI_JAI_SHRI_RAM\\project_panels\\EXAM_PAPER_PROJECT\\PRINT_MANAGER.py",\n))\n',
            'r"D:\\SHRI_JAI_SHRI_RAM\\project_panels\\EXAM_PAPER_PROJECT\\PRINT_MANAGER.py",\n))\n'
            'PAPER_OUTPUT = Path(os.environ.get(\n'
            '    "SAINI_PAPER_OUTPUT",\n'
            '    r"D:\\SHRI_JAI_SHRI_RAM\\project_panels\\EXAM_PAPER_PROJECT\\OUTPUT",\n'
            '))\n',
            "output",
        )
        text = once(text, "\ndef link_saved(conn, folder, school):", BLOCK + "def link_saved(conn, folder, school):", "pull")
    else:
        print("pull already")
    text = text.replace(
        """            action = (
                '<form method="post" enctype="multipart/form-data">'
                '<input type="hidden" name="csrf" value="%s">'
                '<input type="hidden" name="action" value="save">'
                '<input type="hidden" name="line_id" value="%d">'
                '<input type="file" name="final_file" accept=".docx,.pdf" required>'
                '<input name="sheets" inputmode="numeric" placeholder="sheets" size="6">'
                '<button type="submit">Save final file</button></form>'
            ) % (token, int(row["id"]))""",
        '            action = "PAPER.py saves this file here. No file to choose."',
        1,
    )
    text = text.replace(
        "Class 3 to 12: choose the final file from the old project. Both land in the same folder.",
        "Class 3 to 12 is made by PAPER.py and the file comes here by itself.",
        1,
    )
    text = text.replace(
        "            sync_needs(conn, school)\n            link_saved(conn, folder, school)\n",
        "            sync_needs(conn, school)\n            pull_generated(conn, folder, school)\n            link_saved(conn, folder, school)\n",
        1,
    )
    DESK.write_text(text, encoding="utf-8")
    py_compile.compile(str(DESK), doraise=True)
    print("DESK_OK")
    if not PAPER.is_file():
        print("PAPER_SKIP missing")
        return
    paper = PAPER.read_text(encoding="utf-8")
    old = "        export_to_ips_engine(row_data, page_texts, OUTPUT_FOLDER)\n    return output_path\n"
    if "accept_generated(output_path)" in paper:
        print("HOOK already")
    elif old not in paper:
        print("HOOK skipped")
    else:
        PAPER.write_text(paper.replace(old, HOOK, 1), encoding="utf-8")
        py_compile.compile(str(PAPER), doraise=True)
        print("HOOK yes")


if __name__ == "__main__":
    main()
