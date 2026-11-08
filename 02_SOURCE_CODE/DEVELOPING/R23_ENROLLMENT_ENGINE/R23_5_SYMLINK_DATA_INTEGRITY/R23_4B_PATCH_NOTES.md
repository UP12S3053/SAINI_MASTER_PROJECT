# R23.4B patch notes

The original `R23_4A_PATH_SAFETY` package was not overwritten.
`identity_engine.py` was not edited.

## Patched files

- `src/path_guard.py`
  - `require_excel()` line 30, `preflight_required_photos()` line 96.
  - UNC rejection, symlink and reparse rejection, and full photo validation before enrollment.
- `src/teacher_trial.py`
  - `promote()` and `change_roll()` lines 91-95 are closed.
  - `_drop_new_without_photo()` line 136 removes only an unphotographed row created by the same attempt.
- `src/development_launcher.py`
  - `enroll_table()` line 50 and `promote()` line 58 refuse before creating the engine.
- `src/controlled_writers.py`
  - `enforce_writer()` line 37 reads `WRITER_CONTROL` and refuses a blocked policy.
- `src/active_writers.py`
  - `stepE_enroll_from_sheet()` line 35 and the other declared writers call `enforce_writer()` before any engine write.
- `STOP.txt` says not to launch this package.
- `tests/test_r23_4b_safety.py` is new.

## Not patched

- `src/identity_engine.py`
- The live project under `D:\SHRI_JAI_SHRI_RAM\project_panels`
- The original R23.4 and R23.4A folders

Identity allocation and identity-history code inside `identity_engine.py` are unchanged.
