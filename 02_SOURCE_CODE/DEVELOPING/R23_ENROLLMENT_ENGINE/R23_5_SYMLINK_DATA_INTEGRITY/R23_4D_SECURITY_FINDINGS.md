# R23.4D security findings

R23.4A, R23.4B, and R23.4C were not overwritten. `identity_engine.py` was not edited.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect

`identity_engine.py` still contains this unchanged line inside `assign_photo()`:

```
if staging.exists() and not target.exists():
    staging.unlink()
```

R23.4C recorded `staging_existed` but still called `assign_photo()`. A staging file left by an earlier interrupted attempt could therefore be deleted.

## Repair

`teacher_trial.py` now checks the staging path before `create_student()`. If that file or symlink exists, enrollment raises `photo_staging_exists`. The file is not deleted, overwritten, renamed, or reused. No new student row is created, and `assign_photo()` is not called.

## Unresolved

Windows junction protection remains UNVERIFIED. This Linux runner cannot create a Windows junction. Passing these tests does not authorize a teacher trial and does not approve production.
