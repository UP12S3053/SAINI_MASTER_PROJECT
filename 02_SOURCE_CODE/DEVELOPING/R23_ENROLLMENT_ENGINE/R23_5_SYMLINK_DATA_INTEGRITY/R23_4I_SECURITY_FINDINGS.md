# R23.4I security findings

Baseline: `R23_4H_CROSS_PROCESS_PATCH`, copied and not overwritten.
R23.4A through R23.4H were not modified. `identity_engine.py` was not modified.
SHA256 remains `e7d9b3626986e5aa287480ba9de5f2bb5d0d9efdbdf81ee9b9eaf633490910d2`.
The GUI and BAT were not launched. Only synthetic dummy files were used.

## Defect

`linked` was set only after `assign_photo()` returned. If that call committed `photo_path` and then raised `OSError` or `RuntimeError`, the flag stayed false. Cleanup then deleted the committed photo and left the database row.

## Repair

After an exception from `assign_photo()`, and before any file delete, the attempt reads the current row by school, session, and visible ID. The cross-process photo lock is still held.

If that row's `photo_path` points at this target and the file bytes match the payload, the row and photo are kept.
If the database has a committed path but the file is missing, different, or not this target, the result is `photo_reconcile_failed`. Nothing is deleted.
If the database has no committed photo, only this attempt's unlinked new row and unlinked files can be cleaned. A pre-existing student is not deleted.
An exception from `create_student()`, such as a duplicate roll, is not treated as a committed photo of this attempt.

## Still unverified

The live Windows junction was not created on this Linux runner. Two tests still skip with status UNVERIFIED. Those skips are not passes.

Final status: PATCH PREPARED.
Teacher trial: NOT AUTHORIZED.
Production: NOT APPROVED.
