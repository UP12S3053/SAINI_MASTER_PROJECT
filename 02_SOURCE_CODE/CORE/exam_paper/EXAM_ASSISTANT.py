#!/usr/bin/env python3
"""
SAINI EXAM PAPER MASTER ASSISTANT
Saara paper / print control yahin se.
"""

from __future__ import annotations

import sys as _trial_sys
if "--trial" in _trial_sys.argv:
    from trial_bridge import run_trial
    run_trial()
    raise SystemExit(0)


import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from paper_identity import parse_paper_name
except ImportError:
    parse_paper_name = None

HERE = Path(__file__).resolve().parent

if (HERE / "PAPER.py").exists():
    EXAM_ROOT = HERE
elif (HERE / "EXAM_PAPER_PROJECT").is_dir():
    EXAM_ROOT = HERE / "EXAM_PAPER_PROJECT"
else:
    EXAM_ROOT = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT")

PAPER_SCRIPT = EXAM_ROOT / "PAPER.py"
COMBINE_SCRIPT = EXAM_ROOT / "combine_exam_pdfs.py"
if not COMBINE_SCRIPT.exists():
    COMBINE_SCRIPT = HERE / "combine_exam_pdfs.py"
PRINT_PLAN_SCRIPT = EXAM_ROOT / "PRINT_PLAN.py"
if not PRINT_PLAN_SCRIPT.exists():
    PRINT_PLAN_SCRIPT = HERE / "PRINT_PLAN.py"
PRINT_MANAGER_SCRIPT = EXAM_ROOT / "PRINT_MANAGER.py"
if not PRINT_MANAGER_SCRIPT.exists():
    PRINT_MANAGER_SCRIPT = HERE / "PRINT_MANAGER.py"
FIX_MATH_SCRIPT = EXAM_ROOT / "fix_word_math.py"
if not FIX_MATH_SCRIPT.exists():
    FIX_MATH_SCRIPT = HERE / "fix_word_math.py"

IMAGES = EXAM_ROOT / "INPUT"
EXCEL = EXAM_ROOT / "PAPER.xlsx"
OUTPUT = EXAM_ROOT / "OUTPUT"
COMBINED = OUTPUT / "COMBINED_PDF"
SINGLE = COMBINED / "_single"
STRENGTH = EXAM_ROOT / "CLASS_STRENGTH.xlsx"
PRINT_TABLE = EXAM_ROOT / "PRINT_TABLE.xlsx"

SUBJECT_NORM = {
    "E.V.S.": "EVS", "E.V.S": "EVS", "EVS": "EVS", "E V S": "EVS",
    "G.K.": "GK", "G.K": "GK", "GK": "GK", "G K": "GK",
    "COMPUTE": "COMPUTER", "COMPUTER": "COMPUTER",
    "MATHS": "MATH", "MATH": "MATH", "MATHEMATICS": "MATH",
    "ENG": "ENGLISH", "ENGLISH": "ENGLISH",
    "HINDI": "HINDI", "SANSKRIT": "SANSKRIT",
    "SCIENCE": "SCIENCE", "SCI": "SCIENCE",
    "S.ST.": "SST", "S.ST": "SST", "SST": "SST", "S.S.T": "SST", "S.S.T.": "SST",
    "ART": "ART", "GOLU": "GOLU",
}

PRE_PRIMARY_ORDER = ["PLAY", "NUR", "LKG", "UKG"]
BOARD_ORDER = [
    "I", "II", "III", "IV", "V",
    "VI", "VII", "VIII", "IX", "X", "XI", "XII",
]
CLASS_ORDER = PRE_PRIMARY_ORDER + BOARD_ORDER
PRE_PRIMARY = set(PRE_PRIMARY_ORDER)
BOARD_CLASSES = set(BOARD_ORDER)
CLASS1_PLUS = set(BOARD_ORDER)
TOKEN_MAP = {
    "PLAY": "PLAY", "PLAYGROUP": "PLAY", "PLAY-GROUP": "PLAY",
    "PG": "PLAY", "PREPLAY": "PLAY",
    "NURSERY": "NUR", "NUR": "NUR", "PRENUR": "NUR", "PRE-NUR": "NUR",
    "PRENURSERY": "NUR", "PRE-NURSERY": "NUR",
    "LKG": "LKG", "L.K.G": "LKG", "L.K.G.": "LKG",
    "UKG": "UKG", "U.K.G": "UKG", "U.K.G.": "UKG",
    "XII": "XII", "XI": "XI", "VIII": "VIII", "VII": "VII",
    "III": "III", "II": "II", "IV": "IV", "IX": "IX",
    "VI": "VI", "V": "V", "X": "X", "I": "I",
    "12": "XII", "11": "XI", "10": "X",
    "9": "IX", "8": "VIII", "7": "VII", "6": "VI",
    "5": "V", "4": "IV", "3": "III", "2": "II", "1": "I",
    "01": "I", "02": "II", "03": "III", "04": "IV", "05": "V",
    "06": "VI", "07": "VII", "08": "VIII", "09": "IX",
}


def stream_of(cls: str) -> str:
    """PLAY-UKG = worksheet. I-XII = board exam. Kabhi mix nahi."""
    if cls in PRE_PRIMARY:
        return "WORKSHEET"
    return "BOARD"


