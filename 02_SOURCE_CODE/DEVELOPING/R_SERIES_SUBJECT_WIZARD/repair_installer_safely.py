# -*- coding: utf-8 -*-
"""Fail-closed repair for apply_development_patch_corrected.py.

Reads the original SAINI Teacher Trial app and database only to hash them.
Does not run the installer. Does not migrate. Does not create a development copy.
Rewrites only the working installer copy, and only after every baseline hash matches.
"""

from __future__ import annotations

import ast
import hashlib
import os
import py_compile
import re
import sys
import traceback

PATCH_DIR = r"D:\SAINI_SUBJECT_WIZARD_PATCH"
TRIAL_DIR = r"D:\SAINI_TEACHER_TRIAL"
BACKUP_DIR = os.path.join(PATCH_DIR, "BACKUP_BEFORE_FIX")

WORKING_COPY = os.path.join(PATCH_DIR, "apply_development_patch_corrected.py")
ORIGINAL_INSTALLER = os.path.join(PATCH_DIR, "apply_development_patch.py")
INSTALLER_BACKUP = os.path.join(BACKUP_DIR, "apply_development_patch.py")
LINK_BACKUP = os.path.join(
    BACKUP_DIR, "apply_development_patch_corrected_before_link_fix.py"
)
MIGRATE_BACKUP = os.path.join(BACKUP_DIR, "migrate_subject_enrollment.py")
ORIGINAL_APP = os.path.join(
    TRIAL_DIR, "app_phase2_shortlisting_v2_trial_secure.py"
)
ORIGINAL_DB = os.path.join(TRIAL_DIR, "paper_bank.db")
DEV_DEST = os.path.join(TRIAL_DIR, "DEVELOPMENT_SUBJECT_WIZARD")

HASH_INSTALLER = (
    "9d425601c725176ef0df8449779203f18ba7d57f9e4991b116a254a7641cf75d"
)
HASH_MIGRATE_BACKUP = (
    "e11a2b6e2d72fe9802bb74cd0597d4f976f155f4af35b49e5771ed311e43bf21"
)
HASH_APP = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
HASH_DB = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"

PAPER_SETTER_MARK = "Paper Setter"
ROUTE_TOKEN = "subject_enrollment_wizard"
COPY_NAMES = {"copy", "copy2", "copyfile"}
BODY_FIELDS = {"body", "orelse", "finalbody", "handlers"}
RESERVED_NAMES = (
    "_saini_paper_setter_anchor",
    "_saini_anchor_count",
    "_saini_home_count",
)


class RepairError(Exception):
    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        message = reason if not detail else reason + "\n" + detail
        super().__init__(message)


class DbPath:
    pass


class Rec:
    def __init__(self, stmt, body, index, env, try_stack):
        self.stmt = stmt
        self.body = body
        self.index = index
        self.env = env
        self.try_stack = try_stack


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def newline_of(src):
    return "\r\n" if "\r\n" in src else "\n"


def split_kept(src):
    return src.splitlines(keepends=True)


def line_offsets(src, start_line, end_line):
    lines = split_kept(src)
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise RepairError(
            "LINE_SPAN_OUT_OF_RANGE",
            "start=%s end=%s lines=%s" % (start_line, end_line, len(lines)),
        )
    start = sum(len(lines[i]) for i in range(start_line - 1))
    end = sum(len(lines[i]) for i in range(end_line))
    return start, end


def indent_at(src, lineno):
    lines = src.splitlines()
    line = lines[lineno - 1]
    return line[: len(line) - len(line.lstrip(" \t"))]


def snippet(src, lineno, radius=4):
    lines = src.splitlines()
    start = max(1, lineno - radius)
    end = min(len(lines), lineno + radius)
    out = []
    for number in range(start, end + 1):
        out.append("%s: %s" % (number, lines[number - 1]))
    return "\n".join(out)


