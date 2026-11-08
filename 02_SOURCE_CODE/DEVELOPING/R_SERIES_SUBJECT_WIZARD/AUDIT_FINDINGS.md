# Findings from the supplied SAINI_TEACHER_TRIAL.zip

Observed in the uploaded archive:
- Main trial app: `app_phase2_shortlisting_v2_trial_secure.py`.
- Database: `paper_bank.db` (SQLite).
- Board `HR` exists as active board id 1.
- Existing question counts include LKG/MATH = 66, LKG/ENGLISH = 3, III/MATH = 3; total questions = 72.
- No `UKG`/`ENGLISH` question rows were present in the supplied database.
- The current Paper Setter HTML has hardcoded class and subject options.
- `worksheet_resizer.py` resizes images only; it does not enroll subjects or add question records.

Patch design:
- Separate development copy only.
- Additive table `subject_enrollments`; existing questions, patterns, selections and history tables are not altered.
- Draft-only enrollment; `activated=0` and no question records inserted.
- Duplicate enrollment is rejected by database uniqueness constraints.
- A separate master-template metadata scaffold is created without overwriting existing metadata.
- Migration first creates a timestamped backup and checks SQLite integrity.
- Migration checks legacy question row count before and after.

Validation performed in the build environment:
- Python compilation checks passed for patch modules and generated development app.
- 5/5 core unit tests passed.
- Migration test passed on an isolated copy of the uploaded database; 72 legacy question rows remained unchanged.
- HTTP/browser-route integration test could not run in this build environment because Flask is not installed here. Run it in the user's environment where the existing trial app dependencies are installed.
