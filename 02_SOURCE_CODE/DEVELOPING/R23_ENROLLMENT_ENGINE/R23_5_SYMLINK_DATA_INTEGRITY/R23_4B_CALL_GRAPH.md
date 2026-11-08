# Current status: STOP

Teacher Trial is NOT AUTHORIZED. Production is NOT APPROVED.
Do not run `Open_Enrollment.bat`, `open_launcher.py`, the enrollment GUI, or a production workflow.
The word ACTIVE below names a historical code path. It is not permission to launch it.
A skip is not a pass.

# R23.4B call graph

Line numbers for the original routes refer to `R23_4A_PATH_SAFETY` before this patch. The patched routes refer to `R23_4B_FINAL_SAFETY_REVIEW`.

## Active entry points

| Route | Class | Source |
|---|---|---|
| `Open_Enrollment.bat` line 5 calls `open_launcher.py` | ACTIVE entry, not launched in this review | `open_launcher.py` line 13 calls `open_window()` |
| `trial_window.open_window()` | ACTIVE | `trial_window.py` line 272 |
| `EnrollmentScreen.start()` | ACTIVE | `trial_window.py` line 99; builds `TeacherTrial` near line 122 |
| `teacher_trial.main()` | ACTIVE CLI | `teacher_trial.py` line 163 in R23.4A |
| `TeacherTrial.start()` then `_one()` | ACTIVE enrollment | `teacher_trial.py` lines 62 and 107 in R23.4A |
| `IdentityEngine.__init__`, `create_student`, `assign_photo` | ACTIVE only after the R23.4B preflight | `identity_engine.py` lines 131, 170, 253 |

R23.4B keeps this enrollment route. `start()` now calls `preflight_required_photos()` before `_engine()`.

## Blocked routes

| Route | Class | Why |
|---|---|---|
| `refuse_legacy_entry()` | BLOCKED | `legacy_guard.py` lines 14-28 refuse `MAIN_ASSISTANT.py` and the named old steps |
| `assert_development_path()` | BLOCKED | `identity_engine.py` lines 73-76 refuse `SHRI_JAI_SHRI_RAM` and `STUDENT_DATA.XLSX` |
| Excel, photo folder, workspace outside the package | BLOCKED | `path_guard.py` |
| UNC paths | BLOCKED before resolve | `path_guard.py` `_reject_unc()` |
| Symbolic links and detected reparse points | BLOCKED | `path_guard.py` `_is_reparse_point()` |
| `TeacherTrial.promote()` and `change_roll()` | BLOCKED in R23.4B | `teacher_trial.py` lines 91-95; no database is created |
| `DevelopmentLauncher.enroll_table()` and `promote()` | BLOCKED in R23.4B | `development_launcher.py` lines 50-58 raise `writer_blocked` before `IdentityEngine` |
| `active_writers.stepE_enroll_from_sheet` and the other declared writers | BLOCKED in R23.4B | `enforce_writer()` runs before `engine.create_student` |
| `controlled_writers.enroll`, `promote`, `change_roll`, `correct_name`, `reenter`, `assign_photo` | BLOCKED in R23.4B | each calls `enforce_writer()` first |
| `legacy_next_official_uid()` and `active_writers._delete()` | BLOCKED | they already raised |

## Unreachable from the BAT and CLI, before this patch

These were not called by `open_launcher.py`, `trial_window.py`, or `teacher_trial.main()`, but a direct import could use them:

- `DevelopmentLauncher` (`development_launcher.py` line 34)
- `active_writers.stepE_enroll_from_sheet` (line 34), `step1_smart_rename` (line 41), `step4_update_photo_db` (line 48), `step6_data_merge` (line 55), `step_reassign_mixed` (line 77)
- `controlled_writers.enroll` (line 41) and the write functions below it
- `TeacherTrial.promote` and `change_roll`

R23.4B turns those direct calls into blocked calls. They are no longer an open write route.

## Unknown

Windows junction creation was not executed in the original R23.4B Linux review. That old skip was not a pass.
R23.4M later ran the junction tests on Windows and those tests passed. Do not describe the R23.4M passes as skips, or the WinError 1314 skips as passes.
