# Patch changelog

- Added `subject_enrollments` as an additive schema migration.
- Added validation for class, subject, board, content type, and template policy.
- Added draft-only wizard route for a separately generated development app copy.
- Added CSRF token check on the wizard POST route.
- Added a non-overwriting `master_template.json` scaffold.
- Added backup-first migration with integrity check and legacy question-count guard.
- Added unit tests for draft state, duplicate prevention, input validation, scaffold non-overwrite, and LKG Maths row preservation.
- Original project files are read-only inputs to the patch installer.
