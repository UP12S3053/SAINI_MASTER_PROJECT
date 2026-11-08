# -*- coding: utf-8 -*-
"""Run the original R4 and R14 test files. Do not change their source or the R13 installation."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
R13 = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_000I_R13")
REPORT = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\R17B_REMAINING_TESTS_REPORT.txt")
BASELINE = BUNDLE / "r4_baseline"
VIEW = BUNDLE / "r14_view"
ORIGINAL = {
    "test_compat_r4.py": "A21288B52A53F7C2C2800616FAF9ABF7DCD954E15C29AFC29CA1FB387678A716",
    "test_r14_integration.py": "5DDB2A93416B0C4F6B9E20AC29D1B87526BB005FEF4D5A99C36A35BD8E73CD26",
}
R13_FILES = [
    "SAINI_ID_CARD.py",
    "config_editor.py",
    "bsm_selector.py",
    "saini_config_path.py",
    "option_c_modules/gate.py",
    "option_c_modules/identity.py",
    "option_c_modules/journal.py",
    "option_c_modules/safety.py",
    "option_c_modules/sink_verifier.py",
    "baseline/gate.py",
    "baseline/identity.py",
    "baseline/journal.py",
    "baseline/safety.py",
    "baseline/sink_verifier.py",
    "baseline/SAINI_ID_CARD.py",
    "baseline/config_editor.py",
]
LIVE = [
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\SAINI_ID_CARD.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\config_editor.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\templates\IDCARD\BSM.png"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules\gate.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules\identity.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules\journal.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules\safety.py"),
    Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\option_c_modules\sink_verifier.py"),
]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def snapshot(paths):
    found = {}
    for path in paths:
        found[str(path)] = sha(path) if Path(path).is_file() else "MISSING"
    return found


def run_test(script):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(script)],
        text=True,
        capture_output=True,
        timeout=180,
        env=env,
    )


def passed_names(output):
    names = []
    for line in output.splitlines():
        if line.endswith(" ... ok"):
            names.append(line.split(" ... ok")[0].strip())
    return names


def link_file(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, dest)


def link_dir(source, dest):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(source)], check=True, capture_output=True, text=True)


def main():
    if REPORT.exists():
        print("R17B_BLOCKED_SAFETY_CHECK")
        print("report already exists; not overwritten")
        return
    lines = ["R17B_REMAINING_TESTS_REPORT"]
    missing = [name for name in ORIGINAL if not (BUNDLE / "original" / name).is_file()]
    if missing or not R13.is_dir():
        lines += ["status=R17B_ORIGINAL_TESTS_NOT_FOUND", "missing=" + ",".join(missing), f"r13_exists={R13.is_dir()}"]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return
    for name, expected in ORIGINAL.items():
        actual = sha(BUNDLE / "original" / name)
        lines.append(f"source=original/{name} sha256={actual} match={'YES' if actual == expected else 'NO'}")
        if actual != expected:
            lines += ["status=R17B_ORIGINAL_TESTS_NOT_FOUND", "reason=test bytes do not match the original file"]
            REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("\n".join(lines))
            return
    lines.append("r4_original_location=/workspace/SAINI_ID_DEV_000I_R4/tests/test_compat_r4.py")
    lines.append("r14_original_location=/workspace/SAINI_ID_DEV_000I_R14/tests/test_r14_integration.py")
    lines.append("tests_were_not_rewritten=YES")
    before = snapshot(R13 / rel for rel in R13_FILES)
    live_before = snapshot(LIVE)
    r14_names, r4_names = [], []
    r14_code, r4_code = None, None

    if VIEW.exists():
        lines.append("status=R17B_BLOCKED_SAFETY_CHECK")
        lines.append("reason=r14_view already exists and was not overwritten")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return
    try:
        (VIEW / "tests").mkdir(parents=True)
        test_copy = VIEW / "tests" / "test_r14_integration.py"
        shutil.copyfile(BUNDLE / "original" / "test_r14_integration.py", test_copy)
        for name in ("SAINI_ID_CARD.py", "config_editor.py", "bsm_selector.py", "saini_config_path.py"):
            link_file(R13 / name, VIEW / name)
        link_dir(R13 / "option_c_modules", VIEW / "option_c_modules")
        link_dir(R13 / "baseline", VIEW / "baseline")
        result = run_test(test_copy)
        r14_code = result.returncode
        output = (result.stdout + result.stderr).rstrip()
        r14_names = passed_names(output)
        lines += ["R14_COMMAND=" + sys.executable + " " + str(test_copy), "R14_EXIT=" + str(result.returncode), "R14_OUTPUT_BEGIN", output, "R14_OUTPUT_END"]
    except Exception as exc:
        lines += [f"R14_SETUP_ERROR={exc}", "R14_EXIT=NOT_RUN"]
    finally:
        synthetic = VIEW / "synthetic_output"
        kept = BUNDLE / "synthetic_r14"
        if synthetic.is_dir() and not kept.exists():
            kept.mkdir()
            for child in synthetic.iterdir():
                if child.is_file():
                    shutil.move(str(child), kept / child.name)
        links_clear = True
        try:
            for name in ("SAINI_ID_CARD.py", "config_editor.py", "bsm_selector.py", "saini_config_path.py"):
                path = VIEW / name
                if path.exists():
                    path.unlink()
            for name in ("option_c_modules", "baseline"):
                path = VIEW / name
                if path.exists():
                    os.rmdir(path)
        except OSError:
            links_clear = False
        if links_clear and VIEW.exists():
            shutil.rmtree(VIEW)

    mount = Path("/workspace/SAINI_ID_DEV_000I_R4").resolve()
    created_parent = False
    mounted = False
    try:
        if mount.exists():
            lines.append(f"R4_NOT_RUN={mount} already exists and was not replaced")
        elif mount.parent.exists() and any(mount.parent.iterdir()):
            lines.append(f"R4_NOT_RUN={mount.parent} exists and was not touched")
        else:
            if not mount.parent.exists():
                mount.parent.mkdir()
                created_parent = True
            subprocess.run(["cmd", "/c", "mklink", "/J", str(mount), str(BASELINE)], check=True, capture_output=True, text=True)
            mounted = True
            script = BUNDLE / "original" / "test_compat_r4.py"
            result = run_test(script)
            r4_code = result.returncode
            output = (result.stdout + result.stderr).rstrip()
            r4_names = passed_names(output)
            lines += ["R4_COMMAND=" + sys.executable + " " + str(script), f"R4_BASELINE_MOUNT={mount}", "R4_EXIT=" + str(result.returncode), "R4_OUTPUT_BEGIN", output, "R4_OUTPUT_END"]
            lines.append("R4_READS_BUNDLED_BASELINE_COPY=YES")
            lines.append("R4_LIVE_WORKBOOK_OPENED=NO")
    except Exception as exc:
        lines += [f"R4_SETUP_ERROR={exc}", "R4_EXIT=NOT_RUN"]
    finally:
        if mounted and mount.exists():
            os.rmdir(mount)
        if created_parent and mount.parent.exists() and not any(mount.parent.iterdir()):
            mount.parent.rmdir()

    after = snapshot(R13 / rel for rel in R13_FILES)
    live_after = snapshot(LIVE)
    lines.append("r13_source_hashes:")
    source_same = before == after
    for path, digest in before.items():
        lines.append(f"{digest} unchanged={'YES' if after.get(path)==digest else 'NO'} {path}")
    lines.append("live_production_hashes:")
    live_same = live_before == live_after
    for path, digest in live_before.items():
        lines.append(f"{digest} unchanged={'YES' if live_after.get(path)==digest else 'NO'} {path}")
    lines.append(f"R4_PASSED={len(r4_names)} expected=5")
    lines.append(f"R14_PASSED={len(r14_names)} expected=4")
    lines.append("R13_17_TESTS_NOT_COUNTED_AGAIN=YES")
    lines.append("production_deployment=NOT_DONE")
    lines.append("student_records_opened=NO")
    lines.append("photographs_opened=NO")
    if not source_same or not live_same:
        status = "R17B_BLOCKED_SAFETY_CHECK"
    elif r4_code == 0 and r14_code == 0 and len(r4_names) == 5 and len(r14_names) == 4:
        status = "R17B_ALL_9_TESTS_PASSED"
    elif r4_code not in (0, None) or r14_code not in (0, None):
        status = "R17B_TEST_FAILURE"
    elif r4_names or r14_names:
        status = "R17B_PARTIAL_TESTS_PASSED"
    else:
        status = "R17B_ORIGINAL_TESTS_NOT_FOUND"
    lines.append("status=" + status)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