def statement_span_is_safe(src, stmt):
    if stmt.end_lineno is None or stmt.end_col_offset is None:
        return False
    lines = src.splitlines()
    first = lines[stmt.lineno - 1]
    if first[: stmt.col_offset].strip():
        return False
    trailing = lines[stmt.end_lineno - 1][stmt.end_col_offset :].strip()
    if trailing and not trailing.startswith("#"):
        return False
    return True


def is_copy_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in COPY_NAMES
    if isinstance(func, ast.Name):
        return func.id in COPY_NAMES
    return False


def is_join_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "join"
    if isinstance(func, ast.Name):
        return func.id == "join"
    return False


def string_is_db(value):
    if not isinstance(value, str):
        return False
    norm = value.replace("\\", "/")
    return norm == "paper_bank.db" or norm.endswith("/paper_bank.db")


def expr_mentions_db(node, env):
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return string_is_db(node.value)
    if isinstance(node, ast.Name):
        value = env.get(node.id, None)
        if value is DbPath:
            return True
        if isinstance(value, str):
            return string_is_db(value)
        if isinstance(value, (list, tuple)):
            return any(item == "paper_bank.db" or item is DbPath for item in value)
        return False
    if isinstance(node, ast.BinOp):
        return expr_mentions_db(node.left, env) or expr_mentions_db(node.right, env)
    if isinstance(node, (ast.List, ast.Tuple)):
        return any(expr_mentions_db(elt, env) for elt in node.elts)
    if isinstance(node, ast.Call):
        args = list(node.args) + [kw.value for kw in node.keywords]
        return any(expr_mentions_db(arg, env) for arg in args)
    if isinstance(node, ast.Attribute):
        return expr_mentions_db(node.value, env)
    return False


def eval_string(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        value = env.get(node.id, None)
        return value if isinstance(value, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = eval_string(node.left, env)
        right = eval_string(node.right, env)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    return None


def eval_string_list(node, env):
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    items = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            items.append(elt.value)
            continue
        if isinstance(elt, ast.Name) and isinstance(env.get(elt.id, None), str):
            items.append(env[elt.id])
            continue
        if expr_mentions_db(elt, env):
            items.append("paper_bank.db")
            continue
        return None
    return items


def update_env(stmt, env):
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return
    seq = eval_string_list(stmt.value, env)
    if seq is not None:
        env[target.id] = seq
        return
    text = eval_string(stmt.value, env)
    if isinstance(text, str):
        env[target.id] = text
        return
    if expr_mentions_db(stmt.value, env):
        env[target.id] = DbPath


def is_home_test(test):
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotIn)
        and isinstance(test.left, ast.Name)
        and test.left.id == "HOME_LINK"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Name)
        and test.comparators[0].id == "text"
    )


def body_is_text_replace(stmt):
    call = None
    if isinstance(stmt, ast.Assign):
        if not (
            len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and stmt.targets[0].id == "text"
        ):
            return False
        call = stmt.value
    elif isinstance(stmt, ast.Expr):
        call = stmt.value
    else:
        return False
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "replace"
        and isinstance(func.value, ast.Name)
        and func.value.id == "text"
    )


def copy_call_of(stmt):
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return stmt.value
    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
        return stmt.value
    return None


def stmt_is_explicit_db_copy(stmt, env):
    call = copy_call_of(stmt)
    if call is None or not is_copy_call(call):
        return False
    args = list(call.args) + [kw.value for kw in call.keywords]
    return any(expr_mentions_db(arg, env) for arg in args)


def iter_contains_db(node, env):
    if isinstance(node, ast.Name):
        value = env.get(node.id, None)
        return isinstance(value, (list, tuple)) and any(
            item == "paper_bank.db" for item in value
        )
    seq = eval_string_list(node, env)
    return isinstance(seq, list) and "paper_bank.db" in seq


def for_covers_db(stmt, env):
    if not isinstance(stmt, ast.For):
        return False
    if not iter_contains_db(stmt.iter, env):
        return False
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call) and is_copy_call(node):
            return True
    return False


def note_marker(stmt, env, found):
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return
    if "MARKER" not in target.id.upper():
        return
    value = eval_string(stmt.value, env)
    if isinstance(value, str) and value.strip():
        found.append((target.id, value, stmt))


