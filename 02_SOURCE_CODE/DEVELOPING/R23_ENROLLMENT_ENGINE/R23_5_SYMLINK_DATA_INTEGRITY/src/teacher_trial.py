# -*- coding: utf-8 -*-
"""R23.3 controlled teacher trial.

The teacher selects a file, a photo folder, one class, and one session.
No permanent key is shown. The preserved baseline program is not launched.
"""

import argparse
import json
import os
import threading
import time
import uuid
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
from path_guard import (
    _is_reparse_point,
    preflight_required_photos,
    require_excel,
    require_photo_dir,
    require_workspace,
    safe_photo_source,
)

MESSAGES = dict(MESSAGES)
MESSAGES.update({
    "already_enrolled": "यह छात्र पहले से दर्ज है। नया रिकॉर्ड नहीं बना।",
    "photo_exists": "फोटो पहले से मौजूद है। पुरानी फ़ाइल नहीं बदली गई।",
    "photo_invalid": "फोटो फ़ाइल खुल नहीं सकी। रिकॉर्ड नहीं बना।",
    "skipped_selection": "यह पंक्ति चुनी हुई कक्षा या सेशन की नहीं है।",
    "duplicate_identity": "यह रोल नंबर या यही आईडी पहले से दर्ज है।",
    "excel_path_refused": "यह Excel फ़ाइल TEST_EXCEL के बाहर है। काम बंद। / This Excel file is outside TEST_EXCEL. Stopped.",
    "photo_dir_refused": "यह फ़ोटो फ़ोल्डर TEST_PHOTOS नहीं है। काम बंद। / This photo folder is not TEST_PHOTOS. Stopped.",
    "photo_name_refused": "फ़ोटो का नाम सुरक्षित नहीं है। काम बंद। / The photo name is not safe. Stopped.",
    "workspace_refused": "वर्कस्पेस TRIAL_WORKSPACE नहीं है। काम बंद। / The workspace is not TRIAL_WORKSPACE. Stopped.",
    "operation_not_exposed": "यह बदलाव इस ट्रायल में बंद है। / This change is not available in this trial.",
    "writer_blocked": "पुराना राइटर बंद है। / The old writer is blocked.",
    "photo_staging_exists": "पुरानी staging फ़ाइल मौजूद है। उसे नहीं हटाया गया और रिकॉर्ड नहीं बना। / An existing staging file was left unchanged. No record was created.",
    "photo_io_failed": "फोटो लिखी नहीं जा सकी। नया रिकॉर्ड नहीं रखा गया। / The photo could not be written. The new record was not kept.",
    "photo_lock_busy": "यह फोटो किसी दूसरी प्रक्रिया में है। कोई फ़ाइल नहीं हटाई गई। / This photo is busy in another process. No file was removed.",
    "photo_saved": "नामांकन और फोटो सुरक्षित हैं। / The enrollment and photo were kept.",
    "photo_reconcile_failed": "फोटो का रिकॉर्ड और फ़ाइल मेल नहीं खाते। कुछ नहीं हटाया गया। / The photo record and file do not agree. Nothing was removed.",
})

_ENROLLMENT_LOCK = threading.Lock()


def _owner_from_identity(recorded, current):
    """Decide liveness without signaling the other process.

    None means the process is confirmed gone. "unknown" is indeterminate
    and must stay alive so a lock is never stolen by mistake.
    """
    if current is None:
        return False
    if current == "unknown":
        return True
    recorded = str(recorded or "")
    if recorded and recorded != current:
        return False
    return True


def _windows_identity_from_probe(opened, exit_code, creation, error):
    """Map one non-blocking Windows process query to an identity token."""
    error_invalid_parameter = 87
    still_active = 259
    if not opened:
        if error == error_invalid_parameter:
            return None
        return "unknown"
    if exit_code is None or creation is None:
        return "unknown"
    if int(exit_code) != still_active:
        return None
    return str(int(creation))


