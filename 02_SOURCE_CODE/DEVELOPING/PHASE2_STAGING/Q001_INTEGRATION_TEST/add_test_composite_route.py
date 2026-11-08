from pathlib import Path
import hashlib

app = Path("app_phase2_shortlisting_v2.py")
backup = Path("app_phase2_shortlisting_v2_BEFORE_TEST_COMPOSITE_ROUTE.py")
route_marker = '@app.route("/generate", methods=["POST"])'
route_text = '''@app.route("/test_composite_image/<int:qid>")
def test_composite_image(qid):
    # Test-only, read-only route: serve the approved Q001 test composite.
    if qid != 7:
        return jsonify({"error": "Only test question ID 7 is enabled"}), 404

    root = Path(__file__).parent.resolve()
    image_path = (
        root / "output_shortlisting_v2" /
        "LOCKED_FONT100_INTEGRATION_TEST" /
        "LKG-MATH-Q001_FONT100.png"
    ).resolve()

    allowed_root = (
        root / "output_shortlisting_v2" /
        "LOCKED_FONT100_INTEGRATION_TEST"
    ).resolve()

    if allowed_root not in image_path.parents or not image_path.is_file():
        return jsonify({"error": "Test composite not found"}), 404

    return send_file(image_path, mimetype="image/png", conditional=True)


'''

source = app.read_text(encoding="utf-8-sig")
if route_text.strip() in source:
    raise SystemExit("STOP: Test route already exists; no changes made.")
if source.count(route_marker) != 1:
    raise SystemExit("STOP: Expected insertion point not unique; no changes made.")
if not Path("output_shortlisting_v2/LOCKED_FONT100_INTEGRATION_TEST/LKG-MATH-Q001_FONT100.png").is_file():
    raise SystemExit("STOP: Approved test composite missing; no changes made.")

backup.write_text(source, encoding="utf-8")
updated = source.replace(route_marker, route_text + route_marker, 1)
app.write_text(updated, encoding="utf-8")

print("Backup:", backup)
print("Backup SHA256:", hashlib.sha256(backup.read_bytes()).hexdigest())
print("New route added: /test_composite_image/7")
print("Only the test app file was changed.")