def banner():
    print("=" * 70)
    print(" SAINI EXAM PAPER ASSISTANT")
    print("=" * 70)
    school = ""
    f = EXAM_ROOT / "CURRENT_SCHOOL.txt"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                school = line.upper()
                break
    print(f" Project : {EXAM_ROOT}")
    print(f" School  : {school or 'AUTO (INPUT filenames)'}")
    print(f" Time    : {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    print("=" * 70)


def ensure_folders():
    for p in (IMAGES, OUTPUT, COMBINED, SINGLE):
        p.mkdir(parents=True, exist_ok=True)


def count_files(folder: Path, exts) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts)


def status():
    print("\n--- PROJECT STATUS ---")
    n_img = count_files(IMAGES, {".jpg", ".jpeg", ".png", ".webp"})
    n_pdf = count_files(IMAGES, {".pdf"})
    print(f"INPUT images    : {n_img}")
    print(f"INPUT PDFs      : {n_pdf}")
    print(f"PAPER.xlsx      : {'YES' if EXCEL.exists() else 'MISSING'}")
    print(f"Word papers     : {count_files(OUTPUT, {'.docx'})}")
    print(f"Single PDFs     : {count_files(SINGLE, {'.pdf'})}")
    class_pdfs = 0
    schools = 0
    if COMBINED.is_dir():
        for child in COMBINED.iterdir():
            if child.is_dir() and child.name != "_single":
                schools += 1
                class_pdfs += count_files(child, {".pdf"})
        class_pdfs += count_files(COMBINED, {".pdf"})
    print(f"School folders  : {schools}")
    print(f"Combined PDFs   : {class_pdfs}")
    print(f"PAPER.xlsx      : {'YES' if EXCEL.exists() else 'MISSING'}  (STUDENTS yahi se)")
    print(f"PRINT_TABLE     : {'YES' if PRINT_TABLE.exists() else 'MISSING  (pehle F chalao)'}")
    print(f"PRINT_PLAN      : {'YES' if (OUTPUT / 'PRINT_PLAN.xlsx').exists() else 'NO'}")
    print(f"PAPER.py        : {'YES' if PAPER_SCRIPT.exists() else 'MISSING'}")
    print(f"PRINT_PLAN.py   : {'YES' if PRINT_PLAN_SCRIPT.exists() else 'MISSING'}")
    print(f"PRINT_MANAGER   : {'YES' if PRINT_MANAGER_SCRIPT.exists() else 'MISSING'}")


def run_python(script: Path, extra_args=None) -> int:
    if not script.exists():
        print(f"File nahi mili: {script}")
        return 1
    cmd = [sys.executable, str(script)] + list(extra_args or [])
    print("Command:", " ".join(cmd))
    print("-" * 70)
    result = subprocess.run(cmd, cwd=str(EXAM_ROOT))
    return result.returncode


