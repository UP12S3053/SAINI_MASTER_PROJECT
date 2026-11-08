# -*- coding: utf-8 -*-
"""Create one temporary Windows junction and require the path guard to refuse it.

A failed junction creation is skipped. It is never reported as a pass.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from identity_engine import IdentityError
from path_guard import _is_reparse_point, require_photo_dir, safe_photo_source


class JunctionUnavailable(Exception):
    pass


class JunctionCleanupError(Exception):
    """Junction removal failed. This must fail the test. It is not a skip."""


def create_directory_junction(link, target):
    if os.name != "nt":
        raise JunctionUnavailable(
            "Windows junction verification was not executed on this Linux runner. Status: UNVERIFIED."
        )
    link = Path(link)
    target = Path(target)
    if link.exists() or link.is_symlink():
        raise JunctionUnavailable(f"junction creation failed: path already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not link.exists():
        detail = (completed.stderr or completed.stdout or "mklink failed").strip()
        raise JunctionUnavailable(f"junction creation failed: {detail}")


def _windows_rmdir(link):
    completed = subprocess.run(
        ["cmd", "/c", "rmdir", str(link)],
        capture_output=True,
        text=True,
    )
    detail = (completed.stderr or completed.stdout or "").strip()
    return completed.returncode, detail


def remove_directory_junction(link, rmdir_func=None):
    """Remove only the junction entry. Never recurse into its target."""
    link = Path(link)
    if rmdir_func is None and os.name != "nt":
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            raise JunctionCleanupError(
                "junction cleanup failed: refusing to recursively delete a real directory"
            )
        if link.exists() or link.is_symlink():
            raise JunctionCleanupError("junction cleanup failed: path still exists")
        return
    code, detail = (rmdir_func or _windows_rmdir)(link)
    if code != 0:
        raise JunctionCleanupError(f"junction cleanup failed: rmdir returned {code}: {detail}")
    if link.exists() or link.is_symlink():
        raise JunctionCleanupError("junction cleanup failed: path still exists")


def assert_junction_rejected(photo_root, workspace):
    """Refuse a junction that points outside TEST_PHOTOS. Never delete the outside files."""
    outside = None
    link = Path(photo_root) / "JUNCTION_ESCAPE"
    created = False
    try:
        if os.name != "nt":
            raise JunctionUnavailable(
                "Windows junction verification was not executed on this Linux runner. Status: UNVERIFIED."
            )
        outside = Path(tempfile.mkdtemp(prefix="saini_junction_outside_"))
        (outside / "secret.txt").write_bytes(b"synthetic-not-a-student")
        create_directory_junction(link, outside)
        created = True
        detected = _is_reparse_point(link, "photo_dir_refused")
        if not detected:
            raise AssertionError("Windows junction was not detected as a reparse point")
        try:
            require_photo_dir(link)
        except IdentityError as exc:
            if exc.code != "photo_dir_refused":
                raise AssertionError(f"require_photo_dir returned {exc.code}") from exc
        else:
            raise AssertionError("require_photo_dir accepted a junction")
        try:
            safe_photo_source(photo_root, "JUNCTION_ESCAPE")
        except IdentityError as exc:
            if exc.code != "photo_name_refused":
                raise AssertionError(f"safe_photo_source returned {exc.code}") from exc
        else:
            raise AssertionError("safe_photo_source accepted a junction")
        if (Path(workspace) / "identity.sqlite").exists():
            raise AssertionError("identity.sqlite was created after junction rejection")
        if (Path(workspace) / "PHOTO_LIBRARY").exists():
            raise AssertionError("PHOTO_LIBRARY was created after junction rejection")
        if (outside / "secret.txt").read_bytes() != b"synthetic-not-a-student":
            raise AssertionError("outside synthetic file was modified")
    finally:
        cleanup_error = None
        try:
            if created or link.exists() or link.is_symlink():
                remove_directory_junction(link)
        except JunctionCleanupError as exc:
            cleanup_error = exc
        if cleanup_error is None and outside is not None:
            shutil.rmtree(outside)
        if cleanup_error is not None:
            raise cleanup_error


def classify_junction_attempt(creator):
    """Return skipped when creation fails. A successful create is not marked skipped."""
    try:
        creator()
    except JunctionUnavailable as exc:
        reason = str(exc)
        if not reason:
            raise AssertionError("junction failure had no reason")
        return "skipped", reason
    return "created", ""
