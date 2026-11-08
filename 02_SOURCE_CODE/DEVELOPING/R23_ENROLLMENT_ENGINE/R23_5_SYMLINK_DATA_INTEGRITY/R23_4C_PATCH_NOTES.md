# R23.4C patch notes

Separate package: `R23_4C_TARGETED_REMEDIATION`.
Original R23.4A and R23.4B packages were not overwritten.

## Changed

- `src/teacher_trial.py`
  - `_remove_attempt_file()` removes only the photo or staging file created by the failed attempt.
- `src/development_launcher.py`
  - legacy methods no longer call `IdentityEngine`.
- `src/path_guard.py`
  - a failed Windows reparse check raises `IdentityError` instead of returning `False`.
- `tests/test_r23_4c_remediation.py` is new.
- `STOP.txt` says not to launch this package.

## Not changed

- `src/identity_engine.py`
- identity allocation and identity-history rules
- production files under `D:\SHRI_JAI_SHRI_RAM\project_panels`
- existing path allowlists and writer blocks