def walk_children(stmt, env, try_stack, recs, state):
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        walk_body(stmt.body, dict(env), try_stack, recs, state)
        return
    if isinstance(stmt, (ast.For, ast.While, ast.With)):
        walk_body(stmt.body, dict(env), try_stack, recs, state)
        walk_body(getattr(stmt, "orelse", []), dict(env), try_stack, recs, state)
        return
    if isinstance(stmt, ast.If):
        walk_body(stmt.body, dict(env), try_stack, recs, state)
        walk_body(stmt.orelse, dict(env), try_stack, recs, state)
        return
    if isinstance(stmt, ast.Try):
        stacked = try_stack + [stmt]
        walk_body(stmt.body, dict(env), stacked, recs, state)
        for handler in stmt.handlers:
            walk_body(handler.body, dict(env), stacked, recs, state)
        walk_body(stmt.orelse, dict(env), stacked, recs, state)
        walk_body(stmt.finalbody, dict(env), stacked, recs, state)


def walk_body(body, env, try_stack, recs, state):
    for index, stmt in enumerate(body):
        recs.append(Rec(stmt, body, index, dict(env), list(try_stack)))
        if for_covers_db(stmt, env):
            state["loop_covers"] = True
        if stmt_is_explicit_db_copy(stmt, env):
            state["explicit"].append(stmt)
        if isinstance(stmt, ast.If) and is_home_test(stmt.test):
            state["home_ifs"].append((stmt, dict(env), list(try_stack)))
        note_marker(stmt, env, state["markers"])
        child_env = dict(env)
        update_env(stmt, child_env)
        walk_children(stmt, child_env, try_stack, recs, state)
        update_env(stmt, env)


def analyze(src):
    tree = ast.parse(src)
    recs = []
    state = {
        "loop_covers": False,
        "explicit": [],
        "home_ifs": [],
        "markers": [],
    }
    walk_body(tree.body, {}, [], recs, state)
    state["recs"] = recs
    state["tree"] = tree
    return state


def shallow_mentions(stmt, name):
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return False
    nodes = []
    for field, value in ast.iter_fields(stmt):
        if field in BODY_FIELDS:
            continue
        if isinstance(value, list):
            nodes.extend(item for item in value if isinstance(item, ast.AST))
        elif isinstance(value, ast.AST):
            nodes.append(value)
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == name:
                return True
    return False


def assigns_text(stmt):
    found = {"yes": False}

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            return

        def visit_AsyncFunctionDef(self, node):
            return

        def visit_Lambda(self, node):
            return

        def visit_ClassDef(self, node):
            return

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "text":
                    found["yes"] = True
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "text":
                found["yes"] = True
            self.generic_visit(node)

    Visitor().visit(stmt)
    return found["yes"]


def text_is_ready(body, index):
    for prior in body[:index]:
        if assigns_text(prior):
            return True
    return False


def handler_swallows_systemexit(handler):
    kind = handler.type
    if kind is None:
        return True
    names = []
    if isinstance(kind, ast.Name):
        names.append(kind.id)
    elif isinstance(kind, ast.Tuple):
        for elt in kind.elts:
            if isinstance(elt, ast.Name):
                names.append(elt.id)
    return "BaseException" in names


def anchor_from_if(if_node, env):
    stmt = if_node.body[0]
    call = stmt.value if isinstance(stmt, (ast.Assign, ast.Expr)) else None
    if not isinstance(call, ast.Call) or not call.args:
        return []
    value = eval_string(call.args[0], env)
    if isinstance(value, str) and PAPER_SETTER_MARK in value:
        return [value]
    return []


def lines_of_db(src):
    rows = []
    for number, line in enumerate(src.splitlines(), 1):
        if "paper_bank.db" in line or "HOME_LINK" in line or "MARKER" in line.upper():
            rows.append("%s: %s" % (number, line))
    return "\n".join(rows[:80])


