# R23.4D patch notes

Separate package: `R23_4D_TARGETED_PATCH`.

## Changed

- `src/teacher_trial.py`
  - A pre-existing staging file now raises `photo_staging_exists` before `create_student()`.
- `tests/test_r23_4d_staging.py` is new.
- `STOP.txt` says not to launch this package.

## Not changed

- `src/identity_engine.py`
- R23.4A, R23.4B, and R23.4C
- existing path allowlists, writer blocks, and target-photo refusal
- production files