def _windows_process_identity(pid):
    """Return the creation stamp, None if gone, or "unknown". Never signals."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    get_exit = kernel.GetExitCodeProcess
    get_exit.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit.restype = wintypes.BOOL

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    get_times = kernel.GetProcessTimes
    get_times.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
    ]
    get_times.restype = wintypes.BOOL
    close_handle = kernel.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(0x1000, False, int(pid))
    if not handle:
        return _windows_identity_from_probe(False, None, None, ctypes.get_last_error())
    try:
        code = wintypes.DWORD()
        if not get_exit(handle, ctypes.byref(code)):
            return "unknown"
        created = _FILETIME()
        exited = _FILETIME()
        kernel_time = _FILETIME()
        user_time = _FILETIME()
        if not get_times(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return "unknown"
        stamp = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return _windows_identity_from_probe(True, int(code.value), stamp, 0)
    except OSError:
        return "unknown"
    finally:
        close_handle(handle)


def _process_start(pid):
    if os.name == "nt":
        identity = _windows_process_identity(pid)
        if not identity or identity == "unknown":
            return ""
        return identity
    stat = Path(f"/proc/{pid}/stat")
    try:
        text = stat.read_text(encoding="utf-8")
    except OSError:
        return ""
    end = text.rfind(")")
    if end < 0:
        return ""
    fields = text[end + 2:].split()
    if len(fields) < 20:
        return ""
    return fields[19]


def _owner_alive(info):
    try:
        pid = int(info.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        return _owner_from_identity(info.get("start"), _windows_process_identity(pid))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    recorded = str(info.get("start") or "")
    current = _process_start(pid)
    if recorded and current and recorded != current:
        return False
    return True


class CrossProcessPhotoLock:
    """One exclusive lock for a student photo, shared by separate processes."""

    def __init__(self, workspace, school, session, visible_identifier):
        safe = "".join(
            ch if ch.isalnum() or ch in "._-" else "_"
            for ch in f"{school}_{session}_{visible_identifier}"
        )
        self.path = Path(workspace) / "enrollment_locks" / f"{safe}.lock"
        self.token = str(uuid.uuid4())
        self.held = False
        self.timeout = float(os.environ.get("SAINI_PHOTO_LOCK_TIMEOUT", "10"))

    def acquire(self):
        if self.path.is_symlink():
            raise IdentityError("photo_lock_busy")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            if self._try_create():
                return
            if self._steal_if_stale():
                continue
            if time.monotonic() >= deadline:
                raise IdentityError("photo_lock_busy")
            time.sleep(0.05)

    def release(self):
        if not self.held or self.path.is_symlink() or not self.path.is_file():
            self.held = False
            return
        try:
            info = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.held = False
            return
        if info.get("token") == self.token and info.get("pid") == os.getpid():
            try:
                self.path.unlink()
            except OSError:
                pass
        self.held = False

    def _try_create(self):
        payload = json.dumps({
            "pid": os.getpid(),
            "token": self.token,
            "start": _process_start(os.getpid()),
        }).encode("utf-8")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        self.held = True
        return True

    def _steal_if_stale(self):
        """Remove only a dead owner's lock file. Never remove a photo or staging file."""
        if self.path.is_symlink() or not self.path.is_file():
            return False
        try:
            info = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if _owner_alive(info):
            return False
        retired = self.path.with_name(self.path.name + f".stale.{uuid.uuid4().hex}")
        try:
            self.path.rename(retired)
        except OSError:
            return False
        try:
            if retired.is_symlink() or not retired.is_file():
                return False
            retired.unlink()
        except OSError:
            return False
        return True


