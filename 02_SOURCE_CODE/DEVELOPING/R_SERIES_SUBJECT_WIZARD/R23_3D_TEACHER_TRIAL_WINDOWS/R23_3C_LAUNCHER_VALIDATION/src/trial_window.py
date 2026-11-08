# -*- coding: utf-8 -*-
"""Development-only teacher window for R23.3A.

The screen starts with no file and no photo folder selected.
It does not launch the preserved baseline and does not draw ID cards.
"""

from pathlib import Path

from identity_engine import IdentityError, assert_development_path
from legacy_guard import refuse_legacy_entry
from teacher_trial import TeacherTrial

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "TRIAL_WORKSPACE"
SESSIONS = ("2026_27", "2027_28")
CLASSES = (
    ("I", "कक्षा 1 / Class 1"),
    ("II", "कक्षा 2 / Class 2"),
    ("III", "कक्षा 3 / Class 3"),
    ("IV", "कक्षा 4 / Class 4"),
    ("V", "कक्षा 5 / Class 5"),
    ("VI", "कक्षा 6 / Class 6"),
    ("VII", "कक्षा 7 / Class 7"),
    ("VIII", "कक्षा 8 / Class 8"),
    ("IX", "कक्षा 9 / Class 9"),
    ("X", "कक्षा 10 / Class 10"),
    ("XI", "कक्षा 11 / Class 11"),
    ("XII", "कक्षा 12 / Class 12"),
)
CLASS_CODES = {code for code, _label in CLASSES}


class EnrollmentScreen:
    def __init__(self, workspace=WORKSPACE, open_file=None, open_folder=None):
        self.workspace = Path(workspace)
        assert_development_path(self.workspace)
        self.open_file = open_file or default_file_picker
        self.open_folder = open_folder or default_folder_picker
        self.table = ""
        self.photos = ""
        self.session = ""
        self.selected_class = ""
        self.busy = False
        self.cancel_requested = False
        self.exited = False
        self.status = "तैयार / Ready"
        self.progress = ""
        self.summary = []

    def choose_file(self):
        if self.busy:
            return "busy"
        selected = self.open_file()
        if not selected:
            self.status = "कोई फ़ाइल नहीं चुनी गई। / No file selected."
            return "empty"
        path = Path(selected)
        try:
            assert_development_path(path)
        except IdentityError:
            self.table = ""
            self.status = "लाइव फ़ाइल नहीं चुनी जा सकती। / A live file cannot be selected."
            return "blocked"
        if not path.is_file():
            self.table = ""
            self.status = "फ़ाइल नहीं मिली। / File not found."
            return "missing"
        if path.suffix.lower() not in {".xlsx", ".csv"}:
            self.table = ""
            self.status = "केवल Excel या CSV चुनें। / Choose only an Excel or CSV file."
            return "invalid"
        self.table = str(path)
        self.status = path.name
        return "selected"

    def choose_folder(self):
        if self.busy:
            return "busy"
        selected = self.open_folder()
        if not selected:
            self.status = "कोई फ़ोल्डर नहीं चुना गया। / No folder selected."
            return "empty"
        path = Path(selected)
        try:
            assert_development_path(path)
        except IdentityError:
            self.photos = ""
            self.status = "लाइव फ़ोल्डर नहीं चुना जा सकता। / A live folder cannot be selected."
            return "blocked"
        if not path.is_dir():
            self.photos = ""
            self.status = "फोटो फ़ोल्डर नहीं मिला। / Photo folder not found."
            return "missing"
        self.photos = str(path)
        self.status = path.name
        return "selected"

    def start(self):
        if self.exited:
            return "exited"
        if self.busy:
            self.status = "नामांकन पहले से चल रहा है। / Enrollment is already running."
            return "already_running"
        if not self.table:
            self.status = "पहले Excel या CSV चुनें। / Choose the Excel or CSV file first."
            return "invalid"
        if not self.photos:
            self.status = "पहले फोटो फ़ोल्डर चुनें। / Choose the photo folder first."
            return "invalid"
        if self.session not in SESSIONS:
            self.status = "सेशन चुनें। / Choose the session."
            return "invalid"
        if self.selected_class not in CLASS_CODES:
            self.status = "कक्षा चुनें। / Choose the class."
            return "invalid"
        refuse_legacy_entry("teacher_trial.py")
        self.busy = True
        self.cancel_requested = False
        self.status = "जारी है / Running"
        try:
            trial = TeacherTrial(self.workspace)
            try:
                results = trial.start(
                    self.table,
                    self.photos,
                    self.selected_class,
                    self.session,
                    should_stop=lambda: self.cancel_requested,
                    progress=self._progress,
                )
            finally:
                trial.close()
            self.summary = [line for line in (summary_line(item) for item in results) if line]
            self._reject_private_text("\n".join(self.summary))
            if self.cancel_requested:
                self.status = "रद्द / Cancelled"
                return "cancelled"
            self.status = "पूरा / Completed"
            self.progress = f"{len(results)}/{len(results)}"
            return "completed"
        finally:
            self.busy = False

    def cancel(self):
        self.cancel_requested = True
        if self.busy:
            self.status = "रद्द हो रहा है / Cancelling"
            return "cancel_requested"
        self.status = "रद्द / Cancelled"
        return "cancelled"

    def exit(self):
        if self.busy:
            self.cancel_requested = True
            return "busy"
        self.exited = True
        self.status = "बंद / Closed"
        return "exited"

    def _progress(self, index, total):
        self.progress = f"{index}/{total}"
        self.status = f"जारी है / Running {index}/{total}"

    @staticmethod
    def _reject_private_text(text):
        if "permanent_key" in text:
            raise IdentityError("key_leak_blocked")


