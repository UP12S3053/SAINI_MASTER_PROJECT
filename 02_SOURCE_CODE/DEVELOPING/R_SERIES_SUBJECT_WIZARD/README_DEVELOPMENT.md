# SAINI Subject Enrollment Wizard — DEVELOPMENT-only patch

## Scope
- Adds a separate authenticated `/admin/subjects` page to a new DEVELOPMENT copy of the trial app.
- Target enrollment: board `HR`, class `UKG`, subject `ENGLISH`, code `UKG-ENGLISH`.
- Content type defaults to worksheet images; template policy defaults to a separate master template.
- Enrollments are created only as `DRAFT`, `activated=0`. No questions or production records are created.
- The original app scripts and original `paper_bank.db` are not edited.
- The patch does not auto-activate the subject and does not change the existing question dropdown behavior.

## 1. Extract project ZIP
Extract `SAINI_TEACHER_TRIAL.zip` into a folder, for example:
`D:\SAINI_TEACHER_TRIAL`

Check that this folder contains `app_phase2_shortlisting_v2_trial_secure.py` and `paper_bank.db`.

## 2. Extract this patch
Extract this patch ZIP somewhere separate, e.g. `D:\SAINI_SUBJECT_WIZARD_PATCH`.

## 3. Create isolated DEVELOPMENT copy
From CMD:
```bat
cd /d D:\SAINI_SUBJECT_WIZARD_PATCH
python apply_development_patch.py --project-root D:\SAINI_TEACHER_TRIAL
```
This creates `D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD`. It refuses to overwrite an existing folder. If it already exists, stop and inspect it; do not delete it automatically.

## 4. Run tests first
```bat
cd /d D:\SAINI_SUBJECT_WIZARD_PATCH
python -m unittest discover -s tests -v
```

## 5. Run backup-first migration against DEVELOPMENT DB only
```bat
python migrate_subject_enrollment.py --db "D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\paper_bank.db" --development-root "D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD"
```
The migration makes a timestamped DB backup in the DEVELOPMENT `backups` folder, verifies the backup integrity, and adds only the `subject_enrollments` table/index. It checks that the legacy `questions` count is unchanged.

## 6. Start the DEVELOPMENT app
Set a trial password and session secret in the same CMD window. Use your own private values; do not put them in this patch or share them:
```bat
set SAINI_TRIAL_PASSWORD=YOUR_PRIVATE_TRIAL_PASSWORD
set SAINI_SESSION_SECRET=YOUR_PRIVATE_RANDOM_SESSION_SECRET
cd /d D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD
python app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py
```
Open `http://127.0.0.1:5001`, log in, then choose **Subject Enrollment Wizard (DEVELOPMENT)**.

## 7. Create the draft
Select HR, UKG, ENGLISH, Worksheet images, Separate master template, then submit. Expected result: `UKG-ENGLISH` appears as `DRAFT`, `Activated NO`, with a separate metadata scaffold under `subject_templates\UKG-ENGLISH\master_template.json`.

## 8. Validation before any activation
1. Confirm the wizard shows `DRAFT`, `Activated NO`.
2. Confirm the existing LKG Maths question count remains 66.
3. Add only approved UKG English image assets in a controlled development workflow; verify each image and metadata before adding question records.
4. Generate a test paper in DEVELOPMENT and inspect question selection, page layout, numbering, marks and answer space.
5. Run regression checks for LKG Maths.
6. Activation is deliberately outside this patch and requires a separate reviewed change and explicit approval.

## Rollback
Stop the development app. Restore the DEVELOPMENT database from the timestamped backup in `DEVELOPMENT_SUBJECT_WIZARD\backups`. Do not restore or copy this database over any active/production database. The original project files are unchanged by the installer.

## Limitations / important findings
- Existing class and subject controls in the current app are hardcoded; this patch adds a separate wizard but intentionally does not rewrite those existing controls.
- Current database has HR board code; `UKG-ENGLISH` has zero question records in the supplied DB, so the wizard enrolls metadata only. It does not fabricate questions or images.
- Existing `worksheet_resizer.py` only resizes images; it does not enroll subjects.
