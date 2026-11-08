# R23.4H security findings

Baseline: `R23_4G_OWNERSHIP_PATCH`, copied and not overwritten.
R23.4A through R23.4G were not modified. `identity_engine.py` was not modified.
SHA256 remains `e7d9b3626986e5aa287480ba9de5f2bb5d0d9efdbdf81ee9b9eaf633490910d2`.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect A — cross-process file ownership

A `threading.Lock` only covers threads in one process. Two processes could see the same photo bytes and one could delete the other's staging file.

Each student photo now has an exclusive lock file under the trial workspace. It is created with `O_EXCL` and records the owner pid, a private token, and the process start token. A lock is taken over only when that owner is dead or the pid was reused. Recovery removes the lock file only. It never removes a photo or a staging file.

The lock covers the existence check, photo assignment, database linking, and cleanup. Matching bytes are not ownership. A file is removed only when this attempt created it, the database link is not committed, and the bytes still match. A matching file owned by someone else is left untouched.

## Defect B — cleanup after a committed photo link

If photo assignment had already committed `photo_path` and a later `teacher_view()` or `_public_result()` failed, the old handler could delete the photo while correctly refusing to delete the row.

The attempt now records that the link was committed only after the database path points to a real file with the expected bytes. After that point, presentation failures do not delete the row or the photo. They return `photo_saved` and do not include the exception text or the permanent key.

## Still unverified

The live Windows junction was not created on this Linux runner. Two tests still skip with status UNVERIFIED. Those skips are not passes.

Final status: PATCH PREPARED.
Teacher trial: NOT AUTHORIZED.
Production: NOT APPROVED.
