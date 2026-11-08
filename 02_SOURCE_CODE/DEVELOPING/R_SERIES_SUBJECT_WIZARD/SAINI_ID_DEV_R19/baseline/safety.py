"""Fail-closed safety primitives for Option C candidate (Windows/Python 3.11+)."""
from __future__ import annotations
import hashlib, json, os, socket, time, uuid
from contextlib import contextmanager
from pathlib import Path

LOCK_SCHEMA = 1

def _process_start_identity() -> str:
    """Return OS process creation identity where available (not lock creation time)."""
    pid = os.getpid()
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                try:
                    created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                    if kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
                        ticks = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
                        return f"win-filetime:{ticks}"
                finally:
                    kernel32.CloseHandle(handle)
        except Exception:
            pass
    else:
        try:
            stat_text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            fields_after_comm = stat_text[stat_text.rfind(")") + 2:].split()
            return f"proc-start-ticks:{fields_after_comm[19]}"
        except Exception:
            pass
    # Fallback is unique to this loaded process instance; it is not presented as an OS timestamp.
    return f"runtime-instance:{_MODULE_INSTANCE_ID}"

_MODULE_INSTANCE_ID = uuid.uuid4().hex

def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def payload_fingerprint(rows) -> str:
    data = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def make_approval(*, batch_id: str, school_code: str, audio_path: str | Path, rows) -> dict:
    """Capture immutable evidence immediately before presenting approval prompt."""
    return {"schema_version": 1, "batch_id": str(batch_id),
            "school_code": str(school_code).strip().upper(),
            "audio_sha256": sha256_file(audio_path),
            "payload_sha256": payload_fingerprint(rows), "approved": False}

def validate_approval(evidence: dict, *, batch_id: str, school_code: str, audio_path: str | Path, rows) -> bool:
    """Approval is valid only for the exact batch, school, audio bytes and payload."""
    try:
        return bool(evidence and evidence.get("approved") is True
            and evidence.get("schema_version") == 1
            and evidence.get("batch_id") == str(batch_id)
            and evidence.get("school_code") == str(school_code).strip().upper()
            and evidence.get("audio_sha256") == sha256_file(audio_path)
            and evidence.get("payload_sha256") == payload_fingerprint(rows))
    except (OSError, TypeError, ValueError):
        return False

@contextmanager
def school_batch_lock(lock_root: str | Path, school_code: str, batch_id: str):
    """Exclusive per-school lock; stale locks fail closed and are never age-deleted."""
    root = Path(lock_root); root.mkdir(parents=True, exist_ok=True)
    lock = root / (str(school_code).strip().upper() + ".lock")
    token = uuid.uuid4().hex
    record = {"schema_version": LOCK_SCHEMA, "token": token, "batch_id": str(batch_id),
              "school_code": str(school_code).strip().upper(), "pid": os.getpid(),
              "process_start_identity": _process_start_identity(), "host": socket.gethostname(),
              "created_ns": time.time_ns(), "state": "ACTIVE"}
    fd = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            json.dump(record, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"school batch lock already exists; fail closed pending journal/sink reconciliation: {lock}") from exc
    finally:
        if fd is not None: os.close(fd)
    failed = False
    try:
        yield record
    except BaseException:
        # Any exception may mean a sink was partially mutated. Keep the lock so
        # another run cannot race recovery. Reconciliation must explicitly clear it.
        failed = True
        raise
    finally:
        if not failed:
            # Remove only our own lock after a clean exit. Never delete a lock
            # replaced by another process. Exceptions intentionally preserve it.
            try:
                current = json.loads(lock.read_text(encoding="utf-8"))
                if current.get("token") == token and current.get("batch_id") == str(batch_id):
                    lock.unlink()
            except FileNotFoundError:
                pass
            except Exception as exc:
                raise RuntimeError(f"could not safely release school lock; manual recovery required: {lock}") from exc


