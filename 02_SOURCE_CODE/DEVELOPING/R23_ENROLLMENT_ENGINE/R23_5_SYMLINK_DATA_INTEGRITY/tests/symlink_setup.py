# -*- coding: utf-8 -*-
"""Skip a test only when Windows refuses to create the symlink.

A link that exists, and every later assertion, stays a real failure.
"""

import unittest


def _link_present(link):
    return link.exists() or link.is_symlink()


def _is_windows_privilege_block(exc):
    """True only for the known missing-privilege symlink setup error."""
    if not isinstance(exc, OSError):
        return False
    if getattr(exc, "winerror", None) == 1314:
        return True
    return "a required privilege is not held by the client" in str(exc).lower()


def require_symlink(link, target, target_is_directory=False):
    """Create one symlink. Skip only if creation itself is refused and nothing exists."""
    created_before = _link_present(link)
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        if created_before or _link_present(link) or not _is_windows_privilege_block(exc):
            raise
        winerror = getattr(exc, "winerror", None)
        raise unittest.SkipTest(
            "SKIPPED, not passed: Windows refused symlink creation before the "
            f"security check (WinError {winerror}). A required privilege is not held. "
            "The assertion was not executed."
        ) from exc
    if not _link_present(link):
        raise AssertionError("symlink creation returned without creating a link")
    return link
