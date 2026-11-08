# -*- coding: utf-8 -*-
"""Restore a verified R9 backup. The original BSM.png is not deleted or replaced."""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def rollback(root, backup):
    root = Path(root)
    backup = Path(backup)
    manifest = (backup / "SHA256_MANIFEST.txt").read_text(encoding="utf-8").splitlines()
    restored = []
    for line in manifest:
        if "|" not in line:
            continue
        relative, expected = line.split("|", 1)
        source = backup / relative
        if not source.is_file() or sha256(source) != expected:
            print("ROLLBACK_BLOCKED")
            print(f"backup file failed verification: {relative}")
            raise SystemExit(2)
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256(destination) != expected:
            print("ROLLBACK_BLOCKED")
            print(f"restored file failed verification: {relative}")
            raise SystemExit(2)
        restored.append(relative)
    for name in ("bsm_config_loader.py", "config_validator.py", "template_identity.py", "bsm_front_gate.py"):
        added = root / name
        if added.is_file():
            added.unlink()
    print("RESTORED")
    for relative in restored:
        print(relative, sha256(root / relative))
    print("ROLLED_BACK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--backup", required=True)
    args = parser.parse_args()
    rollback(args.root, args.backup)


if __name__ == "__main__":
    main()