@contextmanager
def recovery_school_batch_lock(lock_root: str | Path, school_code: str, batch_id: str, journal_path: str | Path):
    """Take over a preserved lock only for its exact RECOVERY_REQUIRED journal.

    The prior owner must be demonstrably gone (PID/start identity mismatch or absent).
    Lock files are quarantined for audit, never deleted by age. Unknown owner state fails closed.
    """
    from journal import load_journal
    root = Path(lock_root); root.mkdir(parents=True, exist_ok=True)
    school = str(school_code).strip().upper()
    lock = root / (school + ".lock")
    journal = load_journal(journal_path)
    if journal.get("state") != "RECOVERY_REQUIRED" or not journal.get("recovery_required"):
        raise RuntimeError("recovery requires a journal in RECOVERY_REQUIRED state")
    if journal.get("batch_id") != str(batch_id) or str(journal.get("school_code", "")).strip().upper() != school:
        raise RuntimeError("recovery journal identity does not match requested batch/school")
    if not lock.is_file():
        raise RuntimeError("recovery lock is missing; refusing to infer ownership")
    try:
        old = json.loads(lock.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("recovery lock is unreadable; manual review required") from exc
    if old.get("batch_id") != str(batch_id) or str(old.get("school_code", "")).strip().upper() != school:
        raise RuntimeError("preserved lock belongs to a different batch/school")
    if old.get("host") != socket.gethostname():
        raise RuntimeError("lock owner host differs; cannot prove old process is gone")
    pid = old.get("pid")
    expected_start = old.get("process_start_identity")
    actual_start = None
    if isinstance(pid, int) and pid > 0:
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes
                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel32.OpenProcess.restype = wintypes.HANDLE
                kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
                kernel32.GetProcessTimes.restype = wintypes.BOOL
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel32.OpenProcess(0x1000, False, pid)
                if handle:
                    try:
                        created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                        if kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
                            ticks = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
                            actual_start = f"win-filetime:{ticks}"
                    finally:
                        kernel32.CloseHandle(handle)
                else:
                    # ERROR_INVALID_PARAMETER (87) means that PID no longer exists.
                    # Access-denied and all other errors are ambiguous and fail closed.
                    actual_start = "PROCESS_ABSENT" if ctypes.get_last_error() == 87 else None
            except Exception:
                actual_start = None
        else:
            try:
                stat_text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
                fields_after_comm = stat_text[stat_text.rfind(")") + 2:].split()
                actual_start = f"proc-start-ticks:{fields_after_comm[19]}"
            except FileNotFoundError:
                actual_start = "PROCESS_ABSENT"
            except Exception:
                actual_start = None
    if actual_start is None:
        raise RuntimeError("cannot prove previous lock owner process state; recovery fails closed")
    if actual_start == expected_start:
        raise RuntimeError("previous lock owner process is still alive; recovery cannot race it")
    # Preserve the old lock as an audit artifact and claim a fresh exclusive lock.
    quarantine = lock.with_name(lock.name + f".recovered-{batch_id}-{uuid.uuid4().hex[:8]}")
    try:
        os.replace(lock, quarantine)
    except OSError as exc:
        raise RuntimeError("could not safely quarantine old recovery lock") from exc
    token = uuid.uuid4().hex
    record = {"schema_version": LOCK_SCHEMA, "token": token, "batch_id": str(batch_id),
              "school_code": school, "pid": os.getpid(),
              "process_start_identity": _process_start_identity(), "host": socket.gethostname(),
              "created_ns": time.time_ns(), "state": "RECOVERING", "recovered_lock": str(quarantine)}
    fd = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            json.dump(record, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
    except Exception as exc:
        if fd is not None:
            os.close(fd)
        raise RuntimeError("could not claim recovery lock; old lock retained in quarantine") from exc
    failed = False
    try:
        yield record
    except BaseException:
        failed = True
        raise
    finally:
        if not failed:
            try:
                current = json.loads(lock.read_text(encoding="utf-8"))
                if current.get("token") == token and current.get("batch_id") == str(batch_id):
                    lock.unlink()
            except Exception as exc:
                raise RuntimeError("could not safely release recovery lock; manual recovery required") from exc
