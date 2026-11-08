# R23.4G security findings

Baseline: `R23_4F_TARGETED_SECURITY_PATCH`, copied and not overwritten.
R23.4A through R23.4F were not modified. `identity_engine.py` was not modified.
SHA256 remains `e7d9b3626986e5aa287480ba9de5f2bb5d0d9efdbdf81ee9b9eaf633490910d2`.
The GUI and BAT were not launched. Only synthetic dummy records were used.

## Defect

`_drop_new_without_photo()` treated `count_identities() != before` as proof that the returned student belonged to this attempt.
`create_student()` can return an existing row. Another connection can insert a different row before rollback. The count then changes, and the old code could delete the existing student's permanent key.

## Repair

The global count is no longer used.
Before `create_student()`, the attempt records the exact permanent-key set and this connection's `total_changes` inside the engine lock.
This attempt owns the row only when both are true: this connection's change count increased by exactly two, and the returned key was not in that set.
Anything else is uncertain. Uncertain ownership deletes nothing.
The delete itself runs inside `BEGIN IMMEDIATE` and removes one current row only when its photo is still empty and its visible ID matches this attempt.
An in-process enrollment lock stops two trial attempts from sharing that proof.
Photo and staging ownership checks from R23.4F are unchanged.
An `OSError` during photo assignment still rolls back only an owned new row and still returns `photo_io_failed` without the exception text.

## Still unverified

The live Windows junction was not created on this Linux runner. Two tests still skip with status UNVERIFIED. Those skips are not passes.

Final status: PATCH PREPARED.
Teacher trial: NOT AUTHORIZED.
Production: NOT APPROVED.
