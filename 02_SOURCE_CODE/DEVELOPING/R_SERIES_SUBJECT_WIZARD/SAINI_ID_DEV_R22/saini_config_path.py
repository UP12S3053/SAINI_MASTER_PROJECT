# -*- coding: utf-8 -*-
"""Shared workbook path for the R19 development generator and editor.

The resolved path is never the legacy F: workbook and never the live
production workbook. A missing file fails closed, with no fallback.
"""
import os
from pathlib import Path

DEFAULT_CONFIG_WORKBOOK = r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R22\school_config_front.xlsx"
LIVE_PRODUCTION_WORKBOOK = r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
_LEGACY_F_PREFIX = "f:\\shri_jai_shri_ram"


class ConfigPathError(RuntimeError):
    """The development workbook path cannot be used safely."""


def _folded(path):
    return str(path).replace("/", "\\").casefold()


def resolve_config_workbook():
    """Return the one shared path. Do not open a file and do not fall back."""
    override = os.environ.get("SAINI_DEV_CONFIG_XLSX", "")
    path = override.strip() if isinstance(override, str) else ""
    if not path:
        path = DEFAULT_CONFIG_WORKBOOK
    folded = _folded(path)
    if folded.startswith(_LEGACY_F_PREFIX):
        raise ConfigPathError("Refusing legacy F: workbook path. No other workbook will be opened.")
    if folded == _folded(LIVE_PRODUCTION_WORKBOOK):
        raise ConfigPathError("Refusing live production workbook path. Development cannot fall back to the live workbook.")
    return path


def require_config_workbook():
    """Return the shared path or fail closed when that exact file is missing."""
    path = resolve_config_workbook()
    if not Path(path).is_file():
        raise ConfigPathError("Development workbook is missing: " + path + ". No fallback workbook will be opened.")
    return path
