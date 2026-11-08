from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sqlite3, json

ROOT = Path(__file__).parent
OUT = ROOT / "output_shortlisting_v2" / "CENTERED_POSITION_TEST"
OUT.mkdir(parents=True, exist_ok=True)

font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
font = ImageFont.truetype(str(font_path), 100)

# Provisional centers for testing only.
# Q001 approved source anchors were top-left positions, not center points.
# These centers must be visually reviewed before being locked.
template_centers = {
    7:  {"q": (170, 330), "marks": (1935, 330)},
    8:  {"q": (170, 330), "marks": (1935, 330)},
    9:  {"q": (170, 330), "marks": (1935, 330)},
    10: {"q": (170, 330), "marks": (1935, 330)},
}

con = sqlite3.connect(
    f"file:{(ROOT / 'paper_bank.db').as_posix()}?mode=ro", uri=True
)
con.row_factory = sqlite3.Row
rows = con.execute("""
    SELECT id, content_json, image_path, marks
    FROM questions WHERE id BETWEEN 7 AND 10 ORDER BY id
""").fetchall()
con.close()

if len(rows) != 4:
    raise SystemExit(f"STOP: expected 4 questions, found {len(rows)}")

for index, row in enumerate(rows, start=1):
    content = json.loads(row["content_json"] or "{}")
    name = content.get("image") or Path(row["image_path"]).name
    src = ROOT / "images" / name
    if not src.is_file():
        raise SystemExit(f"STOP: missing image {src}")

    im = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(im)

    q_text = f"Q{index}"
    marks_value = float(row["marks"])
    marks_text = f"{marks_value:g} " + ("Mark" if marks_value == 1 else "Marks")
    centers = template_centers[row["id"]]

    draw.text(centers["q"], q_text, font=font, fill=(17,17,17), anchor="mm")
    draw.text(centers["marks"], marks_text, font=font, fill=(17,17,17), anchor="mm")

    target = OUT / f"ORDER_{index}_DBID_{row['id']}_{Path(name).stem}.png"
    im.save(target)
    print(f"Created: {target.name} | {im.size} | {q_text} | {marks_text}")

print("TEST ONLY. Center coordinates are provisional; originals were not changed.")
