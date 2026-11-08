# -*- coding: utf-8 -*-
"""Double-click entry for the R23.3A development trial window."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from trial_window import open_window


if __name__ == "__main__":
    open_window()
