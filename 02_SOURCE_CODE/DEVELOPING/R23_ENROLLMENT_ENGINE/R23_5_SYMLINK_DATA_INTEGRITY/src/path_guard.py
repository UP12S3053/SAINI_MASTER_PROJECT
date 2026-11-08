# -*- coding: utf-8 -*-
"""Fail-closed path allowlist for the R23.4B review package.

Nothing in this module creates a database or a photo library.
A path is refused before resolve when it is a UNC path.
Symbolic links and Windows reparse points are refused.
"""

import os
import re
from pathlib import Path

from identity_engine import IdentityError, assert_development_path, canonical_class

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TEST_EXCEL = PACKAGE_ROOT / "TEST_EXCEL"
TEST_PHOTOS = PACKAGE_ROOT / "TEST_PHOTOS"
TRIAL_WORKSPACE = PACKAGE_ROOT / "TRIAL_WORKSPACE"
_SIMPLE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}\Z")
_REPARSE = 0x400


def require_workspace(path):
    """Accept only this package's real TRIAL_WORKSPACE directory."""
    _reject_unc(path, "workspace_refused")
    allowed = _approved_directory(TRIAL_WORKSPACE, "workspace_refused")
    return _exact_directory(path, allowed, "workspace_refused")


def require_excel(path):
    """Accept only a real workbook file inside this package's TEST_EXCEL directory."""
    _reject_unc(path, "excel_path_refused")
    allowed = _approved_directory(TEST_EXCEL, "excel_path_refused")
    candidate = Path(path)
    assert_development_path(candidate)
    if _is_reparse_point(candidate, "excel_path_refused"):
        raise IdentityError("excel_path_refused")
    if not candidate.exists():
        raise IdentityError("excel_path_refused")
    final = candidate.resolve()
    if not final.is_file() or final.suffix.lower() not in {".xlsx", ".csv"}:
        raise IdentityError("excel_path_refused")
    if not _contained(final, allowed) or final == allowed:
        raise IdentityError("excel_path_refused")
    _reject_reparse_chain(candidate, allowed, "excel_path_refused")
    return final


def require_photo_dir(path):
    """Accept only this package's real TEST_PHOTOS directory."""
    _reject_unc(path, "photo_dir_refused")
    allowed = _approved_directory(TEST_PHOTOS, "photo_dir_refused")
    return _exact_directory(path, allowed, "photo_dir_refused")


def assert_simple_filename(value):
    """Reject every photo name that is not one plain file name."""
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise IdentityError("photo_name_refused")
    if value in {".", ".."} or ".." in value:
        raise IdentityError("photo_name_refused")
    if any(mark in value for mark in ("/", "\\", ":", "\x00")):
        raise IdentityError("photo_name_refused")
    lowered = value.lower()
    if lowered.startswith("\\\\") or lowered.startswith("//"):
        raise IdentityError("photo_name_refused")
    if Path(value).is_absolute() or Path(value).name != value:
        raise IdentityError("photo_name_refused")
    if _SIMPLE_NAME.fullmatch(value) is None:
        raise IdentityError("photo_name_refused")


def preflight_photo_names(photo_root, rows):
    """Refuse an unsafe photo name before a database is created.

    A missing plain filename is not accepted here either. The caller must
    not treat a missing file as a reason to continue into enrollment.
    """
    root = Path(photo_root).resolve()
    for raw in rows:
        value = raw.get("photo_file")
        if value is None or str(value).strip() == "":
            continue
        text = str(value)
        assert_simple_filename(text)
        candidate = root / text
        if _is_reparse_point(candidate, "photo_name_refused"):
            raise IdentityError("photo_name_refused")
        if not candidate.is_file():
            raise IdentityError("photo_source_missing")
        final = candidate.resolve()
        if not _contained(final, root) or final == root or not final.is_file():
            raise IdentityError("photo_name_refused")


def preflight_required_photos(photo_root, rows, selected, session):
    """Validate every selected row's photo before any database is created."""
    root = require_photo_dir(photo_root)
    selected_class = canonical_class(str(selected).strip())
    selected_session = str(session).strip()
    for raw in rows:
        value = raw.get("photo_file")
        text = "" if value is None else str(value)
        if text.strip() != "":
            assert_simple_filename(text)
        row_session = str(raw.get("session") or "").strip()
        row_class = canonical_class(str(raw.get("class") or "").strip())
        if row_session != selected_session or row_class != selected_class:
            if text.strip() != "":
                _contained_file(root, text)
            continue
        source = safe_photo_source(root, text)
        if source.stat().st_size <= 0 or not _opens(source):
            raise IdentityError("photo_invalid")
    return root


