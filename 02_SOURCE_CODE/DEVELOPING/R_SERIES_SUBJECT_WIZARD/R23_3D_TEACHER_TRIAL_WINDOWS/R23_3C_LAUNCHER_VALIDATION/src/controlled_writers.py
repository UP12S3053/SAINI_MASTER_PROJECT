# -*- coding: utf-8 -*-
"""Development entry points that replace identity-creating writers.

The baseline MAIN_ASSISTANT.py is not edited. Production call sites remain
outside this entry point until a separate production approval.
"""

from identity_engine import IdentityError

WRITER_CONTROL = {
    "step1_smart_rename": "blocked_id_allocator",
    "step3_copy_to_library": "blocked_flat_photo_writer",
    "step4_update_photo_db": "blocked_id_allocator",
    "step6_data_merge": "blocked_identity_field_writer",
    "step7_sync_photos": "blocked_flat_photo_overwrite",
    "step7b_update_photo_path": "blocked_photo_path_writer",
    "step_reassign_mixed": "blocked_id_reassignment",
    "write_enroll_to_local_xlsx": "blocked_without_engine_result",
    "stepE_enroll_from_sheet": "blocked_id_allocator",
    "_write_uids_to_school_google_sheet": "blocked_without_engine_result",
    "write_by_name": "not_an_identity_api",
    "update_student_excel": "blocked_identity_field_writer",
    "write_school_csv": "blocked_without_engine_result",
    "_save_edit": "explicit_correction_only",
    "_delete": "not_exposed",
}


class IdentityBypassError(IdentityError):
    pass


def _visible(engine, record):
    return engine.teacher_view(record)


def legacy_next_official_uid(*_args, **_kwargs):
    raise IdentityBypassError("legacy_allocator_blocked")


def enroll(engine, school, session, class_name, roll, student_name, father_name):
    return _visible(engine, engine.create_student(school, session, class_name, roll, student_name, father_name))


def promote(engine, school, permanent_key, session, new_class, new_roll):
    return _visible(engine, engine.promote(school, permanent_key, session, new_class, new_roll))


def change_roll(engine, school, permanent_key, session, new_roll):
    return _visible(engine, engine.change_roll(school, permanent_key, session, new_roll))


def correct_name(engine, school, permanent_key, session, student_name=None, father_name=None):
    return _visible(engine, engine.correct_name(school, permanent_key, session, student_name, father_name))


def reenter(engine, school, session, class_name, roll, student_name, father_name):
    return _visible(engine, engine.reenter(school, session, class_name, roll, student_name, father_name))


def assign_photo(engine, school, session, visible_id, source_path):
    return _visible(engine, engine.assign_photo(school, session, visible_id, source_path))
