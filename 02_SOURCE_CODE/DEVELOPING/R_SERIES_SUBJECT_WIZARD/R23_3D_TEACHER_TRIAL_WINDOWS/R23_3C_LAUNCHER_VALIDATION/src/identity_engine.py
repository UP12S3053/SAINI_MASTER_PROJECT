# -*- coding: utf-8 -*-
"""R23 development-only Student Identity Engine.

This module does not read or write the live project, student_data.xlsx,
or the real photo library. Nursery, LKG, and UKG issuance stays closed
until a roll limit is explicitly approved.
"""

import re
import sqlite3
import threading
import uuid
from pathlib import Path

LIVE_MARKERS = ("SHRI_JAI_SHRI_RAM", "STUDENT_DATA.XLSX")
BLOCKED_SCHOOLS = {"BSM", "NBFP", "SDV", "STVN", "BVM"}
PENDING_LIMIT_CLASSES = {"NUR", "LKG", "UKG"}
SESSION_RE = re.compile(r"^(\d{4})_(\d{2})$")

CLASS_TOKENS = {
    "NUR": "NUR",
    "NURSERY": "NUR",
    "LKG": "LKG",
    "UKG": "UKG",
    "I": "I",
    "1": "I",
    "II": "II",
    "2": "II",
    "III": "III",
    "3": "III",
    "IV": "IV",
    "4": "IV",
    "V": "V",
    "5": "V",
    "VI": "VI",
    "6": "VI",
    "VII": "VII",
    "7": "VII",
    "VIII": "VIII",
    "8": "VIII",
    "IX": "IX",
    "9": "IX",
    "X": "X",
    "10": "X",
    "XI": "XI",
    "11": "XI",
    "XII": "XII",
    "12": "XII",
}
NUMERIC_BASE = {
    "NUR": 10000,
    "LKG": 20000,
    "UKG": 30000,
    "I": 1000,
    "II": 2000,
    "III": 3000,
    "IV": 4000,
    "V": 5000,
    "VI": 6000,
    "VII": 7000,
    "VIII": 8000,
    "IX": 9000,
}
ROMAN = {"X": "X", "XI": "XI", "XII": "XII"}


class IdentityError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def assert_development_path(path):
    text = str(path).replace("/", "\\").upper()
    if any(marker in text for marker in LIVE_MARKERS):
        raise IdentityError("live_path_refused")


def canonical_class(value):
    token = str(value).strip()
    if token != value or token not in CLASS_TOKENS:
        raise IdentityError("class_not_exact")
    return CLASS_TOKENS[token]


def session_start(session):
    match = SESSION_RE.fullmatch(str(session))
    if not match:
        raise IdentityError("session_invalid")
    start = int(match.group(1))
    end = int(match.group(2))
    if end != (start + 1) % 100:
        raise IdentityError("session_invalid")
    return start


