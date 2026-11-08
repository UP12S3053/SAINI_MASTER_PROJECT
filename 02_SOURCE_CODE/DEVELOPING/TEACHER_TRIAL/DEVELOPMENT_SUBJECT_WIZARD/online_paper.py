# Build one Nursery-to-class-2 worksheet paper into the school job folder.
import re
from pathlib import Path

import school_registry

TRIAL = Path(r"D:\SAINI_TEACHER_TRIAL")
ONLINE = {"NUR", "NURSERY", "LKG", "UKG", "PREP", "I", "1", "1ST", "II", "2", "2ND"}


def _class_name(value):
    name = " ".join((value or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9-]{1,12}", name):
        raise ValueError("Class must be like UKG or 1")
    return name


def _subject(value):
    name = " ".join((value or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9-]{2,20}", name):
        raise ValueError("Subject must be like MATH")
    return name


def _sheets(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise ValueError("Worksheet count must be a number")
    if count < 1 or count > 40:
        raise ValueError("Choose 1 to 40 worksheets")
    return count


def _question_number(path):
    match = re.search(r"Q(\d+)", Path(str(path)).name.upper())
    return int(match.group(1)) if match else 10**9


def _image_file(stored):
    raw = Path(str(stored).replace("\\", "/"))
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("Unsafe worksheet path")
    root = (TRIAL / "images").resolve()
    path = (TRIAL / raw).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Worksheet must stay in the common images folder")
    if not path.is_file():
        raise ValueError("Worksheet image missing: " + path.name)
    return path


def _size(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    if not raw.startswith(b"\xff\xd8"):
        return 1000, 1400
    index = 2
    while index + 9 < len(raw):
        if raw[index] != 0xFF:
            break
        marker = raw[index + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height = int.from_bytes(raw[index + 5:index + 7], "big")
            width = int.from_bytes(raw[index + 7:index + 9], "big")
            return width, height
        if marker in (0xD8, 0xD9):
            index += 2
            continue
        length = int.from_bytes(raw[index + 2:index + 4], "big")
        if length < 2:
            break
        index += 2 + length
    return 1000, 1400


def _xml(value):
    text = str(value)
    return text.replace("&", "&").replace("<", "<").replace(">", ">")


def _emu(width, height):
    pixel_x = max(int(width), 1) * 9525
    pixel_y = max(int(height), 1) * 9525
    max_x = 5943600
    max_y = 9000000
    scale = min(max_x / pixel_x, max_y / pixel_y)
    return int(pixel_x * scale), int(pixel_y * scale)


def _picture(index, rel_id, width, height):
    cx, cy = _emu(width, height)
    return (
        '<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '<wp:docPr id="%d" name="Sheet%d"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr>'
        '<pic:cNvPr id="0" name="sheet.jpg"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
        '<a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr>'
        '<a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    ) % (cx, cy, index, index, rel_id, cx, cy)


def _line(text, size, bold=False):
    weight = "<w:b/>" if bold else ""
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr>%s<w:sz w:val="%d"/></w:rPr>'
        '<w:t>%s</w:t></w:r></w:p>'
    ) % (weight, size, _xml(text))


def _docx(target, title, lines, images):
    import zipfile
    body = "".join(_line(line, size, bold) for line, size, bold in lines)
    rels = []
    overrides = []
    for index, image in enumerate(images, 1):
        raw = image.read_bytes()
        width, height = _size(raw)
        suffix = ".png" if raw.startswith(b"\x89PNG") else ".jpg"
        rel_id = "rId%d" % index
        body += _picture(index, rel_id, width, height)
        rels.append(
            '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image%d%s"/>'
            % (rel_id, index, suffix)
        )
        overrides.append((index, suffix, raw))
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/></w:sectPr></w:body></w:document>'
    ) % body
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Default Extension="jpg" ContentType="image/jpeg"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        book.writestr("word/document.xml", document)
        book.writestr("word/_rels/document.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
            % "".join(rels))
        for index, suffix, raw in overrides:
            book.writestr("word/media/image%d%s" % (index, suffix), raw)


def make_online_paper(conn, school_code, class_name, subject, sheets):
    school_registry.assert_development_db(conn)
    class_name = _class_name(class_name)
    subject = _subject(subject)
    count = _sheets(sheets)
    if class_name not in ONLINE:
        raise ValueError("Online setter is only for Nursery to class 2. Class 3-12 stays on the old system.")
    need = conn.execute(
        """SELECT student_strength, max_marks FROM school_paper_needs
        WHERE school_code=? AND class_name=? AND subject=?""",
        (school_code, class_name, subject),
    ).fetchone()
    if need is None:
        raise ValueError("Save this class and subject in Paper data first")
    rows = conn.execute(
        """SELECT image_path FROM questions
        WHERE upper(class_level)=? AND upper(subject)=?
        AND image_path IS NOT NULL AND image_path!=''""",
        (class_name, subject),
    ).fetchall()
    ordered = sorted((row[0] for row in rows), key=_question_number)
    if not ordered:
        raise ValueError("Worksheet images are not ready for " + class_name + " " + subject)
    chosen = ordered[:count]
    images = [_image_file(path) for path in chosen]
    school = conn.execute(
        "SELECT school_name FROM school_accounts WHERE school_code=?",
        (school_code,),
    ).fetchone()
    school_name = school[0] if school else school_code
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    if root.name != "DEVELOPMENT_SUBJECT_WIZARD":
        raise ValueError("Paper can be saved only in the development copy")
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    job = None
    if "production_line" in tables:
        job = conn.execute(
            """SELECT id FROM production_line
            WHERE school_code=? AND kind='PAPER' ORDER BY id DESC LIMIT 1""",
            (school_code,),
        ).fetchone()
    if job:
        folder = root / "production_jobs" / ("JOB-%04d" % job[0])
        place = "JOB-%04d" % job[0]
    else:
        folder = root / "production_jobs" / school_code
        place = school_code
    folder.mkdir(parents=True, exist_ok=True)
    filename = "%s-%s-%s.docx" % (school_code, class_name, subject)
    target = folder / filename
    _docx(target, school_name, [
        (school_name, 44, True),
        ("Time: 1 Hour", 28, False),
        ("%s (%s)" % (class_name, subject), 32, True),
        ("Total Marks: %s" % need[1], 28, False),
        ("Worksheets: %d" % len(images), 24, False),
    ], images)
    mirror = root / "output_shortlisting_v2"
    mirror.mkdir(exist_ok=True)
    mirror.joinpath(filename).write_bytes(target.read_bytes())
    import production_queue
    amount = production_queue._paper_bill(
        conn, school_code, class_name, subject, int(need[0]), "ONLINE",
    )
    conn.commit()
    return "Paper saved in %s\\%s. Worksheets %d. Account Rs %d." % (
        place, filename, len(images), amount,
    )
