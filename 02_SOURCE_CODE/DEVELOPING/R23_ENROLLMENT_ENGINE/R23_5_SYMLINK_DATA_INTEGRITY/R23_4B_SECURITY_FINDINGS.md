# R23.4B security findings

## Confirmed in R23.4A

1. Missing required photos were skipped by `preflight_photo_names()` and the database was created afterward.
2. A photo failure after `create_student()` could leave a student row with no photo. `_one()` caught the error and did not undo the new row.
3. `DevelopmentLauncher` could create a database outside `TRIAL_WORKSPACE` because it used only `assert_development_path()`.
4. `WRITER_CONTROL` was a dictionary. Nothing enforced it.
5. `TeacherTrial.promote()` and `change_roll()` were not on the GUI or CLI, but a direct call wrote through the engine.
6. Resolved-path checks did not explicitly refuse a UNC string before resolve, and they accepted a symlink whose final target stayed inside the folder.

## Repaired in R23.4B

1. Every selected row's photo name, file, symlink status, and image open test finishes before `IdentityEngine` is constructed.
2. A new student without a stored photo is removed if photo assignment fails. An already enrolled student is not removed.
3. The old launcher and the declared writers raise `writer_blocked` before creating a database.
4. `WRITER_CONTROL` is checked by `enforce_writer()`.
5. Promotion and roll change on the trial object raise `operation_not_exposed` before the engine exists.
6. UNC text is refused before resolve. A symlink or detected reparse point is refused even when its target is inside the folder.

## Unresolved

- Windows junctions were not created or tested here.
- This review did not launch the window, so the real Windows file dialog was not observed.
- Passing unit tests does not make the package safe for a teacher or for production.

Teacher trial: NOT AUTHORIZED.
Production: NOT APPROVED.