def roll_number(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise IdentityError("roll_invalid")
    return value


def visible_id(school, class_name, roll):
    """Pure Option A formatter. It does not decide whether issuance is allowed."""
    school = _school(school)
    klass = canonical_class(class_name)
    number = roll_number(roll)
    if number < 1 or number > 999:
        raise IdentityError("roll_out_of_range")
    if klass in ROMAN:
        return f"{school}{ROMAN[klass]}{number:03d}"
    return f"{school}{NUMERIC_BASE[klass] + number}"


def _school(value):
    school = str(value).strip()
    if school != value or not re.fullmatch(r"[A-Z]{2,6}", school):
        raise IdentityError("school_invalid")
    if school in BLOCKED_SCHOOLS:
        raise IdentityError("live_school_refused")
    return school


def _original(value, label):
    if not isinstance(value, str) or value == "":
        raise IdentityError(label)
    return value


class IdentityEngine:
    def __init__(self, db_path, photo_root):
        assert_development_path(db_path)
        assert_development_path(photo_root)
        self.db_path = Path(db_path)
        self.photo_root = Path(photo_root)
        self.photo_root.mkdir(parents=True, exist_ok=True)
        self.photo_fail = None
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                permanent_key TEXT PRIMARY KEY,
                school_code TEXT NOT NULL,
                created_session TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS identities (
                permanent_key TEXT NOT NULL,
                school_code TEXT NOT NULL,
                session TEXT NOT NULL,
                visible_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                roll_number INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                father_name TEXT NOT NULL,
                photo_path TEXT,
                status TEXT NOT NULL,
                UNIQUE (school_code, session, visible_id),
                UNIQUE (school_code, session, class_name, roll_number)
            );
            """
        )
        self._conn.commit()

    def close(self):
        self._conn.close()

    def create_student(self, school, session, class_name, roll, student_name, father_name):
        school = _school(school)
        start = session_start(session)
        klass = canonical_class(class_name)
        number = roll_number(roll)
        name = _original(student_name, "name_invalid")
        father = _original(father_name, "father_invalid")
        self._issue_allowed(klass, number)
        with self._transaction():
            existing = self._exact_current(school, name, father, klass)
            if existing:
                gap = start - session_start(existing["session"])
                if gap == 0 and existing["roll_number"] == number:
                    return self._public(existing)
                if gap == 0:
                    raise IdentityError("explicit_operation_required")
                if gap >= 2:
                    return self._insert_new(school, session, klass, number, name, father)
                raise IdentityError("explicit_operation_required")
            return self._insert_new(school, session, klass, number, name, father)

    def promote(self, school, permanent_key, session, new_class, new_roll):
        return self._move(school, permanent_key, session, new_class, new_roll, "promotion")

    def change_roll(self, school, permanent_key, session, new_roll):
        school = _school(school)
        session_start(session)
        number = roll_number(new_roll)
        with self._transaction():
            current = self._current_key(school, permanent_key, session)
            return self._replace_current(current, session, current["class_name"], number)

    def correct_name(self, school, permanent_key, session, student_name=None, father_name=None):
        school = _school(school)
        session_start(session)
        with self._transaction():
            current = self._current_key(school, permanent_key, session)
            name = current["student_name"] if student_name is None else _original(student_name, "name_invalid")
            father = current["father_name"] if father_name is None else _original(father_name, "father_invalid")
            if name == current["student_name"] and father == current["father_name"]:
                raise IdentityError("correction_unchanged")
            self._conn.execute(
                """
                UPDATE identities
                SET student_name=?, father_name=?
                WHERE school_code=? AND permanent_key=? AND session=? AND status='current'
                """,
                (name, father, school, permanent_key, session),
            )
            return self._public(self._current_key(school, permanent_key, session))

    def reenter(self, school, session, class_name, roll, student_name, father_name):
        school = _school(school)
        start = session_start(session)
        klass = canonical_class(class_name)
        number = roll_number(roll)
        name = _original(student_name, "name_invalid")
        father = _original(father_name, "father_invalid")
        self._issue_allowed(klass, number)
        with self._transaction():
            previous = self._latest_exact(school, name, father, klass)
            if previous is None:
                raise IdentityError("reentry_not_found")
            gap = start - session_start(previous["session"])
            if gap < 0:
                raise IdentityError("session_goes_backward")
            if gap >= 2:
                created = self._insert_new(school, session, klass, number, name, father)
                created["previous_key_linked"] = False
                return created
            if gap == 0:
                if previous["status"] != "current" or previous["roll_number"] != number:
                    raise IdentityError("explicit_operation_required")
                row = self._public(previous)
                row["previous_key_linked"] = True
                return row
            if previous["class_name"] == klass and previous["roll_number"] == number:
                moved = self._replace_current(previous, session, klass, number)
            else:
                moved = self._replace_current(previous, session, klass, number)
            moved["previous_key_linked"] = True
            return moved

    def assign_photo(self, school, session, visible_id, source_path):
        school = _school(school)
        session_start(session)
        source = Path(source_path)
        assert_development_path(source)
        if not source.is_file():
            raise IdentityError("photo_source_missing")
        payload = source.read_bytes()
        if not payload:
            raise IdentityError("photo_source_missing")
        row = self._current_visible(school, session, visible_id)
        if row["photo_path"]:
            raise IdentityError("photo_already_recorded")
        target = self.photo_path(school, session, row["visible_id"])
        assert_development_path(target)
        if target.exists():
            return self._link_verified_photo(school, session, row["visible_id"], target, payload)
        if self.photo_fail == "stage":
            raise IdentityError("photo_stage_failed")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(target.name + ".staging")
        if staging.exists() and not target.exists():
            staging.unlink()
        try:
            with staging.open("xb") as handle:
                handle.write(payload)
            if staging.read_bytes() != payload:
                raise IdentityError("photo_stage_failed")
            if self.photo_fail == "finalize":
                raise IdentityError("photo_finalize_failed")
            with target.open("xb") as handle:
                handle.write(staging.read_bytes())
            if target.read_bytes() != payload:
                raise IdentityError("photo_finalize_failed")
        except IdentityError:
            self._remove_staging(staging)
            if self.photo_fail == "finalize" and target.exists() and target.read_bytes() != payload:
                target.unlink()
            raise
        except FileExistsError as exc:
            self._remove_staging(staging)
            raise IdentityError("photo_exists") from exc
        self._remove_staging(staging)
        if self.photo_fail == "database":
            raise IdentityError("photo_database_failed")
        return self._link_verified_photo(school, session, row["visible_id"], target, payload)

    def _link_verified_photo(self, school, session, visible_student_id, target, payload):
        if not target.is_file() or target.read_bytes() != payload:
            raise IdentityError("photo_exists")
        with self._transaction():
            current = self._current_visible(school, session, visible_student_id)
            if current["photo_path"]:
                raise IdentityError("photo_already_recorded")
            if target.read_bytes() != payload:
                raise IdentityError("photo_exists")
            self._conn.execute(
                """
                UPDATE identities SET photo_path=?
                WHERE school_code=? AND session=? AND visible_id=? AND status='current'
                """,
                (str(target), school, session, visible_student_id),
            )
            updated = self._current_visible(school, session, visible_student_id)
        return self._public(updated)

    @staticmethod
    def _remove_staging(staging):
        if staging.exists():
            staging.unlink()

    def teacher_view(self, record):
        secret = str(record.get("permanent_key") or "")
        visible = {}
        for key, value in record.items():
            if key == "permanent_key":
                continue
            if secret and secret in str(value):
                raise IdentityError("key_leak_blocked")
            visible[key] = value
        return visible

    def export_teacher_csv(self, school, session, destination):
        school = _school(school)
        session_start(session)
        destination = Path(destination)
        assert_development_path(destination)
        rows = self._conn.execute(
            """
            SELECT school_code, session, visible_id, class_name, roll_number,
                   student_name, father_name, photo_path
            FROM identities
            WHERE school_code=? AND session=?
            ORDER BY visible_id
            """,
            (school, session),
        ).fetchall()
        lines = ["school_code,session,visible_id,class_name,roll_number,student_name,father_name,photo_path"]
        for row in rows:
            lines.append(",".join("" if value is None else str(value) for value in row))
        text = "\n".join(lines) + "\n"
        if "permanent_key" in text:
            raise IdentityError("key_leak_blocked")
        destination.write_text(text, encoding="utf-8")
        return destination

    def history(self, school, session, visible_id):
        school = _school(school)
        session_start(session)
        row = self._conn.execute(
            """
            SELECT permanent_key FROM identities
            WHERE school_code=? AND session=? AND visible_id=?
            """,
            (school, session, visible_id),
        ).fetchone()
        if row is None:
            raise IdentityError("identity_not_found")
        rows = self._conn.execute(
            """
            SELECT * FROM identities
            WHERE permanent_key=?
            ORDER BY session, rowid
            """,
            (row["permanent_key"],),
        ).fetchall()
        return [self._public(item) for item in rows]

    def generator_row(self, school, session, visible_id):
        school = _school(school)
        row = self._current_visible(school, session, visible_id)
        return {
            "school_code": row["school_code"],
            "student_unique_id": row["visible_id"],
            "student_name": row["student_name"],
            "father_name": row["father_name"],
            "class": row["class_name"],
            "roll_number": row["roll_number"],
            "STUDENT_PHOTO_PATH": row["photo_path"] or "",
        }

    def count_identities(self):
        return self._conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0]

    def photo_path(self, school, session, visible_student_id):
        return self.photo_root / school / session / f"{visible_student_id}.jpg"

    def _insert_identity(self, sql, params):
        try:
            self._conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise IdentityError("duplicate_identity") from exc

    def _issue_allowed(self, klass, number):
        if number < 1 or number > 999:
            raise IdentityError("roll_out_of_range")
        if klass in PENDING_LIMIT_CLASSES:
            raise IdentityError("roll_limit_pending_user_approval")

    def _insert_new(self, school, session, klass, number, name, father):
        key = str(uuid.uuid4())
        identifier = visible_id(school, klass, number)
        self._conn.execute(
            "INSERT INTO students (permanent_key, school_code, created_session) VALUES (?, ?, ?)",
            (key, school, session),
        )
        self._insert_identity(
            """
            INSERT INTO identities (
                permanent_key, school_code, session, visible_id, class_name,
                roll_number, student_name, father_name, photo_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'current')
            """,
            (key, school, session, identifier, klass, number, name, father),
        )
        return self._public(self._current_visible(school, session, identifier))

    def _replace_current(self, current, session, klass, number):
        self._issue_allowed(klass, number)
        identifier = visible_id(current["school_code"], klass, number)
        if current["session"] == session and current["visible_id"] == identifier:
            return self._public(current)
        self._conn.execute(
            """
            UPDATE identities SET status='history'
            WHERE permanent_key=? AND status='current'
            """,
            (current["permanent_key"],),
        )
        self._insert_identity(
            """
            INSERT INTO identities (
                permanent_key, school_code, session, visible_id, class_name,
                roll_number, student_name, father_name, photo_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'current')
            """,
            (
                current["permanent_key"],
                current["school_code"],
                session,
                identifier,
                klass,
                number,
                current["student_name"],
                current["father_name"],
            ),
        )
        return self._public(self._current_key(current["school_code"], current["permanent_key"], session))

    def _move(self, school, permanent_key, session, new_class, new_roll, _operation):
        school = _school(school)
        session_start(session)
        klass = canonical_class(new_class)
        number = roll_number(new_roll)
        with self._transaction():
            current = self._current_key(school, permanent_key, session)
            if current["class_name"] == klass and current["roll_number"] == number:
                raise IdentityError("identity_unchanged")
            return self._replace_current(current, session, klass, number)

    def _exact_current(self, school, name, father, klass):
        return self._conn.execute(
            """
            SELECT * FROM identities
            WHERE school_code=? AND student_name=? AND father_name=?
              AND class_name=? AND status='current'
            ORDER BY session DESC
            LIMIT 1
            """,
            (school, name, father, klass),
        ).fetchone()

    def _latest_exact(self, school, name, father, klass):
        return self._conn.execute(
            """
            SELECT * FROM identities
            WHERE school_code=? AND student_name=? AND father_name=? AND class_name=?
            ORDER BY session DESC, rowid DESC
            LIMIT 1
            """,
            (school, name, father, klass),
        ).fetchone()

    def _current_key(self, school, permanent_key, session):
        row = self._conn.execute(
            """
            SELECT * FROM identities
            WHERE school_code=? AND permanent_key=? AND session=? AND status='current'
            """,
            (school, permanent_key, session),
        ).fetchone()
        if row is None:
            raise IdentityError("confirmed_identity_not_found")
        return row

    def _current_visible(self, school, session, visible_student_id):
        row = self._conn.execute(
            """
            SELECT * FROM identities
            WHERE school_code=? AND session=? AND visible_id=? AND status='current'
            """,
            (school, session, visible_student_id),
        ).fetchone()
        if row is None:
            raise IdentityError("identity_not_found")
        return row

    def _public(self, row):
        return {
            "permanent_key": row["permanent_key"],
            "school_code": row["school_code"],
            "session": row["session"],
            "visible_id": row["visible_id"],
            "class_name": row["class_name"],
            "roll_number": row["roll_number"],
            "student_name": row["student_name"],
            "father_name": row["father_name"],
            "photo_path": row["photo_path"] or "",
            "status": row["status"],
        }

    def _transaction(self):
        engine = self

        class _Txn:
            def __enter__(self_):
                engine._lock.acquire()
                engine._conn.execute("BEGIN IMMEDIATE")
                return engine

            def __exit__(self_, exc_type, exc, _tb):
                try:
                    if exc_type is None:
                        engine._conn.commit()
                    else:
                        engine._conn.rollback()
                finally:
                    engine._lock.release()
                return False

        return _Txn()
