# R23.4B source audit

Inspected package: `R23_4A_PATH_SAFETY` (not modified).
Review package: `R23_4B_FINAL_SAFETY_REVIEW`.
The GUI and BAT were not launched. No real student data was used.

## Files inspected

- `Open_Enrollment.bat`
- `open_launcher.py`
- `src/trial_window.py`
- `src/teacher_trial.py`
- `src/path_guard.py`
- `src/development_launcher.py`
- `src/active_writers.py`
- `src/controlled_writers.py`
- `src/legacy_guard.py`
- `src/identity_engine.py`
- `src/generator_contract.py`
- `tests/test_r23_4a_path_safety.py`

`identity_engine.py` was read and not changed. Its SHA256 is `e7d9b3626986e5aa287480ba9de5f2bb5d0d9efdbdf81ee9b9eaf633490910d2`.

## What the R23.4A code actually did

`require_excel()` and `require_photo_dir()` checked the resolved path. `require_workspace()` demanded the exact workspace. `safe_photo_source()` checked one photo name. `preflight_photo_names()` skipped a missing plain filename (`path_guard.py` lines 70-71 in R23.4A). `TeacherTrial.start()` then created the engine (`teacher_trial.py` line 76 in R23.4A). A missing photo could therefore create `identity.sqlite` and `PHOTO_LIBRARY` before the row failed.

`TeacherTrial.promote()` and `change_roll()` were not called by `main()` or by `EnrollmentScreen`. A direct call created the engine and wrote. `DevelopmentLauncher.__init__()` created a database after only `assert_development_path()` (`development_launcher.py` lines 35-40 in R23.4A). It was not imported by `open_launcher.py`.

`active_writers.py` wrote through the engine and did not read `WRITER_CONTROL`. `controlled_writers.py` declared `WRITER_CONTROL` at line 10, but `enroll()` at line 41 did not consult it. No other R23.4A module referenced `WRITER_CONTROL`. The dictionary was not an enforced control.

`generator_contract.py` only inspects text. It does not write.

## Identity rules

Visible ID formatting and identity history remain in `identity_engine.py`. That file is byte-for-byte unchanged.