def choose_db_statement(state, src):
    explicit = sorted(state["explicit"], key=lambda stmt: (stmt.lineno, stmt.col_offset))
    loop_covers = state["loop_covers"]
    if loop_covers and len(explicit) == 1:
        return explicit[0]
    if not loop_covers and len(explicit) == 2:
        return explicit[1]
    detail = lines_of_db(src)
    raise RepairError(
        "DB_COPY_NOT_UNIQUE",
        "loop_covers=%s explicit_copies=%s\n%s"
        % (loop_covers, len(explicit), detail),
    )


def choose_home_if(state, src):
    found = state["home_ifs"]
    if len(found) != 1:
        detail = lines_of_db(src)
        raise RepairError(
            "HOME_LINK_BLOCK_NOT_UNIQUE",
            "matches=%s\n%s" % (len(found), detail),
        )
    if_node, env, try_stack = found[0]
    for tri in try_stack:
        for handler in tri.handlers:
            if handler_swallows_systemexit(handler):
                raise RepairError(
                    "HOME_LINK_INSIDE_BARE_EXCEPT",
                    snippet(src, if_node.lineno),
                )
    if if_node.orelse:
        raise RepairError(
            "HOME_LINK_HAS_ELSE",
            snippet(src, if_node.lineno),
        )
    if len(if_node.body) != 1 or not body_is_text_replace(if_node.body[0]):
        segment = ast.get_source_segment(src, if_node) or ""
        raise RepairError(
            "HOME_LINK_BODY_UNEXPECTED",
            segment[:2000],
        )
    anchors = anchor_from_if(if_node, env)
    if len(anchors) != 1:
        segment = ast.get_source_segment(src, if_node) or ""
        raise RepairError(
            "PAPER_SETTER_ANCHOR_NOT_UNIQUE",
            "anchors=%s\n%s" % (len(anchors), segment[:2000]),
        )
    if not statement_span_is_safe(src, if_node):
        raise RepairError(
            "HOME_LINK_SPAN_UNSAFE",
            snippet(src, if_node.lineno),
        )
    return if_node, anchors[0]


def choose_marker(state, src):
    markers = state["markers"]
    if len(markers) != 1:
        detail = lines_of_db(src)
        raise RepairError(
            "STARTUP_MARKER_NOT_UNIQUE",
            "matches=%s\n%s" % (len(markers), detail),
        )
    return markers[0]


def first_marker_use(recs, marker_name, src):
    uses = []
    for rec in recs:
        if shallow_mentions(rec.stmt, marker_name):
            uses.append(rec)
    if not uses:
        raise RepairError(
            "STARTUP_MARKER_UNUSED",
            snippet(src, state_line_from_recs(recs, marker_name)),
        )
    uses.sort(key=lambda rec: (rec.stmt.lineno, rec.stmt.col_offset))
    chosen = uses[0]
    if not text_is_ready(chosen.body, chosen.index):
        raise RepairError(
            "TEXT_NOT_READY_BEFORE_MARKER",
            snippet(src, chosen.stmt.lineno),
        )
    if not statement_span_is_safe(src, chosen.stmt):
        raise RepairError(
            "MARKER_USE_SPAN_UNSAFE",
            snippet(src, chosen.stmt.lineno),
        )
    return chosen


def state_line_from_recs(recs, marker_name):
    for rec in recs:
        if isinstance(rec.stmt, ast.Assign):
            for target in rec.stmt.targets:
                if isinstance(target, ast.Name) and target.id == marker_name:
                    return rec.stmt.lineno
    return 1