def summary_line(item):
    if item.get("visible_id"):
        return f"{item['visible_id']} — {item['message']}"
    return item.get("message", "")


def default_file_picker():
    import tkinter as tk
    from tkinter import filedialog
    root = tk._default_root
    return filedialog.askopenfilename(
        parent=root,
        title="Excel या CSV चुनें / Choose Excel or CSV",
        filetypes=[("Excel or CSV", "*.xlsx *.csv")],
    )


def default_folder_picker():
    import tkinter as tk
    from tkinter import filedialog
    root = tk._default_root
    return filedialog.askdirectory(parent=root, title="फोटो फ़ोल्डर चुनें / Choose photo folder")


def build_window(root, screen=None):
    import tkinter as tk
    screen = screen or EnrollmentScreen()
    root.title("R23.3B नामांकन / Enrollment")
    file_name = tk.StringVar(value="कोई फ़ाइल नहीं / No file")
    folder_name = tk.StringVar(value="कोई फ़ोल्डर नहीं / No folder")
    status = tk.StringVar(value=screen.status)
    summary = tk.Text(root, height=12, width=72)

    def refresh():
        file_name.set(Path(screen.table).name if screen.table else "कोई फ़ाइल नहीं / No file")
        folder_name.set(Path(screen.photos).name if screen.photos else "कोई फ़ोल्डर नहीं / No folder")
        status.set(screen.status + (f"  {screen.progress}" if screen.progress else ""))
        summary.delete("1.0", "end")
        summary.insert("end", "\n".join(screen.summary))

    def choose_file():
        screen.choose_file()
        refresh()

    def choose_folder():
        screen.choose_folder()
        refresh()

    def start():
        screen.session = session.get()
        screen.selected_class = class_code.get()
        screen.start()
        refresh()

    def cancel():
        screen.cancel()
        refresh()

    def exit_window():
        screen.exit()
        if screen.exited:
            root.destroy()

    title = tk.Label(root, text="सिंथेटिक नामांकन / Synthetic enrollment")
    title.pack(anchor="w")
    file_button = tk.Button(root, text="Excel या CSV चुनें / Choose file", command=choose_file)
    file_button.pack(anchor="w")
    file_label = tk.Label(root, textvariable=file_name)
    file_label.pack(anchor="w")
    folder_button = tk.Button(root, text="फोटो फ़ोल्डर चुनें / Choose photo folder", command=choose_folder)
    folder_button.pack(anchor="w")
    folder_label = tk.Label(root, textvariable=folder_name)
    folder_label.pack(anchor="w")
    session_label = tk.Label(root, text="सेशन / Session")
    session_label.pack(anchor="w")
    session = tk.StringVar(value="")
    session_menu = tk.OptionMenu(root, session, "", *SESSIONS)
    session_menu.pack(anchor="w")
    class_label = tk.Label(root, text="कक्षा / Class")
    class_label.pack(anchor="w")
    class_code = tk.StringVar(value="")
    class_menu = tk.OptionMenu(root, class_code, "", *[code for code, _label in CLASSES])
    class_menu.pack(anchor="w")
    start_button = tk.Button(root, text="नामांकन शुरू करें / Start enrollment", command=start)
    start_button.pack(anchor="w")
    cancel_button = tk.Button(root, text="रद्द करें / Cancel", command=cancel)
    cancel_button.pack(anchor="w")
    exit_button = tk.Button(root, text="बाहर निकलें / Exit", command=exit_window)
    exit_button.pack(anchor="w")
    status_label = tk.Label(root, textvariable=status)
    status_label.pack(anchor="w")
    summary.pack(anchor="w")
    return {
        "screen": screen,
        "file_button": file_button,
        "folder_button": folder_button,
        "file_name": file_name,
        "folder_name": folder_name,
        "session": session,
        "class_code": class_code,
        "start_button": start_button,
        "cancel_button": cancel_button,
        "exit_button": exit_button,
        "status": status,
        "summary": summary,
    }


def open_window():
    import os
    import tkinter as tk
    root = tk.Tk()
    parts = build_window(root)
    if os.environ.get("SAINI_GUI_SELFTEST") == "1":
        root.update()
        destination = Path(os.environ["SAINI_GUI_SELFTEST_OUT"])
        lines = [root.title(), parts["file_name"].get(), parts["folder_name"].get()]
        for child in root.winfo_children():
            if child.winfo_class() == "Button":
                lines.append(child.cget("text"))
        destination.write_text("\n".join(lines), encoding="utf-8")
        root.destroy()
        return
    root.mainloop()
