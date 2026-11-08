# R23.4E security findings

R23.4A, R23.4B, R23.4C, and R23.4D were not overwritten. `identity_engine.py` was not edited.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect

`test_windows_junction_is_reported_when_unsupported` treated Windows as a failure because `junction_test_supported()` returns true when `os.name == "nt"`. That test was written for Linux only. On Windows it failed before creating a junction.

## Repair

On Linux the live junction probe is skipped with the exact reason: Windows junction verification was not executed. That skip is not a pass.

On Windows the probe creates a temporary directory junction that points outside `TEST_PHOTOS`, then checks:

- `_is_reparse_point()` detects it
- `require_photo_dir()` raises `photo_dir_refused`
- `safe_photo_source()` raises `photo_name_refused`
- no `identity.sqlite`, `PHOTO_LIBRARY`, or student row is created

The junction is removed with `rmdir`, so the outside dummy files are not deleted. If `mklink /J` fails, the result is SKIPPED with the command's reason. It is never marked passed.

`GetFileAttributesW` now uses an explicit 32-bit unsigned result. A missing or `0xFFFFFFFF` attribute raises and the path is refused. It is not treated as safe.

## This run

The live Windows junction was not created here. This runner is Linux. Windows junction protection remains UNVERIFIED.
