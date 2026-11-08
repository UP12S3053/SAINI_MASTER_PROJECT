# R23.4F security findings

Baseline: `R23_4E_WINDOWS_JUNCTION_VERIFICATION`, copied and not overwritten.
R23.4A through R23.4E were not modified. `identity_engine.py` was not modified.
SHA256 remains `e7d9b3626986e5aa287480ba9de5f2bb5d0d9efdbdf81ee9b9eaf633490910d2`.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect 1 — photo I/O rollback

`TeacherTrial._one()` previously caught only `IdentityError` around photo assignment.
An `OSError` skipped cleanup, so a new student row could remain without a photo.

The attempt now rolls back that new row when photo assignment raises `OSError` or any other exception.
Only a row created by the current attempt, and only while its photo path is empty, is removed.
A pre-existing student is not removed.
A file is removed only when this attempt created it, it is a regular file inside `PHOTO_LIBRARY`, and its bytes still match the source payload.
If those checks cannot be proven, the file is left unchanged.
`OSError` becomes the safe result `photo_io_failed`. The result does not include the exception text or `permanent_key`.
Any other unexpected exception is rolled back and then raised again. It is not turned into a success.

## Defect 2 — junction cleanup

`remove_directory_junction()` now reads the `rmdir` return code.
A non-zero code, or a path that still exists, raises `JunctionCleanupError`.
That error is not a subclass of `JunctionUnavailable`, so the test fails instead of skipping.
The remover never uses a recursive delete. A real directory is refused. A symlink removal does not delete the target.

## Still unverified

The live Windows junction was not created on this Linux runner. Two existing tests still skip with status UNVERIFIED. Those skips are not passes.
Direct `IdentityEngine.assign_photo()` can still delete a staging file. The teacher path does not use that behavior for a file that already existed before the attempt.

Final status: PATCH PREPARED.
Teacher trial: NOT AUTHORIZED.
Production: NOT APPROVED.