def ranges_conflict(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def build_home_block(src, if_node, anchor):
    nl = newline_of(src)
    base = indent_at(src, if_node.lineno)
    body_indent = indent_at(src, if_node.body[0].lineno)
    if body_indent.startswith(base) and len(body_indent) > len(base):
        step = body_indent[len(base) :]
    else:
        step = "    "
    i1 = base + step
    i2 = base + step + step
    i3 = base + step + step + step
    anchor_name = "_saini_paper_setter_anchor"
    count_name = "_saini_anchor_count"
    home_name = "_saini_home_count"
    lines = [
        "%s%s = %s" % (base, anchor_name, repr(anchor)),
        "%s%s = text.count(%s)" % (base, count_name, anchor_name),
        "%s%s = text.count(HOME_LINK)" % (base, home_name),
        "%sif %s > 1:" % (base, home_name),
        "%sraise SystemExit(" % i1,
        '%s"Home Link appears " + str(%s) + " times; refusing to continue"'
        % (i2, home_name),
        "%s)" % i1,
        "%selif %s == 0:" % (base, home_name),
        "%sif %s != 1:" % (i1, count_name),
        "%sraise SystemExit(" % i2,
        '%s"Paper Setter anchor count is " + str(%s) + ", expected 1; refusing to continue"'
        % (i3, count_name),
        "%s)" % i2,
        "%stext = text.replace(" % i1,
        "%s%s," % (i2, anchor_name),
        '%s%s + "\\n" + HOME_LINK,' % (i2, anchor_name),
        "%s1," % i2,
        "%s)" % i1,
        "%sif text.count(HOME_LINK) != 1 or text.count(%s) != 1:"
        % (i1, anchor_name),
        "%sraise SystemExit(" % i2,
        '%s"Home Link insertion verification failed; refusing to continue"' % i3,
        "%s)" % i2,
        "%selif %s != 1:" % (base, home_name),
        "%sraise SystemExit(" % i1,
        '%s"Home Link count is " + str(%s) + "; refusing to continue"'
        % (i2, home_name),
        "%s)" % i1,
    ]
    block = nl.join(lines)
    return block, nl


def build_marker_block(src, stmt, marker_name):
    nl = newline_of(src)
    base = indent_at(src, stmt.lineno)
    step = "    "
    if "\t" in base and " " not in base:
        step = "\t"
    i1 = base + step
    i2 = base + step + step
    lines = [
        "%sif text.count(%s) != 1:" % (base, marker_name),
        "%sraise SystemExit(" % i1,
        '%s"Startup marker count is " + str(text.count(%s)) + ", expected 1; refusing to continue"'
        % (i2, marker_name),
        "%s)" % i1,
        '%sif "def subject_enrollment_wizard(" in text:' % base,
        "%sraise SystemExit(" % i1,
        '%s"subject_enrollment_wizard route already exists; refusing to continue"'
        % i2,
        "%s)" % i1,
    ]
    return nl.join(lines) + nl


def apply_edits(src, edits):
    edits = sorted(edits, key=lambda item: item[0], reverse=True)
    out = src
    for start, end, text in edits:
        if start < 0 or end < start or end > len(out):
            raise RepairError(
                "EDIT_OUT_OF_RANGE",
                "start=%s end=%s length=%s" % (start, end, len(out)),
            )
        out = out[:start] + text + out[end:]
    return out


def assert_repaired(original, repaired, loop_covers):
    compile(repaired, "<repaired>", "exec")
    tree_ok = ast.parse(repaired)
    del tree_ok
    if "if HOME_LINK not in text" in repaired:
        # The old test may still appear only if repair failed to remove it.
        old = analyze(original)
        new = analyze(repaired)
        if new["home_ifs"]:
            raise RepairError("OLD_HOME_LINK_STILL_PRESENT")
    new_state = analyze(repaired)
    if new_state["home_ifs"]:
        raise RepairError("OLD_HOME_LINK_STILL_PRESENT")
    if "_saini_paper_setter_anchor" not in repaired:
        raise RepairError("HOME_LINK_REWRITE_MISSING")
    if "Startup marker count is " not in repaired:
        raise RepairError("MARKER_GUARD_MISSING")
    if "subject_enrollment_wizard route already exists" not in repaired:
        raise RepairError("ROUTE_GUARD_MISSING")
    if original.count(ROUTE_TOKEN) > repaired.count(ROUTE_TOKEN):
        raise RepairError("ROUTE_TEMPLATE_LOST")
    explicit_after = len(new_state["explicit"])
    if loop_covers:
        if explicit_after != 0:
            raise RepairError(
                "DB_COPY_STILL_DUPLICATED",
                "explicit_after=%s" % explicit_after,
            )
        if not new_state["loop_covers"]:
            raise RepairError("DB_LOOP_COPY_LOST")
    else:
        if explicit_after != 1:
            raise RepairError(
                "DB_COPY_COUNT_UNEXPECTED",
                "explicit_after=%s" % explicit_after,
            )
    if "paper_bank.db" not in repaired:
        raise RepairError("DB_REFERENCE_LOST")


def repair_source(src):
    if ROUTE_TOKEN not in src:
        raise RepairError("ROUTE_TEMPLATE_MISSING", lines_of_db(src))
    for name in RESERVED_NAMES:
        if re.search(r"\b%s\b" % name, src):
            raise RepairError("REPAIR_NAME_COLLISION", name)
    state = analyze(src)
    if_node, anchor = choose_home_if(state, src)
    copy_stmt = choose_db_statement(state, src)
    marker_name, _marker_value, _marker_stmt = choose_marker(state, src)
    use = first_marker_use(state["recs"], marker_name, src)

    home_start, home_end = line_offsets(src, if_node.lineno, if_node.end_lineno)
    copy_start, copy_end = line_offsets(src, copy_stmt.lineno, copy_stmt.end_lineno)
    insert_at, _insert_end = line_offsets(src, use.stmt.lineno, use.stmt.lineno)

    if not statement_span_is_safe(src, copy_stmt):
        raise RepairError("DB_COPY_SPAN_UNSAFE", snippet(src, copy_stmt.lineno))

    for label, start, end in (
        ("home", home_start, home_end),
        ("copy", copy_start, copy_end),
    ):
        if start <= insert_at < end:
            raise RepairError(
                "EDIT_OVERLAP",
                "%s contains the startup-marker guard point" % label,
            )
    if ranges_conflict(home_start, home_end, copy_start, copy_end):
        raise RepairError("EDIT_OVERLAP", "home link block overlaps the db copy")

    home_block, nl = build_home_block(src, if_node, anchor)
    if src[home_start:home_end].endswith("\n"):
        home_block += nl
    marker_block = build_marker_block(src, use.stmt, marker_name)

    copy_parent = None
    for rec in state["recs"]:
        if rec.stmt is copy_stmt:
            copy_parent = rec
            break
    if copy_parent is None:
        raise RepairError("DB_COPY_PARENT_MISSING")
    if len(copy_parent.body) == 1:
        indent = indent_at(src, copy_stmt.lineno)
        copy_replacement = indent + "pass"
        if src[copy_start:copy_end].endswith("\n"):
            copy_replacement += nl
    else:
        copy_replacement = ""

    repaired = apply_edits(
        src,
        [
            (home_start, home_end, home_block),
            (copy_start, copy_end, copy_replacement),
            (insert_at, insert_at, marker_block),
        ],
    )
    try:
        assert_repaired(src, repaired, state["loop_covers"])
    except SyntaxError as exc:
        raise RepairError("REPAIRED_SYNTAX_ERROR", str(exc))
    return repaired


def expected_checks():
    return [
        (ORIGINAL_APP, HASH_APP),
        (ORIGINAL_DB, HASH_DB),
        (ORIGINAL_INSTALLER, HASH_INSTALLER),
        (INSTALLER_BACKUP, HASH_INSTALLER),
        (WORKING_COPY, HASH_INSTALLER),
        (LINK_BACKUP, HASH_INSTALLER),
        (MIGRATE_BACKUP, HASH_MIGRATE_BACKUP),
    ]


def verify_hashes(checks):
    for path, expected in checks:
        if not os.path.isfile(path):
            raise RepairError("MISSING", path)
        actual = sha256_file(path)
        if actual.lower() != expected.lower():
            raise RepairError(
                "HASH_MISMATCH",
                "path=%s\nexpected=%s\nactual=%s" % (path, expected, actual),
            )


def backup_path_for_old_working():
    base = os.path.join(
        BACKUP_DIR, "apply_development_patch_corrected_before_repair.py"
    )
    if not os.path.exists(base):
        return base
    stamp = 1
    while True:
        candidate = os.path.join(
            BACKUP_DIR,
            "apply_development_patch_corrected_before_repair_%s.py" % stamp,
        )
        if not os.path.exists(candidate):
            return candidate
        stamp += 1


def execute_repair(checks=None, working_path=None, backup_dir=None):
    checks = expected_checks() if checks is None else checks
    working_path = WORKING_COPY if working_path is None else working_path
    backup_dir = BACKUP_DIR if backup_dir is None else backup_dir
    verify_hashes(checks)
    with open(working_path, "rb") as handle:
        raw = handle.read()
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RepairError("WORKING_COPY_NOT_UTF8", str(exc))
    repaired = repair_source(src)
    os.makedirs(backup_dir, exist_ok=True)
    temp_path = working_path + ".repair_tmp"
    pyc_path = working_path + ".repair_check.pyc"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(repaired.encode("utf-8"))
        py_compile.compile(temp_path, cfile=pyc_path, doraise=True)
        with open(temp_path, "rb") as handle:
            compiled = handle.read()
        if compiled != repaired.encode("utf-8"):
            raise RepairError("TEMP_MISMATCH")
        repair_source_again_blocked = False
        try:
            repair_source(repaired)
        except RepairError:
            repair_source_again_blocked = True
        if not repair_source_again_blocked:
            raise RepairError("REPAIR_WAS_IDEMPOTENT_UNEXPECTEDLY")
        pre_backup = backup_path_for_old_working() if backup_dir == BACKUP_DIR else (
            os.path.join(backup_dir, "apply_development_patch_corrected_before_repair.py")
        )
        if os.path.exists(pre_backup):
            raise RepairError("BACKUP_ALREADY_EXISTS", pre_backup)
        with open(pre_backup, "wb") as handle:
            handle.write(raw)
        if sha256_file(pre_backup) != hashlib.sha256(raw).hexdigest():
            raise RepairError("BACKUP_HASH_FAILED", pre_backup)
        os.replace(temp_path, working_path)
        temp_path = ""
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(pyc_path):
            os.remove(pyc_path)
    verify_hashes(
        [item for item in checks if os.path.normcase(item[0]) != os.path.normcase(working_path)]
    )
    new_hash = sha256_file(working_path)
    if new_hash == hashlib.sha256(raw).hexdigest():
        raise RepairError("WORKING_COPY_UNCHANGED")
    return {
        "old_sha256": hashlib.sha256(raw).hexdigest(),
        "new_sha256": new_hash,
        "backup": pre_backup,
        "dest_exists": os.path.isdir(DEV_DEST),
    }


def main():
    print("REPAIR_SCRIPT %s" % os.path.abspath(__file__))
    print("REPAIR_SCRIPT_SHA256 %s" % sha256_file(os.path.abspath(__file__)))
    print("DEST_EXISTS %s" % os.path.isdir(DEV_DEST))
    try:
        result = execute_repair()
    except RepairError as exc:
        print("REPAIR_ABORTED")
        print("reason=%s" % exc.reason)
        if exc.detail:
            print(exc.detail)
        print("working_copy_unchanged=yes")
        return 2
    except Exception:
        print("REPAIR_ABORTED")
        print("reason=UNEXPECTED")
        print(traceback.format_exc())
        return 4
    print("REPAIR_OK")
    print("working_copy=%s" % WORKING_COPY)
    print("old_sha256=%s" % result["old_sha256"])
    print("new_sha256=%s" % result["new_sha256"])
    print("pre_repair_backup=%s" % result["backup"])
    print("original_installer_unchanged=%s" % HASH_INSTALLER)
    print("original_app_unchanged=%s" % HASH_APP)
    print("original_db_unchanged=%s" % HASH_DB)
    print("link_backup_unchanged=%s" % HASH_INSTALLER)
    print("migrate_backup_unchanged=%s" % HASH_MIGRATE_BACKUP)
    print("development_destination_exists=%s" % result["dest_exists"])
    print("installer_was_not_run=yes")
    print("migration_was_not_run=yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
