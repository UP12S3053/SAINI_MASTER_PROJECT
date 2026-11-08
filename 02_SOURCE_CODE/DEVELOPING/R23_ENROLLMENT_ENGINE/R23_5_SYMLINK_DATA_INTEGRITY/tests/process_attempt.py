# -*- coding: utf-8 -*-
"""Helper process for R23.4H. Not a test module."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from path_guard import TEST_EXCEL, TEST_PHOTOS, TRIAL_WORKSPACE
from teacher_trial import CrossProcessPhotoLock, TeacherTrial


def enroll():
    trial = TeacherTrial(TRIAL_WORKSPACE)
    try:
        result = trial.start(TEST_EXCEL / "TEST_CLASS_1.xlsx", TEST_PHOTOS, "I", "2026_27")[0]
    finally:
        trial.close()
    json.dump(result, sys.stdout, ensure_ascii=True)


def hold():
    ready = Path(sys.argv[2])
    release = Path(sys.argv[3])
    payload = (TEST_PHOTOS / "dummy_a.jpg").read_bytes()
    staging = TRIAL_WORKSPACE / "PHOTO_LIBRARY" / "ABC" / "2026_27" / "ABC1001.jpg.staging"
    lock = CrossProcessPhotoLock(TRIAL_WORKSPACE, "ABC", "2026_27", "ABC1001")
    lock.acquire()
    try:
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(payload)
        ready.write_text("ready", encoding="utf-8")
        deadline = time.monotonic() + 20
        while not release.exists():
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
    finally:
        lock.release()


if __name__ == "__main__":
    if sys.argv[1] == "enroll":
        enroll()
    elif sys.argv[1] == "hold":
        hold()
    else:
        raise SystemExit("unknown command")