class TeacherTrial:
    def __init__(self, workspace):
        self.workspace = require_workspace(workspace)
        self.engine = None

    def close(self):
        if self.engine is not None:
            self.engine.close()

    def _engine(self):
        if self.engine is None:
            database = self.workspace / "identity.sqlite"
            photos = self.workspace / "PHOTO_LIBRARY"
            self.engine = IdentityEngine(database, photos)
        return self.engine

    def start(self, table_path, photo_dir, selected_class, selected_session, entry="teacher_trial.py", should_stop=None, progress=None):
        refuse_legacy_entry(entry)
        table = require_excel(table_path)
        photos = require_photo_dir(photo_dir)
        selected = canonical_class(str(selected_class).strip())
        session = str(selected_session).strip()
        if selected in PENDING_LIMIT_CLASSES:
            return [{
                "ok": False,
                "code": "roll_limit_pending_user_approval",
                "message": MESSAGES["roll_limit_pending_user_approval"],
            }]
        rows = read_table(table)
        preflight_required_photos(photos, rows, selected, session)
        self._engine()
        results = []
        total = len(rows)
        for index, raw in enumerate(rows, start=1):
            if should_stop and should_stop():
                results.append({"ok": False, "code": "cancelled", "message": "रद्द किया गया। / Cancelled."})
                break
            results.append(self._one(raw, photos, selected, session))
            if progress:
                progress(index, total)
        self._reject_key(results)
        return results

    def promote(self, school, session, visible_student_id, new_class, new_roll):
        raise IdentityError("operation_not_exposed")

    def change_roll(self, school, session, visible_student_id, new_roll):
        raise IdentityError("operation_not_exposed")

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
            source = safe_photo_source(photo_dir, photo_name)
            if not _opens(source):
                raise IdentityError("photo_invalid")
            school = str(raw.get("school_code") or "").strip()
            identifier = visible_id(school, row_class, roll)
            target = self._engine().photo_path(school, session, identifier)
            staging = target.with_name(target.name + ".staging")
            photo_lock = CrossProcessPhotoLock(self.workspace, school, session, identifier)
            try:
                photo_lock.acquire()
                try:
                    payload = source.read_bytes()
                    target_existed = target.exists()
                    staging_existed = staging.exists() or staging.is_symlink()
                except OSError as exc:
                    raise IdentityError("photo_io_failed") from exc
                if staging_existed:
                    raise IdentityError("photo_staging_exists")
                if target_existed:
                    try:
                        existing_photo = target.read_bytes()
                    except OSError as exc:
                        raise IdentityError("photo_io_failed") from exc
                    if existing_photo != payload:
                        raise IdentityError("photo_exists")
                with _ENROLLMENT_LOCK:
                    engine = self._engine()
                    owned_before, changes_before = self._ownership_snapshot(engine)
                    created = None
                    created_by_us = False
                    linked = False
                    from_assign = False
                    try:
                        created = engine.create_student(school, session, row_class, roll, name, father)
                        created_by_us = self._created_by_this_attempt(engine, created, owned_before, changes_before)
                        if not created_by_us and created.get("photo_path"):
                            if not self._link_is_committed(engine, created, payload):
                                return self._saved_status(identifier, False)
                            try:
                                viewed = engine.teacher_view(created)
                                return self._public_result(viewed, MESSAGES["already_enrolled"])
                            except Exception:
                                return self._saved_status(identifier, True)
                        if not created.get("photo_path"):
                            from_assign = True
                            created = engine.assign_photo(school, session, created["visible_id"], source)
                        linked = self._link_is_committed(engine, created, payload)
                        if created.get("photo_path") and not linked:
                            return self._saved_status(identifier, False)
                        try:
                            viewed = engine.teacher_view(created)
                            return self._public_result(viewed, "नामांकन हो गया।")
                        except IdentityError:
                            if linked:
                                return self._saved_status(identifier, False)
                            raise
                        except Exception:
                            return self._saved_status(identifier, linked)
                    except Exception as exc:
                        if from_assign:
                            state = self._reconcile_committed_target(
                                engine, school, session, identifier, target, payload
                            )
                            if state == "verified":
                                return self._saved_status(identifier, True)
                            if state == "broken":
                                raise IdentityError("photo_reconcile_failed") from exc
                        if created is not None:
                            self._drop_new_without_photo(created, owned_before, created_by_us, identifier)
                            self._remove_attempt_file(target, payload, target_existed, not target_existed)
                            self._remove_attempt_file(staging, payload, staging_existed, not staging_existed)
                        if isinstance(exc, OSError):
                            raise IdentityError("photo_io_failed") from exc
                        raise
            finally:
                photo_lock.release()
        except IdentityError as exc:
            return {"ok": False, "code": exc.code, "message": MESSAGES.get(exc.code, exc.code)}

    def _ownership_snapshot(self, engine):
        """Read the existing keys without treating a later row count as ownership."""
        with engine._lock:
            engine._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = engine._conn.execute("SELECT permanent_key FROM identities").fetchall()
                changes = engine._conn.total_changes
                engine._conn.rollback()
            except Exception:
                engine._conn.rollback()
                raise
        return {row["permanent_key"] for row in rows}, changes

    def _created_by_this_attempt(self, engine, created, owned_before, changes_before):
        """True only when this connection inserted exactly one new identity."""
        key = created.get("permanent_key") or ""
        if not key or key in owned_before:
            return False
        with engine._lock:
            delta = engine._conn.total_changes - changes_before
        return delta == 2

    def _drop_new_without_photo(self, created, owned_before, created_by_us, visible_identifier):
        """Delete one row only when this attempt has conclusive proof that it created it."""
        if not created_by_us:
            return
        key = created.get("permanent_key") or ""
        if not key or key in owned_before or created.get("visible_id") != visible_identifier:
            return
        engine = self._engine()
        with engine._lock:
            engine._conn.execute("BEGIN IMMEDIATE")
            try:
                engine._conn.execute(
                    """
                    DELETE FROM identities
                    WHERE permanent_key=?
                      AND visible_id=?
                      AND status='current'
                      AND (photo_path IS NULL OR photo_path='')
                    """,
                    (key, visible_identifier),
                )
                deleted = engine._conn.execute("SELECT changes()").fetchone()[0]
                if deleted != 1:
                    engine._conn.rollback()
                    return
                engine._conn.execute(
                    """
                    DELETE FROM students
                    WHERE permanent_key=?
                      AND NOT EXISTS (
                          SELECT 1 FROM identities WHERE identities.permanent_key=students.permanent_key
                      )
                    """,
                    (key,),
                )
                engine._conn.commit()
            except Exception:
                engine._conn.rollback()
                raise

    def _lexical_path(self, path):
        """Absolute path with . and .. removed. This does not follow links."""
        raw = Path(path)
        text = str(raw)
        if text.startswith("\\\\") or text.startswith("//"):
            return None
        if not raw.is_absolute():
            raw = self.workspace / raw
        parts = []
        for part in raw.parts:
            if part == ".":
                continue
            if part == "..":
                if len(parts) <= 1:
                    return None
                parts.pop()
                continue
            parts.append(part)
        if not parts:
            return None
        return Path(*parts)

    def _chain_is_safe(self, path):
        """True only when every component from the workspace to the file is a real path."""
        try:
            candidate = self._lexical_path(path)
            root = self._lexical_path(self.workspace)
        except Exception:
            return False
        if candidate is None or root is None:
            return False
        current = candidate
        seen = set()
        while current not in seen:
            seen.add(current)
            try:
                if _is_reparse_point(current, "photo_reconcile_failed"):
                    return False
            except Exception:
                return False
            if current == root:
                return True
            if current == current.parent:
                return False
            current = current.parent
        return False

    def _reconcile_committed_target(self, engine, school, session, visible_identifier, target, payload):
        """Read the committed photo after a failure. A redirected parent is never verified."""
        try:
            row = engine._conn.execute(
                """
                SELECT photo_path FROM identities
                WHERE school_code=? AND session=? AND visible_id=? AND status='current'
                """,
                (school, session, visible_identifier),
            ).fetchone()
        except Exception:
            return "broken"
        if row is None or not row["photo_path"]:
            if not self._chain_is_safe(target):
                return "broken"
            return "absent"
        stored = Path(row["photo_path"])
        if not self._chain_is_safe(stored) or not self._chain_is_safe(target):
            return "broken"
        if self._lexical_path(stored) != self._lexical_path(target):
            return "broken"
        if stored.is_symlink() or not stored.is_file():
            return "broken"
        if not self._chain_is_safe(stored):
            return "broken"
        try:
            matches = stored.read_bytes() == payload
        except OSError:
            return "broken"
        if not matches or not self._chain_is_safe(stored):
            return "broken"
        return "verified"

    def _saved_status(self, visible_identifier, verified):
        return {
            "ok": bool(verified),
            "skipped": False,
            "code": "photo_saved",
            "message": MESSAGES["photo_saved"],
            "visible_id": visible_identifier,
        }

    def _link_is_committed(self, engine, created, payload):
        """True only when the database photo path is a real file with the expected bytes."""
        visible = created.get("visible_id") or ""
        row = engine._conn.execute(
            """
            SELECT photo_path FROM identities
            WHERE school_code=? AND session=? AND visible_id=? AND status='current'
            """,
            (created.get("school_code"), created.get("session"), visible),
        ).fetchone()
        if row is None or not row["photo_path"]:
            return False
        photo = Path(row["photo_path"])
        if not self._chain_is_safe(photo):
            return False
        if photo.is_symlink() or not photo.is_file():
            return False
        if not self._chain_is_safe(photo):
            return False
        try:
            return photo.read_bytes() == payload and self._chain_is_safe(photo)
        except OSError:
            return False

    def _remove_attempt_file(self, path, payload, existed_before, owned):
        """Delete a file only when this attempt owns it. Matching bytes are not ownership."""
        if existed_before or not owned:
            return
        path = Path(path)
        if not self._chain_is_safe(path) or path.is_symlink() or not path.is_file():
            return
        if not self._chain_is_safe(path):
            return
        try:
            current = path.read_bytes()
        except OSError:
            return
        if current != payload or not self._chain_is_safe(path) or path.is_symlink():
            return
        path.unlink()

    def _public_result(self, created, message):
        return {
            "ok": True,
            "skipped": False,
            "message": message,
            "visible_id": created["visible_id"],
            "photo_path": created.get("photo_path") or "",
            "history": [item["visible_id"] for item in self._engine().history(created["school_code"], created["session"], created["visible_id"])],
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="R23.4A synthetic teacher trial")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--photos", required=True)
    parser.add_argument("--class", dest="selected_class", required=True)
    parser.add_argument("--session", required=True)
    args = parser.parse_args(argv)
    trial = None
    try:
        require_workspace(args.workspace)
        require_excel(args.table)
        require_photo_dir(args.photos)
        trial = TeacherTrial(args.workspace)
        print(json.dumps(
            trial.start(args.table, args.photos, args.selected_class, args.session),
            ensure_ascii=False,
        ))
    except IdentityError as exc:
        print(json.dumps({
            "ok": False,
            "code": exc.code,
            "message": MESSAGES.get(exc.code, exc.code),
        }, ensure_ascii=False))
        return 1
    finally:
        if trial is not None:
            trial.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
