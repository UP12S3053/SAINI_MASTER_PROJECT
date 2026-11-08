# -*- coding: utf-8 -*-
"""Point the DEVELOPMENT app at the common images folder.

Does not edit the original app or any database.
Does not activate a subject and does not create image files.
"""
import hashlib
import py_compile
from pathlib import Path

DEV = Path(
    r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD"
    r"\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py"
)
ORIG = Path(
    r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py"
)
ORIG_EXPECTED = (
    "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
)
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
ROOT_EXPR = 'Path(r"D:\\SAINI_TEACHER_TRIAL")'
IMAGE_LINES = {
    'image_root = (root / "images").resolve()',
    'image_root = (Path(__file__).parent / "images").resolve()',
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def show(lines, start, end):
    for number in range(start, end):
        print("%s:%s" % (number + 1, lines[number]))


def main():
    if sha256(ORIG) != ORIG_EXPECTED:
        print("ABORT")
        print("reason=ORIGINAL_APP_HASH")
        print(sha256(ORIG))
        return 2
    raw = DEV.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = raw.decode("utf-8").splitlines()
    targets = []
    for index, line in enumerate(lines):
        if line.strip() not in IMAGE_LINES:
            continue
        partner = None
        for follow in range(index + 1, min(index + 8, len(lines))):
            if "img_path" in lines[follow] and "=" in lines[follow]:
                partner = follow
                break
        if partner is None:
            print("ABORT")
            print("reason=IMG_PATH_NOT_FOUND")
            show(lines, max(0, index - 2), min(len(lines), index + 8))
            return 2
        targets.append((index, partner))
    if len(targets) != 2:
        print("ABORT")
        print("reason=IMAGE_ROOT_COUNT")
        print("count=%s" % len(targets))
        for index, line in enumerate(lines):
            if "image_root" in line or "img_path" in line:
                print("%s:%s" % (index + 1, line))
        return 2
    updated = list(lines)
    for index, partner in targets:
        partner_line = updated[partner]
        if "(root /" not in partner_line and "(Path(__file__).parent /" not in partner_line:
            print("ABORT")
            print("reason=IMG_PATH_UNEXPECTED")
            print("%s:%s" % (partner + 1, partner_line))
            return 2
        indent = updated[index][: len(updated[index]) - len(updated[index].lstrip(" \t"))]
        updated[index] = (
            indent
            + "image_root = ("
            + ROOT_EXPR
            + ' / "images").resolve()'
        )
        rewritten = partner_line.replace("(root /", "(" + ROOT_EXPR + " /", 1)
        rewritten = rewritten.replace(
            "(Path(__file__).parent /", "(" + ROOT_EXPR + " /", 1
        )
        if rewritten == partner_line:
            print("ABORT")
            print("reason=IMG_PATH_NOT_REWRITTEN")
            print("%s:%s" % (partner + 1, partner_line))
            return 2
        updated[partner] = rewritten
    out = newline.join(updated)
    if raw.decode("utf-8").endswith(("\n", "\r\n")):
        out += newline
    temporary = DEV.with_name(DEV.name + ".image_tmp")
    compiled = DEV.with_name(DEV.name + ".image_check.pyc")
    try:
        temporary.write_bytes(out.encode("utf-8"))
        py_compile.compile(str(temporary), cfile=str(compiled), doraise=True)
    except Exception as exc:
        print("ABORT")
        print("reason=COMPILE")
        print(exc)
        return 2
    finally:
        if temporary.exists():
            temporary.unlink()
        if compiled.exists():
            compiled.unlink()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / "subject_wizard_dev_before_image_root.py"
    stamp = 2
    while backup.exists():
        backup = BACKUP_DIR / (
            "subject_wizard_dev_before_image_root_%s.py" % stamp
        )
        stamp += 1
    backup.write_bytes(raw)
    try:
        DEV.write_bytes(out.encode("utf-8"))
    except OSError as exc:
        print("ABORT")
        print("reason=DEV_FILE_LOCKED")
        print(exc)
        print("backup=%s" % backup)
        return 2
    if sha256(ORIG) != ORIG_EXPECTED:
        DEV.write_bytes(raw)
        print("ABORT")
        print("reason=ORIGINAL_CHANGED")
        return 2
    if sha256(backup) != hashlib.sha256(raw).hexdigest():
        print("ABORT")
        print("reason=BACKUP_HASH")
        return 2
    print("PATCH_OK")
    print("backup=%s" % backup)
    print("original_app=%s" % sha256(ORIG))
    print("common_folder=D:\\SAINI_TEACHER_TRIAL\\images")
    print("name_series=UKG-MATH-Q001.png .. UKG-MATH-Q300.png")
    print("files_created=0")
    print("activation_changed=no")
    for index, line in enumerate(DEV.read_text(encoding="utf-8").splitlines()):
        if "SAINI_TEACHER_TRIAL" in line and (
            "image_root" in line or "img_path" in line
        ):
            print("%s:%s" % (index + 1, line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
