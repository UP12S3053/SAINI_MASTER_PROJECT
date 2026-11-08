# STABLE V2 DEVELOPMENT COPY â€” PATH FIXED
# Base: user-confirmed stable file "SAINI_ID_CARD OLD.py".
# Selective additions: isolated paths, fail-closed Gate guards, natural image sorting,
# refusal to overwrite existing PDF/ID-image outputs, and manual timestamp preservation.
# Back-card pairing logic intentionally unchanged. This is not a production deployment.
# Updated SAINI_ID_CARD.py with fixed generate_selected_ids
import os
import sys
from pathlib import Path
DEV_ROOT = os.environ.get('SAINI_DEV_ROOT', r'D:\SHRI_JAI_SHRI_RAM\project_panels')
GATE_MODULE_DIR = os.environ.get('SAINI_GATE_MODULE_DIR', os.path.join(DEV_ROOT, 'src'))
if GATE_MODULE_DIR not in sys.path:
    sys.path.insert(0, GATE_MODULE_DIR)
# Resolve Option C Gate modules from this project; keep Gate enabled.
import sys
from pathlib import Path as _SainiPath
_SAINI_OPTION_C_MODULES = _SainiPath(__file__).resolve().parent / "option_c_modules"
if not _SAINI_OPTION_C_MODULES.is_dir():
    raise ModuleNotFoundError(f"Option C module directory missing: {_SAINI_OPTION_C_MODULES}")
if str(_SAINI_OPTION_C_MODULES) not in sys.path:
    sys.path.insert(0, str(_SAINI_OPTION_C_MODULES))
from gate import authorize
from saini_config_path import require_config_workbook
from bsm_selector import ConfigSelectionError, select_bsm_row
from saini_column_map import load_guarded_config
import pandas as pd
from tkinter import *
from tkinter import messagebox, ttk
from tkcalendar import DateEntry
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import requests
import tempfile
import time
import re
import shutil
import hashlib
import json

# ... (baaki pura code same rahega, sirf generate_selected_ids class ke andar hai)

# Main change yeh hai ki ab function class ke andar hai
# Constants
EXCEL_CONFIG = require_config_workbook()
EXCEL_STUDENT = os.environ.get("SAINI_DEV_STUDENT_XLSX", r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx")
OUTPUT_DIR = os.environ.get("SAINI_DEV_OUTPUT_DIR", r"D:\SHRI_JAI_SHRI_RAM\project_panels\OUTPUT")
LAST_TS_FILE = os.environ.get("SAINI_DEV_LAST_TS_FILE", r"D:\SHRI_JAI_SHRI_RAM\project_panels\last_processed_timestamp.txt")

_SUFFIX_RE = re.compile(r'(?i)(?:[_\-\s]*(ID[_\-\s]*CARD|FRONT|BACK)|[_\-\s]*[FB])$')

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0"
})


def download_image(url):

    if not url:
        return None

    url = str(url).strip()

    if "drive.google.com" in url:

        file_id = url.split("id=")[-1].split("&")[0]

        url = f"https://drive.google.com/uc?export=download&id={file_id}"

    for retry in range(5):

        try:

            r = session.get(
                url,
                timeout=40,
                stream=True,
                allow_redirects=True
            )

            r.raise_for_status()

            temp = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            ).name

            with open(temp, "wb") as f:

                for chunk in r.iter_content(8192):

                    if chunk:

                        f.write(chunk)

            try:

                Image.open(temp).verify()

            except:

                os.remove(temp)

                raise Exception("Invalid Image")

            return temp

        except Exception as e:

            print("Download Retry", retry + 1)

            print(e)

            time.sleep(2)

    return None

def hex_to_rgb(hex_str):
    if not hex_str or str(hex_str).strip() == '':
        return (0, 0, 0)        # à¤¡à¤¿à¤«à¤¼à¥‰à¤²à¥à¤Ÿ à¤¬à¥à¤²à¥ˆà¤• à¤•à¤²à¤°
    
    hex_str = str(hex_str).lstrip('#').strip()
    if len(hex_str) != 6:       # à¤…à¤—à¤° à¤—à¤²à¤¤ à¤«à¥‰à¤°à¥à¤®à¥‡à¤Ÿ à¤¹à¥‹ à¤¤à¥‹ à¤­à¥€ à¤¬à¥à¤²à¥ˆà¤•
        return (0, 0, 0)
    
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except:
        return (0, 0, 0)        # à¤•à¥‹à¤ˆ à¤­à¥€ à¤¸à¤®à¤¸à¥à¤¯à¤¾ à¤¹à¥‹ à¤¤à¥‹ à¤¬à¥à¤²à¥ˆà¤•

def load_font(font_name, size):
    if size <= 0:           # â† à¤¯à¤¹ à¤²à¤¾à¤‡à¤¨ à¤œà¤°à¥‚à¤° à¤œà¥‹à¤¡à¤¼ à¤¦à¥‹
        size = 25
    
    base = "C:/Windows/Fonts"
    path = os.path.join(base, f"{font_name}.ttf")
    if not os.path.exists(path):
        path = os.path.join(base, "arial.ttf")
    return ImageFont.truetype(path, size)

