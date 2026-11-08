from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = (ROOT / "images").resolve()
OUT_DIR = ROOT / "output_shortlisting_v2" / "LOCKED_COORDINATE_BATCH_TEST"

# Q001 approved settings — do not change during this batch test.
FONT_SIZE = 100
Q_X, Q_Y, Q_ANCHOR = 150, 90, "mm"
M_X, M_Y, M_ANCHOR = 2090, 65, "rt"
FONT_PATH = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")

QUESTIONS = [
    (8, 2, 2.0, "LKG-MATH-Q002.png"),
    (9, 3, 3.0, "LKG-MATH-Q003.png"),
    (10, 4, 4.0, "LKG-MATH-Q004.png"),
]

if not FONT_PATH.is_file():
    raise SystemExit("STOP: Bookman Old Style Bold font not found.")

OUT_DIR.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)

for qid, order, marks, filename in QUESTIONS:
    src = (IMAGE_DIR / filename).resolve()

    if IMAGE_DIR not in src.parents or not src.is_file():
        raise SystemExit(f"STOP: Missing or unsafe source: {filename}")

    before_hash = hashlib.sha256(src.read_bytes()).hexdigest()

    with Image.open(src) as original:
        image = original.convert("RGB")

    draw = ImageDraw.Draw(image)
    draw.text(
        (Q_X, Q_Y), f"Q{order}",
        font=font, fill=(17, 17, 17), anchor=Q_ANCHOR
    )
    mark_text = f"{marks:g} " + ("Mark" if marks == 1 else "Marks")
    draw.text(
        (M_X, M_Y), mark_text,
        font=font, fill=(17, 17, 17), anchor=M_ANCHOR
    )

    target = OUT_DIR / f"Q{order}_QID{qid}_LOCKED_TEST.png"
    if target.exists():
        raise SystemExit(
            f"STOP: Test file already exists; refusing to overwrite: {target}"
        )

    image.save(target, format="PNG")

    after_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    if before_hash != after_hash:
        target.unlink(missing_ok=True)
        raise SystemExit(f"STOP: Source image integrity check failed: {filename}")

    print(f"CREATED: {target}")
    print(f"  Size: {image.width} x {image.height}")
    print(f"  Label: Q{order} | {mark_text}")
    print("  Original unchanged: YES")

print("\nBATCH TEST COMPLETE")
print("Database / Excel / Google Drive modified: NO")

