from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sqlite3, json, hashlib

ROOT = Path(__file__).parent
OUT = ROOT / "output_shortlisting_v2" / "DYNAMIC_PREVIEW_TEST"
OUT.mkdir(parents=True, exist_ok=True)

FONT_PATH = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
if not FONT_PATH.is_file():
    raise SystemExit("STOP: Bookman Bold font missing.")

con = sqlite3.connect(
    f"file:{(ROOT / 'paper_bank.db').as_posix()}?mode=ro", uri=True
)
con.row_factory = sqlite3.Row
rows = con.execute("""
    SELECT id, content_json, image_path, marks
    FROM questions
    WHERE id BETWEEN 7 AND 10
    ORDER BY id
""").fetchall()
con.close()

if len(rows) != 4:
    raise SystemExit(f"STOP: Expected 4 test questions, found {len(rows)}.")

for index, row in enumerate(rows, start=1):
    content = json.loads(row["content_json"] or "{}")
    image_name = content.get("image") or Path(row["image_path"]).name
    src = (ROOT / "images" / image_name).resolve()

    if ROOT / "images" not in src.parents or not src.is_file():
        raise SystemExit(f"STOP: Invalid/missing image: {image_name}")

    original_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    im = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(FONT_PATH), 100)

    # Q001 approved anchors; other templates are TEST ONLY pending alignment review.
    q_text = f"Q{index}"
    marks_value = float(row["marks"])
    marks_text = f"{marks_value:g} " + ("Mark" if marks_value == 1 else "Marks")

    draw.text((170, 128), q_text, font=font, fill=(17, 17, 17), anchor="lt")
    draw.text((1935, 128), marks_text, font=font, fill=(17, 17, 17), anchor="lt")

    target = OUT / f"ORDER_{index}_DBID_{row['id']}_{Path(image_name).stem}.png"
    im.save(target, format="PNG")

    if hashlib.sha256(src.read_bytes()).hexdigest() != original_hash:
        raise SystemExit(f"STOP: Original image hash changed: {src.name}")

    print(f"OK | order={index} | DB ID={row['id']} | {q_text} | "
          f"{marks_text} | size={im.size} | output={target.name}")

print("\nTEST ONLY: output saved outside the original images folder.")
print("Q002-Q004 coordinates are provisional; inspect before UI integration.")