def draw_text(draw, text, x, y, font, fill, align="left"):
    if align == "center":
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text((x - w // 2, y), text, font=font, fill=fill)
    else:
        draw.text((x, y), text, font=font, fill=fill)

# ===== ADDRESS WIDTH BASED WRAP TEXT =====
def draw_wrapped_text(draw, text, x, y, font, fill, max_width,
                      line_spacing=5, align="left"):

    words = str(text).split()
    lines = []
    current_line = ""

    for word in words:
        test_line = word if not current_line else current_line + " " + word

        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)

            current_line = word

    if current_line:
        lines.append(current_line)

    bbox = font.getbbox("Ag")
    line_height = bbox[3] - bbox[1]

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if align == "center":
            draw_x = x - text_width // 2
        elif align == "right":
            draw_x = x - text_width
        else:
            draw_x = x

        draw.text(
            (draw_x, y),
            line,
            font=font,
            fill=fill
        )

        y += line_height + line_spacing
def safe_int(value, default=0):
    if pd.isna(value) or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def parse_timestamp(ts):
    if pd.isna(ts):
        return pd.NaT
    if isinstance(ts, (int, float)):
        return pd.to_datetime('1899-12-30') + pd.to_timedelta(ts, unit='D')
    else:
        ts_str = str(ts).strip()
        formats = ['%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%Y-%m-%d %H:%M:%S']
        for fmt in formats:
            try:
                return pd.to_datetime(ts_str, format=fmt)
            except:
                pass
        return pd.to_datetime(ts_str, errors='coerce')

def generate_front_card(template_path, output_path, student_data, config):
    if not os.path.exists(template_path):
        print("ERROR: Template file missing!")
        return False

    try:
        card = Image.open(template_path).convert("RGB")
    except Exception as e:
        print(f"ERROR opening template: {e}")
        return False

    draw = ImageDraw.Draw(card)
    config = config.fillna('')

    # School logo
    if safe_int(config.get('LOGO_SHOW', 0)) == 1:
        logo_path = config.get('SCHOOL_LOGO_PATH', '')
        if logo_path and os.path.exists(logo_path):
            try:
                logo_x = safe_int(config.get('LOGO_X', 0))
                logo_y = safe_int(config.get('LOGO_Y', 0))
                logo_w = safe_int(config.get('LOGO_W', 100))
                logo_h = safe_int(config.get('LOGO_H', 100))
                logo = Image.open(logo_path).resize((logo_w, logo_h))
                card.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)
            except Exception as e:
                print(f"Logo error: {e}")

    # Principal signature
    if safe_int(config.get('SIGN_SHOW', 0)) == 1:
        sign_path = config.get('PRINCI_SIGN_PATH', '')
        if sign_path and os.path.exists(sign_path):
            try:
                sign_x = safe_int(config.get('SIGN_X', 0))
                sign_y = safe_int(config.get('SIGN_Y', 0))
                sign_w = safe_int(config.get('SIGN_W', 100))
                sign_h = safe_int(config.get('SIGN_H', 100))
                sign = Image.open(sign_path).resize((sign_w, sign_h))
                card.paste(sign, (sign_x, sign_y), sign if sign.mode == 'RGBA' else None)
            except Exception as e:
                print(f"Signature error: {e}")

    # School name
    text = config.get('SCHOOLNAME', '').upper() if safe_int(config.get('SCHOOLNAME_UPPER', 0)) == 1 else config.get('SCHOOLNAME', '')
    if text and config.get('SCHOOLNAME_X') is not None and config.get('SCHOOLNAME_Y') is not None:
        school_size = safe_int(config.get('SCHOOLNAME_SIZE', 25))
        if school_size <= 0:          # â† à¤¸à¥à¤°à¤•à¥à¤·à¤¾ à¤²à¤—à¤¾à¤ˆ
            school_size = 30          # à¤…à¤—à¤° 0 à¤¯à¤¾ à¤¨à¥‡à¤—à¥‡à¤Ÿà¤¿à¤µ à¤¹à¥ˆ à¤¤à¥‹ 30 à¤•à¤° à¤¦à¥‹
        
        font = load_font(config.get('SCHOOLNAME_FONT', 'arial'), school_size)
        color = hex_to_rgb(config.get('SCHOOLNAME_COLOUR', '#000000'))
        x = safe_int(config['SCHOOLNAME_X'])
        y = safe_int(config['SCHOOLNAME_Y'])
        if x > 0 and y > 0:
            draw_text(draw, text, x, y, font, color, "center")

    # School address
    text = config.get('SCHOOLADD', '').upper() if safe_int(config.get('SCHOOLADD_UPPER', 0)) == 1 else config.get('SCHOOLADD', '')
    if text and config.get('SCHOOLADD_X') and config.get('SCHOOLADD_Y'):
        font = load_font(config.get('SCHOOLADD_FONT', 'arial'), safe_int(config.get('SCHOOLADD_SIZE', 15)))
        color = hex_to_rgb(config.get('SCHOOLADD_COLOUR', '#000000'))
        x = safe_int(config['SCHOOLADD_X'])
        y = safe_int(config['SCHOOLADD_Y'])
        draw_text(draw, text, x, y, font, color, "center")

    # Student name
    if safe_int(config.get('NAME_SHOW', 0)) == 1:
        text = str(student_data.get('student_name', '')).upper() if safe_int(config.get('NAME_UPPER', 0)) == 1 else str(student_data.get('student_name', ''))
        if text and config.get('NAME_X') and config.get('NAME_Y'):
            font = load_font(config.get('NAME_FONT', 'arial'), safe_int(config.get('NAME_SIZE', 25)))
            color = hex_to_rgb(config.get('NAME_COLOR', '#000000'))
            x = safe_int(config['NAME_X'])
            y = safe_int(config['NAME_Y'])
            draw_text(draw, text, x, y, font, color, config.get('NAME_ALIGN', 'center'))

    # Class
    if safe_int(config.get('CLASS_SHOW', 0)) == 1:
        text = config.get('CLASS_PREFIX', '') + str(student_data.get('class', ''))
        if text and config.get('CLASS_X') and config.get('CLASS_Y'):
            font = load_font(config.get('CLASS_FONT', 'arial'), safe_int(config.get('CLASS_SIZE', 15)))
            color = hex_to_rgb(config.get('CLASS_COLOR', '#000000'))
            x = safe_int(config['CLASS_X'])
            y = safe_int(config['CLASS_Y'])
            draw_text(draw, text, x, y, font, color)

    # Father name
    if safe_int(config.get('FATHER_SHOW', 0)) == 1:
        text = config.get('FATHER_PREFIX', '') + str(student_data.get('father_name', '')).upper()
        if text and config.get('FATHER_X') and config.get('FATHER_Y'):
            font = load_font(config.get('FATHER_FONT', 'arial'), safe_int(config.get('FATHER_SIZE', 15)))
            color = hex_to_rgb(config.get('FATHER_COLOR', '#000000'))
            x = safe_int(config['FATHER_X'])
            y = safe_int(config['FATHER_Y'])
            draw_text(draw, text, x, y, font, color)

    # Mobile
    if safe_int(config.get('MOB_SHOW', 0)) == 1:
        text = config.get('MOB_PREFIX', '') + str(student_data.get('mob_number', ''))
        if text and config.get('MOB_X') and config.get('MOB_Y'):
            font = load_font(config.get('MOB_FONT', 'arial'), safe_int(config.get('MOB_SIZE', 15)))
            color = hex_to_rgb(config.get('MOB_COLOR', '#000000'))
            x = safe_int(config['MOB_X'])
            y = safe_int(config['MOB_Y'])
            draw_text(draw, text, x, y, font, color)

    # Roll Number
    if safe_int(config.get('ROL_SHOW', 0)) == 1:
        text = config.get('ROL_PREFIX', '') + str(student_data.get('roll_number', ''))
        if text and config.get('ROL_X') and config.get('MOB_Y'):
            font = load_font(config.get('ROL_FONT', 'arial'), safe_int(config.get('ROL_SIZE', 15)))
            color = hex_to_rgb(config.get('ROL_COLOR', '#000000'))
            x = safe_int(config['ROL_X'])
            y = safe_int(config['ROL_Y'])
            draw_text(draw, text, x, y, font, color)

    # Address
    # ===== ADDRESS WIDTH BASED WRAP =====
    if safe_int(config.get('ADDR_SHOW', 0)) == 1:

        text = config.get('ADDR_PREFIX', '') + str(
            student_data.get('address', '')
        ).upper()

        if text and config.get('ADDR_X') is not None and config.get('ADDR_Y') is not None:

            font = load_font(
                config.get('ADDR_FONT', 'arial'),
                safe_int(config.get('ADDR_SIZE', 15))
            )

            color = hex_to_rgb(
                config.get('ADDR_COLOR', '#000000')
            )

            x = safe_int(config['ADDR_X'])
            y = safe_int(config['ADDR_Y'])

            # Address à¤•à¥€ maximum WIDTH
            max_width = safe_int(
                config.get('ADDR_MAX_WIDTH', 450)
            )

            # Lines à¤•à¥‡ à¤¬à¥€à¤š à¤•à¥€ à¤¦à¥‚à¤°à¥€
            line_spacing = safe_int(
                config.get('ADDR_LINE_SPACING', 5)
            )

            draw_wrapped_text(
                draw,
                text,
                x,
                y,
                font,
                color,
                max_width,
                line_spacing,
                config.get('ADDR_ALIGN', 'left')
            )

    # Student photo - FIXED VERSION
    img_path = student_data.get('STUDENT_PHOTO_PATH', '') or student_data.get('OK', '')
    img_path = str(img_path).strip() if img_path else ''
    
    if img_path and img_path.startswith('http'):
        img_path = download_image(img_path)
    
    print(f"\n=== PHOTO DEBUG ===")
    print(f"Path from Excel : [{img_path}]")
    print(f"Exists?         : {os.path.exists(img_path) if img_path else False}")
    
    if img_path and os.path.exists(img_path):
        try:
            photo_x = safe_int(config.get('STUDENT_PHOTO_X', 0))
            photo_y = safe_int(config.get('STUDENT_PHOTO_Y', 0))
            photo_w = safe_int(config.get('STUDENT_PHOTO_W', 100))
            photo_h = safe_int(config.get('STUDENT_PHOTO_H', 100))
            radius = safe_int(config.get('PHOTO_RADIUS', 0))
            
            img = Image.open(img_path).convert("RGB")
            img = img.resize((photo_w, photo_h), Image.LANCZOS)
            
            if radius > 0:
                mask = Image.new("L", img.size, 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
                img = img.convert("RGBA")
                img.putalpha(mask)
                card.paste(img, (photo_x, photo_y), img)
            else:
                card.paste(img, (photo_x, photo_y))
                
            print("Photo pasted successfully!")
        except Exception as e:
            print(f"Photo error: {e}")
    else:
        print("Photo NOT found or path empty!")
    print("====================\n")

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        card.save(output_path)
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False

# PDF Helpers
MM_TO_PT = 2.83465
def mm(v): return v * MM_TO_PT

def sorted_images(folder):
    """Return image paths in stable natural order (1, 2, 10)."""
    if not os.path.isdir(folder):
        return []

    def natural_key(name):
        return [int(part) if part.isdigit() else part.casefold()
                for part in re.split(r"(\\d+)", name)]

    imgs = [
        name for name in os.listdir(folder)
        if name.lower().endswith((".png", ".jpg", ".jpeg"))
        and os.path.isfile(os.path.join(folder, name))
    ]
    imgs.sort(key=natural_key)
    return [os.path.join(folder, name) for name in imgs]

def normalize_key(name: str) -> str:
    key = os.path.splitext(name)[0]
    prev = None
    while prev != key:
        prev = key
        key = _SUFFIX_RE.sub("", key).strip(" _-")
    return key.upper()

def collect_pairs(front_paths, back_paths):
    f_map = {normalize_key(os.path.basename(p)): p for p in front_paths}
    b_map = {normalize_key(os.path.basename(p)): p for p in back_paths}
    pairs = []
    for k in sorted(set(f_map.keys()) & set(b_map.keys())):
        pairs.append({"front_path": f_map[k], "back_path": b_map[k]})
    return pairs

def draw_page(c, images, PAGE_W, PAGE_H, MARGIN_X, MARGIN_Y, GAP_X, GAP_Y, CARD_W, CARD_H, cols, rows):
    idx = 0
    for r in range(rows):
        for col in range(cols):
            if idx >= len(images):
                return
            x = MARGIN_X + col * (CARD_W + GAP_X)
            y = PAGE_H - MARGIN_Y - (r + 1) * CARD_H - r * GAP_Y
            img_path = images[idx]
            c.saveState()
            c.translate(x + CARD_W / 2, y + CARD_H / 2)
            c.rotate(90)
            c.translate(-CARD_H / 2, -CARD_W / 2)
            c.drawImage(img_path, 0, 0, width=CARD_H, height=CARD_W, preserveAspectRatio=False, mask='auto')
            c.restoreState()
            idx += 1

def generate_pdf_layout(front_imgs, back_imgs, output_pdf, pagesize, cols, rows):
    output_parent = os.path.dirname(os.path.abspath(output_pdf))
    os.makedirs(output_parent, exist_ok=True)
    if os.path.exists(output_pdf):
        raise FileExistsError(
            f"Refusing to overwrite existing PDF: {output_pdf}. "
            "Choose a new filename or move the existing file manually."
        )
    c = canvas.Canvas(output_pdf, pagesize=pagesize)

    PAGE_W, PAGE_H = pagesize

    # ===================== EXACT 85mm x 55mm =====================
    CARD_W_MM = 85.0
    CARD_H_MM = 55.0

    CARD_W = mm(CARD_W_MM)
    CARD_H = mm(CARD_H_MM)

    # Precise margins and gaps for exact 85x55mm printing
    MARGIN_X = mm(12.5)
    MARGIN_Y = mm(7.0)
    GAP_X = mm(10.0)
    GAP_Y = mm(3.0)

    cards_per_page = cols * rows

    # Front side
    for i in range(0, len(front_imgs), cards_per_page):
        chunk = front_imgs[i:i + cards_per_page]
        draw_page(c, chunk, PAGE_W, PAGE_H, MARGIN_X, MARGIN_Y, GAP_X, GAP_Y, 
                  CARD_W, CARD_H, cols, rows)
        c.showPage()

    # Back side (for double sided cards)
    if back_imgs:
        for i in range(0, len(back_imgs), cards_per_page):
            chunk = back_imgs[i:i + cards_per_page]
            chunk.reverse()
            draw_page(c, chunk, PAGE_W, PAGE_H, MARGIN_X, MARGIN_Y, GAP_X, GAP_Y, 
                      CARD_W, CARD_H, cols, rows)
            c.showPage()

    c.save()

def generate_marksheet(template_path, output_path, student_data, config, defaults={}):
    template_path = config.get('MARKSHEET_TEMPLATE', template_path)
    if not os.path.exists(template_path):
        print("ERROR: Marksheet template missing!")
        return False

    try:
        sheet = Image.open(template_path).convert("RGB")
    except Exception as e:
        print(f"ERROR opening marksheet template: {e}")
        return False

    draw = ImageDraw.Draw(sheet)
    config = config.fillna('')

    # Marks integer + PER 2 decimal
    mark_fields = [f'S{i}{j}' for i in range(1, 11) for j in range(1, 6)] + ['TERM1', 'TERM2', 'TERM3', 'TERM4', 'GT']
    for field in mark_fields:
        if field in student_data and pd.notna(student_data[field]):
            try:
                student_data[field] = int(round(float(student_data[field])))
            except:
                pass
    if 'PER' in student_data and pd.notna(student_data['PER']):
        try:
            per_val = float(student_data['PER'])
            student_data['PER'] = round(per_val, 2)
        except:
            pass

    # DOB format DD-MM-YY
    dob_raw = student_data.get('DOB', '')
    if dob_raw:
        try:
            if isinstance(dob_raw, (int, float)):
                base_date = datetime(1900, 1, 1)
                dob_date = base_date + timedelta(days=int(dob_raw) - 2)
                student_data['DOB'] = dob_date.strftime('%d-%m-%y')
            else:
                student_data['DOB'] = str(dob_raw).split(' ')[0].replace('/', '-')
        except:
            pass

    # Common elements (logo, sign, school name etc.) - same as ID card
    if safe_int(config.get('LOGO_SHOW', 0)) == 1:
        logo_path = config.get('SCHOOL_LOGO_PATH', '')
        if logo_path and os.path.exists(logo_path):
            logo_x = safe_int(config.get('LOGO_X', 0))
            logo_y = safe_int(config.get('LOGO_Y', 0))
            logo_w = safe_int(config.get('LOGO_W', 100))
            logo_h = safe_int(config.get('LOGO_H', 100))
            logo = Image.open(logo_path).resize((logo_w, logo_h))
            sheet.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    if safe_int(config.get('SIGN_SHOW', 0)) == 1:
        sign_path = config.get('PRINCI_SIGN_PATH', '')
        if sign_path and os.path.exists(sign_path):
            sign_x = safe_int(config.get('SIGN_X', 0))
            sign_y = safe_int(config.get('SIGN_Y', 0))
            sign_w = safe_int(config.get('SIGN_W', 100))
            sign_h = safe_int(config.get('SIGN_H', 100))
            sign = Image.open(sign_path).resize((sign_w, sign_h))
            sheet.paste(sign, (sign_x, sign_y), sign if sign.mode == 'RGBA' else None)

    # School Name - à¤¸à¥à¤•à¥‚à¤² à¤•à¤¾ à¤¨à¤¾à¤®
    text = config.get('SCHOOLNAME', '').upper() if safe_int(config.get('SCHOOLNAME_UPPER', 0)) == 1 else config.get('SCHOOLNAME', '')
    if text and config.get('SCHOOLNAME_X') is not None and config.get('SCHOOLNAME_Y') is not None:
        # à¤•à¤²à¤° à¤–à¤¾à¤²à¥€ à¤¹à¥‹ à¤¤à¥‹ à¤¬à¥à¤²à¥ˆà¤• à¤•à¤° à¤¦à¥‹
        colour_str = config.get('SCHOOLNAME_COLOUR', '#000000')
        if not colour_str or str(colour_str).strip() == '':
            colour_str = '#000000'
        
        color = hex_to_rgb(colour_str)
        
        # à¤¸à¤¾à¤‡à¤œà¤¼ 0 à¤¹à¥‹ à¤¤à¥‹ 30 à¤•à¤° à¤¦à¥‹
        school_size = safe_int(config.get('SCHOOLNAME_SIZE', 25))
        if school_size <= 0:
            school_size = 30
        
        x = safe_int(config['SCHOOLNAME_X'])
        y = safe_int(config['SCHOOLNAME_Y'])
        if x > 0 and y > 0:
            font = load_font(config.get('SCHOOLNAME_FONT', 'arial'), school_size)
            draw_text(draw, text, x, y, font, color, "center")

    text = config.get('SCHOOLADD', '').upper() if safe_int(config.get('SCHOOLADD_UPPER', 0)) == 1 else config.get('SCHOOLADD', '')
    if text and config.get('SCHOOLADD_X') is not None and config.get('SCHOOLADD_Y') is not None:
        font = load_font(config.get('SCHOOLADD_FONT', 'arial'), safe_int(config.get('SCHOOLADD_SIZE', 15)))
        color = hex_to_rgb(config.get('SCHOOLADD_COLOUR', '#000000'))
        x = safe_int(config['SCHOOLADD_X'])
        y = safe_int(config['SCHOOLADD_Y'])
        if x > 0 and y > 0:
            draw_text(draw, text, x, y, font, color, "center")

    if safe_int(config.get('NAME_SHOW', 0)) == 1:
        text = str(student_data.get('student_name', '')).upper() if safe_int(config.get('NAME_UPPER', 0)) == 1 else str(student_data.get('student_name', ''))
        if text and config.get('NAME_X') is not None and config.get('NAME_Y') is not None:
            font = load_font(config.get('NAME_FONT', 'arial'), safe_int(config.get('NAME_SIZE', 25)))
            color = hex_to_rgb(config.get('NAME_COLOR', '#000000'))
            x = safe_int(config['NAME_X'])
            y = safe_int(config['NAME_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color, config.get('NAME_ALIGN', 'center'))

    if safe_int(config.get('CLASS_SHOW', 0)) == 1:
        text = config.get('CLASS_PREFIX', '') + str(student_data.get('class', ''))
        if text and config.get('CLASS_X') is not None and config.get('CLASS_Y') is not None:
            font = load_font(config.get('CLASS_FONT', 'arial'), safe_int(config.get('CLASS_SIZE', 15)))
            color = hex_to_rgb(config.get('CLASS_COLOR', '#000000'))
            x = safe_int(config['CLASS_X'])
            y = safe_int(config['CLASS_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color)

    if safe_int(config.get('FATHER_SHOW', 0)) == 1:
        text = config.get('FATHER_PREFIX', '') + str(student_data.get('father_name', '')).upper()
        if text and config.get('FATHER_X') is not None and config.get('FATHER_Y') is not None:
            font = load_font(config.get('FATHER_FONT', 'arial'), safe_int(config.get('FATHER_SIZE', 15)))
            color = hex_to_rgb(config.get('FATHER_COLOR', '#000000'))
            x = safe_int(config['FATHER_X'])
            y = safe_int(config['FATHER_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color)

    if safe_int(config.get('MOTHER_SHOW', 0)) == 1:
        text = config.get('MOTHER_PREFIX', 'Mrs. ') + str(student_data.get('mother_name', '')).upper()
        if text.strip() and config.get('MOTHER_X') is not None and config.get('MOTHER_Y') is not None:
            font = load_font(config.get('MOTHER_FONT', 'arial'), safe_int(config.get('MOTHER_SIZE', 40)))
            color = hex_to_rgb(config.get('MOTHER_COLOR', '#000080'))
            x = safe_int(config['MOTHER_X'])
            y = safe_int(config['MOTHER_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color, "left")

# DOB à¤•à¥‹ à¤¸à¤¹à¥€ à¤«à¥‰à¤°à¥à¤®à¥‡à¤Ÿ à¤®à¥‡à¤‚ à¤¦à¤¿à¤–à¤¾à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤
    if safe_int(config.get('DOB_SHOW', 0)) == 1:
        dob_raw = student_data.get('DOB', '')
        formatted_dob = "N/A"
    
        if pd.notna(dob_raw) and dob_raw:
            dob_str = str(dob_raw).strip()
        
            # à¤¸à¤‚à¤­à¤¾à¤µà¤¿à¤¤ à¤¸à¤­à¥€ à¤«à¥‰à¤°à¥à¤®à¥‡à¤Ÿ à¤Ÿà¥à¤°à¤¾à¤ˆ à¤•à¤°à¥‡à¤‚
            formats = [
                "%b %d, %Y",      # Jan 12, 2012
                "%b %d %Y",       # Jan 12 2012
                "%d %b %Y",       # 12 Jan 2012
                "%d-%m-%Y",       # 12-01-2012
                "%d/%m/%Y",       # 12/01/2012
                "%m/%d/%Y",       # 01/12/2012
                "%Y-%m-%d",       # 2012-01-12
                "%d-%b-%Y",       # 12-Jan-2012
            ]
        
            for fmt in formats:
                try:
                    dt = datetime.strptime(dob_str, fmt)
                    formatted_dob = dt.strftime("%d-%m-%Y")  # â† à¤ªà¥‚à¤°à¤¾ à¤¡à¥‡à¤Ÿ: 12-01-2012
                    # à¤…à¤—à¤° "12 Jan 2012" à¤šà¤¾à¤¹à¤¿à¤ à¤¤à¥‹ à¤‡à¤¸ à¤²à¤¾à¤‡à¤¨ à¤•à¥‹ à¤¯à¥‚à¤œ à¤•à¤°à¥‹:
                    # formatted_dob = dt.strftime("%d %b %Y")
                    break
                except ValueError:
                    continue
        
            # à¤…à¤—à¤° à¤•à¥à¤› à¤®à¥ˆà¤š à¤¨ à¤•à¤°à¥‡ à¤¤à¥‹ à¤®à¥‚à¤² à¤µà¥ˆà¤²à¥à¤¯à¥‚ à¤°à¤– à¤²à¥‡à¤‚
            if formatted_dob == "N/A" and len(dob_str) > 3:
                formatted_dob = dob_str
    
        text = config.get('DOB_PREFIX', '') + formatted_dob
    
        if text.strip() and config.get('DOB_X') is not None and config.get('DOB_Y') is not None:
            font = load_font(config.get('DOB_FONT', 'arial'), safe_int(config.get('DOB_SIZE', 40)))
            color = hex_to_rgb(config.get('DOB_COLOR', '#000080'))
            x = safe_int(config['DOB_X'])
            y = safe_int(config['DOB_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color, "left")

    if safe_int(config.get('ROLL_SHOW', 0)) == 1:
        text = config.get('ROLL_PREFIX', '') + str(student_data.get('roll_number', ''))
        if text and config.get('ROLL_X') is not None and config.get('ROLL_Y') is not None:
            font = load_font(config.get('ROLL_FONT', 'arial'), safe_int(config.get('ROLL_SIZE', 40)))
            color = hex_to_rgb(config.get('ROLL_COLOR', '#000080'))
            x = safe_int(config['ROLL_X'])
            y = safe_int(config['ROLL_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color, "left")

    if safe_int(config.get('MOB_SHOW', 0)) == 1:
        text = config.get('MOB_PREFIX', '') + str(student_data.get('mob_number', ''))
        if text and config.get('MOB_X') is not None and config.get('MOB_Y') is not None:
            font = load_font(config.get('MOB_FONT', 'arial'), safe_int(config.get('MOB_SIZE', 15)))
            color = hex_to_rgb(config.get('MOB_COLOR', '#000000'))
            x = safe_int(config['MOB_X'])
            y = safe_int(config['MOB_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color)

    if safe_int(config.get('ROL_SHOW', 0)) == 1:
        text = config.get('ROL_PREFIX', '') + str(student_data.get('roll_number', ''))
        if text and config.get('ROL_X') is not None and config.get('ROL_Y') is not None:
            font = load_font(config.get('ROL_FONT', 'arial'), safe_int(config.get('ROL_SIZE', 15)))
            color = hex_to_rgb(config.get('ROL_COLOR', '#000000'))
            x = safe_int(config['ROL_X'])
            y = safe_int(config['ROL_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color)

    if safe_int(config.get('ADDR_SHOW', 0)) == 1:
        text = config.get('ADDR_PREFIX', '') + str(student_data.get('address', '')).upper()
        if text and config.get('ADDR_X') is not None and config.get('ADDR_Y') is not None:
            font = load_font(config.get('ADDR_FONT', 'arial'), safe_int(config.get('ADDR_SIZE', 15)))
            color = hex_to_rgb(config.get('ADDR_COLOR', '#000000'))
            x = safe_int(config['ADDR_X'])
            y = safe_int(config['ADDR_Y'])
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, font, color, config.get('ADDR_ALIGN', 'left'))

    # Student photo
    img_path = student_data.get('STUDENT_PHOTO_PATH', '') or student_data.get('OK', '')
    if img_path and img_path.startswith('http'):
        img_path = download_image(img_path)
    if img_path and os.path.exists(img_path):
        try:
            photo_x = safe_int(config.get('STUDENT_PHOTO_X', 80))
            photo_y = safe_int(config.get('STUDENT_PHOTO_Y', 200))
            photo_w = safe_int(config.get('STUDENT_PHOTO_W', 250))
            photo_h = safe_int(config.get('STUDENT_PHOTO_H', 300))
            radius = safe_int(config.get('PHOTO_RADIUS', 30))
            img = Image.open(img_path).resize((photo_w, photo_h))
            if radius > 0:
                mask = Image.new("L", img.size, 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
                img = img.convert("RGBA")
                img.putalpha(mask)
            sheet.paste(img, (photo_x, photo_y), img if 'A' in img.getbands() else None)
        except Exception as e:
            print(f"Photo error: {e}")

    # Marks drawing
    marks_font = load_font(config.get('MARKS_FONT', 'BOOKOSB'), safe_int(config.get('MARKS_SIZE', 55)))
    marks_color = hex_to_rgb(config.get('MARKS_COLOR', '#003366'))
    mark_fields_all = mark_fields + ['PER', 'DIV']
    for field in mark_fields_all:
        if field in student_data and pd.notna(student_data[field]):
            text = str(student_data[field])
            if field == 'PER':
                text = text + "%"
            x_key = f'{field}_X'
            y_key = f'{field}_Y'
            x = safe_int(config.get(x_key, 0))
            y = safe_int(config.get(y_key, 0))
            if x > 0 and y > 0:
                draw_text(draw, text, x, y, marks_font, marks_color, "center")

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        sheet.save(output_path)
        return True
    except Exception as e:
        print(f"Marksheet save error: {e}")
        return False



def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_master_roster_manifest():
    manifest_value = os.environ.get("SAINI_MASTER_ROSTER_MANIFEST", "").strip()
    config_value = os.environ.get("SAINI_MASTER_ROSTER_CONFIG_XLSX", "").strip()
    student_value = os.environ.get("SAINI_MASTER_ROSTER_STUDENT_XLSX", "").strip()
    if not manifest_value or not config_value or not student_value:
        return None, "Master-roster authorization configuration is missing."
    manifest_path = Path(manifest_value).resolve()
    config_path = Path(config_value).resolve()
    student_path = Path(student_value).resolve()
    if not manifest_path.is_file() or not config_path.is_file() or not student_path.is_file():
        return None, "Master-roster manifest or bound workbook is missing."
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("mode") != "MASTER_ROSTER":
            return None, "Unsupported master-roster manifest schema/mode."
        if manifest.get("approved_by_interactive_operator") is not True:
            return None, "Master-roster manifest has no interactive operator approval."
        if manifest.get("config_path") != str(config_path) or manifest.get("student_path") != str(student_path):
            return None, "Master-roster workbook path mismatch."
        if manifest.get("config_sha256") != _sha256_file(config_path):
            return None, "School configuration workbook changed after authorization. Re-authorize."
        if manifest.get("student_sha256") != _sha256_file(student_path):
            return None, "student_data.xlsx changed after authorization. Re-authorize."
        if "IDCARD" not in manifest.get("allowed_outputs", []):
            return None, "Master-roster authorization does not permit ID-card output."
        return manifest, None
    except Exception as exc:
        return None, f"Cannot validate master-roster manifest: {exc}"


def _master_roster_school_ids(school_code):
    manifest, error = _load_master_roster_manifest()
    if error:
        return None, error
    school = str(school_code or "").strip().upper()
    if not school or school != str(manifest.get("authorized_school", "")).strip().upper():
        return None, "Requested school does not match the explicitly authorized master roster."
    ids = manifest.get("student_ids_by_school", {}).get(school, [])
    if not isinstance(ids, list) or not ids:
        return None, f"No authorized unique student IDs for school {school}."
    return {str(uid).strip().upper() for uid in ids if str(uid).strip()}, None


def authorize_selected_student_rows(rows, school_code, output_kind="IDCARD"):
    """Validate every selected row against the current hash-bound roster snapshot."""
    if os.environ.get("SAINI_AUTH_MODE", "").strip().upper() != "MASTER_ROSTER":
        return True, "Non-master-roster mode; use existing Gate authorization."
    if str(output_kind or "").strip().upper() != "IDCARD":
        return False, "Master-roster mode authorizes IDCARD only; OCR Gate required for other outputs."
    allowed, error = _master_roster_school_ids(school_code)
    if error:
        return False, error
    seen = set()
    for row in rows:
        row_school = str(row.get("school_code", "")).strip().upper()
        uid = str(row.get("student_unique_id", "")).strip().upper()
        if row_school != str(school_code or "").strip().upper():
            return False, "Selected row has missing or wrong school_code."
        if not uid or uid in {"NAN", "NONE", "NULL"}:
            return False, "Selected student has missing student_unique_id."
        if uid in seen:
            return False, f"Duplicate selected student_unique_id blocked: {uid}"
        if uid not in allowed:
            return False, f"Student ID is not in the authorized unique roster: {uid}"
        seen.add(uid)
    return True, "Master-roster row authorization passed."


def authorize_school_generation(school_code, output_kind=None):
    """Use Mode B roster authorization only for IDCARD; all other modes use Option C Gate."""
    school_code = str(school_code or "").strip()
    if not school_code:
        return False, "Missing school_code."
    if os.environ.get("SAINI_AUTH_MODE", "").strip().upper() == "MASTER_ROSTER":
        if str(output_kind or "").strip().upper() != "IDCARD":
            return False, "Mode B master-roster authorization permits IDCARD only; OCR Gate evidence is required for other outputs."
        allowed, error = _master_roster_school_ids(school_code)
        return (False, error) if error else (True, "Hash-bound master-roster authorization passed.")

    journal_path, batch_id, fingerprint, error = get_gate_configuration()
    if error:
        return False, error
    return authorize(
        journal_path,
        expected_batch_id=batch_id,
        expected_school_code=school_code,
        expected_fingerprint=fingerprint,
    )


def get_gate_configuration():
    """Read Option C Gate evidence; never invent run evidence."""
    journal_value = os.environ.get("SAINI_GATE_JOURNAL", "").strip()
    batch_id = os.environ.get("SAINI_GATE_BATCH_ID", "").strip()
    fingerprint = os.environ.get("SAINI_GATE_FINGERPRINT", "").strip()
    if not journal_value or not batch_id or not fingerprint:
        return None, None, None, (
            "Gate configuration missing. Set SAINI_GATE_JOURNAL, "
            "SAINI_GATE_BATCH_ID and SAINI_GATE_FINGERPRINT from validated run evidence."
        )
    journal_path = Path(journal_value)
    if not journal_path.is_file():
        return None, None, None, f"Gate journal file not found: {journal_path}"
    return journal_path, batch_id, fingerprint, None


def _validate_school_image_roster(school, image_paths):
    """In Mode B, reject any card image not named for an authorized student ID."""
    if os.environ.get("SAINI_AUTH_MODE", "").strip().upper() != "MASTER_ROSTER":
        return True, "Existing OCR Gate mode."
    allowed, error = _master_roster_school_ids(school)
    if error:
        return False, error
    bad = []
    for path in image_paths:
        uid = normalize_key(os.path.basename(path))
        if not uid or uid not in allowed:
            bad.append(os.path.basename(path))
            if len(bad) >= 10:
                break
    if bad:
        return False, "Images not linked to authorized student IDs (first 10): " + ", ".join(bad)
    return True, "All card images belong to authorized roster IDs."

class IDCardGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("ID Card Generator - DP Public School")
        self.root.geometry("1350x900")

        self.config_df = load_guarded_config(EXCEL_CONFIG, sheet_name='Sheet1')
        self.student_df = pd.DataFrame()
        self.temp_dir = None

        Label(root, text="Select Schools (Ctrl for multiple):", font=("Arial", 12)).pack(pady=10)
        self.school_listbox = Listbox(root, selectmode="extended", height=6, font=("Arial", 11))
        for school in self.config_df['school_code'].dropna().unique():
            self.school_listbox.insert(END, school)
        self.school_listbox.pack(pady=5)

        cutoff_frame = Frame(root)
        cutoff_frame.pack(pady=20)
        Label(cutoff_frame, text="Cut-off Date:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=20)
        self.date_picker = DateEntry(cutoff_frame, width=12, background='darkblue', foreground='white',
                                     borderwidth=3, date_pattern='m/d/y', font=("Arial", 12))
        self.date_picker.grid(row=0, column=1, padx=10)
        self.date_picker.set_date(datetime.now())

        Label(cutoff_frame, text="Time (HH:MM):", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=20)
        self.time_entry = Entry(cutoff_frame, width=10, font=("Arial", 12))
        self.time_entry.grid(row=0, column=3, padx=10)
        self.time_entry.insert(0, "00:00")

        Label(cutoff_frame, text="← Calendar से तारीख चुनें\nसमय HH:MM में लिखें या खाली छोड़ें → अपने-आप", 
              fg="darkgreen", font=("Arial", 10, "italic")).grid(row=1, column=0, columnspan=4, pady=10)

        Button(root, text="Load Students (चुनी गई cut-off के बाद वाले रिकॉर्ड)", bg="green", fg="white",
               font=("Arial", 14, "bold"), width=45, command=self.load_students).pack(pady=20)

        reset_frame = Frame(root)
        reset_frame.pack(pady=10)
        Button(reset_frame, text="Reset Cut-off (सभी पुराने और नए रिकॉर्ड दिखाएँ)", 
               bg="purple", fg="white", font=("Arial", 12, "bold"), width=55, command=self.reset_cutoff).pack()

        select_all_frame = Frame(root)
        select_all_frame.pack(pady=10)
        Button(select_all_frame, text="Select All Students (सभी विद्यार्थियों को चुनें)", 
               bg="darkgreen", fg="white", font=("Arial", 12, "bold"), width=55, command=self.select_all_students).pack()

        self.tree = ttk.Treeview(root, columns=list(pd.read_excel(EXCEL_STUDENT, nrows=1).columns), show="headings", selectmode="extended")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.pack(fill=BOTH, expand=True, pady=10)

        button_frame = Frame(root)
        button_frame.pack(pady=20)

        Button(button_frame, text="Edit Configs", bg="blue", fg="white", command=self.edit_configs).pack(side=LEFT, padx=15)
        Button(button_frame, text="Generate IDs for Selected Students", bg="orange", fg="white", command=self.generate_selected_ids).pack(side=LEFT, padx=15)
        Button(button_frame, text="Generate ID CARD PDFs (2×5 A4 Portrait)", bg="#006400", fg="white", font=("Arial", 12, "bold"), command=self.generate_idcard_pdfs).pack(side=LEFT, padx=15)
        Button(button_frame, text="Generate ADMIT CARD PDFs (5×5, 19×13 Landscape)", bg="#8B0000", fg="white", font=("Arial", 12, "bold"), command=self.generate_admitcard_pdfs).pack(side=LEFT, padx=15)
        Button(button_frame, text="Generate MARKSHEETS for Selected", bg="#8B4513", fg="white", font=("Arial", 12, "bold"), command=self.generate_selected_marksheets).pack(side=LEFT, padx=15)
        Button(button_frame, text="Generate MARKSHEET PDFs (1×1 A4 Portrait)", bg="#A52A2A", fg="white", font=("Arial", 12, "bold"), command=self.generate_marksheet_pdfs).pack(side=LEFT, padx=15)

    def create_blank_image(self):
        if self.temp_dir is None:
            self.temp_dir = tempfile.mkdtemp()
        blank_path = os.path.join(self.temp_dir, "blank.png")
        Image.new("RGB", (1, 1), (255, 255, 255)).save(blank_path)
        return blank_path

    def select_all_students(self):
        self.tree.selection_set(self.tree.get_children())
        total = len(self.tree.get_children())
        messagebox.showinfo("Success", f"कुल {total} विद्यार्थी चुने गए।")

    def load_students(self):
        selected_schools = [self.school_listbox.get(i) for i in self.school_listbox.curselection()]
        if not selected_schools:
            messagebox.showwarning("Warning", "कृपया स्कूल चुनें।")
            return

        date_str = self.date_picker.get()
        time_str = self.time_entry.get().strip()
        full_str = f"{date_str} {time_str or '00:00'}"

        last_ts = None
        if time_str:
            try:
                last_ts = pd.to_datetime(full_str, format='%m/%d/%Y %H:%M')
            except:
                messagebox.showwarning("Warning", "समय गलत है। HH:MM format में लिखें।")
                return
        else:
            if os.path.exists(LAST_TS_FILE):
                with open(LAST_TS_FILE, 'r') as f:
                    last_ts = pd.to_datetime(f.read().strip(), errors='coerce')

        # ðŸ”¥ðŸ”¥ MAIN FIX - String dtype + Mobile Fix ðŸ”¥ðŸ”¥
        self.student_df = pd.read_excel(EXCEL_STUDENT, dtype=str)
        
        # Mobile number final fix
        if 'mob_number' in self.student_df.columns:
            def fix_mob(x):
                if pd.isna(x) or str(x).strip().lower() in ['nan', '', 'none']:
                    return ""
                x = str(x).strip().replace('.0', '').replace('.00', '').replace('.000', '')
                if '.' in x:
                    x = x.split('.')[0]
                x = ''.join(filter(str.isdigit, x))
                return x
            self.student_df['mob_number'] = self.student_df['mob_number'].apply(fix_mob)

        self.student_df['timestamp'] = self.student_df['timestamp'].apply(parse_timestamp)

        filtered = self.student_df[self.student_df['school_code'].isin(selected_schools) & self.student_df['timestamp'].notna()]
        if last_ts is not None:
            filtered = filtered[filtered['timestamp'] > last_ts]

        self.tree.delete(*self.tree.get_children())
        for _, row in filtered.iterrows():
            self.tree.insert("", "end", values=list(row))

        messagebox.showinfo("Success", f"{len(filtered)} रिकॉर्ड लोड हुए।")

        filtered = self.student_df[self.student_df['school_code'].isin(selected_schools) & self.student_df['timestamp'].notna()]
        if last_ts is not None:
            filtered = filtered[filtered['timestamp'] > last_ts]

        self.tree.delete(*self.tree.get_children())
        for _, row in filtered.iterrows():
            self.tree.insert("", "end", values=list(row))

        messagebox.showinfo("Success", f"{len(filtered)} रिकॉर्ड लोड हुए।")

    def reset_cutoff(self):
        target = os.path.realpath(os.path.abspath(LAST_TS_FILE))
        allowed_roots = [
            os.path.realpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "ID_CARD_PROJECT", "INPUT"
            )),
            os.path.realpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "ID_CARD_PROJECT", "OUTPUT"
            )),
        ]

        if os.path.basename(target).casefold() != "last_processed_timestamp.txt":
            messagebox.showwarning(
                "Blocked",
                "Cut-off reset रोका गया: file का नाम अनुमत नहीं है।"
            )
            return

        try:
            permitted = any(
                os.path.commonpath([root, target]).casefold()
                == root.casefold()
                for root in allowed_roots
            )
        except (ValueError, OSError):
            permitted = False

        if not permitted:
            messagebox.showwarning(
                "Blocked",
                "Cut-off reset रोका गया: timestamp file अनुमत INPUT/OUTPUT folders से बाहर है।"
            )
            return

        if os.path.isfile(target):
            os.remove(target)
            messagebox.showinfo("Success", "Cut-off reset हो गया।")
        else:
            messagebox.showinfo("Info", "कोई cut-off file नहीं मिली।")
    def edit_configs(self):
        from config_editor import open_config_editor
        open_config_editor()

    def _select_bsm_config(self):
        """First eligible BSM row, or a fail-closed stop. Non-BSM callers stay unchanged."""
        try:
            return select_bsm_row(self.config_df)
        except ConfigSelectionError as exc:
            messagebox.showerror("BSM Config", str(exc))
            return "STOP"

    def generate_selected_ids(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "कृपया विद्यार्थी चुनें।")
            return

        selected_rows = [
            dict(zip(self.tree["columns"], self.tree.item(item)["values"]))
            for item in selected_items
        ]
        selected_schools = {str(row.get("school_code", "")).strip() for row in selected_rows}
        if "" in selected_schools or len(selected_schools) != 1:
            messagebox.showerror("Gate Scope", "Gate authorization के लिए एक ही school_code के विद्यार्थी चुनें।")
            return
        school_for_gate = next(iter(selected_schools))
        gate_ok, gate_reason = authorize_selected_student_rows(selected_rows, school_for_gate, "IDCARD")
        if not gate_ok:
            messagebox.showerror("Authorization Reject", gate_reason)
            return
        if os.environ.get("SAINI_AUTH_MODE", "").strip().upper() != "MASTER_ROSTER":
            gate_ok, gate_reason = authorize_school_generation(school_for_gate, "IDCARD")
            if not gate_ok:
                messagebox.showerror("Gate Reject", gate_reason)
                return

        generated = 0

        for item in selected_items:
            values = self.tree.item(item)['values']
            student_data = dict(zip(self.tree["columns"], values))
            
            school = str(student_data.get('school_code', '')).strip()
            if not school:
                continue

            if school.upper() == "BSM":
                config = self._select_bsm_config()
                if config == "STOP":
                    return
            else:
                config_row = self.config_df[self.config_df['school_code'].astype(str).str.strip() == school]
                if config_row.empty:
                    continue
                config = config_row.iloc[0]
            template_path = str(config.get('template', '')).strip()

            if not template_path or not os.path.exists(template_path):
                continue

            school_dir = os.path.join(OUTPUT_DIR, school, "FRONT")
            os.makedirs(school_dir, exist_ok=True)
            
            output_path = os.path.join(school_dir, f"{student_data.get('student_unique_id','Unknown')}.png")

            if os.path.exists(output_path):
                messagebox.showwarning("Output Exists", f"à¤®à¥Œà¤œà¥‚à¤¦à¤¾ ID image overwrite à¤¨à¤¹à¥€à¤‚ à¤•à¥€ à¤—à¤ˆ:\\n{output_path}")
                continue

            if generate_front_card(template_path, output_path, student_data, config):
                generated += 1

        if generated > 0:
            messagebox.showinfo("Success", f"{generated} ID कार्ड बनाए गए।")
        else:
            messagebox.showwarning("Warning", "कोई ID Card नहीं बना।")

    def process_group(self, schools, kind_name, pagesize, cols, rows):
        single_fronts = []
        double_pairs = []
        has_double = False

        for school in schools:
            if str(school or "").strip().upper() == "BSM":
                config = self._select_bsm_config()
                if config == "STOP":
                    return False
            else:
                config = self.config_df[self.config_df['school_code'] == school].iloc[0]
            card_type = config.get('CARD_TYPE', 'SINGLE').upper()
            front_dir = os.path.join(OUTPUT_DIR, school, "FRONT")
            fronts = sorted_images(front_dir)
            roster_ok, roster_reason = _validate_school_image_roster(school, fronts)
            if not roster_ok:
                messagebox.showerror("Roster Validation", f"{school}: {roster_reason}")
                return False

            if card_type == "DOUBLE":
                has_double = True
                back_dir = os.path.join(OUTPUT_DIR, school, "BACK")
                backs = sorted_images(back_dir)
                roster_ok, roster_reason = _validate_school_image_roster(school, backs)
                if not roster_ok:
                    messagebox.showerror("Roster Validation", f"{school}: {roster_reason}")
                    return False
                pairs = collect_pairs(fronts, backs)
                if not pairs and fronts:
                    messagebox.showwarning("Warning", f"{school} (DOUBLE) के लिए BACK images नहीं मिलीं।")
                    return False
                double_pairs.extend(pairs)
            else:
                single_fronts.extend(fronts)

        if not single_fronts and not double_pairs:
            messagebox.showwarning("Warning", "कोई images नहीं मिलीं।")
            return False

        front_imgs = single_fronts + [p["front_path"] for p in double_pairs]
        back_imgs = []
        if has_double:
            blank = self.create_blank_image()
            back_imgs = [blank] * len(single_fronts) + [p["back_path"] for p in double_pairs]

        N = len(front_imgs)
        max_per_part = 250
        for part in range(0, N, max_per_part):
            chunk_f = front_imgs[part:part+max_per_part]
            chunk_b = back_imgs[part:part+max_per_part] if back_imgs else []
            pdf_name = f"COMBINED_{kind_name}S.pdf" if part == 0 else f"COMBINED_{kind_name}S_part{(part//max_per_part)+1}.pdf"
            generate_pdf_layout(chunk_f, chunk_b, os.path.join(OUTPUT_DIR, pdf_name), pagesize, cols, rows)

        return True
    def generate_idcard_pdfs(self):
        selected = [self.school_listbox.get(i) for i in self.school_listbox.curselection()]

        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return
        if len(selected) != 1:
            messagebox.showwarning("Gate Scope", "Gate authorization à¤•à¥‡ à¤²à¤¿à¤ à¤à¤• à¤¬à¤¾à¤° à¤®à¥‡à¤‚ à¤•à¥‡à¤µà¤² à¤à¤• à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚à¥¤")
            return
        gate_ok, gate_reason = authorize_school_generation(selected[0], "IDCARD")
        if not gate_ok:
            messagebox.showerror("Gate Reject", gate_reason)
            return
        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return

        id_schools = []
        for s in selected:
            try:
                if str(s or "").strip().upper() == "BSM":
                    row = self._select_bsm_config()
                    if row == "STOP":
                        return
                else:
                    row = self.config_df[self.config_df['school_code'] == s].iloc[0]
                card_value = str(row.get('CARD', '')).strip().upper()
                if card_value in ['IDCARD', '']:
                    id_schools.append(s)
            except:
                pass

        if not id_schools:
            messagebox.showinfo("Info", "चुने गए स्कूलों में कोई IDCARD नहीं है।")
            return

        portrait_a4 = A4
        
        # 2Ã—5 layout for exact 85mm Ã— 55mm cards
        success = self.process_group(id_schools, "IDCARD", portrait_a4, cols=2, rows=5)
        
        if success:
            messagebox.showinfo("Success", 
                "✓ IDCARD PDFs बन गए!\n\n"
                "Target Size: 85mm Ã— 55mm\n"
                "Layout: 2 Columns × 5 Rows (10 कार्ड प्रति A4)\n\n"
                "प्रिंट करते समय Actual Size या 100% चुनें!")


    def generate_admitcard_pdfs(self):
        selected = [self.school_listbox.get(i) for i in self.school_listbox.curselection()]

        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return
        if len(selected) != 1:
            messagebox.showwarning("Gate Scope", "Gate authorization à¤•à¥‡ à¤²à¤¿à¤ à¤à¤• à¤¬à¤¾à¤° à¤®à¥‡à¤‚ à¤•à¥‡à¤µà¤² à¤à¤• à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚à¥¤")
            return
        gate_ok, gate_reason = authorize_school_generation(selected[0], "ADMITCARD")
        if not gate_ok:
            messagebox.showerror("Gate Reject", gate_reason)
            return
        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return

        admit_schools = []
        for s in selected:
            try:
                if str(s or "").strip().upper() == "BSM":
                    row = self._select_bsm_config()
                    if row == "STOP":
                        return
                else:
                    row = self.config_df[self.config_df['school_code'] == s].iloc[0]
                card_value = str(row.get('CARD', '')).strip().upper()
                if card_value == 'ADMITCARD':
                    admit_schools.append(s)
            except:
                pass

        if not admit_schools:
            messagebox.showinfo("Info", "चुने गए स्कूलों में कोई ADMITCARD नहीं है। Excel के CARD column में ADMITCARD होना चाहिए।")
            return

        admit_pagesize = (19*72, 13*72)
        if self.process_group(admit_schools, "ADMITCARD", admit_pagesize, 5, 5):
            messagebox.showinfo("Success", "ADMITCARD PDFs बन गए! (19×13 Landscape, 5×5 - 25 Cards/Sheet)")


    def generate_selected_marksheets(self):
        if os.environ.get("SAINI_AUTH_MODE", "").strip().upper() == "MASTER_ROSTER":
            messagebox.showerror("Authorization Reject", "Mode B master-roster authorization permits IDCARD only. Use the verified OCR Gate for marksheets.")
            return
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "मार्कशीट बनाने के लिए विद्यार्थी चुनें।")
            return

        generated = 0
        for item in selected_items:
            values = self.tree.item(item)['values']
            student_data = dict(zip(self.tree["columns"], values))
            school = student_data.get('school_code', '')

            if str(school or "").strip().upper() == "BSM":
                config = self._select_bsm_config()
                if config == "STOP":
                    return
                if str(config.get('CARD', '')).upper() != 'MARKSHEET':
                    continue
            else:
                config_row = self.config_df[self.config_df['school_code'] == school]
                if config_row.empty or str(config_row.iloc[0].get('CARD', '')).upper() != 'MARKSHEET':
                    continue
                config = config_row.iloc[0]
            template_path = str(config.get('template', ''))
            if not template_path or not os.path.exists(template_path):
                messagebox.showwarning("Warning", f"{school} के लिए मार्कशीट टेम्पलेट नहीं मिला।")
                continue

            school_dir = os.path.join(OUTPUT_DIR, school, "MARKSHEET")
            os.makedirs(school_dir, exist_ok=True)
            output_path = os.path.join(school_dir, f"{student_data.get('student_name','Unknown')}_{student_data.get('class','')}_MARKSHEET.png")

            if generate_marksheet(template_path, output_path, student_data, config):
                generated += 1

        if generated > 0:
            messagebox.showinfo("Success", f"{generated} मार्कशीट सफलतापूर्वक बनीं।")
        else:
            messagebox.showwarning("Warning", "कोई मार्कशीट नहीं बनी।")


    def generate_marksheet_pdfs(self):
        selected = [self.school_listbox.get(i) for i in self.school_listbox.curselection()]

        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return
        if len(selected) != 1:
            messagebox.showwarning("Gate Scope", "Gate authorization à¤•à¥‡ à¤²à¤¿à¤ à¤à¤• à¤¬à¤¾à¤° à¤®à¥‡à¤‚ à¤•à¥‡à¤µà¤² à¤à¤• à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚à¥¤")
            return
        gate_ok, gate_reason = authorize_school_generation(selected[0], "MARKSHEET")
        if not gate_ok:
            messagebox.showerror("Gate Reject", gate_reason)
            return
        if not selected:
            messagebox.showwarning("Warning", "à¤¸à¥à¤•à¥‚à¤² à¤šà¥à¤¨à¥‡à¤‚!")
            return

        marks_schools = []
        for s in selected:
            try:
                if str(s or "").strip().upper() == "BSM":
                    row = self._select_bsm_config()
                    if row == "STOP":
                        return
                else:
                    row = self.config_df[self.config_df['school_code'] == s].iloc[0]
                card_value = str(row.get('CARD', '')).strip().upper()
                if card_value == 'MARKSHEET':
                    marks_schools.append(s)
            except:
                pass

        if not marks_schools:
            messagebox.showinfo("Info", "चुने गए स्कूलों में कोई MARKSHEET नहीं है।")
            return

        single_fronts = []
        for school in marks_schools:
            marks_dir = os.path.join(OUTPUT_DIR, school, "MARKSHEET")
            fronts = sorted_images(marks_dir)
            single_fronts.extend(fronts)

        if not single_fronts:
            messagebox.showwarning("Warning", "कोई marksheet images नहीं मिलीं।")
            return

        portrait_a4 = A4
        generate_pdf_layout(single_fronts, [], os.path.join(OUTPUT_DIR, "COMBINED_MARKSHEETS.pdf"), portrait_a4, 1, 1)
        messagebox.showinfo("Success", "MARKSHEET PDFs बन गए! (A4 Portrait - 1 प्रति शीट)")

if __name__ == "__main__":
    root = Tk()
    try:
        app = IDCardGenerator(root)
        root.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Program crash ho gaya!\n\nError: {str(e)}")
        input("Press Enter to exit...")   # Window band hone se rokne ke liye
    finally:
        if app.temp_dir and os.path.exists(app.temp_dir):
            shutil.rmtree(app.temp_dir, ignore_errors=True)
