# -*- coding: utf-8 -*-
"""Active R23.1 enrollment paths.

Identity creation and reassignment call the Student Identity Engine.
The preserved baseline is not called from this module.
write_by_name remains a generic header writer and is not used to mint a student ID.
"""

from pathlib import Path

from identity_engine import IdentityError


def _teacher(engine, record):
    visible = engine.teacher_view(record)
    if "permanent_key" in visible:
        raise IdentityError("key_leak_blocked")
    return visible


def _confirmed(engine, school, session, visible_student_id):
    return engine._current_visible(school, session, visible_student_id)


def write_by_name(sheet, row_idx, hmap, data, template_row=2):
    """Unchanged generic writer. It does not create or validate an identity."""
    for logical, value in data.items():
        column = hmap.get(logical)
        if not column:
            continue
        sheet.setdefault(row_idx, {})[column] = value


def stepE_enroll_from_sheet(engine, school, session, class_name, roll, student_name, father_name, photo_source=None):
    created = engine.create_student(school, session, class_name, roll, student_name, father_name)
    if photo_source is not None:
        created = engine.assign_photo(school, session, created["visible_id"], photo_source)
    return _teacher(engine, created)


def step1_smart_rename(engine, school, session, class_name, roll, student_name, father_name, source_photo):
    """The old highest-number rename is not used. The engine issues the ID first."""
    created = engine.create_student(school, session, class_name, roll, student_name, father_name)
    saved = engine.assign_photo(school, session, created["visible_id"], source_photo)
    return _teacher(engine, saved)


def step4_update_photo_db(engine, school, session, visible_student_id, source_photo):
    """A filename does not create a student. The engine must already have issued the ID."""
    _confirmed(engine, school, session, visible_student_id)
    saved = engine.assign_photo(school, session, visible_student_id, source_photo)
    return _teacher(engine, saved)


def step6_data_merge(engine, school, session, visible_student_id, student_name=None, father_name=None):
    row = _confirmed(engine, school, session, visible_student_id)
    corrected = engine.correct_name(
        school,
        row["permanent_key"],
        session,
        student_name=student_name,
        father_name=father_name,
    )
    return _teacher(engine, corrected)


def step7b_update_photo_path(engine, school, session, visible_student_id, requested_path):
    row = _confirmed(engine, school, session, visible_student_id)
    recorded = row["photo_path"] or ""
    if not recorded:
        raise IdentityError("photo_not_recorded")
    if str(Path(requested_path)) != recorded:
        raise IdentityError("flat_path_refused")
    return _teacher(engine, engine._public(row))


def step_reassign_mixed(engine, school, session, visible_student_id, new_class, new_roll):
    row = _confirmed(engine, school, session, visible_student_id)
    old_photo = Path(row["photo_path"]) if row["photo_path"] else None
    old_bytes = old_photo.read_bytes() if old_photo and old_photo.is_file() else None
    if new_class == row["class_name"]:
        moved = engine.change_roll(school, row["permanent_key"], session, new_roll)
    else:
        moved = engine.promote(school, row["permanent_key"], session, new_class, new_roll)
    if old_photo is not None and old_bytes is not None:
        if not old_photo.is_file() or old_photo.read_bytes() != old_bytes:
            raise IdentityError("existing_photo_changed")
    return _teacher(engine, moved)


def write_enroll_to_local_xlsx(engine, school, session, visible_student_id):
    row = _confirmed(engine, school, session, visible_student_id)
    return {
        "school_code": row["school_code"],
        "student_unique_id": row["visible_id"],
        "student_name": row["student_name"],
        "father_name": row["father_name"],
        "class": row["class_name"],
        "roll_number": row["roll_number"],
        "STUDENT_PHOTO_PATH": row["photo_path"] or "",
    }


def _write_uids_to_school_google_sheet(engine, school, session, visible_student_id):
    row = write_enroll_to_local_xlsx(engine, school, session, visible_student_id)
    return {"sheet": "STUDENTS", "student_unique_id": row["student_unique_id"], "network": "not_used"}


def step3_copy_to_library(engine, school, session, visible_student_id, source_photo):
    return step4_update_photo_db(engine, school, session, visible_student_id, source_photo)


def step7_sync_photos(engine, school, session, visible_student_id, source_photo):
    return step4_update_photo_db(engine, school, session, visible_student_id, source_photo)


def update_student_excel(engine, school, session, visible_student_id, student_name=None, father_name=None):
    return step6_data_merge(engine, school, session, visible_student_id, student_name, father_name)


def write_school_csv(engine, school, session, destination):
    return engine.export_teacher_csv(school, session, destination)


def _save_edit(engine, school, session, visible_student_id, student_name=None, father_name=None, new_class=None):
    if new_class is not None:
        raise IdentityError("explicit_operation_required")
    return step6_data_merge(engine, school, session, visible_student_id, student_name, father_name)


def _delete(*_args, **_kwargs):
    raise IdentityError("delete_not_exposed")


ACTIVE_IDENTITY_WRITERS = (
    "step1_smart_rename",
    "step4_update_photo_db",
    "step6_data_merge",
    "step7b_update_photo_path",
    "step_reassign_mixed",
    "write_enroll_to_local_xlsx",
    "stepE_enroll_from_sheet",
    "_write_uids_to_school_google_sheet",
    "step3_copy_to_library",
    "step7_sync_photos",
    "update_student_excel",
    "write_school_csv",
    "_save_edit",
)