def safe_photo_source(photo_root, photo_name):
    """Return one real photo path inside TEST_PHOTOS, or refuse."""
    text = "" if photo_name is None else str(photo_name)
    if text.strip() == "":
        raise IdentityError("photo_source_missing")
    assert_simple_filename(text)
    root = Path(photo_root).resolve()
    candidate = root / text
    if _is_reparse_point(candidate, "photo_name_refused"):
        raise IdentityError("photo_name_refused")
    if not candidate.is_file():
        raise IdentityError("photo_source_missing")
    final = candidate.resolve()
    if not _contained(final, root) or final == root or not final.is_file():
        raise IdentityError("photo_name_refused")
    _reject_reparse_chain(candidate, root, "photo_name_refused")
    return final


def junction_test_supported():
    """True only means this process is Windows. It is not a passed junction test."""
    return os.name == "nt"


def interpret_file_attributes(attrs):
    """Fail closed when Windows file attributes are missing or indeterminate."""
    if attrs is None:
        raise OSError("reparse_check_indeterminate")
    value = int(attrs) & 0xFFFFFFFF
    if value == 0xFFFFFFFF:
        raise OSError("reparse_check_indeterminate")
    return bool(value & _REPARSE)


def _contained_file(root, name):
    candidate = Path(root) / name
    if _is_reparse_point(candidate, "photo_name_refused"):
        raise IdentityError("photo_name_refused")
    if not candidate.exists() and not candidate.is_symlink():
        return None
    final = candidate.resolve()
    if not _contained(final, root) or not final.is_file():
        raise IdentityError("photo_name_refused")
    return final


def _approved_directory(raw, code):
    raw = Path(raw)
    package = PACKAGE_ROOT.resolve()
    if _is_reparse_point(raw, code) or not raw.is_dir():
        raise IdentityError(code)
    resolved = raw.resolve()
    assert_development_path(resolved)
    if not _contained(resolved, package):
        raise IdentityError(code)
    _reject_reparse_chain(raw, package, code)
    return resolved


def _exact_directory(path, allowed, code):
    candidate = Path(path)
    assert_development_path(candidate)
    if _is_reparse_point(candidate, code):
        raise IdentityError(code)
    if not candidate.exists():
        raise IdentityError(code)
    final = candidate.resolve()
    if final != allowed or not final.is_dir():
        raise IdentityError(code)
    return final


def _contained(path, root):
    path = Path(path).resolve()
    root = Path(root).resolve()
    if path == root:
        return True
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_unc(path, code):
    text = str(path).replace("/", "\\")
    if text.startswith("\\\\"):
        raise IdentityError(code)


def _is_reparse_point(path, code, platform=None):
    """Return True for a symlink or a confirmed Windows reparse point.

    On Linux this does not pretend to inspect Windows junctions.
    If a Windows attribute check fails or is indeterminate, this refuses
    the path. It does not treat that failure as safe.
    """
    path = Path(path)
    if path.is_symlink():
        return True
    system = os.name if platform is None else platform
    if system != "nt":
        return False
    if not path.exists():
        return False
    try:
        return _windows_reparse_attribute(path)
    except Exception as exc:
        raise IdentityError(code) from exc


def _windows_reparse_attribute(path):
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_attributes = kernel.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = ctypes.c_uint32
    attrs = get_attributes(str(path))
    if int(attrs) & 0xFFFFFFFF == 0xFFFFFFFF:
        raise OSError(ctypes.get_last_error(), "reparse_check_indeterminate")
    return interpret_file_attributes(attrs)


def _reject_reparse_chain(path, stop_at, code):
    current = Path(path)
    stop = Path(stop_at).resolve()
    seen = set()
    while current not in seen:
        seen.add(current)
        if _is_reparse_point(current, code):
            raise IdentityError(code)
        try:
            if current.resolve() == stop:
                break
        except OSError:
            raise IdentityError(code)
        if current == current.parent:
            break
        current = current.parent


def _opens(path):
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(path) as image:
            image.load()
        return True
    except (OSError, UnidentifiedImageError):
        return False
