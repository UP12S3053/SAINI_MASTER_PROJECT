# R23.4C security findings

R23.4A and R23.4B were not overwritten. `identity_engine.py` was not edited.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect 1 — orphan photo

Confirmed in R23.4B: `photo_fail = "database"` writes `PHOTO_LIBRARY/ABC/2026_27/ABC1001.jpg` and then raises. `_drop_new_without_photo()` deleted the student row and left the file.

R23.4C deletes that file only when all of these are true:

- this attempt created it
- it is a regular file inside this workspace's `PHOTO_LIBRARY`
- its bytes still equal the photo bytes from this attempt

A pre-existing photo is not deleted. A file whose bytes were replaced is not deleted. `photo_stage_failed` and `photo_finalize_failed` were also run against the real `assign_photo()` method.

## Defect 2 — legacy history created a database

Confirmed in R23.4B: `DevelopmentLauncher.visible_history()` called `_engine()`, and `_engine()` created `identity.sqlite` and `PHOTO_LIBRARY`.

R23.4C makes `_engine()`, `visible_history()`, `enroll_table()`, `promote()`, `run_legacy_baseline()`, `_enroll_row()`, and `_success()` raise `writer_blocked` before any database is created.

## Defect 3 — reparse failure was treated as safe

Confirmed in R23.4B: `_is_reparse_point()` caught every exception and returned `False`.

R23.4C raises `IdentityError` when a Windows attribute check fails or is indeterminate. On Linux the function returns `False` only after an explicit non-Windows check. A symlink is still refused. This does not prove that Windows junctions are blocked.

## Unresolved

Windows junction behavior was not executed on this Linux runner. One older test remains skipped for that reason.
Passing these tests does not authorize a teacher trial and does not approve production.
