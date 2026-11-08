# -*- coding: utf-8 -*-
"""Stops the R23.2 workflow from launching the preserved baseline program."""

from pathlib import Path

from identity_engine import IdentityError


class LegacyEntryBlocked(IdentityError):
    def __init__(self):
        super().__init__("legacy_entry_blocked")


def refuse_legacy_entry(entry):
    name = Path(str(entry)).name
    blocked = {
        "MAIN_ASSISTANT.py",
        "next_official_uid",
        "stepE_enroll_from_sheet",
        "step1_smart_rename",
        "step_reassign_mixed",
    }
    # The active replacements live in active_writers and are not files.
    # A request that names the baseline file or the old allocator is refused.
    if name in blocked or str(entry) in blocked:
        raise LegacyEntryBlocked()
    if "baseline" in str(entry).replace("\\", "/").split("/"):
        raise LegacyEntryBlocked()
