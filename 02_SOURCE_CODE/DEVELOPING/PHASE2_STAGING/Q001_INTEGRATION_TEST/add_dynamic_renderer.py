from pathlib import Path
import hashlib

app = Path("app_phase2_shortlisting_v2.py")
backup = Path("app_phase2_shortlisting_v2_BEFORE_DYNAMIC_RENDERER.py")
source = app.read_text(encoding="utf-8-sig")

marker = '@app.route("/generate", methods=["POST"])'

route = r'''
@app.route("/dynamic_preview_image/<int:qid>/<int:order>/<float:marks>")
def dynamic_preview_image(qid, order, marks):
    """Isolated read-only-data renderer; writes only to a test output folder."""
    from PIL import Image, ImageDraw, ImageFont
    import sqlite3
    import json
    import hashlib

    if qid not in (7, 8, 9, 10) or order < 1 or marks < 0:
        return jsonify({"error": "Invalid test parameters"}), 400

    root = Path(__file__).parent.resolve()
    db = root / "paper_bank.db"
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT content_json, image_path FROM questions WHERE id=?",
            (qid,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Question not found"}), 404

    try:
        content = json.loads(row["content_json"] or "{}")
    except Exception:
        content = {}

    name = content.get("image") or Path(row["image_path"]).name
    image_root = (root / "images").resolve()
    src = (image_root / Path(name).name).resolve()
    if image_root not in src.parents or not src.is_file():
        return jsonify({"error": "Invalid or missing original image"}), 404

    font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
    if not font_path.is_file():
        return jsonify({"error": "Bookman Bold font missing"}), 500

    out_dir = root / "output_shortlisting_v2" / "DYNAMIC_ROUTE_TEST"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"QID_{qid}_ORDER_{order}_MARKS_{marks:g}.png"

    original_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    with Image.open(src) as original:
        im = original.convert("RGB")

    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(font_path), 100)
    q_text = f"Q{order}"
    marks_text = f"{marks:g} " + ("Mark" if marks == 1 else "Marks")

    # Locked Q001 reference anchors; coordinates are original-image pixels.
    draw.text((170, 128), q_text, font=font, fill=(17, 17, 17), anchor="lt")
    draw.text((1935, 128), marks_text, font=font, fill=(17, 17, 17), anchor="lt")
    im.save(target, format="PNG")

    if hashlib.sha256(src.read_bytes()).hexdigest() != original_hash:
        return jsonify({"error": "Original image integrity check failed"}), 500

    return send_file(target, mimetype="image/png", conditional=True)


'''

if route.strip() in source:
    raise SystemExit("STOP: Dynamic renderer already exists; no changes made.")
if source.count(marker) != 1:
    raise SystemExit("STOP: Expected insertion marker is not unique.")
if not Path("output_shortlisting_v2/LOCKED_FONT100_INTEGRATION_TEST/LKG-MATH-Q001_FONT100.png").is_file():
    raise SystemExit("STOP: Approved Q001 reference composite is missing.")

backup.write_text(source, encoding="utf-8")
app.write_text(source.replace(marker, route + marker, 1), encoding="utf-8")
print("Backup created:", backup)
print("Dynamic test renderer added.")
print("Original image files and database were not modified.")
