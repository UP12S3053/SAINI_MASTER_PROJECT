# -*- coding: utf-8 -*-
"""Read-only contract with the existing ID card generator.

The generator is not imported and its card code is not executed here.
"""

from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / "baseline" / "SAINI_ID_CARD.py"


def generator_reads_prepared_fields(source_text):
    return "STUDENT_PHOTO_PATH" in source_text and "student_unique_id" in source_text


def baseline_generator_text():
    return BASELINE.read_text(encoding="utf-8")
