"""
FILE NAME   : config_editor.py
PROJECT     : ID_CARD_PROJECT
PURPOSE     : Multi-School Config Editor - Fields Update on School Change
VERSION     : v33.0 (Final - 100% Working)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pandas as pd
import os
from saini_config_path import ConfigPathError, require_config_workbook
from saini_column_map import assert_writable, load_guarded_config

def editor_workbook_path():
    """Same resolved workbook path the ID generator uses."""
    return require_config_workbook()

def open_config_editor():
    try:
        workbook = editor_workbook_path()
    except ConfigPathError as exc:
        messagebox.showerror("Config workbook", str(exc))
        return

    root = tk.Tk()
    root.title("School Config Editor - श्री श्री राम")
    root.geometry("1400x900")
    root.configure(bg="#f4f6f8")

    # Load config
    config_df = load_guarded_config(workbook)
    school_codes = config_df['school_code'].tolist()

    selected_school = tk.StringVar()

    entries = {}
    config_data = {}

    def refresh_school_list():
        nonlocal config_df, school_codes
        config_df = load_guarded_config(editor_workbook_path())
        school_codes = config_df['school_code'].tolist()
        school_combo['values'] = school_codes
        if school_codes and selected_school.get() not in school_codes:
            selected_school.set(school_codes[0])
        load_school_config()

    def load_school_config(*args):
        school = selected_school.get()
        if not school:
            return
        row_df = config_df[config_df['school_code'] == school]
        if row_df.empty:
            messagebox.showwarning("Warning", f"स्कूल {school} का कॉन्फिग नहीं मिला!")
            return
        row = row_df.iloc[0]

        # Clear all entries
        for entry in entries.values():
            entry.delete(0, tk.END)

        # Load new data
        for col in config_df.columns:
            value = str(row[col]) if not pd.isna(row[col]) else ""
            config_data[col] = value
            if col in entries:
                entries[col].insert(0, value)
                print(f"Loaded {col}: {value}")

    def save_config():
        assert_writable(editor_workbook_path())
        school = selected_school.get()
        if not school:
            messagebox.showwarning("Warning", "कोई स्कूल चुनें!")
            return
        idx = config_df[config_df['school_code'] == school].index[0]
        for col, entry in entries.items():
            config_df.at[idx, col] = entry.get().strip()
        try:
            config_df.to_excel(editor_workbook_path(), index=False)
            messagebox.showinfo("Success", f"Config updated for {school}!")
            refresh_school_list()
        except PermissionError as e:
            messagebox.showerror("Permission Denied", f"File save failed!\n{e}\n\nClose Excel or run as Administrator.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def add_new_school():
        assert_writable(editor_workbook_path())
        new_school = simpledialog.askstring("New School", "Enter School Code (e.g. XYZ):")
        if new_school and new_school not in school_codes:
            new_row = pd.DataFrame([{"school_code": new_school}])
            config_df = pd.concat([config_df, new_row], ignore_index=True)
            config_df.to_excel(editor_workbook_path(), index=False)
            refresh_school_list()
            messagebox.showinfo("Success", f"New school {new_school} added!")
        else:
            messagebox.showwarning("Warning", "Code already exists or is empty!")

    def delete_school():
        assert_writable(editor_workbook_path())
        school = selected_school.get()
        if not school:
            messagebox.showwarning("Warning", "Please select a school!")
            return
        if messagebox.askyesno("Delete", f"Delete school {school}?"):
            config_df.drop(config_df[config_df['school_code'] == school].index, inplace=True)
            config_df.to_excel(editor_workbook_path(), index=False)
            refresh_school_list()
            messagebox.showinfo("Success", f"School {school} deleted!")

    # UI Setup
    main_frame = tk.Frame(root, bg="#f4f6f8")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Top Controls
    top_frame = tk.Frame(main_frame, bg="#f4f6f8")
    top_frame.pack(fill=tk.X, pady=10)

    tk.Label(top_frame, text="Select School:", font=("Arial", 12), bg="#f4f6f8").pack(side=tk.LEFT, padx=10)
    school_combo = ttk.Combobox(top_frame, textvariable=selected_school, values=school_codes, state="readonly", width=20)
    school_combo.pack(side=tk.LEFT, padx=10)

    tk.Button(top_frame, text="Add New School", bg="green", fg="white", command=add_new_school).pack(side=tk.LEFT, padx=5)
    tk.Button(top_frame, text="Delete School", bg="red", fg="white", command=delete_school).pack(side=tk.LEFT, padx=5)
    tk.Button(top_frame, text="Refresh Config", bg="#2196F3", fg="white", command=refresh_school_list).pack(side=tk.LEFT, padx=5)

    # Bind combobox change
    selected_school.trace("w", load_school_config)

    # Scrollable Config Fields
    canvas = tk.Canvas(main_frame, bg="#f4f6f8")
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#f4f6f8")

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Fields - Keys match Excel columns EXACTLY
    fields = [
        ("school_code", "स्कूल कोड"),
        ("template", "टेम्पलेट पाथ"),
        ("ACTIVE", "एक्टिव (YES/NO)"),
        ("STUDENT_PHOTO_X", "फोटो X"),
        ("STUDENT_PHOTO_Y", "फोटो Y"),
        ("STUDENT_PHOTO_W", "चौड़ाई"),
        ("STUDENT_PHOTO_H", "ऊँचाई"),
        ("PHOTO_RADIUS", "राउंडिंग"),
        ("LOGO_X", "लोगो X"),
        ("LOGO_Y", "लोगो Y"),
        ("LOGO_W", "चौड़ाई"),
        ("LOGO_H", "ऊँचाई"),
        ("LOGO_SHOW", "लोगो दिखाएं 1/0"),
        ("SCHOOLNAME", "स्कूल नाम"),
        ("SCHOOLNAME_X", "X"),
        ("SCHOOLNAME_Y", "Y"),
        ("SCHOOLNAME_FONT", "फॉन्ट"),
        ("SCHOOLNAME_SIZE", "साइज"),
        ("SCHOOLNAME_COLOUR", "रंग"),
        ("SCHOOLNAME_UPPER", "बड़ा 1/0"),
        ("SCHOOLADD", "पता"),
        ("SCHOOLADD_X", "X"),
        ("SCHOOLADD_Y", "Y"),
        ("SCHOOLADD_FONT", "फॉन्ट"),
        ("SCHOOLADD_SIZE", "साइज"),
        ("SCHOOLADD_COLOUR", "रंग"),
        ("SCHOOLADD_UPPER", "बड़ा 1/0"),
        ("NAME_SHOW", "नाम दिखाएं 1/0"),
        ("NAME_ALIGN", "संरेखण"),
        ("NAME_X", "X"),
        ("NAME_Y", "Y"),
        ("NAME_FONT", "फॉन्ट"),
        ("NAME_SIZE", "साइज"),
        ("NAME_COLOR", "रंग"),
        ("NAME_UPPER", "बड़ा 1/0"),
        ("CLASS_SHOW", "क्लास 1/0"),
        ("CLASS_X", "X"),
        ("CLASS_Y", "Y"),
        ("CLASS_FONT", "फॉन्ट"),
        ("CLASS_SIZE", "साइज"),
        ("CLASS_COLOR", "रंग"),
        ("CLASS_PREFIX", "प्रीफिक्स"),
        ("FATHER_SHOW", "पिता 1/0"),
        ("FATHER_X", "X"),
        ("FATHER_Y", "Y"),
        ("FATHER_FONT", "फॉन्ट"),
        ("FATHER_SIZE", "साइज"),
        ("FATHER_COLOR", "रंग"),
        ("FATHER_PREFIX", "प्रीफिक्स"),
        ("MOB_SHOW", "मोबाइल 1/0"),
        ("MOB_X", "X"),
        ("MOB_Y", "Y"),
        ("MOB_FONT", "फॉन्ट"),
        ("MOB_SIZE", "साइज"),
        ("MOB_COLOR", "रंग"),
        ("MOB_PREFIX", "प्रीफिक्स"),
        ("ADDR_SHOW", "पता 1/0"),
        ("ADDR_X", "X"),
        ("ADDR_Y", "Y"),
        ("ADDR_WRAP_W", "लाइन चौड़ाई"),
        ("ADDR_LINE_H", "लाइन ऊँचाई"),
        ("ADDR_FONT", "फॉन्ट"),
        ("ADDR_SIZE", "साइज"),
        ("ADDR_COLOR", "रंग"),
        ("ADDR_PREFIX", "प्रीफिक्स"),
    ]

    for i, (key, label) in enumerate(fields):
        if label == "":
            tk.Label(scrollable_frame, text="", bg="#f4f6f8").grid(row=i, column=0, columnspan=2, pady=8)
            continue
        tk.Label(scrollable_frame, text=label + " :", font=("Arial", 10), bg="#f4f6f8").grid(row=i, column=0, sticky="w", pady=4, padx=5)
        entry = tk.Entry(scrollable_frame, width=60, font=("Arial", 10))
        entry.grid(row=i, column=1, pady=4, padx=5, sticky="w")
        entries[key] = entry

    # Bottom Buttons - Fixed at bottom
    btn_frame = tk.Frame(root, bg="#f4f6f8")
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

    tk.Button(btn_frame, text="SAVE", bg="#16a34a", fg="white", font=("Arial", 12, "bold"), width=15, command=save_config).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="Refresh Config", bg="#2196F3", fg="white", font=("Arial", 12, "bold"), width=15, command=refresh_school_list).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="EXIT", bg="#dc2626", fg="white", font=("Arial", 12, "bold"), width=10, command=root.destroy).pack(side=tk.LEFT, padx=10)

    # Initial Load
    refresh_school_list()

    root.mainloop()

if __name__ == "__main__":
    open_config_editor()