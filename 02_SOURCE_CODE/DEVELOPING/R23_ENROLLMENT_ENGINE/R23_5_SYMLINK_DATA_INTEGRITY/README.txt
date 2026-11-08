R23.5 SYMLINK AND DATA INTEGRITY
final_status=PATCH PREPARED
teacher_trial=NOT AUTHORIZED
production=NOT APPROVED
do_not_launch=YES

STOP
Teacher Trial is NOT AUTHORIZED.
Production is NOT APPROVED.
Do not run Open_Enrollment.bat, open_launcher.py, or the enrollment GUI.

WHAT CHANGED
R23.4N was copied and not overwritten.
No production source file was changed.
identity_engine.py and teacher_trial.py are unchanged.
New tests use a real Windows directory junction for two checks that the
symlink tests could not reach on this PC:
- removing the junction does not delete the outside target
- a failed rmdir stays a failure, not a skip or a pass

WHAT DID NOT CHANGE
The ten WinError 1314 symlink skips are still skips.
A file symlink still cannot be created on this PC without the missing privilege.
Those file-symlink assertions stay unverified. They are not passed.
A junction is not a symlink.

Linux cannot run the new junction checks. Those two tests skip here as UNVERIFIED.
That skip is not a pass. The older Linux symlink checks still run their assertions.
