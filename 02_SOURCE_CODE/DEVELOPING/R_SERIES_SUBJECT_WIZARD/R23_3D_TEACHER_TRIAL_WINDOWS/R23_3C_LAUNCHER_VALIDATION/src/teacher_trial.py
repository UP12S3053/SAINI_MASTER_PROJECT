# -*- coding: utf-8 -*-
"""R23.3 controlled teacher trial.

The teacher selects a file, a photo folder, one class, and one session.
No permanent key is shown. The preserved baseline program is not launched.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from development_launcher import MESSAGES, read_table, _roll
from identity_engine import (
    PENDING_LIMIT_CLASSES,
    IdentityEngine,
    IdentityError,
    assert_development_path,
    canonical_class,
    visible_id,
)
from legacy_guard import refuse_legacy_entry

MESSAGES = dict(MESSAGES)
MESSAGES.update({
    "already_enrolled": "यह छात्र पहले से दर्ज है। नया रिकॉर्ड नहीं बना।",
    "photo_exists": "फोटो पहले से मौजूद है। पुरानी फ़ाइल नहीं बदली गई।",
    "photo_invalid": "फोटो फ़ाइल खुल नहीं सकी। रिकॉर्ड नहीं बना।",
    "skipped_selection": "यह पंक्ति चुनी हुई कक्षा या सेशन की नहीं है।",
    "duplicate_identity": "यह रोल नंबर या यही आईडी पहले से दर्ज है।",
})


class TeacherTrial:
    def __init__(self, workspace):
        workspace = Path(workspace)
        assert_development_path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace
        self.engine = IdentityEngine(workspace / "identity.sqlite", workspace / "PHOTO_LIBRARY")

    def close(self):
        self.engine.close()

    def start(self, table_path, photo_dir, selected_class, selected_session, entry="teacher_trial.py", should_stop=None, progress=None):
        refuse_legacy_entry(entry)
        selected = canonical_class(str(selected_class).strip())
        session = str(selected_session).strip()
        if selected in PENDING_LIMIT_CLASSES:
            return [{
                "ok": False,
                "code": "roll_limit_pending_user_approval",
                "message": MESSAGES["roll_limit_pending_user_approval"],
            }]
        rows = read_table(table_path)
        results = []
        total = len(rows)
        for index, raw in enumerate(rows, start=1):
            if should_stop and should_stop():
                results.append({"ok": False, "code": "cancelled", "message": "रद्द किया गया। / Cancelled."})
                break
            results.append(self._one(raw, Path(photo_dir), selected, session))
            if progress:
                progress(index, total)
        self._reject_key(results)
        return results

    def promote(self, school, session, visible_student_id, new_class, new_roll):
        row = self.engine._current_visible(school, session, visible_student_id)
        moved = self.engine.teacher_view(
            self.engine.promote(school, row["permanent_key"], session, new_class, _roll(new_roll))
        )
        result = self._public_result(moved, "कक्षा बदल गई।")
        self._reject_key(result)
        return result

    def change_roll(self, school, session, visible_student_id, new_roll):
        row = self.engine._current_visible(school, session, visible_student_id)
        moved = self.engine.teacher_view(
            self.engine.change_roll(school, row["permanent_key"], session, _roll(new_roll))
        )
        result = self._public_result(moved, "रोल नंबर बदल गया।")
        self._reject_key(result)
        return result

    def _one(self, raw, photo_dir, selected, session):
        try:
            row_session = str(raw.get("session") or "").strip()
            row_class = canonical_class(str(raw.get("class") or "").strip())
            if row_session != session or row_class != selected:
                return {"ok": True, "skipped": True, "code": "skipped_selection", "message": MESSAGES["skipped_selection"]}
            if row_class in PENDING_LIMIT_CLASSES:
                raise IdentityError("roll_limit_pending_user_approval")
            roll = _roll(raw.get("roll_number"))
            name = raw.get("student_name")
            father = raw.get("father_name")
            photo_name = str(raw.get("photo_file") or "").strip()
            source = photo_dir / photo_name
            if not photo_name or not source.is_file():
                raise IdentityError("photo_source_missing")
            if not _opens(source):
                raise IdentityError("photo_invalid")
            school = str(raw.get("school_code") or "").strip()
            identifier = visible_id(school, row_class, roll)
            target = self.engine.photo_path(school, session, identifier)
            payload = source.read_bytes()
            if target.exists() and target.read_bytes() != payload:
                raise IdentityError("photo_exists")
            before = self.engine.count_identities()
            created = self.engine.create_student(school, session, row_class, roll, name, father)
            if self.engine.count_identities() == before and created.get("photo_path"):
                return self._public_result(self.engine.teacher_view(created), MESSAGES["already_enrolled"])
            if not created.get("photo_path"):
                created = self.engine.assign_photo(school, session, created["visible_id"], source)
            return self._public_result(self.engine.teacher_view(created), "नामांकन हो गया।")
        except IdentityError as exc:
            return {"ok": False, "code": exc.code, "message": MESSAGES.get(exc.code, exc.code)}

    def _public_result(self, created, message):
        return {
            "ok": True,
            "skipped": False,
            "message": message,
            "visible_id": created["visible_id"],
            "photo_path": created.get("photo_path") or "",
            "history": [item["visible_id"] for item in self.engine.history(created["school_code"], created["session"], created["visible_id"])],
        }

    @staticmethod
    def _reject_key(result):
        if "permanent_key" in json.dumps(result):
            raise IdentityError("key_leak_blocked")


def _opens(path):
    try:
        with Image.open(path) as image:
            image.load()
        return True
    except (OSError, UnidentifiedImageError):
        return False


def main():
    parser = argparse.ArgumentParser(description="R23.3 synthetic teacher trial")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--photos", required=True)
    parser.add_argument("--class", dest="selected_class", required=True)
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    trial = TeacherTrial(args.workspace)
    try:
        print(json.dumps(trial.start(args.table, args.photos, args.selected_class, args.session), ensure_ascii=False))
    finally:
        trial.close()


if __name__ == "__main__":
    main()
