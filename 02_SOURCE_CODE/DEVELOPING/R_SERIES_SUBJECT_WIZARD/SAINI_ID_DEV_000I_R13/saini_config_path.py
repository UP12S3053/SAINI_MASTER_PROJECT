# -*- coding: utf-8 -*-
"""One workbook path for the ID generator and the Config Editor.

The generator previously defaulted to the D: project workbook while the
editor wrote a hard-coded F: workbook. Both now call resolve_config_workbook().
"""
import os

DEFAULT_CONFIG_WORKBOOK = r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
_LEGACY_F_PREFIX = "f:\\shri_jai_shri_ram"


def _folded(path):
    return str(path).replace("/", "\\").casefold()


def resolve_config_workbook():
    """Return the shared workbook path. Never opens or writes a file."""
    override = os.environ.get("SAINI_DEV_CONFIG_XLSX", "")
    path = override.strip() if isinstance(override, str) else ""
    if not path:
        path = DEFAULT_CONFIG_WORKBOOK
    if _folded(path).startswith(_LEGACY_F_PREFIX):
        raise RuntimeError(
            "Refusing legacy F: workbook path. "
            "Config Editor and Generator must share the generator workbook path."
        )
    return path
