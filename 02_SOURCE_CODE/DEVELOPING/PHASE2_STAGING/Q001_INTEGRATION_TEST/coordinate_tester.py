from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

# =====================================================
# EDIT ONLY THESE SETTINGS FOR EACH POSITION TEST
# =====================================================

QUESTION_ID = 7              # 7=Q001, 8=Q002, 9=Q003, 10=Q004
QUESTION_NUMBER = 1          # Display Q1, Q2, Q3...
MARKS = 1

FONT_SIZE = 100
Q_X = 150
Q_Y = 110
Q_ANCHOR = "mm"              # mm = center; lt = top-left

# Marks label position
MARKS_X = 2090
MARKS_Y = 85
MARKS_ANCHOR = "rt"          # rt = right-top; mm = center

# =====================================================
# SAFETY RULES: DO NOT CHANGE THESE PATHS
# =====================================================

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = (ROOT / "images").resolve()
OUTPUT_DIR = (
    ROOT / "output_shortlisting_v2" / "COORDINATE_TESTS"
).resolve()

IMAGE_NAMES = {
    7: "LKG-MATH-Q001.png",
    8: "LKG-MATH-Q002.png",
    9: "LKG-MATH-Q003.png",
    10: "LKG-MATH-Q004.png",
}

ALLOWED_ANCHORS = {"lt", "mm", "rt"}

def main():
    if QUESTION_ID not in IMAGE_NAMES:
        raise SystemExit("STOP: QUESTION_ID must be 7, 8, 9, or 10.")

    if Q_ANCHOR not in ALLOWED_ANCHORS:
        raise SystemExit("STOP: Invalid Q_ANCHOR.")
    if MARKS_ANCHOR not in ALLOWED_ANCHORS:
        raise SystemExit("STOP: Invalid MARKS_ANCHOR.")
    if FONT_SIZE < 10 or FONT_SIZE > 200:
        raise SystemExit("STOP: FONT_SIZE must be between 10 and 200.")

    source = (IMAGE_DIR / IMAGE_NAMES[QUESTION_ID]).resolve()

    if IMAGE_DIR not in source.parents or not source.is_file():
        raise SystemExit(f"STOP: Original image not found: {source}")

    font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
    if not font_path.is_file():
        raise SystemExit("STOP: Bookman Old Style Bold font not found.")

    # Record the original image hash before processing.
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    with Image.open(source) as im:
        image = im.convert("RGB")

    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), FONT_SIZE)

    question_text = f"Q{QUESTION_NUMBER}"
    marks_text = (
        f"{MARKS:g} " + ("Mark" if MARKS == 1 else "Marks")
    )

    draw.text(
        (Q_X, Q_Y), question_text,
        font=font, fill=(17, 17, 17), anchor=Q_ANCHOR
    )
    draw.text(
        (MARKS_X, MARKS_Y), marks_text,
        font=font, fill=(17, 17, 17), anchor=MARKS_ANCHOR
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # New file on every run; never overwrite an earlier test.
    existing = list(OUTPUT_DIR.glob("test_*.png"))
    run_number = len(existing) + 1
    target = OUTPUT_DIR / f"test_{run_number:04d}_Q{QUESTION_NUMBER}.png"

    image.save(target, format="PNG")

    # Confirm that the source file was not changed.
    final_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if final_hash != original_hash:
        target.unlink(missing_ok=True)
        raise SystemExit("STOP: Source image hash changed!")

    print("TEST IMAGE CREATED:", target)
    print("Question:", question_text, "| Marks:", marks_text)
    print("Image size:", image.width, "x", image.height)
    print("Q position:", Q_X, Q_Y, "| anchor:", Q_ANCHOR)
    print("Marks position:", MARKS_X, MARKS_Y,
          "| anchor:", MARKS_ANCHOR)
    print("Font size:", FONT_SIZE)
    print("Original image unchanged: YES")
    print("Database / Excel / Google Drive modified: NO")

if __name__ == "__main__":
    main()