def _clean_cell(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return s


def _norm_subject(v) -> str:
    s = _clean_cell(v).upper().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if not s:
        return ""
    if s in SUBJECT_NORM:
        return SUBJECT_NORM[s]
    compact = s.replace(".", "").replace(" ", "")
    for k, val in SUBJECT_NORM.items():
        if compact == k.replace(".", "").replace(" ", ""):
            return val
    return compact


def _norm_layout(v) -> str:
    """Excel LAYOUT column. Class se 1-UP/2-UP hardcode nahi."""
    s = _clean_cell(v).upper().replace(" ", "").replace("_", "").replace("-", "")
    if s in {"1", "1UP", "ONEUP", "FULL", "FULLA4", "A4"}:
        return "1-UP"
    if s in {"2", "2UP", "TWOUP", "TWIN", "2UPTWIN"}:
        return "2-UP"
    return "2-UP"


def _cls_of(token: str):
    t = (token or "").strip().upper()
    if t in {"7,8", "7-8", "78", "VII_VIII", "VII-VIII"}:
        return "VII_VIII"
    raw = re.sub(r"[^A-Z0-9]", "", t)
    return TOKEN_MAP.get(raw) or TOKEN_MAP.get(t)


def _parse_name(name: str):
    """class, subject, medium, school Ã¢â‚¬â€ HM/EM alag job."""
    if parse_paper_name is not None:
        meta = parse_paper_name(name)
        if not meta.get("class"):
            return None
        return meta["class"], meta["subject"], meta.get("medium") or "", meta["school"]

    stem = Path(name).stem
    parts = [p for p in re.split(r"[_\-]+", stem) if p]
    if len(parts) < 2:
        return None
    cls = _cls_of(parts[0])
    if not cls:
        return None
    subject_idx = None
    for i, p in enumerate(parts[1:], start=1):
        if p.upper() in [
            "ENGLISH", "HINDI", "MATH", "EVS", "SCIENCE", "COMPUTER",
            "GK", "SST", "SANSKRIT", "ART", "GOLU", "E.V.S.", "E.V.S",
            "ENG-GRAMMER", "ENG-I", "ENG-II",
            "HINDI-I", "HINDI-II", "G.K.", "PHY. EDU.", "ACCOUNTANCY",
            "BUSINESS STUDY", "HISTORY", "ECO", "PHYSICAL", "BUSINESS",
            "MATHS", "PHY.EDU.", "S.S.T", "S.S.T.",
            "PHYSICAL SCIENCE", "CONVERSATION", "COMMUNICATION", "URDU"
        ]:
            subject_idx = i
            break
    medium = ""
    if subject_idx is None:
        school = "_".join(parts[1:]).strip("_").upper() or "UNKNOWN_SCHOOL"
        subject = parts[1] if len(parts) > 1 else "PAPER"
    else:
        subject = parts[subject_idx]
        rest = parts[subject_idx + 1:]
        if rest and rest[0].upper() in {"HM", "EM", "HINDI_MEDIUM", "ENGLISH_MEDIUM"}:
            medium = "HINDI_MEDIUM" if rest[0].upper() in {"HM", "HINDI_MEDIUM"} else "ENGLISH_MEDIUM"
            rest = rest[1:]
        school = "_".join(rest).strip("_").upper() or "UNKNOWN_SCHOOL"
    school = re.sub(r"[^\w]+", "_", school).strip("_").upper()
    return cls, subject, medium, school


def _merge_pdfs_with_watermark(files, dest: Path, watermark_text="") -> int:
    """Merge PDFs and add a diagonal watermark to every page."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            print("  pypdf missing. Run:  pip install pypdf")
            return 0

    # Watermark support imports
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import Color
        from io import BytesIO
    except ImportError:
        canvas = None
        A4 = None
        Color = None
        BytesIO = None

    writer = PdfWriter()
    pages = 0
    for f in files:
        try:
            reader = PdfReader(str(f))
            for page in reader.pages:
                if watermark_text and canvas is not None:
                    # Create watermark PDF for this page
                    watermark_buf = BytesIO()
                    c = canvas.Canvas(watermark_buf, pagesize=A4)
                    c.saveState()
                    c.translate(A4[0] / 2, A4[1] / 2)
                    c.rotate(45)
                    c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.3))
                    c.setFont("Helvetica", 30)
                    c.drawCentredString(0, 0, watermark_text)
                    c.restoreState()
                    c.save()
                    watermark_buf.seek(0)

                    watermark_reader = PdfReader(watermark_buf)
                    watermark_page = watermark_reader.pages[0]
                    page.merge_page(watermark_page)

                writer.add_page(page)
                pages += 1
        except Exception as exc:
            print(f"  skip {Path(f).name}: {exc}")
    if pages == 0:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)
    return pages


def _docx_to_pdf(docx: Path, pdf: Path, word) -> bool:
    doc = None
    try:
        if pdf.exists():
            try:
                pdf.unlink()
            except OSError:
                pass
        pdf.parent.mkdir(parents=True, exist_ok=True)
        doc = word.Documents.Open(str(docx.resolve()), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.ExportAsFixedFormat(str(pdf.resolve()), 17)
        except Exception:
            doc.SaveAs(str(pdf.resolve()), FileFormat=17)
        return pdf.exists() and pdf.stat().st_size > 0
    except Exception as exc:
        print(f"  X {docx.name}: {exc}")
        return False
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass


def build_pdfs_builtin() -> int:
    print("\n=== B: Word se PDF + class-wise combine ===")
    
    # ============================================================
    # COMMAND-LINE WATERMARK CONTROL
    # ============================================================
    # Usage:
    #   python EXAM_ASSISTANT.py --watermark "TEXT"   (watermark ON)
    #   python EXAM_ASSISTANT.py --no-watermark       (watermark OFF)
    #   python EXAM_ASSISTANT.py                      (default: watermark ON)
    # ============================================================
    watermark_text = "PROOF COPY - NOT FOR DISTRIBUTION"  # DEFAULT
    if "--no-watermark" in sys.argv:
        watermark_text = ""
    elif "--watermark" in sys.argv:
        try:
            idx = sys.argv.index("--watermark")
            if idx + 1 < len(sys.argv):
                watermark_text = sys.argv[idx + 1]
        except Exception:
            watermark_text = "PROOF COPY - NOT FOR DISTRIBUTION"
    
    print(f"  Watermark Status: {'OFF' if not watermark_text else watermark_text}")
    
    OUTPUT.mkdir(parents=True, exist_ok=True)
    COMBINED.mkdir(parents=True, exist_ok=True)
    SINGLE.mkdir(parents=True, exist_ok=True)
    docx_files = [
        p for p in sorted(OUTPUT.glob("*.docx"))
        if not p.name.startswith("~$") and not p.name.startswith("__paper_")
    ]
    print(f" OUTPUT folder : {OUTPUT}")
    print(f" Word papers   : {len(docx_files)}")
    if not docx_files:
        print(" OUTPUT me koi .docx nahi hai. Pehle option A se papers banao.")
        return 1
    try:
        import win32com.client
    except ImportError:
        print(" pywin32 nahi hai. Run:  pip install pywin32")
        return 1
    print(" Microsoft Word se PDF bana raha hoon...")
    word = None
    made = 0
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        total = len(docx_files)
        for i, docx in enumerate(docx_files, 1):
            dest = SINGLE / (docx.stem + ".pdf")
            if dest.exists() and dest.stat().st_size > 0:
                print(f"  [{i}/{total}] already {dest.name}")
                made += 1
                continue
            print(f"  [{i}/{total}] PDF: {docx.name}")
            if _docx_to_pdf(docx, dest, word):
                made += 1
                print(f"      OK {dest.name}")
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
    print(f" Single PDFs   : {made}")
    pdfs = []
    seen = set()
    # SIRF SINGLE folder se PDFs scan karein Ã¢â‚¬â€ current school ki hi PDFs
    for folder in (SINGLE,):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.pdf")):
            up = p.name.upper()
            if up.startswith(("CLASS_", "ALL_PAPERS", "ALL_SCHOOLS")):
                continue
            if p.name.upper() in seen:
                continue
            seen.add(p.name.upper())
            pdfs.append(p)
    if not pdfs:
        print(" Single PDF nahi bani.")
        return 1
    by_school = {}
    unused = []
    wanted = ""
    cf = EXAM_ROOT / "CURRENT_SCHOOL.txt"
    if cf.exists():
        for line in cf.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                wanted = re.sub(r"[^\w]+", "", line.upper())
                break
    if not wanted:
        try:
            import pdf_input
            wanted = re.sub(r"[^\w]+", "", pdf_input.current_school_token(EXAM_ROOT, IMAGES) or "")
        except Exception:
            wanted = ""
    print(f" CURRENT SCHOOL LOCK: {wanted or 'OFF'}")

    for p in pdfs:
        meta = _parse_name(p.name)
        if not meta:
            unused.append(p.name)
            continue
        cls, _subj, _med, school = meta[:4] if len(meta) >= 4 else (*meta, "", meta[-1])
        if wanted:
            tag = re.sub(r"[^\w]+", "", (school or "") + p.stem.upper())
            if wanted not in tag:
                continue
        class_bits = re.split(r"[+&,_\-\s]+", str(cls or ""))
        mapped = []
        for bit in class_bits:
            got = _cls_of(bit)
            if got:
                mapped.append(got)
        if not mapped:
            mapped = [cls]
        for one_cls in mapped:
            by_school.setdefault(school, {}).setdefault(one_cls, []).append(p)
    every_board = []
    every_ws = []
    for school, buckets in sorted(by_school.items()):
        ws_dir = COMBINED / school / "WORKSHEET_PLAY_UKG"
        board_dir = COMBINED / school / "BOARD_I_XII"
        ws_dir.mkdir(parents=True, exist_ok=True)
        board_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n School: {school}")
        print("  Stream alag: PLAY-UKG worksheet  |  I-XII board exam")
        school_ws = []
        school_board = []
        for cls in PRE_PRIMARY_ORDER:
            group = buckets.get(cls) or []
            if not group:
                continue
            dest = ws_dir / f"CLASS_{cls}_WORKSHEETS.pdf"
            n = _merge_pdfs_with_watermark(group, dest, watermark_text)
            print(f"  [WORKSHEET] CLASS_{cls}_WORKSHEETS.pdf  ({len(group)} papers, {n} pages)")
            school_ws.extend(group)
        for cls in BOARD_ORDER:
            group = buckets.get(cls) or []
            if not group:
                continue
            dest = board_dir / f"CLASS_{cls}_ALL_SUBJECTS.pdf"
            n = _merge_pdfs_with_watermark(group, dest, watermark_text)
            print(f"  [BOARD] CLASS_{cls}_ALL_SUBJECTS.pdf  ({len(group)} papers, {n} pages)")
            school_board.extend(group)
        if school_ws:
            dest = ws_dir / "PLAY_TO_UKG_ALL_WORKSHEETS.pdf"
            n = _merge_pdfs_with_watermark(school_ws, dest, watermark_text)
            print(f"  [WORKSHEET] PLAY_TO_UKG_ALL_WORKSHEETS.pdf  ({len(school_ws)} papers, {n} pages)")
            every_ws.extend(school_ws)
        if school_board:
            dest = board_dir / "CLASS_1_AND_ABOVE_ALL_SUBJECTS.pdf"
            n = _merge_pdfs_with_watermark(school_board, dest, watermark_text)
            print(f"  [BOARD] CLASS_1_AND_ABOVE_ALL_SUBJECTS.pdf  ({len(school_board)} papers, {n} pages)")
            dest = board_dir / "ALL_BOARD_PAPERS_COMBINED.pdf"
            n = _merge_pdfs_with_watermark(school_board, dest, watermark_text)
            print(f"  [BOARD] ALL_BOARD_PAPERS_COMBINED.pdf  ({len(school_board)} papers, {n} pages)")
            every_board.extend(school_board)
    if every_ws:
        dest = COMBINED / "ALL_SCHOOLS_PLAY_UKG_WORKSHEETS.pdf"
        n = _merge_pdfs_with_watermark(every_ws, dest, watermark_text)
        print(f"\n ALL_SCHOOLS_PLAY_UKG_WORKSHEETS.pdf  ({len(every_ws)} papers, {n} pages)")
    if every_board:
        dest = COMBINED / "ALL_SCHOOLS_BOARD_I_XII.pdf"
        n = _merge_pdfs_with_watermark(every_board, dest, watermark_text)
        print(f"\n ALL_SCHOOLS_BOARD_I_XII.pdf  ({len(every_board)} papers, {n} pages)")
    if unused:
        print("\n Unclassified:")
        for name in unused:
            print(f"  {name}")
    print(f"\n Combined folder: {COMBINED}")
    return 0


def _index_paper_files():
    """OUTPUT + _single se class/subject -> best file path."""
    catalog = []
    folders = [OUTPUT, SINGLE, COMBINED]
    for folder in folders:
        if not folder.is_dir():
            continue
        try:
            items = list(folder.iterdir())
        except OSError:
            continue
        for p in items:
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".pdf", ".docx"}:
                continue
            if p.name.startswith("~$") or p.name.upper().startswith(("CLASS_", "ALL_", "PRINT")):
                continue
            meta = _parse_name(p.name)
            if not meta:
                # fallback: first token class
                parts = [x for x in re.split(r"[_\-]+", p.stem) if x]
                if len(parts) >= 2:
                    cls = _cls_of(parts[0])
                    sub = _norm_subject(parts[1])
                    if cls:
                        catalog.append((cls, sub, "", p))
                continue
            if len(meta) >= 4:
                cls, subject, medium, _school = meta
            else:
                cls, subject, _school = meta
                medium = ""
            catalog.append((cls, _norm_subject(subject), medium or "", p))
    return catalog


def _class_from_text(class_name: str) -> str:
    raw = _clean_cell(class_name).upper()
    if raw in {"7,8", "7,8", "78", "VII_VIII"}:
        return "VII_VIII"
    token = re.sub(r"[^A-Z0-9]", "", raw)
    return TOKEN_MAP.get(token, "") or TOKEN_MAP.get(raw, "")


def resolve_class_and_path(class_name: str, subject: str, source_hint: str = "") -> tuple[str, str]:
    """
    CLASS kabhi subject-only guess se nahi bharega (wahi III wala bug).
    Priority:
      1) FILE/path ke filename se CLASS+SUBJECT
      2) sheet ki CLASS + SUBJECT se exact file
      3) file na mile to CLASS waise hi, path khali
    """
    hint = _clean_cell(source_hint)
    sheet_cls = _class_from_text(class_name)
    sub = _norm_subject(subject)

    file_cls = ""
    file_sub = ""
    if hint:
        meta = _parse_name(Path(hint).name)
        if meta:
            if len(meta) >= 4:
                file_cls, file_sub, file_med, _school = meta
            else:
                file_cls, file_sub, _school = meta
                file_med = ""
            file_sub = _norm_subject(file_sub)

    # filename jeetega Ã¢â‚¬â€ galat III overwrite nahi
    cls = file_cls or sheet_cls
    if file_sub:
        sub = file_sub

    catalog = getattr(resolve_class_and_path, "_cat", None)
    if catalog is None:
        catalog = _index_paper_files()
        resolve_class_and_path._cat = catalog

    file_med = locals().get("file_med", "")
    hits = []
    for item in catalog:
        if len(item) >= 4:
            fcls, fsub, fmed, path = item[0], item[1], item[2], item[3]
        else:
            fcls, fsub, path = item[0], item[1], item[2]
            fmed = ""
        if sub and fsub != sub:
            continue
        if cls and fcls != cls:
            continue
        if file_med and fmed and file_med != fmed:
            continue
        hits.append((fcls, fsub, path))

    # class khali + kai files (I MATH, III MATH, IV MATH) -> guess MAT karo
    if not cls:
        classes = {h[0] for h in hits if h[0]}
        if len(classes) != 1:
            if hint:
                p = Path(hint)
                if p.exists():
                    return sheet_cls, str(p)
            return sheet_cls, hint
        cls = classes.pop()

    def score(item):
        fcls, _fsub, path = item
        return (
            0 if path.suffix.lower() == ".pdf" else 1,
            0 if path.parent == SINGLE else 1,
            0 if fcls == cls else 1,
            len(path.name),
        )

    exact = [h for h in hits if h[0] == cls]
    use = exact or hits
    if use:
        use.sort(key=score)
        fcls, _fsub, path = use[0]
        return (cls or fcls), str(path)

    if hint:
        p = Path(hint)
        if p.exists():
            return cls or sheet_cls, str(p)
        for folder in (SINGLE, OUTPUT):
            cand = folder / Path(hint).name
            if cand.exists():
                return cls or sheet_cls, str(cand)
    return cls or sheet_cls, hint


def fill_excel_paths(xlsx_path: Path) -> int:
    """
    CLASS nan/khali ho to filename se bharo.
    SOURCE_FILE / FILE khali ho to OUTPUT se path bharo.
    PRINT_MANAGER ko alag update ki zarurat nahi.
    """
    if not xlsx_path.exists():
        print(f"  path fill skip, file nahi: {xlsx_path}")
        return 0
    try:
        import pandas as pd
    except ImportError:
        print("  pandas nahi. pip install pandas openpyxl")
        return 0

    resolve_class_and_path._cat = None
    changed = 0
    try:
        sheets = pd.read_excel(xlsx_path, sheet_name=None)
    except Exception as exc:
        print(f"  Excel read fail: {exc}")
        return 0

    out_sheets = {}
    for sname, df in sheets.items():
        cols = {str(c).strip().upper(): c for c in df.columns}
        c_class = cols.get("CLASS")
        c_sub = cols.get("SUBJECT")
        c_src = None
        for key in ("SOURCE_FILE", "FILE", "PDF", "DOCX", "PATH"):
            if key in cols:
                c_src = cols[key]
                break
        if c_class is None and "CLASS" not in df.columns:
            df.insert(0, "CLASS", "")
            c_class = "CLASS"
        if c_src is None:
            df["SOURCE_FILE"] = ""
            c_src = "SOURCE_FILE"
        if c_sub is None:
            out_sheets[sname] = df
            continue

        df[c_class] = df[c_class].map(lambda v: _clean_cell(v)).astype(object)
        df[c_src] = df[c_src].map(lambda v: _clean_cell(v)).astype(object)
        df[c_sub] = df[c_sub].map(lambda v: _clean_cell(v)).astype(object)

        for i, row in df.iterrows():
            new_cls, new_src = resolve_class_and_path(
                row.get(c_class, ""),
                row.get(c_sub, ""),
                row.get(c_src, ""),
            )
            old_cls = _clean_cell(row.get(c_class, ""))
            old_src = _clean_cell(row.get(c_src, ""))
            # PAPER.xlsx CLASS jeetega. Filename se CLASS overwrite nahi.
            if (not _class_from_text(old_cls)) and new_cls:
                df.at[i, c_class] = new_cls
                changed += 1
            if (not old_src) and new_src:
                df.at[i, c_src] = new_src
                changed += 1
        out_sheets[sname] = df

    if changed:
        try:
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                for sname, df in out_sheets.items():
                    df.to_excel(writer, index=False, sheet_name=str(sname)[:31])
            print(f"  AUTO PATH/CLASS update: {changed} cells  -> {xlsx_path.name}")
        except Exception as exc:
            print(f"  Excel write fail (file band karo): {exc}")
            return 0
    else:
        print(f"  PATH/CLASS already filled: {xlsx_path.name}")
    return changed


def rebuild_jobs_from_files(xlsx_path: Path) -> int:
    """
    PAPER.xlsx ki gali CLASS rows hatao.
    OUTPUT/_single ki har unique paper = 1 sample job.
    """
    try:
        import pandas as pd
    except ImportError:
        print("  pandas nahi")
        return 0

    catalog = _index_paper_files()
    best = {}
    for item in catalog:
        if len(item) >= 4:
            cls, sub, medium, path = item[0], item[1], item[2], item[3]
        else:
            cls, sub, path = item[0], item[1], item[2]
            medium = ""
        if not cls or not sub:
            continue
        if path.suffix.lower() not in {".pdf", ".docx"}:
            continue
        key = (cls, sub, medium or "")
        prev = best.get(key)
        score = (
            0 if path.suffix.lower() == ".pdf" else 1,
            0 if path.parent == SINGLE else 1,
            len(path.name),
        )
        if prev is None or score < prev[0]:
            best[key] = (score, path)

    if not best:
        print("  disk par paper file nahi mili")
        return 0

    old_map = {}
    if xlsx_path.exists():
        try:
            old_df = pd.read_excel(xlsx_path)
            cols = {str(c).strip().upper(): c for c in old_df.columns}
            c_class = cols.get("CLASS")
            c_sub = cols.get("SUBJECT")
            if c_class and c_sub:
                for _, row in old_df.iterrows():
                    c_med = cols.get("MEDIUM")
                    med = ""
                    if c_med:
                        med = _clean_cell(row.get(c_med, ""))
                    k = (_class_from_text(row.get(c_class, "")), _norm_subject(row.get(c_sub, "")), med)
                    if k[0] and k[1]:
                        old_map[k] = row
        except Exception:
            old_map = {}

    rows = []
    for key in sorted(best.keys(), key=lambda x: (CLASS_ORDER.index(x[0]) if x[0] in CLASS_ORDER else 99, x[1], x[2] if len(x) > 2 else "")):
        cls, sub = key[0], key[1]
        medium = key[2] if len(key) > 2 else ""
        path = best[key][1]
        prev = old_map.get(key) or old_map.get((cls, sub, "")) or old_map.get((cls, sub))
        school = "D.P. PUBLIC SCHOOL (PANIPAT)"
        students = 1
        sheets_per = 0.5
        printed = 0
        layout = "2-UP"
        if prev is not None:
            prev_cols = {str(c).strip().upper(): c for c in prev.index}
            if prev_cols.get("SCHOOL NAME"):
                school = _clean_cell(prev.get(prev_cols["SCHOOL NAME"])) or school
            if prev_cols.get("STUDENTS"):
                try:
                    students = int(float(str(prev.get(prev_cols["STUDENTS"])).strip() or 1))
                except Exception:
                    students = 1
            if prev_cols.get("SHEETS_PER_COPY"):
                sheets_per = prev.get(prev_cols["SHEETS_PER_COPY"])
            if prev_cols.get("PRINTED_SHEETS"):
                printed = prev.get(prev_cols["PRINTED_SHEETS"])
            layout_col = prev_cols.get("LAYOUT") or prev_cols.get("UP") or prev_cols.get("PRINT_MODE")
            if layout_col:
                layout = _norm_layout(prev.get(layout_col))
        rows.append({
            "CLASS": cls,
            "SUBJECT": sub,
            "MEDIUM": medium,
            "SCHOOL NAME": school,
            "STUDENTS": students,
            "LAYOUT": layout,
            "SHEETS_PER_COPY": sheets_per,
            "REQUIRED_SHEETS": 1,
            "PRINTED_SHEETS": printed,
            "FILE": str(path),
            "SOURCE_FILE": str(path),
        })

    bak = xlsx_path.with_suffix(xlsx_path.suffix + ".bak")
    try:
        if xlsx_path.exists() and not bak.exists():
            bak.write_bytes(xlsx_path.read_bytes())
    except Exception:
        pass

    try:
        pd.DataFrame(rows).to_excel(xlsx_path, index=False)
    except Exception as exc:
        print(f"  Excel write fail (file band karo): {exc}")
        return 0

    print(f"  SAMPLE LIST rebuild: {len(rows)} papers -> {xlsx_path.name}")
    for r in rows:
        print(f"    {r['CLASS']:>8} / {r['SUBJECT']:<12} {r.get('MEDIUM') or '-':<4} {Path(r['FILE']).name}")
    return len(rows)


def prepare_print_excels():
    """PAPER.xlsx master. Rows/students/layout/school overwrite nahi."""
    print("\n--- PAPER.xlsx MASTER (rows overwrite nahi) ---")
    print(" F: VI_VII file se VI_GK + VII_GK copies bana raha hoon...")
    split_combined_output()
    resolve_class_and_path._cat = None
    n = 0
    if EXCEL.exists():
        n += fill_excel_paths(EXCEL)
        n += sync_input_pdfs()
        print(f"  PAPER.xlsx control ON: {EXCEL}")
    else:
        print(f"  PAPER.xlsx nahi mili: {EXCEL}")
    if PRINT_TABLE.exists():
        n += fill_excel_paths(PRINT_TABLE)
    print("  rebuild_jobs_from_files BAND Ã¢â‚¬â€ PAPER.xlsx ki STUDENTS/LAYOUT/SCHOOL safe")
    print(f" Papers indexed: {len(_index_paper_files())}")
    return n


def fix_math_in_output():
    """OUTPUT + school subfolders: \\frac / \\sqrt\\frac -> Word Equation."""
    print(" Math fix script:", FIX_MATH_SCRIPT)
    print(" Target folder  :", OUTPUT)
    if not FIX_MATH_SCRIPT.exists():
        print(" fix_word_math.py project folder me rakho.")
        return 1
    if FIX_MATH_SCRIPT.exists():
        return run_python(FIX_MATH_SCRIPT, [str(OUTPUT)])
    try:
        from fix_word_math import fix_folder
        n = fix_folder(OUTPUT)
        print(f" Math fix paragraphs: {n}")
        return 0
    except Exception as exc:
        print(f" Math fix skip: {exc}")
        print(" fix_word_math.py isi folder me rakho.")
        return 1


def sync_input_pdfs():
    """INPUT/VI_MATH_MOHALI.pdf -> PAPER.xlsx SOURCE_FILE path khud."""
    helper = HERE / "pdf_input.py"
    if not helper.exists():
        helper = EXAM_ROOT / "pdf_input.py"
    if not helper.exists():
        print("  pdf_input.py project folder me rakho")
        return 0
    try:
        if str(helper.parent) not in sys.path:
            sys.path.insert(0, str(helper.parent))
        import pdf_input
        return pdf_input.sync_excel_source_files(EXCEL, IMAGES)
    except Exception as exc:
        print(f"  PDF sync skip: {exc}")
        return 0


def make_papers():
    print("\n=== A: Papers banana (OCR + Word + PDF auto) ===")
    if not EXCEL.exists():
        print(f"PAPER.xlsx nahi mili: {EXCEL}")
        return
    sync_input_pdfs()
    n_img = count_files(IMAGES, {".jpg", ".jpeg", ".png", ".webp"})
    n_pdf = count_files(IMAGES, {".pdf"})
    if n_img == 0 and n_pdf == 0:
        print(f"INPUT folder khali hai: {IMAGES}")
        print("  jpg : 101.jpg     ya")
        print("  pdf : VI_MATH_MOHALI.pdf")
        return
    print(f" INPUT images {n_img} | PDFs {n_pdf}")
    code = run_python(PAPER_SCRIPT)
    from question_engine.output_pass import pass_locked_layouts
    pass_locked_layouts(OUTPUT)
    print(f"PAPER.py exit code: {code}")
    print("\nLaTeX \\frac ko Word Equation me badal raha hoon...")
    fix_math_in_output()
    print("\nCombined class (VI_VII) se alag header copies...")
    split_combined_output()
    print("\nAb PDF combine...")
    build_pdfs_builtin()


def split_combined_output():
    """VI_VII ek Word Ã¢â€ â€™ VI header + VII header. Gemini dubara nahi."""
    helper = HERE / "split_combined_class_docs.py"
    if not helper.exists():
        helper = EXAM_ROOT / "split_combined_class_docs.py"
    if not helper.exists():
        print("  split_combined_class_docs.py project folder me rakho")
        return 0
    try:
        if str(helper.parent) not in sys.path:
            sys.path.insert(0, str(helper.parent))
        import split_combined_class_docs as scd
        made = scd.split_folder(OUTPUT)
        print(f"  class copies: {len(made)}")
        return len(made)
    except Exception as exc:
        print(f"  class split skip: {exc}")
        return 0


def combine_pdfs():
    print("\nPDF se pehle math fix...")
    fix_math_in_output()
    split_combined_output()
    code = build_pdfs_builtin()
    if code != 0 and COMBINE_SCRIPT.exists():
        run_python(COMBINE_SCRIPT, ["--output", str(OUTPUT)])


def run_print_plan():
    print("\n=== F: Printing plan + PRINT_TABLE ===")
    prepare_print_excels()
    if not EXCEL.exists():
        print(f"  PAPER.xlsx nahi mili: {EXCEL}")
    if not PRINT_PLAN_SCRIPT.exists():
        print("PRINT_PLAN.py project folder me rakho.")
        return
    run_python(PRINT_PLAN_SCRIPT)
    if PRINT_TABLE.exists():
        print(f"\n PRINT_TABLE ready: {PRINT_TABLE}")
        print(" Ab G se batch dekho, H se print chalao.")
    else:
        print(" PRINT_TABLE nahi bani. Latest PRINT_PLAN.py rakho.")


def run_print_preview():
    print("\n=== G: Print batches preview ===")
    prepare_print_excels()
    if not EXCEL.exists():
        print(" PAPER.xlsx nahi mili. Pehle F chalao.")
        return
    if not PRINT_MANAGER_SCRIPT.exists():
        print("PRINT_MANAGER.py project folder me rakho.")
        return
    run_python(PRINT_MANAGER_SCRIPT, ["--plan-only", "--excel", str(EXCEL)])


def run_print_operator():
    print("\n=== H: Printer operator ===")
    prepare_print_excels()
    if not EXCEL.exists():
        print(" PAPER.xlsx nahi mili. Pehle F chalao.")
        return
    if not PRINT_MANAGER_SCRIPT.exists():
        print("PRINT_MANAGER.py project folder me rakho.")
        return
    print(" Batch kaise chale?")
    print("  Enter     = sab batches 1 se")
    print("  2         = batch 2 se aage (1 skip)")
    print("  3         = batch 3 se aage")
    print("  only 4    = sirf batch 4")
    print("  only 5,6  = sirf 5 aur 6")
    raw = input(" Batch: ").strip().lower()
    extra = []
    if raw.startswith("only"):
        nums = [int(x) for x in raw.replace("only", "").replace(",", " ").split() if x.isdigit()]
        if len(nums) == 1:
            extra = ["--only-batch", str(nums[0])]
        elif nums:
            extra = ["--from-batch", str(min(nums)), "--to-batch", str(max(nums))]
    elif raw.isdigit():
        extra = ["--from-batch", raw]
    print(" PAPER.xlsx se print. FRONT ke baad palatna.")
    run_python(PRINT_MANAGER_SCRIPT, ["--print", "--excel", str(EXCEL), *extra])


def open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    else:
        print(path)


def main():
    banner()
    ensure_folders()
    status()
    print("\nKya karna hai?")
    print("A -> Papers banao (OCR + Word) phir PDF jodo")
    print("B -> Sirf PDF banao + class-wise combine")
    print("C -> Status")
    print("D -> OUTPUT folder kholo")
    print("E -> COMBINED_PDF folder kholo")
    print("F -> Printing plan (pair 1->2 / 3->4 + PRINT_TABLE)")
    print("G -> Print batches dekho (print nahi)")
    print("H -> Print chalao (single-side, flip)")
    print("I -> Auto bill (Rs 1.10 photocopy + Rs 15 typing, PAPER.xlsx)")
    print("P -> Booklet preview (FRONT + BACK)")
    print("S -> PAPER.xlsx kholo (STUDENTS yahi hain)")
    print("M -> OUTPUT ki sabhi Word me \\frac / \\sqrt\\frac ko Equation banao")
    print("Q -> Exit")
    while True:
        choice = input("\nChoice (A/B/C/D/E/F/G/H/I/P/S/M/Q): ").strip().upper()
        if choice in {"A", "B", "C", "D", "E", "F", "G", "H", "I", "P", "S", "M", "Q"}:
            break
        print("A B C D E F G H I P S M ya Q likho")
    if choice == "A":
        make_papers()
    elif choice == "B":
        combine_pdfs()
    elif choice == "C":
        status()
    elif choice == "D":
        open_folder(OUTPUT)
    elif choice == "E":
        open_folder(COMBINED)
    elif choice == "F":
        run_print_plan()
    elif choice == "G":
        run_print_preview()
    elif choice == "H":
        run_print_operator()
    elif choice == "I":
        print("\n=== I: AUTO BILL ===")
        print(" Photostat Rs 1.10 / photocopy")
        print(" Typing     Rs 15   / paper")
        print(" 1-UP = 1 page 1 copy | 2-UP = 2 pages 1 copy")
        print(f" Source: {EXCEL}")
        bill = EXAM_ROOT / "BILL_ASSISTANT.py"
        if bill.exists():
            run_python(bill, ["--auto", "--excel", str(EXCEL)])
        else:
            print(" BILL_ASSISTANT.py isi folder me rakho:")
            print(f" {EXAM_ROOT}")
    elif choice == "P":
        preview = EXAM_ROOT / "PREVIEW_PAIR.py"
        if preview.exists():
            run_python(preview, [])
        else:
            print("PREVIEW_PAIR.py aur IMPOSE.py project folder me rakho")
    elif choice == "M":
        print("\n=== M: Word math fix (\\frac / \\sqrt\\frac -> Equation) ===")
        print(" School folders ke andar bhi sab .docx scan hongi.")
        print(" Pehle Word band karo.")
        fix_math_in_output()
    elif choice == "S":
        print(f" PAPER.xlsx : {EXCEL}")
        if not EXCEL.exists():
            print(" File nahi mili. Project folder me PAPER.xlsx rakho.")
        else:
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(EXCEL))
                    print(" Excel open command gayi. Taskbar / peeche dekho.")
                    print(" STUDENTS column bharo, save + band karke F chalao.")
                else:
                    print(EXCEL)
            except Exception as exc:
                print(f" Open fail: {exc}")
                print(" Khud kholo:", EXCEL)
    else:
        print("Bye.")
        return
    input("\nEnter daba kar band karo...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBand kiya.")
    except Exception as exc:
        print(f"Error: {exc}")
        input("\nEnter...")

