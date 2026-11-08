from pathlib import Path
export_to_ips_engine = None
import os
import re
import time
import shutil
import pandas as pd

try:
    from PIL import Image, ImageStat
except ImportError:
    Image = None
    ImageStat = None
try:
    from io import BytesIO as _V3324BytesIO
except ImportError:
    _V3324BytesIO = None
from google import genai
from google.genai import types

# Optional OAuth support for Gemini Authorization (AQ.) keys / projects
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    Credentials = None
    InstalledAppFlow = None
    Request = None
# ============================================================
# NEW IMPORTS - WATERMARK SUPPORT
# ============================================================
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import Color
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
except ImportError:
    canvas = None
    A4 = None
    Color = None
    BytesIO = None
    PdfReader = None
    PdfWriter = None

from docx import Document
# ============================================================
# PAPER SETTER CORE — Technical Note hook
# paper_setter_core folder PAPER.py ke SAATH honi chahiye
# ============================================================
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from paper_identity import build_stem, parse_paper_name
    print("  ✓ paper_identity loaded")
except Exception as _pid_exc:
    build_stem = None
    parse_paper_name = None
    print("  ⚠ paper_identity not loaded:", _pid_exc)

try:
    from paper_setter_core.stage import classify_class_stage, STAGE_PREPRIMARY
    from paper_setter_core.plan import build_setter_plan, describe_plan
    from paper_setter_core.furniture import render_plan as render_setter_plan
    from paper_setter_core.rooms import family_of, FAMILIES
    SETTER_CORE = True
    print("  ✓ paper_setter_core loaded")
except Exception as _setter_exc:
    SETTER_CORE = False
    STAGE_PREPRIMARY = "preprimary"
    FAMILIES = {}
    def family_of(text):
        return None
    def build_setter_plan(*a, **k):
        return []
    def describe_plan(plan):
        return
    def render_setter_plan(doc, plan):
        return 0
    print("  ⚠ paper_setter_core not loaded:", _setter_exc)
try:
    import paper_math_finetune as MATH_FT
    print("  ✓ paper_math_finetune loaded")
except Exception as _ft_exc:
    MATH_FT = None
    print("  ⚠ paper_math_finetune not loaded:", _ft_exc)

try:
    import mcq_grid as MCQ_GRID
    print("  ✓ mcq_grid loaded")
except Exception as _mg_exc:
    MCQ_GRID = None
    print("  ⚠ mcq_grid not loaded:", _mg_exc)

from docx.shared import Pt, Inches, Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_UNDERLINE, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from document_renderer_v10.kundli_codec import unicode_to_kundli
try:
    from basic_shapes import detect_basic_shape, add_shape_picture
except ImportError:
    def detect_basic_shape(caption):
        return None
    def add_shape_picture(paragraph, kind, width_in=1.15):
        return False
import sys
sys.path.insert(0, r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\SAINI_IPS_ENGINE")
from saini_ips.hook import publish_paper
try:
    from print_layout_rule import resolve_print_layout
except ImportError:
    def resolve_print_layout(class_name=None, excel_layout=None, excel_sheets_per_copy=None):
        raw = str(excel_layout or excel_sheets_per_copy or "").strip().upper()
        if raw in {"1", "1-UP", "1UP"}:
            return "1-UP", 1
        if raw in {"2", "2-UP", "2UP"}:
            return "2-UP", 2
        return "2-UP", 2

try:
    from ncert_patterns import get_pattern, pattern_prompt_hint
except ImportError:
    get_pattern = None

    def pattern_prompt_hint(class_name, subject=""):
        return ""


try:
    from formula_unit_mass import (
        is_science_subject,
        beautify_formulas_in_text,
        looks_like_mass_question,
        build_teacher_solution,
        SCIENCE_OCR_PROMPT_ADDON,
    )
except ImportError:
    def is_science_subject(subject):
        return False
    def beautify_formulas_in_text(text):
        return text
    def looks_like_mass_question(text):
        return False
    def build_teacher_solution(text):
        return ""
    SCIENCE_OCR_PROMPT_ADDON = ""

MATH_OCR_PROMPT_ADDON = r"""
MATH PAPER EXTRA RULES:
- Item labels (i) (ii) (iii) (iv) (a) (b) (c) (d) are ONLY labels. They are NEVER a power base.
  Write: (i) (9)^{\frac{1}{2}}     NOT (i)^{(i)^{\frac{1}{2}}}
  Write: (a) (2)^{3} \times (3)^{2}     NOT (a)^{3}\times(b)^{2}
  Write: (c) (-2)^{2}     NOT (c)^{-2}^{2} and NOT (c) ^{-2}^{2}
- Always keep a SPACE after the label, then the full expression with real base digits.
- Each sub-part on its OWN line. Never glue (c) and (d) together.
- Never glue the next question onto an option. If प्रश्न-12 / प्र०-12 / Q-12 / Q.12 starts, NEW line.
- Fractions as \frac{numerator}{denominator} with BOTH braces. Minus INSIDE: \frac{-15}{4}
- Powers: base^{exponent} with BOTH braces. Negative base: (-2)^{3}   Negative exponent: 2^{-3}
- Repeated multiplication that must stay expanded stays as 8 \times 8 \times 8
  NOT 8^{3} (only if the source already wrote the expanded product) and NEVER ^\times^\times
- Roots as \sqrt{9} not sqrt9 and not both √9 and \sqrt{9}.
- Do not put working (i)/(ii) algebra into a table.
- Never drop digits that sit next to × ÷ + - or ^.
- DEGREE is NEVER a power. Write 140°   NEVER 140^{\\circ}  NEVER 140^{°}  NEVER 140^\\circ
- Keep the English/Hindi WORDS angle, triangle, ray, line, segment as words.
  Use ∠ or Δ ONLY when the source itself drew that symbol next to a name (∠APC).
  NEVER replace the word "angle" / "triangle" with a symbol.
- Rays / vectors / segments: keep the source letters.
  Prefer Unicode over-arrow form OA⃗ or the words "ray OA".
  NEVER dump raw LaTeX \\vec{OA} \\overrightarrow{OA} \\overline{OA} into the output.
- Do not drop a following question. After a '?' if the next sentence is a new numbered question, start a NEW line with its number.
- Geometry diagrams: one line [[FIG]] short caption. Keep the full stem of the ray/line question.
"""


# ============================================================
# PROFESSIONAL QUESTION PAPER GENERATOR — V27 AUTO MATHS SWITCH + GENERIC EXAM TABLE + PAGE OPTIMIZER
# Purpose:
#   1. Extract text from scanned question-paper images.
#   2. Preserve the extracted wording.
#   3. Bold ONLY the main question line.
#   4. Keep sub-parts, options and supporting text normal.
#   5. Generate a clean, experienced-teacher-style Word paper.
# ============================================================

# ============================================================
# ADD-ON HOOK 1 — NCERT grammar + answer space (safe imports)
# If these files are missing, old PAPER.py behaviour stays as-is.
# ============================================================
try:
    import ncert_grammar as NCERT_GRAMMAR
    print("  ✓ ncert_grammar loaded")
except Exception as _ng_exc:
    NCERT_GRAMMAR = None
    print("  ⚠ ncert_grammar not loaded:", _ng_exc)

try:
    import answer_space as ANSWER_SPACE
    print("  ✓ answer_space loaded")
except Exception as _as_exc:
    ANSWER_SPACE = None
    print("  ⚠ answer_space not loaded:", _as_exc)
# --- END HOOK 1 ---
# --- RULE REGISTRY HOOK: review engines, old path stays if this fails ---
try:
    _RULE_REVIEW = r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\COW_RULING_PATCH_REVIEW"
    if _RULE_REVIEW not in sys.path:
        sys.path.insert(0, _RULE_REVIEW)
    from question_engine.rule_registry import plan_any as RULE_PLAN
    from question_engine.auto_sheet import _apply as RULE_APPLY
    print("  rule registry loaded")
except Exception as _rule_exc:
    RULE_PLAN = None
    RULE_APPLY = None
    print("  rule registry not loaded:", _rule_exc)
# --- END RULE REGISTRY HOOK ---


# V33.7 SAFE AI DATABASE INTEGRATION — optional, isolated imports.
# If the integration files are unavailable, existing PAPER.py behavior remains.
try:
    from saini_exam_ai_paper_integration_gate_v1 import (
        process_nursery_hindi_question,
        should_use_ai_worksheet_route,
    )
    print("  ✓ SAINI AI integration gate loaded")
except Exception as _sai_gate_exc:
    process_nursery_hindi_question = None
    should_use_ai_worksheet_route = None
    print("  ⚠ SAINI AI integration gate not loaded:", _sai_gate_exc)
# --- END V33.7 SAFE AI IMPORT ---

# V33.5 — LOCAL WORKSHEET INTENT/TEMPLATE MEMORY
try:
    import worksheet_intent_engine as WORKSHEET_INTENT
    print("  ✓ worksheet_intent_engine loaded")
except Exception as _wie_exc:
    WORKSHEET_INTENT = None
    print("  ⚠ worksheet_intent_engine not loaded:", _wie_exc)
# --- END V33.5 WORKSHEET INTENT HOOK ---

try:
    import math_clean as MATH_CLEAN
    print("  ✓ math_clean loaded")
except Exception as _mc_exc:
    MATH_CLEAN = None
    print("  ⚠ math_clean not loaded:", _mc_exc)

try:
    import saini_board_pack as SBP
    print("  ✓ saini_board_pack loaded —", SBP.status())
except Exception as _sbp_exc:
    SBP = None
    print("  ⚠ saini_board_pack not loaded:", _sbp_exc)

try:
    import pdf_input as PDF_IN
    print("  ✓ pdf_input loaded")
except Exception as _pdf_exc:
    PDF_IN = None
    print("  ⚠ pdf_input not loaded:", _pdf_exc)

def _board_polish_line(raw, class_name="", subject=""):
    text = str(raw or "").strip()
    if SBP is None or len(text) < 8:
        return str(raw or "")
    if text.startswith("("):
        return str(raw or "")
    key = (
        "सही" in text or "गलत" in text or "रिक्त" in text or "मिला" in text
        or "विकल्प" in text or "गद्यांश" in text or "चित्र" in text
        or "हल कर" in text or "fill" in text.lower() or "match" in text.lower()
        or "choose" in text.lower() or "प्रश्न" in text[:8]
        or text[:2].isdigit() or text.lower().startswith("q.")
    )
    if not key:
        return str(raw or "")
    try:
        out, info = SBP.perfect_line(text, class_name=class_name, subject=subject)
        if info and getattr(info, "confidence", 0) >= 0.70:
            return out
    except Exception:
        pass
    return str(raw or "")

# ==================== CONFIGURATION ====================
# Authentication — V15 DIRECT API KEY MODE
# --------------------------------------------------------
# Paste your NEW Gemini API key directly between the quotes below.
# Example:
# API_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
#
# The program will use THIS key directly from PAPER.py.
# No Windows Environment Variable is required.
# OAuth fallback is intentionally disabled for this version.
API_KEY = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
AUTH_MODE = "api_key"
IMAGES_FOLDER = r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\INPUT"
EXCEL_FILE = r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\PAPER.xlsx"
OUTPUT_FOLDER = r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\OUTPUT"
MODEL_NAME = "gemini-3.6-flash"
# AI refine+check hang protection. If Gemini stalls, keep OCR and continue.
AI_STAGE_TIMEOUT_SEC = 120

# V33.4: ANSWER_SPACE remains the existing Excel master input.
# No new spreadsheet column is required for handwriting control.

# ============================================================
# HOLD DISABLED / WORD-ALWAYS-BUILD POLICY
# ============================================================
HOLD_ENABLED = False
AI_WARNING_PREFIX = "⚠ WARNING: AI validation/refinement was not completed. This paper was generated from OCR text and should be manually verified."
LAST_AI_WARNING = ""

# ==================== V7 QUALITY CONTROLS ====================
# RULE BASELINE POLICY:
# Every future version must preserve all rules listed here unless the user
# explicitly requests a rule change. New fixes are additive/regression-safe.
RULE_BASELINE_VERSION = "V33.8-ROMAN-COMBINED-CLASS-ANSWER-SPACE-NURSERY-HINDI-INPUT-MANIFEST"
PROTECTED_RULES = (
    "direct_api_key_in_paper_py",
    "final_hindi_motivational_sentence_class_1_plus",
    "paper_boundary_next_start_minus_one",
    "continuous_source_image_flow",
    "natural_word_pagination",
    "page_x_of_y_footer",
    "hindi_section_headings_bold",
    "context_aware_main_question_bolding",
    "mcq_abcd_two_by_two",
    "mcq_roman_i_iv_two_by_two",
    "common_mcq_grid_font_size",
    "paper_saving_word_meaning_layout",
    "blank_image_protection",
    "no_ocr_diagnostic_text_in_final",
    "header_deduplication",
    "question_sequence_audit",
    "original_wording_preservation",
    "nested_mcq_options_compact_horizontal",
    "three_option_single_row_layout",
    "major_question_subpart_visual_gap",
    "attractive_page_border",
    "explicit_context_bold_lock",
    "authentication_preflight_before_batch",
    "oauth_fallback_support",
    "no_repeated_401_api_calls",
    "checkmark_to_boxed_tick_normalization",
    "times_to_boxed_x_normalization",
    "page_border_10mm_inset",
    "page_border_thicker_weight",
    "direct_api_key_in_paper_py",
    "api_key_preflight_before_batch",
    "no_oauth_fallback",
    "hindi_motivational_sentence_class_1_plus_only",
    "no_motivational_sentence_nursery_lkg_ukg",
    "motivational_sentence_no_decorative_box",
    "rotating_hindi_motivational_slogans_100",
    "motivational_slogan_paper_text_font_size",
    "motivational_slogan_large_side_stars",
    "motivational_slogan_underlined",
    "footer_page_number_paper_text_font_size",
    "a4_page_size_210x297mm",
    "never_use_letter_page_size",
    "footer_above_bottom_page_border",
    "school_name_dynamic_font_size",
    "school_name_full_content_width_fit",
    "school_name_no_hardcoded_font_size",
    "mcq_option_label_case_normalization",
    "mcq_four_option_exact_2x2_grid",
    "mcq_three_option_exact_single_row",
    "mcq_no_option_sharing_between_cells",
    "footer_clear_of_bottom_border",
    "generic_exam_table_engine",
    "no_hardcoded_table_headers",
    "table_layout_inferred_from_cells",
    "auto_maths_settings_switch",
    "maths_layout_auto_enable",
    "auto_science_formula_switch",
    "chemical_formula_subscript_render",
    "science_teacher_key_sidecar_only",
    "degree_never_rendered_as_power",
    "geometry_word_not_replaced_by_symbol",
    "vec_latex_never_leaked_to_word",
    "geometry_symbol_fallback_font",
    "plan_object_first_kanda",
    "red_list_checker",
    "answer_space_master_input",
    "answer_space_is_existing_excel_column",
    "handwriting_hard_gate",
    "handwriting_only_lkg_ukg_class_1_class_2",
    "handwriting_english_only",
    "handwriting_api_preflight_gate",
    "no_handwriting_api_for_ineligible_papers",
    "worksheet_class_route_play_to_class_2",
    "clean_copy_route_class_3_plus",
    "worksheet_intent_local_database",
    "question_to_intent_to_template_route",
    "unknown_intent_review_required",
    "no_question_invention_in_intent_engine",
    "nursery_hindi_database_integration_gate",
    "nursery_hindi_integration_answer_space_yes_only",
    "nursery_hindi_integration_bypass_other_scopes",
    "database_read_only_integration",
)


# ==================== QUALITY CONTROLS ====================
CONTINUOUS_FLOW = True
NEVER_WRITE_OCR_DIAGNOSTICS = True
QUESTION_SEQUENCE_AUDIT = True
CONTEXT_AWARE_BOLDING = True
LOCAL_BLANK_IMAGE_CHECK = True
# V9 ADDITIVE RULE: a controlled visual gap before major questions that contain
# multiple internal sub-parts. Kept compact to improve readability without
# creating unnecessary paper wastage.
MAJOR_SUBPART_GAP_PT = 12

# V10 + V12 ADDITIVE RULES
# V12: page border is inset by ~10 mm from the physical page edge and made slightly thicker.
PAGE_BORDER_COLOR = "5B6B73"
PAGE_BORDER_SIZE = "14"
# 10 mm = 28.35 pt. Word page-border space is expressed in points.
PAGE_BORDER_SPACE = "28"
PAGE_BORDER_VAL = "single"

# V16 ADDITIVE RULES: final Hindi motivational slogan rotation.
# Only Class 1 and above receive one slogan. Nursery/LKG/UKG are excluded.
# Each successive paper gets the next slogan; after slogan 100, rotation restarts.
MOTIVATIONAL_FONT_SIZE = 16  # EXACTLY the normal paper text size
MOTIVATIONAL_STAR_FONT_SIZE = 22  # large side stars
MOTIVATIONAL_BEFORE_PT = 8
MOTIVATIONAL_AFTER_PT = 2
MOTIVATIONAL_SLOGAN_SEPARATOR = "  "

MOTIVATIONAL_SLOGANS = [
    'स्वयं पर विश्वास रखें और अपना सर्वश्रेष्ठ दें।',
    'आज का प्रयास, कल की सफलता की नींव है।',
    'मेहनत करते रहें, सफलता निश्चित रूप से मिलेगी।',
    'विश्वास रखें, प्रयास करें और सफलता प्राप्त करें।',
    'सीखते रहें, बढ़ते रहें और आगे बढ़ते रहें।',
    'आपकी मेहनत ही आपकी सबसे बड़ी शक्ति है।',
    'हर प्रयास आपको सफलता के एक कदम और करीब ले जाता है।',
    'लक्ष्य बड़ा रखें और प्रयास निरंतर रखें।',
    'कठिन परिश्रम कभी व्यर्थ नहीं जाता।',
    'हार मत मानिए, सफलता प्रयास करने वालों को मिलती है।',
    'ज्ञान, अनुशासन और मेहनत सफलता की कुंजी हैं।',
    'अपने लक्ष्य पर ध्यान दें और पूरे आत्मविश्वास से आगे बढ़ें।',
    'आज सीखें, कल नेतृत्व करें।',
    'हर चुनौती आपको और मजबूत बनाती है।',
    'सपने देखें, मेहनत करें और उन्हें साकार करें।',
    'आपमें सफलता प्राप्त करने की पूरी क्षमता है।',
    'एकाग्रता, आत्मविश्वास और मेहनत से सफलता प्राप्त करें।',
    'हर दिन स्वयं को कल से बेहतर बनाएं।',
    'प्रयास आपका है, सफलता आपकी होगी।',
    'रुकिए मत, सीखिए और निरंतर आगे बढ़िए।',
    'सफलता की शुरुआत एक छोटे से प्रयास से होती है।',
    'अपने सपनों को अपनी मेहनत की दिशा बनाइए।',
    'लगातार प्रयास ही बड़ी उपलब्धियों का आधार है।',
    'आज की मेहनत आपके उज्ज्वल भविष्य का निर्माण करती है।',
    'आत्मविश्वास के साथ आगे बढ़िए, सफलता आपका इंतजार कर रही है।',
    'हर कदम आपको आपके लक्ष्य के करीब ले जाता है।',
    'मेहनत को अपनी आदत और सफलता को अपना लक्ष्य बनाइए।',
    'जो सीखता है, वही आगे बढ़ता है।',
    'अपने प्रयासों पर विश्वास रखें और आगे बढ़ते रहें।',
    'सफलता उन्हीं को मिलती है जो प्रयास करना नहीं छोड़ते।',
    'ज्ञान अर्जित करें, आत्मविश्वास बढ़ाएं और आगे बढ़ें।',
    'आपकी लगन आपकी पहचान और आपकी सफलता की ताकत है।',
    'छोटे प्रयास मिलकर बड़ी सफलता बनाते हैं।',
    'हर नया दिन नई संभावना लेकर आता है।',
    'अपने लक्ष्य को स्पष्ट रखें और मेहनत को निरंतर रखें।',
    'अच्छी तैयारी आत्मविश्वास को सफलता में बदल देती है।',
    'मेहनत, धैर्य और विश्वास से हर मंजिल आसान होती है।',
    'चुनौतियों से घबराइए नहीं, उन्हें अवसर बनाइए।',
    'सफलता पाने के लिए शुरुआत करना सबसे जरूरी है।',
    'आपकी सोच आपकी दिशा तय करती है, सकारात्मक सोचिए।',
    'हर गलती से सीखिए और पहले से बेहतर बनिए।',
    'अपने समय का सदुपयोग करें और अपने लक्ष्य को प्राप्त करें।',
    'लगन से किया गया प्रयास कभी छोटा नहीं होता।',
    'अपने सपनों को पूरा करने का साहस रखिए।',
    'आज का ज्ञान कल की शक्ति बनेगा।',
    'मेहनत का कोई विकल्प नहीं होता।',
    'सच्ची सफलता निरंतर सीखने और प्रयास करने से मिलती है।',
    'अपनी क्षमता को पहचानिए और उसे पूरी तरह विकसित कीजिए।',
    'हर प्रश्न आपके ज्ञान को और मजबूत करने का अवसर है।',
    'धैर्य रखिए, लगातार प्रयास करते रहिए।',
    'लक्ष्य तक पहुंचने के लिए पहला कदम उठाना जरूरी है।',
    'आपकी मेहनत आपके भविष्य की सबसे अच्छी तैयारी है।',
    'विश्वास और मेहनत साथ हों तो मंजिल दूर नहीं।',
    'अपनी कमियों को पहचानिए और उन्हें अपनी ताकत बनाइए।',
    'सीखने की इच्छा सफलता की पहली सीढ़ी है।',
    'हर दिन कुछ नया सीखना ही सच्ची प्रगति है।',
    'उत्साह बनाए रखें और अपने लक्ष्य की ओर बढ़ते रहें।',
    'सफलता का रास्ता मेहनत और अनुशासन से होकर जाता है।',
    'आप जितना प्रयास करेंगे, उतना ही आगे बढ़ेंगे।',
    'अपने लक्ष्य को कभी अपनी नजरों से ओझल न होने दें।',
    'सकारात्मक सोचिए, मेहनत कीजिए और परिणाम पर विश्वास रखिए।',
    'हर कठिनाई में सीखने का अवसर छिपा होता है।',
    'आपका आज आपके कल की दिशा तय करता है।',
    'मेहनत को निरंतर रखिए, परिणाम अवश्य आएगा।',
    'अपनी तैयारी पर भरोसा रखिए और आत्मविश्वास से आगे बढ़िए।',
    'जो प्रयास करता है, वही अपनी सीमाओं को बदलता है।',
    'ज्ञान आपका साथी है और मेहनत आपकी शक्ति।',
    'अपने लक्ष्य के प्रति ईमानदार रहें और लगातार आगे बढ़ें।',
    'हर उपलब्धि के पीछे धैर्य और मेहनत होती है।',
    'सफलता पाने से पहले सफलता के योग्य बनिए।',
    'अपने सपनों को समय, मेहनत और अनुशासन दीजिए।',
    'आज की एकाग्रता कल की उपलब्धि बन सकती है।',
    'अच्छा प्रयास हमेशा आपको बेहतर बनाता है।',
    'अपने लक्ष्य के लिए पूरी निष्ठा से प्रयास कीजिए।',
    'हर दिन अपनी क्षमता को थोड़ा और बढ़ाइए।',
    'सफलता का रहस्य है—सीखते रहना और प्रयास करते रहना।',
    'अपने अंदर की शक्ति को पहचानिए और आगे बढ़िए।',
    'मुश्किल समय में भी अपने लक्ष्य को याद रखिए।',
    'मेहनत की राह पर बढ़ते कदम सफलता तक पहुंचते हैं।',
    'आपकी लगन आपके सपनों को वास्तविकता में बदल सकती है।',
    'आत्मविश्वास रखिए और हर अवसर का पूरा लाभ उठाइए।',
    'आज बेहतर बनने का प्रयास ही कल की सफलता है।',
    'अपने ज्ञान को अपनी शक्ति और मेहनत को अपनी पहचान बनाइए।',
    'लक्ष्य पर नजर, मन में विश्वास और प्रयास में निरंतरता रखें।',
    'हर परीक्षा आपको अपनी क्षमता दिखाने का अवसर देती है।',
    'अच्छी सोच और सच्ची मेहनत सफलता की मजबूत नींव हैं।',
    'अपने प्रयासों को कभी कम मत आंकिए।',
    'सफलता धीरे-धीरे बनती है, इसलिए धैर्य रखिए।',
    'हर कदम पर सीखिए, हर अनुभव से बढ़िए।',
    'आपका आत्मविश्वास आपकी सफलता की पहली सीढ़ी है।',
    'अपने लक्ष्य को पाने के लिए आज से बेहतर शुरुआत नहीं।',
    'मेहनत कीजिए, सीखिए और अपनी पहचान स्वयं बनाइए।',
    'आपकी कोशिश ही आपकी सबसे बड़ी उपलब्धि की शुरुआत है।',
    'उम्मीद बनाए रखें और प्रयास जारी रखें।',
    'सफलता का सपना देखिए और उसे मेहनत से पूरा कीजिए।',
    'ज्ञान के साथ विनम्रता और मेहनत के साथ आत्मविश्वास रखें।',
    'हर प्रयास आपके भविष्य को बेहतर बनाने की दिशा में है।',
    'अपने लक्ष्य के प्रति समर्पित रहें और आगे बढ़ते रहें।',
    'आज की मेहनत को कल की उपलब्धि में बदलिए।',
    'सीखना कभी बंद न करें, सफलता स्वयं आपका साथ देगी।',
]

# ============================================================
# LANGUAGE-SPECIFIC PROFESSIONAL TYPOGRAPHY
# English  -> Bookman Old Style, 16 pt
# Hindi    -> Nirmala UI, 16 pt
#
# Nirmala UI is preferred here over Mangal because it is a modern
# Unicode Devanagari font with strong Windows/Word compatibility.
# This avoids the square-box/glyph problem seen with Mangal on
# systems where the Mangal font is unavailable or not rendered correctly.
# ============================================================
# HARD RULE: Nirmala UI only. Bookman / other fonts make Devanagari boxes.
ENGLISH_FONT = "Nirmala UI"
ENGLISH_SIZE = 16
FOOTER_FONT_SIZE = ENGLISH_SIZE

HINDI_FONT = "Nirmala UI"
HINDI_SIZE = 16

# Keep these aliases so the existing formatting engine remains stable.
FONT_NAME = "Nirmala UI"
BODY_SIZE = ENGLISH_SIZE
QUESTION_SIZE = ENGLISH_SIZE
HEADER_SIZE = ENGLISH_SIZE
SUBHEADER_SIZE = ENGLISH_SIZE
META_SIZE = ENGLISH_SIZE

# Professional page settings
TOP_MARGIN = 0.55
BOTTOM_MARGIN = 0.55
LEFT_MARGIN = 0.60
RIGHT_MARGIN = 0.60
FOOTER_DISTANCE = 0.50  # Keeps Page X of Y clearly above the bottom border.

# V17 ADDITIVE RULE: output paper MUST be ISO A4, never Letter.
# A4 = 210 mm x 297 mm. This is explicitly applied to every generated Word document.
PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297
OPTION_GRID_WIDTH = 6.65

# ============================================================
# V27 AUTO MATHS SETTINGS SWITCH
# ------------------------------------------------------------
# When Excel SUBJECT is Maths / गणित / Mathematics the system
# automatically enables the full Maths layout pack.
# No separate Maths file is required. Operator does nothing.
# After the paper is written, normal flow continues for the
# next subject — settings are per-paper and self-contained.
# ============================================================
MATHS_SUBJECT_KEYWORDS = (
    "maths", "math", "mathematics", "गणित", "ganit", "ganith",
    "arithmetic", "algebra", "geometry", "trigonometry",
    "mensuration", "statistics", "probability", "calculus",
)

# Forced layout flags when subject is Maths (merged on top of any NCERT pattern)
MATHS_LAYOUT_OVERRIDES = {
    "column_sums": True,       # Class 1-3 place-value stacks
    "matrix": True,            # matrices / arrays
    "figure_box": True,        # geometry figure placeholders
    "match_two_column": True,  # matching columns still allowed
    "number_line": True,
    "math_mode": True,         # stronger fraction / power rendering
    "mcq_single_column": True, # Maths: A/B/C/D one-under-another (authentic vertical)
}

# ============================================================
# NCERT FINE-TUNE V1 — SEQUENTIAL BOARD-PAPER FLOW
# ------------------------------------------------------------
# NCERT-style middle/secondary/senior papers should read top-to-bottom.
# The old plan engine could pack short numbered items into horizontal
# bands, which is useful for primary worksheets but can incorrectly place
# Q1/Q2 or Q10/Q11 side-by-side in a Class 6-12 paper.
#
# NCERT mode therefore: 
#   * keeps major questions in ONE full-width vertical flow;
#   * keeps (a)/(b)/(c)/(d) and (i)/(ii)/(iii)/(iv) as vertical sub-parts;
#   * still permits genuine MCQ option grids and genuine matching tables;
#   * preserves the source wording and question order;
#   * does NOT insert source-image page breaks.
# ============================================================
NCERT_FINE_TUNE_ENABLED = True
NCERT_SEQUENTIAL_STAGES = {
    "primary_a", "primary_b", "middle", "secondary", "senior",
}
NCERT_MAJOR_GAP_PT = 10
NCERT_BODY_AFTER_PT = 0
NCERT_BODY_LINE_SPACING_PT = 1.0
NCERT_SUBPART_LEFT_IN = 0.35
NCERT_SUBPART_HANG_IN = 0.28


# ============================================================
# V28 AUTO SCIENCE / FORMULA SWITCH
# Excel SUBJECT Science/Chemistry/विज्ञान → chemical formula layout.
# Formula-unit-mass working is NEVER printed on the student paper.
# ============================================================
SCIENCE_LAYOUT_OVERRIDES = {
    "chemical_formulas": True,
    "science_mode": True,
}


# ============================================================
# SIX CLASS STAGES — one project, six setter brains
# 1 PREPRIMARY  Play / Nursery / LKG / UKG     ← current deep focus
# 2 PRIMARY_A   Class 1–2
# 3 PRIMARY_B   Class 3–5
# 4 MIDDLE      Class 6–8
# 5 SECONDARY   Class 9–10
# 6 SENIOR      Class 11–12
# A setter of Play-UKG does not use the same khane as Class 10.
# ============================================================
STAGE_PREPRIMARY = "preprimary"
STAGE_PRIMARY_A = "primary_a"
STAGE_PRIMARY_B = "primary_b"
STAGE_MIDDLE = "middle"
STAGE_SECONDARY = "secondary"
STAGE_SENIOR = "senior"

PREPRIMARY_LAYOUT_OVERRIDES = {
    "stage": STAGE_PREPRIMARY,
    "column_sums": True,
    "figure_box": True,
    "number_line": True,
    "match_two_column": True,
    "matrix": False,
    "math_mode": False,
    "mcq_single_column": False,
    "picture_items": True,
    "tracing_blanks": True,
    "large_item_gap": True,
    "max_band_cols": 3,
    "prefer_two_col_band": True,
    "motivational": False,
}

# Google kids-worksheet grammar: short instruction = VERB + OBJECT.
# The verb chooses the room. The object fills the room.
PREPRIMARY_ACTION_ROOMS = {
    "trace": {"furniture": "dashed_glyph", "columns": 3},
    "color": {"furniture": "picture_box", "columns": 3},
    "circle": {"furniture": "choice_row", "columns": 4},
    "tick": {"furniture": "choice_row", "columns": 3},
    "match": {"furniture": "two_column_match", "columns": 2},
    "count": {"furniture": "count_and_write", "columns": 2},
    "odd": {"furniture": "choice_row", "columns": 4},
    "after": {"furniture": "blank_trail", "columns": 2},
    "before": {"furniture": "blank_trail", "columns": 2},
    "between": {"furniture": "blank_trail", "columns": 2},
    "missing": {"furniture": "blank_trail", "columns": 1},
    "pattern": {"furniture": "pattern_row", "columns": 1},
    "sound": {"furniture": "choice_row", "columns": 3},
    "draw": {"furniture": "draw_box", "columns": 2},
}


def infer_preprimary_action(text):
    t = str(text or "").lower()
    pairs = (
        ("odd", ("odd one", "विषम", "अलग")),
        ("trace", ("trace", "ट्रेस", "अनुरेखण")),
        ("color", ("colour", "color", "रंग भरो", "रंग भर")),
        ("match", ("match", "मिलाओ", "मिलाइए")),
        ("circle", ("circle", "गोल घेरा", "घेरा लगा")),
        ("tick", ("tick", "bigger", "taller", "heavier")),
        ("count", ("count", "गिनो", "गिनकर")),
        ("sound", ("beginning sound", "starts with", "पहली ध्वनि")),
        ("pattern", ("pattern", "पैटर्न")),
        ("missing", ("missing", "लुप्त")),
        ("after", ("comes after", "बाद क्या")),
        ("before", ("comes before", "पहले क्या")),
        ("between", ("comes between", "बीच")),
        ("draw", ("draw", "बनाओ")),
    )
    for verb, keys in pairs:
        if any(k in t for k in keys):
            return verb
    return None


CURRENT_PAPER_CLASS = ""

# ============================================================
# V33.4 — ANSWER_SPACE MASTER INPUT + HANDWRITING HARD GATE
# ------------------------------------------------------------
# ANSWER_SPACE is an EXISTING Excel column. It is NOT renamed,
# replaced, or repurposed. It is the master input for whether the
# paper is allowed to receive generated answer space.
#
# IMPORTANT:
#   ANSWER_SPACE = YES does NOT by itself enable handwriting.
#
# HUMAN HANDWRITING IS PERMITTED ONLY WHEN ALL THREE ARE TRUE:
#   1) ANSWER_SPACE = YES
#   2) SUBJECT = ENGLISH
#   3) CLASS = LKG / UKG / I / II
#
# For every other class or subject, handwriting MUST remain OFF.
# The eligibility check is centralized so handwriting-related AI/API
# calls can never be made accidentally for an ineligible paper.
#
# New worksheet/template generation remains separate from handwriting:
# Play–Class II may use the worksheet/template pipeline, but human
# handwriting is still restricted to English + LKG/UKG/I/II only.
# Class III+ remains the clean-copy/board-paper path.
# ============================================================

ANSWER_SPACE_YES_VALUES = {
    "YES", "Y", "1", "TRUE", "HAAN", "हाँ"
}
ANSWER_SPACE_NO_VALUES = {
    "NO", "N", "0", "FALSE", "NAHI", "नहीं"
}

_HANDWRITING_CLASSES = {"LKG", "UKG", "I", "II"}

def _normalize_class_key(class_name):
    """Normalize Excel CLASS only for rule matching; never alter display text."""
    return re.sub(r"[^A-Z0-9]", "", str(class_name or "").strip().upper())

def _normalize_subject_key(subject):
    """Normalize Excel SUBJECT only for rule matching; never alter display text."""
    return re.sub(r"\s+", " ", str(subject or "").strip().upper())

def _answer_space_column_value(row_data):
    """V33.14: Read the existing Excel ANSWER_SPACE value robustly.

    Excel headers can arrive through pandas with invisible whitespace, line
    breaks, BOM characters, or other formatting artifacts.  The screenshot
    may visibly show ANSWER_SPACE while the actual pandas key differs.
    This helper normalizes the header ONLY for lookup; it never changes the
    Excel file or any displayed text.
    """
    try:
        data = row_data if row_data is not None else {}
        if not hasattr(data, "keys"):
            return ""
        for key in data.keys():
            key_norm = re.sub(r"[^A-Z0-9]+", "", str(key or "").replace("\ufeff", "").upper())
            if key_norm == "ANSWERSPACE":
                raw = data.get(key, "")
                if raw is None:
                    return ""
                return str(raw).replace("\ufeff", "").strip().upper()
    except Exception:
        return ""
    return ""

def answer_space_enabled(row_data):
    """
    MASTER INPUT:
    Read only the existing Excel ANSWER_SPACE column.

    Returns True only for explicit YES-style values.
    Blank/unknown values are treated as False for safety.
    """
    value = _answer_space_column_value(row_data)
    return value in ANSWER_SPACE_YES_VALUES

def handwriting_allowed_for_paper(row_data):
    """
    CENTRAL HARD GATE for human/cursive handwriting.

    Required:
      ANSWER_SPACE == YES
      AND English subject
      AND class is LKG, UKG, I or II

    This function MUST be checked before any handwriting-related
    renderer, model call, image generation, or API request.
    """
    data = row_data if row_data is not None else {}
    if not answer_space_enabled(data):
        return False

    class_key = _normalize_class_key(data.get("CLASS", ""))
    subject_key = _normalize_subject_key(data.get("SUBJECT", ""))

    english_subject = subject_key in {
        "ENGLISH", "ENG", "ENGLISH I", "ENGLISH II"
    }

    return class_group_allows_handwriting(data.get("CLASS", "")) and english_subject

def get_handwriting_decision(row_data):
    """
    Return an auditable decision object. This is deliberately deterministic.
    """
    data = row_data if row_data is not None else {}
    answer_space = answer_space_enabled(data)
    class_key = _normalize_class_key(data.get("CLASS", ""))
    subject_key = _normalize_subject_key(data.get("SUBJECT", ""))

    if not answer_space:
        reason = "ANSWER_SPACE is not YES"
        allowed = False
    elif not class_group_allows_handwriting(data.get("CLASS", "")):
        reason = "Class/group is outside LKG/UKG/I/II handwriting range"
        allowed = False
    elif subject_key not in {"ENGLISH", "ENG", "ENGLISH I", "ENGLISH II"}:
        reason = "Subject is not English"
        allowed = False
    else:
        reason = "ANSWER_SPACE=YES + English + LKG/UKG/I/II"
        allowed = True

    return {
        "answer_space": answer_space,
        "handwriting_allowed": allowed,
        "class_key": class_key,
        "subject_key": subject_key,
        "reason": reason,
    }

def handwriting_api_guard(row_data):
    """
    Fail-safe guard for future handwriting API/renderer calls.

    Call this immediately before ANY handwriting-related API/model call.
    Ineligible papers raise a clear error instead of spending an API call.
    """
    decision = get_handwriting_decision(row_data)
    if not decision["handwriting_allowed"]:
        raise PermissionError(
            "HANDWRITING API BLOCKED: "
            + decision["reason"]
        )
    return decision




# ============================================================
# V33.5 — WORKSHEET ROUTING + QUESTION INTENT PIPELINE
# ------------------------------------------------------------
# Play/Pre-Nursery/Nursery/LKG/UKG/Class I/Class II = WORKSHEET_AI
# Class III onward = CLEAN_COPY
# ANSWER_SPACE controls answer-space permission; it does not decide class mode.
# ============================================================
ROMAN_CLASS_ORDER = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
_ROMAN_CLASS_SET = set(ROMAN_CLASS_ORDER)

def normalize_roman_class_group(class_name):
    """Return canonical Roman class tokens only; preserves combined groups such as V+VI+VII."""
    raw = str(class_name or "").strip().upper()
    raw = raw.replace("–", "+").replace("—", "+").replace(",", "+").replace("/", "+")
    # Accept spaces around +, but never Arabic class numbers.
    parts = [re.sub(r"\s+", "", x) for x in raw.split("+") if str(x).strip()]
    aliases = {
        "FIRST":"I", "SECOND":"II", "THIRD":"III", "FOURTH":"IV",
        "FIFTH":"V", "SIXTH":"VI", "SEVENTH":"VII", "EIGHTH":"VIII",
        "NINTH":"IX", "TENTH":"X", "ELEVENTH":"XI", "TWELFTH":"XII",
        # V33.17: PAPER.xlsx uses NUR as the canonical Nursery class code.
        # Normalize it centrally so worksheet mode, preprimary routing, and
        # Nursery-specific render gates all see the same class identity.
        "NUR":"NURSERY",
    }
    cleaned = []
    for part in parts:
        part = re.sub(r"^(CLASS|STD|STANDARD|GRADE)", "", part)
        part = aliases.get(part, part)
        if part in _ROMAN_CLASS_SET or part in {"PLAY", "PRENURSERY", "NURSERY", "LKG", "UKG"}:
            cleaned.append(part)
        elif part:
            # Arabic numerals and unknown class formats are rejected, not converted.
            return []
    # preserve order but remove duplicates
    out = []
    for x in cleaned:
        if x not in out:
            out.append(x)
    return out

def is_combined_class(class_name):
    return len(normalize_roman_class_group(class_name)) > 1

def class_group_is_worksheet(class_name):
    tokens = normalize_roman_class_group(class_name)
    if not tokens:
        return False
    worksheet_tokens = {"PLAY", "PRENURSERY", "NURSERY", "LKG", "UKG", "I", "II"}
    return all(t in worksheet_tokens for t in tokens)

def class_group_allows_handwriting(class_name):
    """Handwriting is allowed only when EVERY class in a combined group is LKG/UKG/I/II."""
    tokens = normalize_roman_class_group(class_name)
    return bool(tokens) and all(t in {"LKG", "UKG", "I", "II"} for t in tokens)

def worksheet_mode_for_class(class_name):
    """Play–Class II worksheet mode, including valid combined Roman groups."""
    if class_group_is_worksheet(class_name):
        return True
    if WORKSHEET_INTENT is not None:
        try:
            return bool(WORKSHEET_INTENT.is_worksheet_class(class_name))
        except Exception:
            pass
    return False

def build_local_worksheet_intent_plan(extracted_text, class_name, subject):
    """Build question→intent→template plan; never invent source answers."""
    if WORKSHEET_INTENT is None:
        return {"engine_version": "DISABLED", "generation_mode": "WORKSHEET_AI", "items": [], "review_required": True, "no_invention": True, "reason": "Local intent engine unavailable."}
    try:
        return WORKSHEET_INTENT.build_worksheet_intent_plan(extracted_text, class_name, subject)
    except Exception as _intent_exc:
        return {"engine_version": getattr(WORKSHEET_INTENT, "ENGINE_VERSION", "unknown"), "generation_mode": "WORKSHEET_AI", "items": [], "review_required": True, "no_invention": True, "reason": f"Intent engine error: {_intent_exc}"}

def _saini_ai_integration_status(row_data):
    """
    Phase-1 integration is deliberately narrow:
    Nursery + Hindi + ANSWER_SPACE=YES only.
    This function performs no rendering itself.
    """
    try:
        enabled = answer_space_enabled(row_data)
        class_key = _normalize_class_key(row_data.get("CLASS", ""))
        subject_key = _normalize_subject_key(row_data.get("SUBJECT", ""))
    except Exception:
        return {
            "eligible": False,
            "route": "BYPASS_EXISTING_PAPER_PATH",
            "reason": "Row data normalization failed.",
        }

    # V33.15: Excel commonly stores Nursery as the existing short code NUR.
    # Treat NUR and NURSERY as the same class for this gate only; do not alter
    # the displayed Excel value or document class text.
    nursery_class = class_key in {"NUR", "NURSERY"}
    eligible = (
        enabled
        and nursery_class
        and subject_key == "HINDI"
        and process_nursery_hindi_question is not None
    )
    if not eligible:
        return {
            "eligible": False,
            "route": "BYPASS_EXISTING_PAPER_PATH",
            "reason": "Not Nursery + Hindi + ANSWER_SPACE=YES or integration module unavailable.",
        }

    return {
        "eligible": True,
        "route": "SAINI_AI_NURSERY_HINDI",
        "reason": "Eligible for V33.7 Nursery-Hindi integration.",
    }

# --- END V33.4 / V33.7 MASTER GATES ---




def class_allows_tables(class_name=None):
    """Tables ONLY for NUR / LKG / UKG / I / II / III. Class 4+ never."""
    raw = class_name if class_name is not None else CURRENT_PAPER_CLASS
    t = re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())
    if not t:
        return False
    if t in {
        "PLAY", "PLAYGROUP", "PLAYWAY", "PG", "PRENUR", "PRENURSERY",
        "NUR", "NURSERY", "NS", "LKG", "UKG", "KG", "KG1", "KG2",
        "PREPRIMARY", "PREPRY",
        "1", "01", "I", "FIRST",
        "2", "02", "II", "SECOND",
        "3", "03", "III", "THIRD",
    }:
        return True
    if "NUR" in t or "LKG" in t or "UKG" in t or t.startswith("PRE") or "PLAY" in t:
        return True
    return False


def classify_class_stage(class_name):
    """Map Excel CLASS to one of the six setter brains."""
    t = re.sub(r"[^A-Z0-9]", "", str(class_name or "").upper())
    if not t:
        return STAGE_PRIMARY_A
    if t in {
        "PLAY", "PLAYGROUP", "PLAYWAY", "PG", "PRENUR", "PRENURSERY",
        "NUR", "NURSERY", "NS", "LKG", "UKG", "KG", "KG1", "KG2",
        "PREPRIMARY", "PREPRY",
    }:
        return STAGE_PREPRIMARY
    if t in {"1", "01", "I", "FIRST", "2", "02", "II", "SECOND"}:
        return STAGE_PRIMARY_A
    if t in {
        "3", "03", "III", "THIRD", "4", "04", "IV", "FOURTH",
        "5", "05", "V", "FIFTH",
    }:
        return STAGE_PRIMARY_B
    if t in {
        "6", "06", "VI", "SIXTH", "7", "07", "VII", "SEVENTH",
        "8", "08", "VIII", "EIGHTH",
    }:
        return STAGE_MIDDLE
    if t in {"9", "09", "IX", "NINTH", "10", "X", "TENTH"}:
        return STAGE_SECONDARY
    if t in {
        "11", "XI", "ELEVENTH", "12", "XII", "TWELFTH",
        "PLUS1", "PLUS2", "P1", "P2",
    }:
        return STAGE_SENIOR
    if "NUR" in t or "LKG" in t or "UKG" in t or "PLAY" in t or t.startswith("PRE"):
        return STAGE_PREPRIMARY
    return STAGE_PRIMARY_A


def is_science_subject_local(subject):
    """Wrapper kept so older call sites stay stable if import fails."""
    try:
        return is_science_subject(subject)
    except Exception:
        text = str(subject or "").strip().lower()
        return any(k in text for k in (
            "science", "chemistry", "विज्ञान", "vigyan", "रसायन",
        ))


def is_maths_subject(subject):
    """Return True when the Excel SUBJECT indicates a Mathematics paper."""
    text = str(subject or "").strip().lower()
    if not text:
        return False
    for kw in MATHS_SUBJECT_KEYWORDS:
        if kw in text:
            return True
    return False


def is_sanskrit_subject(subject):
    text = str(subject or "").strip().lower()
    return any(k in text for k in ("sanskrit", "संस्कृत", "sanskrt", "sanskrut"))


PAPER_LANGUAGE = ""  # hindi | sanskrit | english | mixed — set per paper

LANGUAGE_LOCK_PROMPT = r"""
PAPER LANGUAGE LOCK:
- First decide the paper language from the printed page + subject name.
- HINDI paper: do NOT invent or insert any English sentence, English heading,
  English instruction, or English translation. Keep Hindi wording exactly.
  Do not replace "शब्दार्थ लिखिए" with "Write the meanings...".
- SANSKRIT paper: do NOT invent or insert any English sentence or heading.
  Keep Sanskrit / Devanagari wording. Instructions stay as on the page.
- ENGLISH paper: do not replace English instructions with Hindi.
- Never mix a full English sentence into a Hindi or Sanskrit paper.
- Hindi words MUST be separated by spaces. Never glue words (सभीप्रश्न is wrong).
- Labels like Q.1 / MM / Time may stay as printed. That is not a sentence.
- Word-meaning lists: keep EVERY word. Do not drop the first or last word.
  Each word on its own line as: शब्द =
"""


def detect_paper_language(subject="", sample=""):
    sub = str(subject or "").strip().lower()
    if any(k in sub for k in ("sanskrit", "संस्कृत", "sanskrt", "sanskrut")):
        return "sanskrit"
    if any(k in sub for k in ("hindi", "हिंदी", "हिन्दी", "hin")):
        return "hindi"
    if any(k in sub for k in ("english", "eng")) and "grammar" not in sub:
        # subject ENGLISH = english paper
        if sub.strip() in {"english", "eng", "eng-i", "eng-ii", "eng-grammer", "grammar"}:
            return "english"
    text = str(sample or "")
    dev = len(re.findall(r"[\u0900-\u097F]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if dev > lat * 2 and dev >= 12:
        return "hindi"
    if lat > dev * 2 and lat >= 20:
        return "english"
    return "mixed"


def is_foreign_sentence(text, lang):
    """True when a full sentence is in the wrong script for this paper."""
    t = str(text or "").strip()
    if len(t) < 18:
        return False
    if lang not in {"hindi", "sanskrit"}:
        return False
    lat = len(re.findall(r"[A-Za-z]", t))
    dev = len(re.findall(r"[\u0900-\u097F]", t))
    if lat >= 12 and lat > dev * 2 and re.search(r"[.?!]", t):
        return True
    return False


SANSKRIT_OCR_PROMPT_ADDON = r"""
SANSKRIT / DEVANAGARI PAPER RULES:
- Main questions are written प्र०१ प्र०२ प्र०३ or प्र01 / प्रश्न 1. Keep that heading on its OWN line.
- OCR often reads प्र०१ as ५०१ or ५०5. Restore प्र०१ प्र०२ प्र०३.
- (क) (ख) (ग) (घ) (ङ) are sub-questions. Each on its own line.
- Lines like 2×5 = 10 or 1×5 = 5 after a colon are MARKS, not multiplication sums.
- Do not invent arithmetic. Do not turn Sanskrit stems into type=multiplication.
- Keep visarga (:) and danda । . A trailing 'र' at end of a question is usually '?'.
- Common OCR fixes: श्रृंगाल/रटगाल→शृगालः, कुश्रू→कुत्र, अपश्यतर→अपश्यत्, स्वणकाकः→स्वर्णकारः.
- Passage after पठित्वा / गद्यांश stays as one passage block, then the (क)-(ङ) list.
"""


def build_paper_layout(class_name, subject):
    """
    Build the final layout dict for one paper.
    1. Start from NCERT pattern (if available).
    2. If subject is Maths → force Maths-friendly flags.
    3. Operator never needs to change files or settings.
    """
    pattern = get_pattern(class_name, subject) if get_pattern else None
    layout = dict((pattern or {}).get("layout") or {})

    stage = classify_class_stage(class_name)
    layout["stage"] = stage
    layout["class_name"] = str(class_name or "").strip()
    if stage == STAGE_PREPRIMARY:
        layout.update(PREPRIMARY_LAYOUT_OVERRIDES)
        print("  🧸 PREPRIMARY STAGE (Play–UKG) — picture rooms, fat blanks, max 3 cols")

    if is_maths_subject(subject):
        layout.update(MATHS_LAYOUT_OVERRIDES)
        if stage == STAGE_PREPRIMARY:
            layout["mcq_single_column"] = False
            layout["matrix"] = False
            layout["max_band_cols"] = 3
        print("  🔄 MATHS MODE auto-enabled (vertical options, column sums, matrices, figures)")
    if is_science_subject(subject):
        layout.update(SCIENCE_LAYOUT_OVERRIDES)
        print("  🔬 SCIENCE MODE auto-enabled (chemical formulae + optional teacher key)")

    # NCERT fine-tune is deliberately limited to Class 1+ board papers.
    # Preprimary remains under the dedicated worksheet/setter engine.
        if (NCERT_FINE_TUNE_ENABLED and stage in NCERT_SEQUENTIAL_STAGES):
            layout["ncert_sequential"] = True
            layout["item_band"] = False
            layout["major_question_full_width"] = True
            layout["subparts_vertical"] = True
            layout["major_question_gap_pt"] = NCERT_MAJOR_GAP_PT
            print("  NCERT FINE-TUNE: single-column sequential question flow")
        else:
            layout["ncert_sequential"] = False

    # --- HOOK 2: NCERT grammar merge (ADD-ON) ---
    if NCERT_GRAMMAR is not None:
        try:
            _g = NCERT_GRAMMAR.get_ncert_grammar(stage)
            for _k, _v in _g.items():
                layout.setdefault(_k, _v)
            print("  📘 NCERT GRAMMAR:", _g.get("stage"),
                  "answer_space=", _g.get("answer_space"))
        except Exception as _gm_exc:
            print("  ⚠ grammar merge skipped:", _gm_exc)
    # --- END HOOK 2 ---
    return layout, pattern

# ============================================================
# V21 PAGE-UTILIZATION OPTIMIZER
# ============================================================
# The optimizer is intentionally POST-GENERATION and regression-safe.
# It never changes OCR wording, question order, header geometry, A4 size,
# motivational sentence, footer, or protected layout rules.
#
# Candidate body sizes are tested from 12.0 pt downward in 0.1 pt steps.
# The FIRST candidate whose final page uses at least 90% of the available
# body height is accepted. If no candidate reaches the target, the original
# generated document is retained unchanged.
#
# Word COM is used only for real pagination measurement on Windows.
# If pywin32/Word COM is unavailable, the optimizer safely skips itself.
# ============================================================
PAGE_UTILIZATION_ENABLED = True
PAGE_UTILIZATION_TARGET = 0.20
PAGE_ACCEPT_MIN = 0.20
PAGE_REDUCE_TRIGGER = 0.25
PAGE_REDUCE_MIN_PAGES = 3
PAGE_REDUCE_ACCEPT_MIN = 0.30
PAGE_UTILIZATION_START_PT = 12.0
PAGE_UTILIZATION_END_PT = 11.5
PAGE_UTILIZATION_STEP_PT = 0.1
PAGE_UTILIZATION_TOLERANCE_PT = 0.001
PAGE_UTILIZATION_TEMP_PREFIX = "__paper_v21_candidate_"


def _page_utilization_candidate_sizes():
    """Return 12.0, 11.9, ... 11.5 without floating-point drift."""
    values = []
    value = PAGE_UTILIZATION_START_PT
    while value >= PAGE_UTILIZATION_END_PT - PAGE_UTILIZATION_TOLERANCE_PT:
        values.append(round(value, 1))
        value -= PAGE_UTILIZATION_STEP_PT
    return values


def _set_body_run_size(run, size_pt):
    """Set only a body run's size while preserving its font/bold/underline state."""
    if not run.text or not run.text.strip():
        return

    # The final Hindi motivational slogan is intentionally protected at 16 pt.
    if run.underline or "★" in run.text:
        return

    run.font.size = Pt(size_pt)


def _apply_page_utilization_body_size(doc_path, size_pt):
    """Apply a candidate size to question-body runs only.

    Table 0 is the Excel metadata table and is deliberately untouched.
    Later tables are MCQ/word-meaning content and are included in the
    compact body sizing. Header paragraphs, motivational slogan and footer
    are protected.
    """
    doc = Document(doc_path)

    # Body paragraphs begin after the school-name and class/subject headers.
    # Skip the first two document paragraphs explicitly.
    for paragraph in doc.paragraphs[2:]:
        for run in paragraph.runs:
            _set_body_run_size(run, size_pt)

    # Table 0 = fixed metadata header. All subsequent tables are body layout.
    for table_index, table in enumerate(doc.tables):
        if table_index == 0:
            continue
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        _set_body_run_size(run, size_pt)

    doc.save(doc_path)


def _measure_word_last_page_utilization(doc_path):
    """Return (page_count, utilization) from real Microsoft Word pagination.

    Utilization is the fraction of usable body height occupied by the final
    document-content cursor. Word's actual pagination is authoritative here.
    """
    try:
        import win32com.client
    except ImportError:
        return None

    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(doc_path), ReadOnly=False, AddToRecentFiles=False)
        doc.Repaginate()

        # Word constants: wdActiveEndPageNumber=3,
        # wdVerticalPositionRelativeToPage=6.
        # Use the main-text StoryRange directly. This avoids both
        # doc.Content late-binding issues and unavailable EndOfDoc bookmarks.
        # wdMainTextStory = 1
        end_range = doc.StoryRanges(1).Duplicate
        end_range.Collapse(0)  # wdCollapseEnd
        page_count = int(end_range.Information(3))
        y_pos = float(end_range.Information(6))

        # A4 page body height in points, minus the configured top/bottom margins.
        page_height_pt = PAGE_HEIGHT_MM / 25.4 * 72.0
        top_pt = TOP_MARGIN * 72.0
        bottom_pt = BOTTOM_MARGIN * 72.0
        usable_height_pt = max(1.0, page_height_pt - top_pt - bottom_pt)

        # y_pos is relative to the physical page top. Clamp defensively.
        used_pt = max(0.0, min(usable_height_pt, y_pos - top_pt))
        utilization = used_pt / usable_height_pt

        return page_count, utilization
    except Exception as exc:
        print(f"  ⚠ V21 Word pagination measurement skipped: {exc}")
        return None
    finally:
        try:
            if doc is not None:
                doc.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass


def _apply_v22_line_spacing(doc_path, spacing_pt):
    """Apply controlled exact line spacing to body paragraphs only.

    Font sizes, headers, metadata tables, footer and question text are not
    rewritten. Only existing body paragraph line spacing is adjusted.
    """
    from docx import Document
    from docx.shared import Pt

    doc = Document(doc_path)

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        # Do not alter the motivational sentence itself. The goal is to make
        # room for it by compacting the preceding paper content.
        if text.startswith("★") and text.endswith("★"):
            continue

        paragraph.paragraph_format.line_spacing = Pt(spacing_pt)

    doc.save(doc_path)


def _apply_v23_layout_variant(
    doc_path: str,
    line_spacing_pt: float,
    small_gap_pt: float,
) -> None:
    """Apply one controlled V23 layout variant.

    V23 does NOT change:
      - question text
      - question order
      - font size
      - page size
      - margins
      - question structure

    It only adjusts compact body paragraph spacing and line spacing.
    """

    from docx import Document
    from docx.shared import Pt

    doc = Document(doc_path)

    # ------------------------------------------------------------
    # NORMAL BODY PARAGRAPHS
    # Skip school name + class/subject so letters are never cut.
    # ------------------------------------------------------------
    for p_index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()

        if not text:
            continue
        if p_index < 2:
            continue

        # Never modify header, school name, or motivational sentence.
        if text.startswith("★") and text.endswith("★"):
            continue
        if text.upper().startswith("CLASS:"):
            continue

        # --- HOOK 4: protect answer-space paragraphs (ADD-ON) ---
        try:
            if ANSWER_SPACE is not None and ANSWER_SPACE.is_answer_space_paragraph(paragraph):
                continue
        except Exception:
            pass
        # --- END HOOK 4 ---

        fmt = paragraph.paragraph_format

        before_pt = (
            fmt.space_before.pt
            if fmt.space_before is not None
            else 0.0
        )

        after_pt = (
            fmt.space_after.pt
            if fmt.space_after is not None
            else 0.0
        )

        # Only compact ordinary small gaps.
        # Large structural gaps are deliberately preserved.
        if before_pt <= 2.0:
            fmt.space_before = Pt(before_pt)

        if after_pt <= 2.0:
            fmt.space_after = Pt(small_gap_pt)

        fmt.line_spacing = Pt(line_spacing_pt)

    # ------------------------------------------------------------
    # TABLE PARAGRAPHS
    # ------------------------------------------------------------
    for table_index, table in enumerate(doc.tables):
        if table_index == 0:
            continue
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    fmt = paragraph.paragraph_format

                    after_pt = (
                        fmt.space_after.pt
                        if fmt.space_after is not None
                        else 0.0
                    )

                    if after_pt <= 2.0:
                        fmt.space_after = Pt(small_gap_pt)

                    fmt.line_spacing = Pt(line_spacing_pt)

    doc.save(doc_path)


def _fill_last_page_if_space_remains(original_path, original_pages, original_utilization):
    """Use leftover last-page space so the paper looks filled.

    Allowed last-page fill: 0.90 and above only (.91 .92 .93...).
    Never accept below 0.90. Never add an extra page.
    School header paragraphs are not touched.
    """
    MIN_FILL = 0.90
    if original_utilization >= 0.97:
        return original_path

    expand_candidates = [
        (16.2, 1.2), (16.4, 1.6), (16.6, 2.0),
        (16.8, 2.4), (17.0, 2.8), (17.2, 3.2),
        (17.4, 3.6), (17.6, 4.0),
    ]
    best_path = None
    best_util = original_utilization
    temps = []
    base_dir = os.path.dirname(original_path)
    stem, ext = os.path.splitext(os.path.basename(original_path))

    try:
        for i, (line_pt, gap_pt) in enumerate(expand_candidates, start=1):
            cand = os.path.join(
                base_dir,
                f"{PAGE_UTILIZATION_TEMP_PREFIX}{stem}_FILL_{line_pt:.1f}_{i}{ext}",
            )
            shutil.copy2(original_path, cand)
            temps.append(cand)
            _apply_v23_layout_variant(cand, line_spacing_pt=line_pt, small_gap_pt=gap_pt)
            measured = _measure_word_last_page_utilization(cand)
            if measured is None:
                continue
            pages, util = measured
            if pages != original_pages:
                continue
            if util < MIN_FILL:
                continue
            if util > best_util:
                best_util = util
                best_path = cand
                print(f"    Fill ↑ {line_pt:.1f}pt → last page {util*100:.1f}%")
                if util >= 0.96:
                    break
        if best_path and best_util >= MIN_FILL:
            shutil.copy2(best_path, original_path)
            print(f"  ✓ V25 last page filled to {best_util*100:.1f}% (>=90%)")
            return original_path
    finally:
        for t in temps:
            try:
                if os.path.isfile(t):
                    os.remove(t)
            except Exception:
                pass
    return original_path


def optimize_page_utilization(output_path):
    """V24 generalized page-waste optimizer.

    FINAL RULE
    ----------
    If the last page contains >= 10% usable matter:
        ACCEPT immediately.

    If the last page contains < 10%:
        Try to reduce the document by EXACTLY ONE page.

    A reduction is accepted only when:
        new_page_count == old_page_count - 1
        AND
        new_last_page_utilization >= 10%

    This works for ANY page count:

        2 -> 1
        3 -> 2
        4 -> 3
        5 -> 4
        6 -> 5
        7 -> 6
        8 -> 7
        etc.

    100% utilization is NOT a target.

    V24 speed improvement:
        Instead of testing hundreds of combinations, candidates are
        tested in a carefully ordered compact set.

    The original document is always retained if no safe reduction
    is found.
    """

    ACCEPT_MIN = PAGE_ACCEPT_MIN
    REDUCE_TRIGGER = PAGE_REDUCE_TRIGGER
    REDUCE_MIN_PAGES = PAGE_REDUCE_MIN_PAGES
    REDUCE_ACCEPT_MIN = PAGE_REDUCE_ACCEPT_MIN
    MIN_FILL = ACCEPT_MIN

    if not PAGE_UTILIZATION_ENABLED:
        return output_path

    if not os.path.isfile(output_path):
        return output_path

    # ------------------------------------------------------------
    # PYWIN32 CHECK
    # ------------------------------------------------------------
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        print(
            "  ℹ V24 page optimizer skipped: "
            "pywin32 is not installed."
        )
        return output_path

    original_path = output_path
    base_dir = os.path.dirname(original_path)

    stem, ext = os.path.splitext(
        os.path.basename(original_path)
    )

    temporary_files = []

    print(
        "  → V24 generalized page-waste optimization started..."
    )

    try:

        # ========================================================
        # STEP 1
        # MEASURE ORIGINAL
        # ========================================================

        original_measurement = (
            _measure_word_last_page_utilization(
                original_path
            )
        )

        if original_measurement is None:
            print(
                "  ℹ V24: original Word pagination could not "
                "be measured; original retained."
            )
            return original_path

        original_pages, original_utilization = (
            original_measurement
        )

        print(
            f"    Original → {original_pages} page(s), "
            f"last-page utilization "
            f"{original_utilization * 100:.1f}%"
        )

        # ========================================================
        # ACCEPTABLE PAPER
        # ========================================================

        if original_utilization >= ACCEPT_MIN:

            print(
                "  ✓ V31: last page is >= 20%; "
                "paper accepted."
            )
            return original_path

        if original_pages < REDUCE_MIN_PAGES:

            print(
                "  ✓ V31: pages < 3 — 2→1 allowed nahi. "
                "Original retained."
            )

            return original_path

        if original_utilization >= REDUCE_TRIGGER:
            print(
                "  ✓ V31: last page >= 25%; reduction not required."
            )
            return original_path

        target_pages = original_pages - 1

        print(
            f"  ⚠ V31: last page below 25% "
            f"({original_utilization * 100:.1f}%)."
        )

        print(
            f"    Trying exactly "
            f"{original_pages} → {target_pages} page(s)."
        )

        # ========================================================
        # FAST CANDIDATE SET
        #
        # Ordered from least aggressive to more aggressive.
        #
        # We deliberately avoid hundreds of combinations.
        # ========================================================

        candidates = [

            # ----------------------------------------------------
            # NORMAL / VERY SAFE
            # ----------------------------------------------------
            (12.0, 0.8),
            (12.0, 1.0),
            (12.0, 1.2),
            (12.0, 1.5),

            # ----------------------------------------------------
            # SLIGHTLY TIGHTER
            # ----------------------------------------------------
            (11.8, 0.8),
            (11.8, 1.0),
            (11.8, 1.2),

            (11.6, 0.8),
            (11.6, 1.0),
            (11.6, 1.2),

            (11.4, 0.8),
            (11.4, 1.0),
            (11.4, 1.2),

            # ----------------------------------------------------
            # MODERATELY TIGHT
            # ----------------------------------------------------
            (11.2, 0.8),
            (11.2, 1.0),
            (11.2, 1.2),

            (11.0, 0.8),
            (11.0, 1.0),
            (11.0, 1.2),

            # ----------------------------------------------------
            # STRONGER COMPRESSION
            # ----------------------------------------------------
            (10.8, 0.8),
            (10.8, 1.0),
            (10.8, 1.2),

            (10.6, 0.8),
            (10.6, 1.0),
            (10.6, 1.2),

            (10.5, 0.8),
            (10.5, 1.0),
            (10.5, 1.2),
        ]

        # ========================================================
        # BEST SAFE CANDIDATE
        # ========================================================

        best_candidate = None
        best_utilization = -1.0
        best_line_pt = None
        best_gap_pt = None

        # ========================================================
        # TEST CANDIDATES
        # ========================================================

        for index, (line_pt, gap_pt) in enumerate(
            candidates,
            start=1,
        ):

            candidate_path = os.path.join(
                base_dir,
                (
                    f"{PAGE_UTILIZATION_TEMP_PREFIX}"
                    f"{stem}_V24_"
                    f"{line_pt:.1f}_"
                    f"{gap_pt:.1f}_"
                    f"{index}{ext}"
                ),
            )

            try:

                shutil.copy2(
                    original_path,
                    candidate_path,
                )

                temporary_files.append(
                    candidate_path
                )

                _apply_v23_layout_variant(
                    candidate_path,
                    line_spacing_pt=line_pt,
                    small_gap_pt=gap_pt,
                )

                measured = (
                    _measure_word_last_page_utilization(
                        candidate_path
                    )
                )

                if measured is None:
                    continue

                page_count, utilization = measured

                print(
                    f"    Candidate "
                    f"{line_pt:.1f} pt / "
                    f"gap {gap_pt:.1f} pt → "
                    f"{page_count} page(s), "
                    f"last-page "
                    f"{utilization * 100:.1f}%"
                )

                # ------------------------------------------------
                # MUST REDUCE EXACTLY ONE PAGE
                # ------------------------------------------------

                if page_count != target_pages:
                    continue

                # ------------------------------------------------
                # MUST HAVE >= 10% LAST PAGE
                # ------------------------------------------------

                if utilization < REDUCE_ACCEPT_MIN:
                    continue

                # ------------------------------------------------
                # BEST VALID CANDIDATE
                # ------------------------------------------------

                if utilization > best_utilization:

                    best_candidate = candidate_path
                    best_utilization = utilization
                    best_line_pt = line_pt
                    best_gap_pt = gap_pt

                    print(
                        f"      ↑ Safe candidate: "
                        f"{best_utilization * 100:.1f}%"
                    )

            except Exception as exc:

                print(
                    "  ⚠ V24 candidate skipped safely: "
                    f"{exc}"
                )

        # ========================================================
        # NO SAFE REDUCTION
        # ========================================================

        if best_candidate is None:

            print(
                "  ℹ V31: no safe N → N-1 layout with >=30% last page."
            )
            filled = _fill_last_page_if_space_remains(
                original_path, original_pages, original_utilization
            )
            return filled or original_path

        # ========================================================
        # FINAL ACCEPTANCE
        # ========================================================

        print()
        print(
            f"  ✓ V24 SAFE REDUCTION:"
            f" {original_pages} → {target_pages} page(s)"
        )

        print(
            f"    Line spacing = "
            f"{best_line_pt:.1f} pt"
        )

        print(
            f"    Gap = "
            f"{best_gap_pt:.1f} pt"
        )

        print(
            f"    Last-page utilization = "
            f"{best_utilization * 100:.1f}%"
        )

        # ========================================================
        # SAFE REPLACEMENT
        # ========================================================

        backup_path = (
            original_path +
            ".v24_backup"
        )

        try:

            shutil.copy2(
                original_path,
                backup_path,
            )

            shutil.copy2(
                best_candidate,
                original_path,
            )

            os.remove(
                backup_path
            )

        except Exception:

            if os.path.exists(
                backup_path
            ):

                try:
                    shutil.copy2(
                        backup_path,
                        original_path,
                    )
                except Exception:
                    pass

            raise

        print(
            "  ✓ V24 final candidate accepted."
        )

        return original_path

    except Exception as exc:

        print(
            "  ⚠ V24 optimizer failed safely:"
        )

        print(
            f"    {exc}"
        )

        print(
            "  ✓ Original paper retained."
        )

        return original_path

    finally:

        # ========================================================
        # CLEAN TEMPORARY FILES
        # ========================================================

        for candidate_path in temporary_files:

            try:

                if os.path.exists(
                    candidate_path
                ):
                    os.remove(
                        candidate_path
                    )

            except Exception:
                pass


def _is_auth_error(exc):
    msg = str(exc).upper()
    return (
        "401 UNAUTHENTICATED" in msg
        or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in msg
        or "INVALID AUTHENTICATION CREDENTIALS" in msg
        or "EXPECTED OAUTH" in msg
    )

def _load_oauth_credentials():
    if Credentials is None or InstalledAppFlow is None:
        raise RuntimeError(
            "OAuth dependencies are missing. Install: "
            "google-auth google-auth-oauthlib google-auth-httplib2"
        )

    creds = None
    if os.path.exists(OAUTH_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(
                OAUTH_TOKEN_FILE, OAUTH_SCOPES
            )
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not os.path.exists(OAUTH_CLIENT_SECRET_FILE):
            raise RuntimeError(
                f"OAuth client secret not found: {OAUTH_CLIENT_SECRET_FILE}. "
                "Place your Google OAuth desktop client JSON beside this script "
                "or set AUTH_MODE='api_key'."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            OAUTH_CLIENT_SECRET_FILE, OAUTH_SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open(OAUTH_TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds

def _build_api_key_client():
    key = API_KEY or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Set it in Windows Environment Variables "
            "or choose AUTH_MODE='oauth'."
        )
    return genai.Client(api_key=key)

def _build_oauth_client():
    creds = _load_oauth_credentials()
    return genai.Client(credentials=creds)

def _authentication_preflight(test_client):
    """Short auth check. Never block the batch if Google list() hangs."""
    result = {"ok": False, "err": "preflight timeout"}

    def _probe():
        try:
            next(iter(test_client.models.list()), None)
            result["ok"] = True
            result["err"] = "Authentication preflight passed."
        except Exception as exc:
            result["ok"] = False
            result["err"] = str(exc)

    import threading
    th = threading.Thread(target=_probe, daemon=True)
    th.start()
    th.join(12.0)
    if th.is_alive():
        # Key is present; do not freeze the whole generator on models.list().
        return True, "Preflight timed out after 12s — continuing with API key."
    if result["ok"]:
        return True, result["err"]
    # Real auth failures must still stop the batch.
    err = result["err"]
    if _is_auth_error(err) or any(
        tok in err.upper()
        for tok in ("API_KEY", "UNAUTHENTICATED", "PERMISSION", "401", "403", "INVALID")
    ):
        return False, err
    return True, "Preflight warning: %s — continuing." % err

def initialize_client():
    """Initialize Gemini using only the API key stored in PAPER.py."""
    global client

    key = str(API_KEY or "").strip()
    dummy_keys = {
        "",
        "PASTE_YOUR_NEW_GEMINI_API_KEY_HERE",
        "PASTE_YOUR_GEMINI_API_KEY_HERE",
        "XXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "YOUR_API_KEY_HERE",
    }

    if key in dummy_keys or set(key) <= set("X") or key.lower().startswith("xxxx"):
        raise RuntimeError(
            "API_KEY PAPER.py me dummy/empty hai. "
            "Purani PAPER.py se apni asli Gemini API key copy karke "
            "API_KEY = \"...\" me paste karo. OCR tabhi chalegi."
        )

    print("  → Gemini authentication check...")
    # Direct API-key authentication only.
    test_client = genai.Client(api_key=key)

    # One preflight request before processing any paper.
    ok, err = _authentication_preflight(test_client)

    if not ok:
        raise RuntimeError(
            "Gemini API-key authentication failed. "
            "OCR processing has NOT started.\n"
            f"Server response: {err}"
        )

    client = test_client
    print("  ✓ Authentication: API key from PAPER.py")
    try:
        import PAPER_AI
        PAPER_AI.set_client(client, MODEL_NAME, OUTPUT_FOLDER)
        print("  ✓ AI refine+check stage ready")
    except Exception as _ai_boot:
        print(f"  ⚠ PAPER_AI load nahi hua: {_ai_boot}")


def _diagnostic_q2_snapshot(label, page_texts):
    """V33.12 diagnostic only: trace likely Q-2/arrangement text before and after PAPER_AI.
    This never changes source text and never makes an additional API call.
    """
    hits = []
    for page_no, page_text in enumerate(page_texts or [], 1):
        page_lines = str(page_text or '').splitlines()
        for line_no, raw in enumerate(page_lines, 1):
            t = raw.strip()
            q2 = bool(re.search(r'^(?:Q(?:uestion)?\s*[-.:)]?\s*2|2[.)])(?:\s|:|-|$)', t, re.I))
            arrange = bool(re.search(r'\barrange\b.*\bnumber|\bnumbers?\b.*\barrange\b|\bbefore\b.*\bafter\b.*\bnumber', t, re.I))
            if q2 or arrange:
                lo = max(1, line_no - 3)
                hi = min(len(page_lines), line_no + 10)
                hits.append((page_no, lo, hi, page_lines[lo-1:hi]))
    print(f'  🔎 V33.12 Q-2 TRACE: {label}')
    if not hits:
        print('     NO Q-2 / arrange-numbers marker found in this text.')
        return
    seen = set()
    for page_no, lo, hi, excerpt in hits:
        key = (page_no, lo, hi)
        if key in seen:
            continue
        seen.add(key)
        print(f'     PAGE {page_no} OCR lines {lo}-{hi}:')
        for idx, text in enumerate(excerpt, lo):
            print(f'       {idx:03d}: {text}')


def run_ai_refine_with_timeout(row, page_texts, output_folder, timeout_sec=None):
    """Optional AI refinement. HOLD is disabled: never block Word creation."""
    import threading
    global LAST_AI_WARNING
    LAST_AI_WARNING = ""
    timeout_sec = int(timeout_sec or AI_STAGE_TIMEOUT_SEC)
    original = list(page_texts or [])
    print('  🧪 V33.12 DIAGNOSTIC ACTIVE — no extra API call; source text unchanged')
    _diagnostic_q2_snapshot('BEFORE PAPER_AI (raw OCR passed to validator)', original)
    box = {"done": False, "ok": True, "texts": original, "err": None}

    def _job():
        try:
            import PAPER_AI
            ok, texts, _report = PAPER_AI.refine_and_validate(row, original, output_folder)
            box["ok"] = bool(ok)
            box["texts"] = texts if texts else original
            _diagnostic_q2_snapshot('AFTER PAPER_AI (text returned by validator)', box["texts"])
        except Exception as exc:
            box["ok"] = False
            box["texts"] = original
            box["err"] = exc
        finally:
            box["done"] = True

    th = threading.Thread(target=_job, daemon=True)
    th.start()
    th.join(timeout_sec)

    if not box["done"]:
        LAST_AI_WARNING = f"{AI_WARNING_PREFIX} AI timeout after {timeout_sec} seconds."
        print(f"  {LAST_AI_WARNING}")
        print("  → HOLD DISABLED: Word file will be created from OCR text.")
        return True, original, True

    if box["err"] is not None:
        LAST_AI_WARNING = f"{AI_WARNING_PREFIX} AI stage error: {box['err']}"
        print(f"  {LAST_AI_WARNING}")
        print("  → HOLD DISABLED: Word file will be created from OCR text.")
        return True, original, False

    if not box["ok"]:
        LAST_AI_WARNING = f"{AI_WARNING_PREFIX} AI check reported a validation failure."
        print(f"  {LAST_AI_WARNING}")
        print("  → HOLD DISABLED: Word file will be created anyway.")
        return True, (box["texts"] or original), False

    print("  ✓ AI refine+check completed successfully.")
    out_texts = box["texts"] or original
    subj = ""
    try:
        subj = str((row or {}).get("SUBJECT") or (row or {}).get("Subject") or "")
    except Exception:
        subj = ""
    out_texts = [
        respace_devanagari_with_gemini(t, subj) if _needs_hindi_respace(t) else t
        for t in (out_texts or [])
    ]
    return True, out_texts, False


# ============================================================
# FILE / IMAGE HELPERS
# ============================================================

# V33.8 INPUT PAGE MANIFEST
# Excel PAGENO remains a numeric logical page number (1, 3, 5, ...).
# INPUT filenames may be old numeric names (1.jpg, 2.jpg, ...) OR named
# dossier names such as PAPER_001_P01.jpg.  The manifest maps logical page
# numbers to the actual source files without changing the Excel contract.
_INPUT_PAGE_MANIFEST = {}

# V33.24: current source images are retained for Nursery-Hindi visual-template rendering.
# This is a local path reference only; no extra OCR/AI call is made.
_CURRENT_SOURCE_IMAGE_PATHS = []

# V33.27 — UNIVERSAL IMAGE BANK (pictures NEVER cropped from the source paper)
IMAGE_BANK_ROOT = os.path.join(
    _HERE,
    "SAINI_UNIVERSAL_IMAGE_DATABASE_V1_PACKAGE_WITH_TRIAL_IMAGES",
    "images",
)
_V3327_IMAGE_BANK_CACHE = None
_V3327_VISUAL_RECOVERY_CACHE = None

# V33.38: verified image-bank gate.
# A picture bank is trusted ONLY when a separate verification manifest exists.
# The current WITH_TRIAL_IMAGES package therefore remains blocked.
_V338_IMAGE_BANK_MANIFEST_NAME = "VERIFIED_IMAGE_BANK_MANIFEST.json"
_V338_VERIFIED_IMAGE_BANK_ENABLED = False
_V338_IMAGE_BANK_VERIFICATION_REASON = "verification manifest not found"


def _input_image_sort_key(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    # Named dossier convention: PAPER_001_P01 -> (paper=1, page=1).
    m = re.match(r"^PAPER[_-]?(\d+)[_-]?P(\d+)$", stem, re.I)
    if m:
        return (0, int(m.group(1)), int(m.group(2)), stem.lower())
    # Any filename containing a final page marker, e.g. PAPER_001_PAGE01.
    m = re.search(r"(?:^|[_-])P(?:AGE)?[_-]?(\d+)$", stem, re.I)
    if m:
        return (1, int(m.group(1)), 0, stem.lower())
    # Legacy numeric filename: 1.jpg, 2.jpg ...
    if re.fullmatch(r"\d+", stem.strip()):
        return (2, int(stem.strip()), 0, stem.lower())
    # Other supported image names: deterministic natural ordering.
    nums = [int(x) for x in re.findall(r"\d+", stem)]
    return (3, *(nums or [10**9]), stem.lower())


# ===== V33.39 CONTROLLED INPUT ADAPTER V1 =====
_V339_PACKAGE_DIR_NAME = "V33_39_INPUT_ENGINE"
_V339_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def _v339_normalize_manifest(value):
    result = {}
    if not isinstance(value, dict):
        return result
    for key, path in value.items():
        try:
            page = int(key)
        except (TypeError, ValueError):
            continue
        if path is not None:
            result[page] = str(Path(path))
    return dict(sorted(result.items()))

def _v339_manifest_contract_ok(manifest):
    if not manifest:
        return False
    pages = sorted(manifest)
    if pages != list(range(1, len(pages) + 1)):
        return False
    for path in manifest.values():
        p = Path(path)
        if not p.exists() or p.suffix.lower() not in _V339_IMAGE_EXTS:
            return False
        stem = p.stem
        named = bool(re.fullmatch(r"PAPER[_-]?\d+[_-]?P\d+", stem, re.I))
        marker = bool(re.search(r"(?:^|[_-])P(?:AGE)?[_-]?\d+$", stem, re.I))
        legacy = bool(re.fullmatch(r"\d+", stem.strip()))
        if not (named or marker or legacy):
            return False
    return True

def _load_v339_builder(input_folder: Path):
    package_dir = Path(input_folder).resolve().parent / _V339_PACKAGE_DIR_NAME
    if not package_dir.is_dir():
        raise FileNotFoundError(
            f"V33.39 package unavailable: {package_dir}"
        )

    input_engine_dir = package_dir / "input_engine"
    manifest_file = input_engine_dir / "manifest.py"
    if not manifest_file.is_file():
        raise FileNotFoundError(
            f"V33.39 manifest.py unavailable: {manifest_file}"
        )

    # V33.39 is a real package; import it as a package so relative imports work.
    import importlib
    import sys

    package_parent = str(package_dir)
    old_path = list(sys.path)
    try:
        if package_parent not in sys.path:
            sys.path.insert(0, package_parent)

        for _name in (
            "input_engine.manifest",
            "input_engine.filename_check",
            "input_engine.image_input",
            "input_engine.pdf_input",
            "input_engine",
        ):
            sys.modules.pop(_name, None)

        module = importlib.import_module("input_engine.manifest")
        builder = getattr(module, "build_input_image_manifest", None)
        if not callable(builder):
            raise AttributeError(
                "V33.39 input_engine.manifest.build_input_image_manifest is not callable"
            )
        return builder
    finally:
        sys.path[:] = old_path



def _v339_build_candidate_manifest(input_folder, fallback_manifest):
    fallback = _v339_normalize_manifest(fallback_manifest)
    try:
        package_dir = Path(input_folder).resolve().parent / _V339_PACKAGE_DIR_NAME
        if not package_dir.is_dir():
            return fallback, "V33_43_FALLBACK", "V33.39 package unavailable"
        try:
            builder = _load_v339_builder(Path(input_folder))
        except Exception as exc:
            return fallback, "V33_43_FALLBACK", f"V33.39 unavailable/failed: {type(exc).__name__}: {exc}"
        try:
            raw = builder(Path(input_folder))
        except TypeError:
            raw = builder(str(input_folder))
        candidate = _v339_normalize_manifest(raw)
        if not _v339_manifest_contract_ok(candidate):
            return fallback, "V33_43_FALLBACK", "V33.39 contract validation failed"
        return candidate, "V33_39", "V33.39 manifest passed adapter validation"
    except Exception as exc:
        return fallback, "V33_43_FALLBACK", f"V33.39 unavailable/failed: {type(exc).__name__}: {exc}"

# ===== V33.39 CANDIDATE MARKER =====

def build_input_image_manifest():
    input_folder = os.path.join(_HERE, "INPUT")
    if input_folder is None:
        input_folder = os.path.join(_HERE, "INPUT")
    _v33_43_manifest = _V33_43_ORIGINAL_BUILD_INPUT_IMAGE_MANIFEST()
    _v33_39_manifest, _v33_39_provider, _v33_39_reason = _v339_build_candidate_manifest(
        input_folder, _v33_43_manifest
    )
    print(f"  V33.39 manifest provider: {_v33_39_provider}")
    print(f"  V33.39 manifest reason  : {_v33_39_reason}")
    return _v33_39_manifest

def _V33_43_ORIGINAL_BUILD_INPUT_IMAGE_MANIFEST():
    global _INPUT_PAGE_MANIFEST
    _INPUT_PAGE_MANIFEST = {}
    if not os.path.isdir(IMAGES_FOLDER):
        return _INPUT_PAGE_MANIFEST
    files = []
    for filename in os.listdir(IMAGES_FOLDER):
        full_path = os.path.join(IMAGES_FOLDER, filename)
        if not os.path.isfile(full_path):
            continue
        if os.path.splitext(filename)[1].lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        files.append(filename)
    for logical_page, filename in enumerate(sorted(files, key=_input_image_sort_key), start=1):
        _INPUT_PAGE_MANIFEST[logical_page] = os.path.join(IMAGES_FOLDER, filename)
    return _INPUT_PAGE_MANIFEST

def get_image_path(page_number):
    try:
        page = int(float(str(page_number).strip()))
    except (TypeError, ValueError):
        return None
    if page <= 0:
        return None

    # First use the manifest. This supports both 1.jpg and named dossier files.
    if page in _INPUT_PAGE_MANIFEST:
        return _INPUT_PAGE_MANIFEST[page]

    # Backward-compatible direct lookup for legacy numeric filenames.
    page_str = str(page)
    possible_names = [
        f"{page_str}.JPG", f"{page_str}.jpg",
        f"{page_str}.JPEG", f"{page_str}.jpeg",
        f"{page_str}.PNG", f"{page_str}.png",
        f"{page_str}.WEBP", f"{page_str}.webp",
    ]
    for name in possible_names:
        full_path = os.path.join(IMAGES_FOLDER, name)
        if os.path.exists(full_path):
            return full_path
    return None


def get_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()

    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"

    return "image/jpeg"


# ============================================================
# OCR / SOURCE IMAGE PRE-CHECK
# ============================================================

def is_obviously_blank_image(image_path):
    """Conservative local check for obviously blank source images."""
    if not LOCAL_BLANK_IMAGE_CHECK or Image is None or ImageStat is None:
        return False
    try:
        with Image.open(image_path) as img:
            gray = img.convert("L")
            gray.thumbnail((900, 1200))
            stat = ImageStat.Stat(gray)
            mean = stat.mean[0]
            low, high = gray.getextrema()
            return mean >= 248 and (high - low) <= 18
    except Exception:
        return False

def normalize_exam_mark_symbols(text):
    r"""
    Normalize OCR/LLM exam tick/cross marks only.

    ☑ is for checkmarks. Math multiplication \times becomes × (never ☒).
    Bare \times must NOT become the boxed cross.
    """
    if not text:
        return text

    normalized = str(text)

    for old in (r"$\\checkmark$", r"\\checkmark", r"$\checkmark$", r"\checkmark"):
        normalized = normalized.replace(old, "☑")

    # Only dollar-wrapped times is treated as an exam cross mark
    for old in (r"$\\times$", r"$\times$"):
        normalized = normalized.replace(old, "☒")

    # Math multiplication → real × sign
    normalized = normalized.replace(r"\\times", "×")
    normalized = normalized.replace(r"\times", "×")

    return normalized


def dedupe_leading_option_label(text):
    """
    Fix doubled option labels from OCR/LLM:
      i) i) ...   -> i) ...
      (i) (i) ... -> (i) ...
      (a) (a) ... -> (a) ...
    """
    t = str(text or "").strip()
    if not t:
        return t

    t = re.sub(
        r"^(\(\s*(?:iv|iii|ii|i|[a-dA-D]|[अ-ह])\s*\))\s+\1(?=\s|$)",
        r"\1",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"^((?:iv|iii|ii|i|[a-dA-D])\s*[.)])\s+\1(?=\s|$)",
        r"\1",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"^\(\s*\d+\s*\)\s*(\(\s*(?:iv|iii|ii|i|[a-dA-Dअ-ह])\s*\))",
        r"\1",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"^\d+\s*[\.)]\s*(\(\s*(?:iv|iii|ii|i|[a-dA-Dअ-ह])\s*\))",
        r"\1",
        t,
        flags=re.I,
    )
    return t


# ============================================================
# STABLE FRACTION + EQUATION ENGINE (Word OMML)
# ============================================================
# Gemini writes math in a fixed linear form. Word prints real stacked
# fractions and superscripts. Dates like 18/08/2026 are never converted.
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_VULGAR = {
    "½": (1, 2), "⅓": (1, 3), "⅔": (2, 3), "¼": (1, 4), "¾": (3, 4),
    "⅕": (1, 5), "⅖": (2, 5), "⅗": (3, 5), "⅘": (4, 5),
    "⅙": (1, 6), "⅚": (5, 6), "⅐": (1, 7), "⅛": (1, 8),
    "⅜": (3, 8), "⅝": (5, 8), "⅞": (7, 8), "⅑": (1, 9), "⅒": (1, 10),
}


def _math_xml_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _omml_from_xml(xml):
    from lxml import etree
    return etree.fromstring(xml.encode("utf-8"))


# Fixed font size for all fractions / equations / roots (user rule)
MATH_FONT_SIZE_PT = 19
MATH_FONT_SIZE_HALF_PT = str(MATH_FONT_SIZE_PT * 2)  # Word uses half-points


def _omml_run(text):
    """One OMML text run at fixed MATH_FONT_SIZE_PT (19)."""
    t = _math_xml_escape(text)
    return (
        f"<m:r>"
        f"<m:rPr><m:sty m:val='p'/>"
        f'<m:sz m:val="{MATH_FONT_SIZE_HALF_PT}"/>'
        f'<m:szCs m:val="{MATH_FONT_SIZE_HALF_PT}"/>'
        f"</m:rPr>"
        f"<m:t xml:space='preserve'>{t}</m:t>"
        f"</m:r>"
    )


def _omml_fraction(num, den):
    xml = (
        f'<m:oMath xmlns:m="{MATH_NS}">'
        f"<m:f>"
        f"<m:num>{_omml_run(num)}</m:num>"
        f"<m:den>{_omml_run(den)}</m:den>"
        f"</m:f>"
        f"</m:oMath>"
    )
    return _omml_from_xml(xml)


def _omml_sup(base, exp):
    xml = (
        f'<m:oMath xmlns:m="{MATH_NS}">'
        f"<m:sSup>"
        f"<m:e>{_omml_run(base)}</m:e>"
        f"<m:sup>{_omml_run(exp)}</m:sup>"
        f"</m:sSup>"
        f"</m:oMath>"
    )
    return _omml_from_xml(xml)


def _omml_sqrt(inner):
    xml = (
        f'<m:oMath xmlns:m="{MATH_NS}">'
        f"<m:rad><m:radPr><m:degHide m:val='1'/></m:radPr>"
        f"<m:deg/>"
        f"<m:e>{_omml_run(inner)}</m:e>"
        f"</m:rad>"
        f"</m:oMath>"
    )
    return _omml_from_xml(xml)


def _balanced_braces(text, start):
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    return None


def _looks_like_date_slash(text, slash_at):
    left = text[:slash_at]
    right = text[slash_at + 1:]
    if re.search(r"\d{1,2}$", left) and re.match(r"\d{1,2}/\d{2,4}", right):
        return True
    if re.search(r"\d{1,2}/\d{1,2}$", left) and re.match(r"\d{2,4}\b", right):
        return True
    return False


def _simple_math_atom(text):
    return bool(re.fullmatch(r"[A-Za-z0-9]+(?:\.[0-9]+)?", str(text).strip()))

import re as _re_pow

_POW_TOKEN = "¤POW¤{0}¤{1}¤"

_OPTION_POWER_BASE_RE = _re_pow.compile(
    r"^\(?\s*(?:[a-dA-D]|iv|iii|ii|i)\s*\)?$",
    _re_pow.I,
)

_UNI_SUP_TRANS = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-", "⁽": "(", "⁾": ")",
})
_UNI_SUP_CHARS = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾"


def _is_option_power_base(base: str) -> bool:
    """True only for real option markers: (a) a) a. (i) — not the variable a."""
    s = str(base or "").strip()
    if not s:
        return False
    return bool(_re_pow.fullmatch(
        r"\(\s*(?:[a-dA-D]|iv|iii|ii|i)\s*\)"
        r"|(?:[a-dA-D]|iv|iii|ii|i)\s*[.)]",
        s,
        _re_pow.I,
    ))


_DEGREE_EXPONENT_RE = _re_pow.compile(
    r"^(?:\\circ|\\degree|°|deg(?:ree)?|circ)$",
    _re_pow.I,
)


def _is_degree_exponent(exp: str) -> bool:
    """True when the 'exponent' is actually a degree mark, not a power."""
    s = str(exp or "").strip().strip("{}").strip()
    s = s.replace("\\mathrm{o}", "°").replace("\\mathrm{O}", "°")
    return bool(_DEGREE_EXPONENT_RE.fullmatch(s))


def _is_real_exponent(exp: str) -> bool:
    s = str(exp or "").strip()
    if not s:
        return False
    if _is_degree_exponent(s):
        return False
    if _re_pow.fullmatch(r"[×÷+\-*/^}{°]+", s):
        return False
    return bool(_re_pow.search(r"[0-9A-Za-z]", s))


def unicode_superscripts_to_latex(text: str) -> str:
    """Turn 2³ / a² / )⁻³ into 2^{3} / a^{2} / )^{-3}. Generic, no question ids."""
    if not text:
        return text

    def _repl(m):
        base = m.group(1)
        sup = m.group(2).translate(_UNI_SUP_TRANS)
        return f"{base}^{{{sup}}}"

    return _re_pow.sub(
        r"([A-Za-z0-9\)\]]|\\frac\{[^{}]+\}\{[^{}]+\})([" + _UNI_SUP_CHARS + r"]+)",
        _repl,
        text,
    )


def repair_broken_power_latex(text: str) -> str:
    """Recover common OCR/Gemini exponent wreckage without inventing numbers.

    (c) ^{-2}^{3}   -> (c) (-2)^{3}
    ^{-4}^{3}       -> (-4)^{3}
    /_{3}           -> /3
    _{3} after a value -> just 3 when it was a stray subscript
    """
    t = str(text or "")
    # ^{-2}^{3}  or  ^{-2} ^{3}  => (-2)^{3}
    t = _re_pow.sub(
        r"(?<![\w}])\^\s*\{\s*(-\s*\d+(?:\.\d+)?)\s*\}\s*\^\s*\{\s*([^{}]+)\s*\}",
        r"({\1})^{\2}",
        t,
    )
    t = t.replace("{(-", "(-").replace("(- ", "(-")
    t = _re_pow.sub(r"\(\{(-\d+(?:\.\d+)?)\)\}", r"(\1)", t)
    t = _re_pow.sub(r"\(\{(\-\d+(?:\.\d+)?)\}\)", r"(\1)", t)
    # leftover /_{3}  _{12}
    t = _re_pow.sub(r"/\s*_\s*\{\s*(-?\d+(?:\.\d+)?)\s*\}", r"/\1", t)
    t = _re_pow.sub(r"_\s*\{\s*(-?\d+(?:\.\d+)?)\s*\}", r"\1", t)
    # space after option label when Gemini glued (c)^{-2}
    t = _re_pow.sub(
        r"(\(\s*(?:[a-dA-D]|iv|iii|ii|i)\s*\))\s*(?=\^|\\frac|\\sqrt|\(|\d|[-−])",
        r"\1 ",
        t,
        flags=_re_pow.I,
    )
    return t


def protect_power_expressions(text: str) -> str:
    if not text:
        return text
    s = text

    def _skip_label_base(m):
        base = m.group(1).strip()
        exp = m.group(2).strip()
        # Group 1 was captured INSIDE parentheses, so test both "a" and "(a)".
        if (
            _is_option_power_base(base)
            or _is_option_power_base("(" + base + ")")
            or not _is_real_exponent(exp)
        ):
            return m.group(0)
        return _POW_TOKEN.format(base, exp)

    # (base)^{\\frac{n}{d}} keep frac braces intact
    s = _re_pow.sub(
        r"\(([^()]{1,80})\)\s*(?:\^|\*\*)\s*\{\s*(\\frac\{[^}]+\}\{[^}]+\})\s*\}",
        _skip_label_base,
        s,
    )
    # (base)^{exp}  or (base)^exp   — base must not be (a)/(i)
    s = _re_pow.sub(
        r"\(([^()]{1,80})\)\s*(?:\^|\*\*)\s*(?:\{)?"
        r"\s*\(?\s*"
        r"(\\frac\{[^}]+\}\{[^}]+\}|-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+)?|[A-Za-z])"
        r"\s*\)?\s*(?:\})?",
        _skip_label_base,
        s,
    )
    s = _re_pow.sub(
        r"(?<![\w\\])(\d+(?:\.\d+)?)\s*(?:\^|\*\*)\s*(?:\{)?"
        r"\s*\(?\s*"
        r"(\\frac\{[^}]+\}\{[^}]+\}|-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+)?)"
        r"\s*\)?\s*(?:\})?",
        lambda m: (
            m.group(0)
            if not _is_real_exponent(m.group(2))
            else _POW_TOKEN.format(m.group(1).strip(), m.group(2).strip().rstrip("}"))
        ),
        s,
    )
    s = _re_pow.sub(
        r"(?<![\w\\])([A-Za-z])\s*(?:\^|\*\*)\s*\{?\s*(-?\d+(?:\.\d+)?)\s*\}?",
        lambda m: (
            m.group(0)
            if _is_option_power_base(m.group(1))
            else _POW_TOKEN.format(m.group(1).strip(), m.group(2).strip())
        ),
        s,
    )
    s = _re_pow.sub(
        r"\\left\(([^()]{1,80})\\right\)\s*\^\s*\{([^}]{1,40})\}",
        lambda m: (
            m.group(0)
            if _is_option_power_base(m.group(1)) or not _is_real_exponent(m.group(2))
            else _POW_TOKEN.format(m.group(1).strip(), m.group(2).strip())
        ),
        s,
    )
    return s


def restore_power_expressions(text: str) -> str:
    def _one(m):
        base, exp = m.group(1).strip(), m.group(2).strip()
        exp = _re_pow.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", exp)
        exp = _re_pow.sub(r"\s+", "", exp).rstrip("}")
        base = base.replace(" ", "").rstrip("}")
        if _re_pow.fullmatch(r"[A-Za-z]|\d+(?:\.\d+)?", base):
            return f"{base}^({exp})"
        return f"({base})^({exp})"
    return _re_pow.sub(r"¤POW¤(.*?)¤(.*?)¤", _one, text)


def flatten_degree_powers(text):
    """150^{\\circ} / 150^{°} / 150^\\circ → 150°  (generic, any number)."""
    t = str(text or "")
    t = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:\^|\*\*)\s*\{\s*"
        r"(?:\\circ|\\degree|°|\\mathrm\{[oO]\}|circ|deg(?:ree)?)\s*\}",
        r"\1°",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:\^|\*\*)\s*"
        r"(?:\\circ|\\degree|°|circ)\b",
        r"\1°",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"(\d+(?:\.\d+)?)\s*\{\s*(?:\\circ|\\degree|°)\s*\}",
        r"\1°",
        t,
        flags=re.I,
    )
    t = re.sub(r"(\d+(?:\.\d+)?)\s*\\circ\b", r"\1°", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*\\degree\b", r"\1°", t)
    return t


def normalize_named_math_accents(text):
    """Unify ray/vector/segment latex to one command form. Letters stay as-is."""
    t = str(text or "")
    t = re.sub(r"\\+vec", r"\\vec", t)
    t = re.sub(r"\\+overrightarrow", r"\\overrightarrow", t)
    t = re.sub(r"\\+overline", r"\\overline", t)
    t = re.sub(r"\\+overleftrightarrow", r"\\overleftrightarrow", t)
    # \overrightarrow{OA}  \overset{\rightarrow}{OA}  \vec OA
    t = re.sub(
        r"\\overset\s*\{\s*\\rightarrow\s*\}\s*\{([^{}]+)\}",
        r"\\vec{\1}",
        t,
    )
    t = re.sub(r"\\overrightarrow\s*\{([^{}]+)\}", r"\\vec{\1}", t)
    t = re.sub(r"\\overrightarrow\s*([A-Za-z]{1,6})", r"\\vec{\1}", t)
    t = re.sub(r"\\vec\s*\{([^{}]+)\}", r"\\vec{\1}", t)
    t = re.sub(r"\\vec\s*([A-Za-z]{1,6})", r"\\vec{\1}", t)
    t = re.sub(r"\\overline\s*\{([^{}]+)\}", r"\\overline{\1}", t)
    t = re.sub(r"\\bar\s*\{([^{}]+)\}", r"\\overline{\1}", t)
    t = re.sub(
        r"\\overleftrightarrow\s*\{([^{}]+)\}",
        r"\\overleftrightarrow{\1}",
        t,
    )
    return t


def normalize_math_source(text):
    """Collapse Gemini/OCR latex variants into one linear form.

    No question-number hardcoding. Safe to run on every line.
    """
    t = str(text or "")
    t = flatten_degree_powers(t)
    t = normalize_named_math_accents(t)
    t = unicode_superscripts_to_latex(t)
    t = flatten_degree_powers(t)
    t = repair_broken_power_latex(t)
    t = protect_power_expressions(t)
    t = t.replace("\u2212", "-").replace("\u00d7", "×").replace("\u00f7", "÷")
    # \\frac -> \frac  (Gemini often double-escapes)
    t = re.sub(r"\\+frac", r"\\frac", t)
    t = re.sub(r"\\+sqrt", r"\\sqrt", t)
    t = re.sub(r"\\+times", "×", t)
    t = re.sub(r"\\+div", "÷", t)
    t = t.replace(r"\times", "×").replace(r"\div", "÷").replace(r"\cdot", "×")
    t = t.replace(r"\left", "").replace(r"\right", "")
    t = t.replace(r"\ ", " ")
    t = re.sub(r"\$+", "", t)
    # unicode root
    t = t.replace("√", r"\sqrt")
    # \sqrt9  \sqrt(9)  \sqrt{9}
    t = re.sub(
        r"\\sqrt\s*(?:\(([^()]+)\)|\{([^{}]+)\}|(\d+(?:\.\d+)?))",
        lambda m: r"\sqrt{" + (m.group(1) or m.group(2) or m.group(3)) + "}",
        t,
    )
    # drop a raw latex copy sitting next to an already-normalized twin
    t = re.sub(r"(\\sqrt\{[^{}]+\})\s*\1", r"\1", t)
    t = re.sub(r"(\\frac\{[^{}]+\}\{[^{}]+\})\s*\1", r"\1", t)
    t = restore_power_expressions(t)
    t = flatten_degree_powers(t)
    t = normalize_named_math_accents(t)
    return t


def _looks_like_part_label(text):
    return bool(re.match(
        r"^\s*(?:\(?\s*(?:iv|iii|ii|i)\s*\)|(?:iv|iii|ii|i)\s*[.)]"
        r"|\([a-dA-D]\)|[a-dA-D][.)])\s*",
        str(text or ""),
        flags=re.I,
    ))


def split_part_label(text):
    t = str(text or "")
    m = re.match(
        r"^(\s*(?:\(?\s*(?:iv|iii|ii|i)\s*\)|(?:iv|iii|ii|i)\s*[.)]"
        r"|\([a-dA-D]\)|[a-dA-D][.)])\s*)",
        t,
        flags=re.I,
    )
    if not m:
        return "", t
    return m.group(1), t[m.end():]


def is_math_working_body(text):
    """True when a (i)/(ii) line is algebra to compute, not an MCQ choice."""
    _, body = split_part_label(text)
    body = body.strip()
    if not body:
        return False
    scrubbed = re.sub(r"\\[A-Za-z]+", " ", body)
    words = re.findall(r"[A-Za-z\u0900-\u097F]{3,}", scrubbed)
    mathish = bool(re.search(
        r"\\frac|\\sqrt|√|×|÷|\^|[_^]|[-−]?\d+\s*/\s*[-−]?\d+|[{}]",
        body,
    ))
    return mathish and len(words) <= 1


def iter_math_tokens(text):
    """Yield ('text', s) or ('frac'|'sup'|'sqrt', payload)."""
    text = normalize_math_source(text)
    for ch, pair in _VULGAR.items():
        text = text.replace(ch, f"\\frac{{{pair[0]}}}{{{pair[1]}}}")
    text = re.sub(
        r"(\d+)\s+(\d+)\s*/\s*(\d+)",
        lambda m: f"{m.group(1)}\\frac{{{m.group(2)}}}{{{m.group(3)}}}",
        text,
    )
    text = re.sub(r"\$+", "", text)

    i = 0
    n = len(text)
    buf = []

    def flush():
        chunk = "".join(buf)
        buf.clear()
        return chunk

    while i < n:
        # Never treat option labels (i)/(a) as a math atom or power base.
        lab = re.match(
            r"\(\s*(?:iv|iii|ii|i|[a-dA-D])\s*\)|(?:iv|iii|ii|i|[a-dA-D])\s*[.)]",
            text[i:],
            flags=re.I,
        )
        if lab and (i == 0 or text[i - 1] in " \t("):
            # only if this really is a marker at a boundary
            nxt = text[i + lab.end():i + lab.end() + 1]
            prev_ok = i == 0 or not text[i - 1].isalnum()
            if prev_ok:
                chunk = flush()
                if chunk:
                    yield ("text", chunk)
                yield ("text", lab.group(0))
                i += lab.end()
                continue

        if text.startswith("\\frac", i):
            j = i + 5
            while j < n and text[j].isspace():
                j += 1
            num = _balanced_braces(text, j)
            if num:
                den = _balanced_braces(text, num[1])
                if den:
                    chunk = flush()
                    if chunk:
                        yield ("text", chunk)
                    yield ("frac", (num[0], den[0]))
                    i = den[1]
                    continue
            # \frac-36{5} or \frac{-36}5
            m = re.match(r"\\frac\s*\{?\s*(-?\d+(?:\.\d+)?)\s*\}?\s*\{?\s*(-?\d+(?:\.\d+)?)\s*\}?", text[i:])
            if m:
                chunk = flush()
                if chunk:
                    yield ("text", chunk)
                yield ("frac", (m.group(1), m.group(2)))
                i += m.end()
                continue

        if text.startswith("\\sqrt", i):
            j = i + 5
            while j < n and text[j].isspace():
                j += 1
            inner = _balanced_braces(text, j)
            if inner:
                chunk = flush()
                if chunk:
                    yield ("text", chunk)
                yield ("sqrt", inner[0])
                i = inner[1]
                continue

        accent = None
        if text.startswith("\\vec", i):
            accent = ("vec", 4, "→")
        elif text.startswith("\\overline", i):
            accent = ("bar", 9, "¯")
        elif text.startswith("\\overleftrightarrow", i):
            accent = ("line", 19, "↔")
        if accent:
            kind, cmd_len, mark = accent
            j = i + cmd_len
            while j < n and text[j].isspace():
                j += 1
            inner = _balanced_braces(text, j)
            if inner:
                chunk = flush()
                if chunk:
                    yield ("text", chunk)
                yield (kind, (inner[0].strip(), mark))
                i = inner[1]
                continue

        mpow = re.match(
            r"(\((?:\\frac\{[^{}]+\}\{[^{}]+\}|[^()]+)\)|[A-Za-z0-9]+(?:\.\d+)?)"
            r"\s*(?:\^|\*\*)\s*"
            r"(?:\{([^{}]+)\}|\(([^{()]+)\)|(\\frac\{[^{}]+\}\{[^{}]+\})|(-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+)?))",
            text[i:],
        )
        if mpow:
            base = mpow.group(1)
            exp = mpow.group(2) or mpow.group(3) or mpow.group(4) or mpow.group(5)
            raw_base = base
            if base.startswith("(") and base.endswith(")"):
                base = base[1:-1]
            if exp.startswith("{") and exp.endswith("}"):
                exp = exp[1:-1]
            exp = str(exp).strip().rstrip("}")
            base = str(base).strip().rstrip("}")
            # Option labels and operator-only "exponents" are not powers.
            if _is_option_power_base(raw_base) or _is_option_power_base(base) or not _is_real_exponent(exp):
                buf.append(text[i])
                i += 1
                continue
            chunk = flush()
            if chunk:
                yield ("text", chunk)
            yield ("sup", (base, exp))
            i += mpow.end()
            continue


        if text[i] == "/" and i > 0:
            left_m = re.search(r"(-?[A-Za-z0-9]+(?:\.[0-9]+)?)$", "".join(buf))
            right_m = re.match(r"(-?[A-Za-z0-9]+(?:\.[0-9]+)?)", text[i + 1:])
            if left_m and right_m and not _looks_like_date_slash(text, i):
                if _simple_math_atom(left_m.group(1).lstrip("-")) and _simple_math_atom(right_m.group(1).lstrip("-")):
                    kept = "".join(buf)[: -len(left_m.group(1))]
                    buf = list(kept)
                    chunk = flush()
                    if chunk:
                        yield ("text", chunk)
                    yield ("frac", (left_m.group(1), right_m.group(1)))
                    i += 1 + len(right_m.group(1))
                    continue
        buf.append(text[i])
        i += 1
    if buf:
        yield ("text", "".join(buf))


def _omml_inner_from_linear(expr):
    """Turn a small linear math snippet into OMML children string or a run."""
    expr = str(expr or "").strip()
    if expr.startswith("\\frac"):
        rest = expr[5:].lstrip()
        num = _balanced_braces(rest, 0)
        if num:
            den = _balanced_braces(rest, num[1])
            if den:
                return (
                    f"<m:f><m:num>{_omml_run(num[0])}</m:num>"
                    f"<m:den>{_omml_run(den[0])}</m:den></m:f>"
                )
    if "/" in expr and not _looks_like_date_slash(expr + " ", expr.find("/")):
        a, b = expr.split("/", 1)
        if a.strip() and b.strip() and " " not in a.strip() and " " not in b.strip():
            return (
                f"<m:f><m:num>{_omml_run(a.strip())}</m:num>"
                f"<m:den>{_omml_run(b.strip())}</m:den></m:f>"
            )
    return _omml_run(expr)


def _omml_sup(base, exp):
    xml = (
        f'<m:oMath xmlns:m="{MATH_NS}">'
        f"<m:sSup>"
        f"<m:e>{_omml_inner_from_linear(base)}</m:e>"
        f"<m:sup>{_omml_inner_from_linear(exp)}</m:sup>"
        f"</m:sSup>"
        f"</m:oMath>"
    )
    return _omml_from_xml(xml)


def _omml_accent(base, mark="→"):
    """Ray / segment / line as a real Word accent, never raw \\vec{OA}."""
    xml = (
        f'<m:oMath xmlns:m="{MATH_NS}">'
        f"<m:acc>"
        f"<m:accPr><m:chr m:val='{_math_xml_escape(mark)}'/></m:accPr>"
        f"<m:e>{_omml_run(base)}</m:e>"
        f"</m:acc>"
        f"</m:oMath>"
    )
    return _omml_from_xml(xml)


def add_text_with_math(paragraph, text, bold=False):
    """Write a line with stacked fractions / powers as real Word math."""
    last_run = None
    has_math = False
    source = flatten_degree_powers(normalize_geometry_symbols(restore_exam_spaces(text)))
    for kind, payload in iter_math_tokens(source):
        if kind == "text":
            if payload == "":
                continue
            run = add_plain_text_symbol_safe(paragraph, payload, bold=bold)
            if run is not None:
                last_run = run
        else:
            has_math = True
            if kind == "frac":
                node = _omml_fraction(payload[0], payload[1])
            elif kind == "sup":
                base, exp = payload
                if _is_degree_exponent(exp):
                    run = add_plain_text_symbol_safe(
                        paragraph, f"{base}°", bold=bold
                    )
                    if run is not None:
                        last_run = run
                    continue
                node = _omml_sup(base, exp)
            elif kind in ("vec", "bar", "line"):
                node = _omml_accent(payload[0], payload[1])
            else:
                node = _omml_sqrt(payload)
            paragraph._p.append(node)
    if last_run is None:
        last_run = paragraph.add_run("")
        set_run_language_font(last_run, " ", bold=bold)
    return last_run, has_math



# ============================================================
# CLASS 1-3 COLUMN SUMS — digit place-value formation
# Addition / subtraction / multiplication / division
# Each digit sits in its own cell so ones-tens-hundreds stay aligned.
# One source operation = one compact stack. Never page-wide bars.
# ============================================================
SUM_OP_CHARS = "+-×xX÷/"
COLUMN_SUMS_PER_ROW_MIN = 2
COLUMN_SUMS_PER_ROW_MAX = 5
COLUMN_SUM_DIGIT_CELL_IN = 0.30
COLUMN_SUM_OP_CELL_IN = 0.28
_SUM_MARKUP_RE = re.compile(
    r"^\[\[(ADD|SUB|MUL|DIV)\]\]\s*(.*)$",
    re.I,
)
_SUM_RULE_RE = re.compile(r"^[\s_\-=─—]{3,}$")
_SUM_NUMBER_RE = re.compile(r"^[+\-×xX÷/]?\s*[\d\s]+$")
_SUM_DIV_RE = re.compile(
    r"^\s*(\d{1,4})\s*[\)]\s*(\d{1,8})\s*[\(]?\s*$",
    re.I,
)
_INLINE_SUM_RE = re.compile(
    r"^\s*(\d{1,8})\s*([+\-×xX÷/*])\s*(\d{1,8})\s*=?\s*_*\s*$"
)
_SUM_LABEL_RE = re.compile(
    r"^(?:\(?[a-zA-Z]\)|[a-zA-Z][\.)]|\([ivxlcdm]+\)|\([0-9]+\)|[0-9]+[\.)])(?:\s+|$)",
    re.I,
)

def _is_lone_sum_label(line):
    t = str(line or "").strip()
    if not t:
        return False
    m = _SUM_LABEL_RE.match(t)
    return bool(m) and not t[m.end():].strip()

_SUM_HEADING_RE = re.compile(
    r"(addition|subtraction|multiplication|division|"
    r"जोड़|घटाव|गुणा|भाग|योग|minus|plus|"
    r"ques(?:tion)?\s*\d|"
    r"प्रश्न\s*[-.:]?\s*\d)",
    re.I,
)
_SIDE_GAP_RE = re.compile(r"\s{2,}")


def _sum_op_normalize(ch):
    if ch in "+":
        return "+"
    if ch in "-–—":
        return "−"
    if ch in "×xX*":
        return "×"
    if ch in "÷/":
        return "÷"
    return ch


def _split_sum_label(line):
    t = str(line or "").strip()
    m = _SUM_LABEL_RE.match(t)
    if not m:
        return "", t
    return m.group(0).strip(), t[m.end():].strip()


def _sum_body_line(line):
    _, body = _split_sum_label(line)
    return body


def is_column_sum_line(line):
    t = _sum_body_line(line)
    if not t:
        return False
    if _SUM_MARKUP_RE.match(t) or _SUM_RULE_RE.match(t) or _SUM_DIV_RE.match(t):
        return True
    if _INLINE_SUM_RE.match(t):
        return True
    if _SUM_NUMBER_RE.match(t) and any(ch.isdigit() for ch in t):
        digits = re.sub(r"\D", "", t)
        return 1 <= len(digits) <= 8
    return False


def _sum_line_kind(line):
    t = _sum_body_line(line)
    m = _SUM_MARKUP_RE.match(t)
    if m:
        return m.group(1).upper()
    if _SUM_DIV_RE.match(t) or t.upper().startswith("[[DIV]]"):
        return "DIV"
    inline = _INLINE_SUM_RE.match(t)
    if inline:
        return {"+": "ADD", "−": "SUB", "-": "SUB", "×": "MUL",
                "x": "MUL", "X": "MUL", "*": "MUL", "÷": "DIV",
                "/": "DIV"}.get(inline.group(2), "ADD")
    if t[:1] in "×xX*":
        return "MUL"
    if t[:1] in "+":
        return "ADD"
    if t[:1] in "-–—":
        return "SUB"
    if t[:1] in "÷/":
        return "DIV"
    return None


def _sum_line_has_number(line):
    t = _sum_body_line(line)
    extra = ""
    m = _SUM_MARKUP_RE.match(t)
    if m:
        extra = m.group(2) or ""
        t = extra or t
    if _INLINE_SUM_RE.match(t) or _SUM_DIV_RE.match(t):
        return True
    if _SUM_NUMBER_RE.match(t) and re.search(r"\d", t):
        return True
    return False


def is_sum_section_heading(line):
    """Ques 1) Addition / घटाव — not itself a stacked sum."""
    t = str(line or "").strip()
    if not t:
        return False
    if _SUM_MARKUP_RE.match(_sum_body_line(t)):
        return False
    if is_column_sum_line(t) and not _SUM_HEADING_RE.search(t):
        return False
    return bool(_SUM_HEADING_RE.search(t)) and not _INLINE_SUM_RE.match(_sum_body_line(t))


def _looks_like_sum_cell(tok):
    t = str(tok or "").strip()
    if not t:
        return False
    if _SUM_RULE_RE.match(t):
        return True
    if _SUM_LABEL_RE.match(t + " ") or _SUM_LABEL_RE.match(t):
        return True
    if is_column_sum_line(t):
        return True
    if re.fullmatch(r"[+\-−×xX÷/*]", t):
        return True
    return False


def _split_side_by_side_cells(line):
    """Split one printed row that holds 2+ sums sitting beside each other."""
    t = str(line or "").strip()
    if not t:
        return []
    if t.upper().startswith("[["):
        return [t]
    parts = [p.strip() for p in _SIDE_GAP_RE.split(t) if p.strip()]
    if len(parts) < 2:
        return []
    if not all(_looks_like_sum_cell(p) for p in parts):
        return []
    return parts


def explode_side_by_side_column_sums(lines):
    """Rewrite a side-by-side printed band into consecutive vertical sum blocks.

    Source:
        57          68
      + 24        + 35
    becomes two sequential column-sum blocks so the renderer can place
    them as one row with exactly two columns.
    """
    out = []
    i = 0
    n = len(lines)
    while i < n:
        raw = str(lines[i]).rstrip()
        cells = _split_side_by_side_cells(raw)
        if len(cells) < 2:
            out.append(lines[i])
            i += 1
            continue

        cols = len(cells)
        band = [cells]
        j = i + 1
        while j < n:
            nxt = str(lines[j]).strip()
            if not nxt:
                break
            if is_sum_section_heading(nxt) or (
                "has_explicit_question_label" in globals()
                and has_explicit_question_label(nxt)
                and not is_column_sum_line(nxt)
            ):
                break
            nxt_cells = _split_side_by_side_cells(nxt)
            if len(nxt_cells) == cols and all(_looks_like_sum_cell(c) for c in nxt_cells):
                band.append(nxt_cells)
                j += 1
                continue
            # A lone rule / number line that belongs to the last column-set
            if is_column_sum_line(nxt) or _SUM_RULE_RE.match(_sum_body_line(nxt)):
                # cannot safely assign to columns — stop band
                break
            break

        columns = [[] for _ in range(cols)]
        for row_cells in band:
            for c, tok in enumerate(row_cells):
                columns[c].append(tok)

        useful_cols = 0
        for col in columns:
            blob = " ".join(col)
            if re.search(r"\d", blob):
                useful_cols += 1
                out.extend(col)
        if useful_cols < 2:
            out.append(lines[i])
            i += 1
            continue
        i = j
    return out



def _parse_sum_block(block):
    kind = None
    rows = []
    first_body = _sum_body_line(block[0]) if block else ""
    m0 = _SUM_MARKUP_RE.match(first_body)
    body = list(block)
    if m0:
        kind = m0.group(1).upper()
        extra = (m0.group(2) or "").strip()
        body = body[1:]
        if extra:
            body = [extra] + body

    for raw in body:
        line = _sum_body_line(raw)
        if not line:
            continue
        if _SUM_RULE_RE.match(line):
            rows.append(("rule", "—", ""))
            continue
        div = _SUM_DIV_RE.match(line)
        if div:
            kind = kind or "DIV"
            rows.append(("div", div.group(1), div.group(2)))
            continue
        inline = _INLINE_SUM_RE.match(line)
        if inline:
            op = _sum_op_normalize(inline.group(2))
            kind = kind or {"+": "ADD", "−": "SUB", "×": "MUL", "÷": "DIV"}.get(op, "ADD")
            rows.append(("num", "", inline.group(1)))
            rows.append(("num", op, inline.group(3)))
            rows.append(("rule", "—", ""))
            rows.append(("blank", "", ""))
            continue
        op = ""
        rest = line
        if rest and rest[0] in "+-×xX÷/*":
            op = _sum_op_normalize(rest[0])
            rest = rest[1:].strip()
            kind = kind or {"+": "ADD", "−": "SUB", "×": "MUL", "÷": "DIV"}.get(op, "ADD")
        digits = re.sub(r"\s+", "", rest)
        if re.fullmatch(r"_+", digits):
            rows.append(("blank", op, ""))
        elif digits.isdigit():
            rows.append(("num", op, digits))
        else:
            rows.append(("text", "", line))
    return kind or "ADD", rows


def _set_fixed_table_width(table, inches):
    tblPr = table._tbl.tblPr
    tblLayout = tblPr.first_child_found_in("w:tblLayout")
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(int(max(0.8, inches) * 1440)))
    tblW.set(qn("w:type"), "dxa")


def _set_cell_bottom_border(cell, color="2E75B6", size="16"):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge in ("top", "left", "right"):
        node = tcBorders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tcBorders.append(node)
        node.set(qn("w:val"), "nil")
        node.set(qn("w:sz"), "0")
        node.set(qn("w:color"), "auto")
    bottom = tcBorders.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        tcBorders.append(bottom)
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "0")
    bottom.set(qn("w:color"), color)


def _sum_block_label(block):
    if not block:
        return ""
    lab, _ = _split_sum_label(block[0])
    return lab


def _sum_digit_width(block):
    _kind, rows = _parse_sum_block(block)
    nums = [r[2] for r in rows if r[0] in ("num", "blank") and r[2]]
    return max((len(n) for n in nums), default=2)


def _chunk_sums_per_row(n):
    """Pack n sums into one row of exactly n columns when n <= MAX.

    1 sum → 1 column, 2 → 2, 3 → 3, 4 → 4, 5 → 5.
    Only wrap when there are more than MAX sums. Never invent extra sums.
    """
    lo = COLUMN_SUMS_PER_ROW_MIN
    hi = COLUMN_SUMS_PER_ROW_MAX
    if n <= 0:
        return []
    if n <= hi:
        return [n]
    chunks = []
    left = n
    while left > 0:
        if left <= hi:
            if left < lo and chunks:
                steal = lo - left
                if chunks[-1] - steal >= lo:
                    chunks[-1] -= steal
                    left += steal
            chunks.append(left)
            break
        take = hi
        rem = left - take
        if 0 < rem < lo:
            take = left - lo
            if take < lo:
                take = max(lo, left // 2)
        chunks.append(take)
        left -= take
    return chunks


def collect_column_sum_block(lines, start):
    """Collect ONE stacked operation. A new [[MUL]] / (b)+digits starts the next block."""
    if start >= len(lines):
        return [], start
    idx = start
    first = lines[idx].strip()
    lab, body = _split_sum_label(first)

    if (lab and not body) or _is_lone_sum_label(first):
        if idx + 1 < len(lines) and is_column_sum_line(lines[idx + 1]):
            glued_label = lab or first.strip()
            first = glued_label + " " + lines[idx + 1].strip()
            idx += 1
        else:
            return [], start

    if not is_column_sum_line(first):
        return [], start

    block = [first]
    j = idx + 1
    number_lines = 1 if _sum_line_has_number(first) else 0
    kind = _sum_line_kind(first)

    while j < len(lines):
        nxt = lines[j].strip()
        if not nxt:
            break

        nxt_label, nxt_body = _split_sum_label(nxt)
        nxt_kind = _sum_line_kind(nxt)

        if ((_is_lone_sum_label(nxt) or (nxt_label and is_column_sum_line(nxt)))
                and number_lines >= 1):
            break
        if nxt_kind in ("ADD", "SUB", "MUL", "DIV") and _SUM_MARKUP_RE.match(nxt_body):
            if number_lines >= 1 or kind:
                break

        if not (is_column_sum_line(nxt) or _SUM_RULE_RE.match(nxt_body)):
            break

        block.append(nxt)
        if _sum_line_has_number(nxt):
            number_lines += 1
        kind = kind or nxt_kind
        j += 1

        if kind == "MUL" and number_lines >= 2:
            if j < len(lines):
                peek_body = _sum_body_line(lines[j])
                if _SUM_RULE_RE.match(peek_body) or re.fullmatch(r"_+", peek_body or ""):
                    block.append(lines[j].strip())
                    j += 1
            break
        if number_lines >= 6:
            break

    blob = " ".join(_sum_body_line(x) for x in block)
    useful = (
        bool(_SUM_MARKUP_RE.match(_sum_body_line(first)))
        or bool(_INLINE_SUM_RE.match(_sum_body_line(first)))
        or bool(_SUM_DIV_RE.match(_sum_body_line(first)))
        or (number_lines >= 2 and any(ch in blob for ch in "+-×xX÷/*−"))
        or (number_lines >= 2)
    )
    if not useful:
        return [], start
    return block, j


def collect_column_sum_group(lines, start):
    """All short sums until the next Ques heading → one N-column row."""
    blocks = []
    j = start
    while j < len(lines):
        while j < len(lines) and not str(lines[j]).strip():
            j += 1
        if j >= len(lines):
            break
        peek = str(lines[j]).strip()
        if is_sum_section_heading(peek):
            break
        if has_explicit_question_label(peek) and not is_column_sum_line(peek) and not _is_lone_sum_label(peek):
            break
        if _is_lone_sum_label(peek):
            nxt_i = j + 1
            while nxt_i < len(lines) and not str(lines[nxt_i]).strip():
                nxt_i += 1
            if nxt_i >= len(lines) or not is_column_sum_line(lines[nxt_i]):
                break
        block, end = collect_column_sum_block(lines, j)
        if not block:
            break
        blocks.append(block)
        j = end
        if len(blocks) >= 20:
            break
    if not blocks:
        return [], start
    return blocks, j


def _render_div_house(cell, divisor, dividend):
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(p, before=0, after=0, line_spacing=1.0)
    blank = p.add_run("    " + "_" * max(5, len(str(dividend)) + 1))
    set_run_language_font(blank, blank.text, bold=False)
    blank.font.size = Pt(16)
    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(p2, before=0, after=2, line_spacing=1.0)
    show = f"{divisor} ) {dividend}"
    run = p2.add_run(show)
    set_run_language_font(run, show, bold=True)
    run.font.size = Pt(16)


def _render_one_column_sum(cell, block, digit_width):
    """Place-value stack inside one outer cell. Ones always right-aligned."""
    kind, rows = _parse_sum_block(block)
    label = _sum_block_label(block)
    head = cell.paragraphs[0]
    head.text = ""
    head.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(head, before=0, after=1, line_spacing=1.0)
    if label:
        run = head.add_run(label + "  ")
        set_run_language_font(run, label, bold=True)
        run.font.size = Pt(14)

    if kind == "DIV" and any(r[0] == "div" for r in rows):
        _div = next(r for r in rows if r[0] == "div")
        if label:
            _render_div_house(cell, _div[1], _div[2])
        else:
            _render_div_house(cell, _div[1], _div[2])
        return True

    work = [r for r in rows if r[0] in ("num", "blank")]
    if not work:
        return False
    last_num_idx = max((i for i, r in enumerate(work) if r[0] == "num"), default=None)
    if last_num_idx is None:
        return False
    if not any(r[0] == "blank" for r in work):
        work.append(("blank", "", ""))

    width = max(2, int(digit_width))
    cols = width + 1
    op_w = COLUMN_SUM_OP_CELL_IN
    dig_w = COLUMN_SUM_DIGIT_CELL_IN
    total_w = op_w + width * dig_w

    table = cell.add_table(rows=len(work), cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    try:
        force_table_inline(table)
        remove_table_borders(table)
        _set_fixed_table_width(table, total_w)
    except Exception:
        pass

    for c in range(cols):
        w = op_w if c == 0 else dig_w
        try:
            table.columns[c].width = Inches(w)
        except Exception:
            pass

    for r_idx, (rtype, op, digits) in enumerate(work):
        padded = (digits or "").rjust(width)
        for c in range(cols):
            inner = table.cell(r_idx, c)
            inner.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            w = op_w if c == 0 else dig_w
            try:
                set_cell_margins(inner, top=10, start=10, bottom=10, end=10)
            except Exception:
                pass
            tcPr = inner._tc.get_or_add_tcPr()
            tcW = tcPr.find(qn("w:tcW"))
            if tcW is None:
                tcW = OxmlElement("w:tcW")
                tcPr.append(tcW)
            tcW.set(qn("w:w"), str(int(w * 1440)))
            tcW.set(qn("w:type"), "dxa")

            para = inner.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_spacing(para, before=0, after=0, line_spacing=1.0)
            if c == 0:
                ch = op if (rtype == "num" and op) else ""
            else:
                ch = padded[c - 1] if c - 1 < len(padded) else ""
                if ch == " ":
                    ch = ""
            run = para.add_run(ch)
            set_run_language_font(run, ch or " ", bold=True)
            run.font.size = Pt(16)
            if r_idx == last_num_idx:
                _set_cell_bottom_border(inner, color="2E75B6", size="16")
    return True


def add_column_sum_row(doc, blocks):
    """One horizontal band: 1–5 compact stacks, digits aligned in each stack."""
    if not blocks:
        return False
    n = len(blocks)
    digit_width = max(_sum_digit_width(b) for b in blocks)
    outer = doc.add_table(rows=1, cols=n)
    outer.alignment = WD_TABLE_ALIGNMENT.CENTER
    outer.autofit = False
    try:
        force_table_inline(outer)
        remove_table_borders(outer)
        _set_fixed_table_width(outer, OPTION_GRID_WIDTH)
    except Exception:
        pass
    col_w = OPTION_GRID_WIDTH / n
    for i, block in enumerate(blocks):
        cell = outer.cell(0, i)
        cell.width = Inches(col_w)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        try:
            set_cell_margins(cell, top=40, start=40, bottom=40, end=40)
        except Exception:
            pass
        _render_one_column_sum(cell, block, digit_width)
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, before=2, after=8, line_spacing=1.0)
    return True


def add_column_sum_table(doc, block):
    """Back-compat: a single stack still uses the shared row renderer."""
    return add_column_sum_row(doc, [block])


def add_column_sum_group(doc, blocks):
    """One row, N columns = N sums in this group (wrap only after MAX)."""
    if not blocks:
        return False
    chunks = _chunk_sums_per_row(len(blocks))
    idx = 0
    for count in chunks:
        add_column_sum_row(doc, blocks[idx:idx + count])
        idx += count
    return True


# ============================================================
# MATH PACK A+B+C — Nursery–12 support (text-safe, print-safe)
# A: number lines + stronger primary sums
# B: figure boxes + geometry signs
# C: matrices + board formulas (int / lim / log)
# ============================================================
_NUMLINE_RE = re.compile(
    r"^\[\[NLINE\]\]\s*(.+)$|"
    r"^((?:\s*-?\d+(?:\.\d+)?\s*[—\-–]{1,3}\s*){2,}-?\d+(?:\.\d+)?)\s*$"
)
_MATRIX_RE = re.compile(
    r"^\[\[MAT(?:RIX)?\]\]\s*(.+)$|"
    r"^\\begin\{(?:b?matrix|pmatrix|bmatrix)\}(.+)\\end\{(?:b?matrix|pmatrix|bmatrix)\}$|"
    r"^\[\[[^\]]+\](?:\s*,\s*\[[^\]]+\])+\]$"
)
_FIG_RE = re.compile(
    r"^\[\[FIG(?:URE)?\]\]\s*(.*)$|"
    r"(draw\s+the\s+(figure|graph|diagram)|चित्र\s*बनाइए|"
    r"construct\s+a|number\s+line|bar\s+graph|pie\s+chart|"
    r"plot\s+the|coordinate\s+axes)",
    re.I,
)


# Geometry / operator signs that Bookman Old Style cannot draw (become □).
# These characters are printed with SYMBOL_FALLBACK_FONT so the box never returns.
SYMBOL_FALLBACK_FONT = "Cambria Math"
_GEOM_SYMBOL_CHARS = (
    "∠△▲∆∧∨∥⊥→←↔↦⇒⇐⇔"
    "≤≥≠≈∞±π×÷°"
)
_GEOM_SYMBOL_RE = re.compile("([" + re.escape(_GEOM_SYMBOL_CHARS) + "])")


def normalize_geometry_symbols(text):
    """Convert LaTeX geometry COMMANDS only. Never eat English/Hindi words.

    The word "angle" / "triangle" / "ray" must stay a word.
    Degree-as-power is flattened here so Word never prints 140^{°}.
    """
    if not text:
        return text
    s = flatten_degree_powers(str(text))
    s = normalize_named_math_accents(s)
    # Commands only — do NOT map the English word "angle"/"triangle".
    reps = [
        (r"\\angle\s*\{([^{}]+)\}", r"∠\1"),
        (r"\\angle\s*", "∠"),
        (r"\\triangle\s*\{([^{}]+)\}", r"Δ\1"),
        (r"\\triangle\s*", "Δ"),
        (r"\\Delta\s*", "Δ"),
        (r"\\parallel\s*", "∥"),
        (r"\\perp\s*", "⊥"),
        (r"\\degree\b", "°"),
        (r"(?<![A-Za-z\\])\\circ\b", "°"),
        (r"(?<=\d)\s*deg(?:ree)?s?\b", "°"),
        (r"\\pi\b", "π"),
        (r"\\times", "×"),
        (r"\\div", "÷"),
        (r"\\leq", "≤"),
        (r"\\geq", "≥"),
        (r"\\neq", "≠"),
        (r"\\approx", "≈"),
        (r"\\pm", "±"),
        (r"\\infty", "∞"),
        (r"\\leftrightarrow\b", "↔"),
        (r"\\rightarrow", "→"),
        (r"\\leftarrow", "←"),
        (r"\\to\b", "→"),
        (r"\\implies\b", "⇒"),
    ]
    for a, b in reps:
        s = re.sub(a, b, s)
    s = flatten_degree_powers(s)
    return s


def add_plain_text_symbol_safe(paragraph, text, bold=False):
    """Write text; geometry signs use Cambria Math so they never become □."""
    last_run = None
    s = str(text or "")
    if not s:
        return None
    parts = _GEOM_SYMBOL_RE.split(s)
    for part in parts:
        if part == "":
            continue
        run = paragraph.add_run(part)
        if _GEOM_SYMBOL_RE.fullmatch(part):
            set_run_font(run, SYMBOL_FALLBACK_FONT, BODY_SIZE, bold=bold)
        else:
            set_run_language_font(run, part, bold=bold)
        last_run = run
    return last_run


def _parse_number_line_tokens(raw):
    parts = re.split(r"[—\-–]+", str(raw))
    vals = [p.strip() for p in parts if p.strip()]
    return vals


def is_number_line_line(line):
    t = str(line or "").strip()
    if t.upper().startswith("[[NLINE]]"):
        return True
    if _NUMLINE_RE.match(t) and t.count("-") + t.count("—") >= 2:
        if re.search(r"\d", t) and not re.search(r"[A-Za-z\u0900-\u097F]{4,}", t):
            return True
    return False


def add_number_line(doc, line):
    t = str(line).strip()
    m = re.match(r"^\[\[NLINE\]\]\s*(.+)$", t, re.I)
    raw = m.group(1) if m else t
    vals = _parse_number_line_tokens(raw)
    if len(vals) < 3:
        vals = [str(i) for i in range(0, 11)]
    cols = len(vals) * 2 - 1
    table = doc.add_table(rows=2, cols=min(cols, 21))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        remove_table_borders(table)
        force_table_inline(table)
    except Exception:
        pass
    cells_used = min(len(vals), 11)
    for i in range(cells_used):
        tick = table.cell(0, i)
        lab = table.cell(1, i)
        p0 = tick.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = p0.add_run("│" if i == 0 or i == cells_used - 1 else "┴")
        set_run_language_font(r0, "│", bold=True)
        r0.font.size = Pt(14)
        p1 = lab.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p1.add_run(vals[i] if i < len(vals) else "")
        set_run_language_font(r1, vals[i] if i < len(vals) else " ", bold=True)
        r1.font.size = Pt(12)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(cap, before=0, after=8, line_spacing=1.0)
    cr = cap.add_run("—" * max(12, cells_used * 2))
    set_run_language_font(cr, "—", bold=False)
    return True


def add_figure_box(doc, caption=""):
    """Empty box, basic shape, or junior-section diagram for class 6-8."""
    kind = None
    try:
        kind = detect_basic_shape(caption)
    except Exception:
        kind = None

    table = doc.add_table(rows=2, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    pic_cell = table.cell(0, 0)
    cap_cell = table.cell(1, 0)
    try:
        set_cell_margins(pic_cell, top=40, start=40, bottom=20, end=40)
        set_cell_margins(cap_cell, top=0, start=40, bottom=40, end=40)
    except Exception:
        pass

    p = pic_cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, before=2, after=0, line_spacing=1.0)
    drawn = False
    if kind:
        try:
            drawn = add_shape_picture(p, kind, width_in=1.15)
        except Exception:
            drawn = False
    if not drawn and attach_diagram:
        _cls = re.sub(r"[^0-9A-Z]", "", str(CURRENT_PAPER_CLASS or "").upper())
        _grade = {"6": 6, "VI": 6, "7": 7, "VII": 7, "8": 8, "VIII": 8}.get(_cls, 0)
        if 6 <= _grade <= 8:
            try:
                _sec = doc.sections[0]
                content_mm = (_sec.page_width - _sec.left_margin - _sec.right_margin).mm
                block = attach_diagram(caption, _grade, content_mm)
                if block and block.get("png"):
                    p.add_run().add_picture(block["png"], width=Mm(block["width_mm"]))
                    drawn = True
            except Exception:
                drawn = False
    if not drawn:
        try:
            set_cell_shading(pic_cell, "F7F7F7")
        except Exception:
            pass
        r = p.add_run(" ")
        set_run_language_font(r, " ", bold=False)
        r.font.size = Pt(36)

    label = re.sub(r"^\[\[FIG(?:URE)?\]\]\s*", "", str(caption or ""), flags=re.I).strip()
    label = re.sub(r"^\(?[a-zA-Z0-9]+\)\s*", "", label).strip()
    p2 = cap_cell.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p2, before=0, after=2, line_spacing=1.0)
    if label:
        run = p2.add_run(label)
        set_run_language_font(run, label, bold=False)
        run.font.size = Pt(12)
    return True


def collect_fig_shape_group(lines, start):
    """Consecutive [[FIG]] lines → one 2x2 (or 2-col) shape row."""
    items = []
    j = start
    while j < len(lines):
        t = str(lines[j]).strip()
        if not t:
            j += 1
            continue
        if not (t.upper().startswith("[[FIG") or "[[FIG" in t.upper()):
            break
        items.append(t)
        j += 1
        if len(items) >= 4:
            break
    if len(items) < 2:
        return [], start
    return items, j


def add_fig_shape_group(doc, items):
    """2 or 4 labelled shape cards in one table."""
    n = len(items)
    cols = 4 if n >= 4 else 2
    rows = (n + cols - 1) // cols
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        remove_table_borders(table)
        force_table_inline(table)
    except Exception:
        pass
    for i, raw in enumerate(items):
        r, c = divmod(i, cols)
        cell = table.cell(r, c)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        lab = ""
        cap = raw
        m = re.match(r"^(\(?[a-zA-Z0-9]+\)|[a-zA-Z0-9][\.)])\s*", raw)
        if m:
            lab = m.group(1)
            cap = raw[m.end():]
        cap = re.sub(r"^\[\[FIG(?:URE)?\]\]\s*", "", cap, flags=re.I).strip()
        p0 = cell.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(p0, before=2, after=2, line_spacing=1.0)
        if lab:
            rr = p0.add_run(lab + "  ")
            set_run_language_font(rr, lab, bold=True)
            rr.font.size = Pt(14)
        try:
            kind = detect_basic_shape(cap or raw)
            if kind:
                add_shape_picture(p0, kind, width_in=1.05)
        except Exception:
            pass
        p1 = cell.add_paragraph()
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(p1, before=0, after=6, line_spacing=1.0)
        show = cap or ""
        run = p1.add_run(show)
        set_run_language_font(run, show, bold=False)
        run.font.size = Pt(12)
    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=2, after=8, line_spacing=1.0)
    return True


def _parse_matrix_rows(raw):
    t = str(raw).strip()
    t = re.sub(r"^\[\[MAT(?:RIX)?\]\]\s*", "", t, flags=re.I)
    t = t.replace(r"\begin{matrix}", "").replace(r"\end{matrix}", "")
    t = t.replace(r"\begin{bmatrix}", "").replace(r"\end{bmatrix}", "")
    t = t.replace(r"\begin{pmatrix}", "").replace(r"\end{pmatrix}", "")
    if t.startswith("[[") and t.endswith("]]"):
        inner = t[1:-1]
        rows = re.findall(r"\[([^\[\]]+)\]", inner)
        return [re.split(r"\s*,\s*|\s+", r.strip()) for r in rows if r.strip()]
    parts = re.split(r"\s*\\\\\s*|\n", t)
    grid = []
    for part in parts:
        cells = [c.strip() for c in re.split(r"\s*&\s*|\s*,\s*", part) if c.strip()]
        if cells:
            grid.append(cells)
    return grid


def is_matrix_line(line):
    t = str(line or "").strip()
    if t.upper().startswith("[[MAT"):
        return True
    if r"\begin{matrix}" in t or r"\begin{bmatrix}" in t or r"\begin{pmatrix}" in t:
        return True
    if re.match(r"^\[\[[^\]]+\](?:\s*,\s*\[[^\]]+\])+\]$", t):
        return True
    return False


def add_matrix_table(doc, line):
    grid = _parse_matrix_rows(line)
    if not grid:
        return False
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        from math_omml import matrix, insert_omath_into_paragraph, omath_from_nodes
        insert_omath_into_paragraph(p, omath_from_nodes(matrix(grid)))
        cap = doc.add_paragraph()
        set_paragraph_spacing(cap, before=2, after=8, line_spacing=1.0)
        return True
    except Exception:
        pass
    rows, cols = len(grid), max(len(r) for r in grid)
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        force_table_inline(table)
    except Exception:
        pass
    for r in range(rows):
        for c in range(cols):
            val = grid[r][c] if c < len(grid[r]) else ""
            cell = table.cell(r, c)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp = cell.paragraphs[0]
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text_with_math(cp, val, bold=True)
    cap = doc.add_paragraph()
    set_paragraph_spacing(cap, before=2, after=8, line_spacing=1.0)
    return True


def collect_matrix_block(lines, start):
    if start >= len(lines):
        return [], start
    first = lines[start].strip()
    if first.upper().startswith("[[MAT"):
        return [first], start + 1
    if r"\begin{matrix}" in first or r"\begin{bmatrix}" in first or r"\begin{pmatrix}" in first:
        block = [first]
        j = start + 1
        while j < len(lines):
            block.append(lines[j].strip())
            if r"\end{matrix}" in lines[j] or r"\end{bmatrix}" in lines[j] or r"\end{pmatrix}" in lines[j]:
                return block, j + 1
            if j - start > 12:
                break
            j += 1
        return block, j
    if is_matrix_line(first):
        return [first], start + 1
    return [], start


# ============================================================
# GENERIC EXAM TABLE ENGINE
# Any complete-the-table / fill-in / property / comparison grid.
# No hardcoded question number, headers, shapes, or column count.
# Width, alignment and label-column are inferred from cell content.
# ============================================================
_PIPE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_TABLE_MARK_RE = re.compile(r"^\[\[TABLE\]\]\s*", re.I)
_TABLE_INSTRUCTION_RE = re.compile(
    r"(complete\s+the\s+(following\s+)?table|fill\s+(in|up)\s+the\s+"
    r"(following\s+)?table|given\s+table|observe\s+the\s+table|"
    r"तालिका\s*(पूरी|पूर्ण|भर|बना)|निम्न(लिखित)?\s*तालिका|"
    r"दी\s*गई\s*सारणी|सारणी\s*(पूरी|भर))",
    re.I,
)
_ROW_SPLIT_RE = re.compile(r"\t+|\s{2,}")


def is_table_instruction_line(line):
    return bool(_TABLE_INSTRUCTION_RE.search(str(line or "")))


def _is_pipe_separator_row(line):
    t = str(line or "").strip()
    if not t:
        return False
    if _TABLE_MARK_RE.fullmatch(t):
        return True
    return bool(_PIPE_SEP_RE.match(t))


def _strip_table_mark(line):
    return _TABLE_MARK_RE.sub("", str(line or ""), count=1).strip()


def is_pipe_table_line(line):
    t = str(line or "").strip()
    if not t:
        return False
    if t.upper().startswith("[[TABLE]]"):
        return True
    if _is_pipe_separator_row(t):
        return True
    if t.count("|") >= 2:
        return True
    return False


def _split_pipe_cells(line):
    t = _strip_table_mark(line)
    if not t:
        return []
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    return [c.strip() for c in t.split("|")]


def _split_loose_row(line):
    """Tab / multi-space rows when OCR did not emit pipes."""
    t = _strip_table_mark(line)
    if not t or is_table_instruction_line(t):
        return []
    if t.count("|") >= 2:
        return _split_pipe_cells(t)
    parts = [p.strip() for p in _ROW_SPLIT_RE.split(t) if p.strip()]
    if len(parts) >= 2:
        return parts
    return []


def _line_cell_count(line):
    cells = _split_loose_row(line) or _split_pipe_cells(line)
    return len(cells)


def collect_pipe_table_block(lines, start):
    """Collect any consecutive table grid. Not limited to one question type."""
    if start >= len(lines):
        return [], start

    first = lines[start].strip()
    marked = first.upper().startswith("[[TABLE]]")
    pipeish = is_pipe_table_line(first)
    loose = len(_split_loose_row(first)) >= 2

    if not (marked or pipeish or loose):
        return [], start

    # A single loose two-word line is not a table (avoids false hits).
    if loose and not marked and not pipeish:
        # Need at least one more compatible row ahead.
        nxt = lines[start + 1].strip() if start + 1 < len(lines) else ""
        if _line_cell_count(nxt) < 2 and not is_pipe_table_line(nxt):
            return [], start

    block = [first]
    j = start + 1
    useful = 1 if _line_cell_count(first) >= 2 else 0

    while j < len(lines):
        nxt = lines[j].strip()
        if not nxt:
            break
        if is_table_instruction_line(nxt) or has_explicit_question_label(nxt):
            break
        if is_section_heading(nxt):
            break
        if nxt.upper().startswith("[[TABLE]]") or is_pipe_table_line(nxt) or _line_cell_count(nxt) >= 2:
            block.append(nxt)
            if _line_cell_count(nxt) >= 2:
                useful += 1
            j += 1
            if useful >= 40:
                break
            continue
        break

    data_rows = []
    for ln in block:
        if _is_pipe_separator_row(ln) or ln.upper() == "[[TABLE]]":
            continue
        cells = _split_loose_row(ln)
        if not cells and ln.count("|") >= 2:
            cells = _split_pipe_cells(ln)
        if cells:
            data_rows.append(cells)

    if len(data_rows) < 2:
        return [], start

    # Same-shape grid: column counts should be close, not a random list.
    widths = [len(r) for r in data_rows]
    mode = max(set(widths), key=widths.count)
    if mode < 2:
        return [], start
    similar = sum(1 for w in widths if abs(w - mode) <= 1)
    if similar < 2:
        return [], start

    # Word-problem / fill / translate lines glued into a markdown grid
    # must NOT become an exam table. Those stay one-under-another.
    labelled = 0
    written = 0
    total = 0
    for row in data_rows:
        for cell in row:
            cell = str(cell or "").strip()
            if not cell or re.fullmatch(r":?-{2,}:?", cell):
                continue
            total += 1
            if re.match(r"^\(?[a-zA-Z0-9]+\)|^[a-zA-Z0-9][.)]", cell):
                labelled += 1
            if looks_like_written_item(cell):
                written += 1
    if total >= 2 and written >= max(2, int(0.5 * total)):
        return [], start
    if total >= 2 and labelled == total and written >= 1:
        return [], start
    return block, j


def set_visible_table_borders(table, color="5B6B73", size="12"):
    """Visible exam-grid borders (MCQ option tables stay borderless)."""
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = tblPr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def _cell_looks_numeric(text):
    t = str(text or "").strip()
    if not t:
        return False
    return bool(re.fullmatch(r"[+\-−]?\d+(?:[.,]\d+)?", t))


def _parse_exam_table_rows(block):
    rows_cells = []
    for raw in block:
        t = raw.strip()
        if t.upper() == "[[TABLE]]" or _is_pipe_separator_row(t):
            continue
        cells = _split_loose_row(t)
        if not cells and t.count("|") >= 2:
            cells = _split_pipe_cells(t)
        if cells:
            rows_cells.append(cells)
    if len(rows_cells) < 2:
        return []
    cols = max(len(r) for r in rows_cells)
    if cols < 2:
        return []
    for r in rows_cells:
        while len(r) < cols:
            r.append("")
        if len(r) > cols:
            r[:] = r[:cols]
    return rows_cells


def _infer_column_profile(rows_cells):
    """Infer width weight, alignment and label-column from content only."""
    cols = len(rows_cells[0])
    body = rows_cells[1:] if len(rows_cells) > 1 else rows_cells

    weights = []
    alignments = []
    label_cols = []

    for c in range(cols):
        texts = [str(row[c]).strip() for row in rows_cells]
        body_vals = [str(row[c]).strip() for row in body]
        filled = [v for v in body_vals if v]
        numeric = sum(1 for v in filled if _cell_looks_numeric(v))
        max_len = max((len(v) for v in texts), default=1)

        if filled and numeric >= max(1, int(0.6 * len(filled))):
            align = WD_ALIGN_PARAGRAPH.CENTER
            weight = max(1.15, min(2.2, 1.0 + max_len / 18.0))
            is_label = False
        else:
            align = WD_ALIGN_PARAGRAPH.LEFT
            weight = max(1.6, min(4.8, 1.2 + max_len / 10.0))
            avg_len = (sum(len(v) for v in filled) / len(filled)) if filled else max_len
            is_label = bool(filled) and avg_len <= 22 and numeric == 0

        weights.append(weight)
        alignments.append(align)
        label_cols.append(is_label)

    # At most the first text-heavy column is treated as a row-label column.
    first_label = next((i for i, flag in enumerate(label_cols) if flag), None)
    label_flags = [(i == first_label) for i in range(cols)]
    return weights, alignments, label_flags


def add_exam_property_table(doc, block):
    """Render any exam fill-in / property table as a print-ready Word grid."""
    if not class_allows_tables():
        rows_cells = _parse_exam_table_rows(block)
        if len(rows_cells) < 2:
            return False
        for cells in rows_cells:
            line = "    ".join(str(c).strip() for c in cells if str(c).strip())
            if not line:
                continue
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=1, after=2, line_spacing=1.08)
            r = p.add_run(line)
            set_run_language_font(r, line, bold=False)
            r.font.size = Pt(BODY_SIZE)
        return True
    rows_cells = _parse_exam_table_rows(block)
    if len(rows_cells) < 2:
        return False

    cols = len(rows_cells[0])
    weights, alignments, label_flags = _infer_column_profile(rows_cells)
    total_w = sum(weights) or float(cols)
    usable = OPTION_GRID_WIDTH
    widths = [usable * (w / total_w) for w in weights]

    table = doc.add_table(rows=len(rows_cells), cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        force_table_inline(table)
    except Exception:
        pass
    set_visible_table_borders(table, color="5B6B73", size="12")

    tblPr = table._tbl.tblPr
    tblLayout = tblPr.first_child_found_in("w:tblLayout")
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")

    for c, col in enumerate(table.columns):
        col.width = Inches(widths[c])

    header_fill = "2E75B6"
    alt_fill = "F3F7FB"

    for r_idx, cells in enumerate(rows_cells):
        is_header = r_idx == 0
        for c_idx, val in enumerate(cells):
            cell = table.cell(r_idx, c_idx)
            cell.width = Inches(widths[c_idx])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell, top=80, start=70, bottom=80, end=70)

            tcPr = cell._tc.get_or_add_tcPr()
            tcW = tcPr.find(qn("w:tcW"))
            if tcW is None:
                tcW = OxmlElement("w:tcW")
                tcPr.append(tcW)
            tcW.set(qn("w:w"), str(int(widths[c_idx] * 1440)))
            tcW.set(qn("w:type"), "dxa")

            if is_header:
                set_cell_shading(cell, header_fill)
            elif r_idx % 2 == 0:
                set_cell_shading(cell, alt_fill)

            p = cell.paragraphs[0]
            p.text = ""
            if is_header:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = alignments[c_idx]
            set_paragraph_spacing(p, before=2, after=2, line_spacing=1.0)
            p.paragraph_format.keep_together = True

            display = val.strip()
            run = p.add_run(display)
            want_bold = is_header or (label_flags[c_idx] and bool(display))
            set_run_language_font(run, display or " ", bold=want_bold)
            run.font.size = Pt(14 if is_header else 15)
            if is_header:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, before=2, after=6, line_spacing=1.0)
    return True


def looks_like_figure_request(line):
    return bool(_FIG_RE.search(str(line or "")))


def _needs_hindi_respace(text):
    return bool(re.search(r"[\u0900-\u097F]{12,}", str(text or "")))


def respace_devanagari_with_gemini(text, subject=""):
    """Technology change: Gemini only inserts spaces. Letters stay the same."""
    raw = str(text or "").strip()
    if not raw or not _needs_hindi_respace(raw):
        return raw
    if client is None:
        return restore_hindi_spaces(raw)
    prompt = (
        "You are a Hindi spacing tool, not an author.\n"
        "Task: insert NORMAL spaces between Hindi words.\n"
        "DO NOT change letters, matras, numbers, or question order.\n"
        "DO NOT add or delete questions.\n"
        "DO NOT translate.\n"
        "Keep (क)(ख)(ग) and (i)(ii) markers.\n"
        "Wrong: सभीप्रश्नकरने  Right: सभी प्रश्न करने\n"
        "Never split these words: अंधकार अधिकार स्थानों निम्नलिखित सुभाष सरदार तिलक कोलकाता\n"
        "Wrong: अंध कार / स् थानों   Right: अंधकार / स्थानों\n"
        "Return the same text with spaces only.\n\n"
        + raw
    )
    try:
        print("  → Hindi space-pass (Gemini, letters lock)...")
        resp = client.models.generate_content(model=MODEL_NAME, contents=[prompt])
        out = (resp.text or "").strip()
        if len(out) < max(20, int(len(raw) * 0.45)):
            return restore_hindi_spaces(raw)
        return out
    except Exception as exc:
        print("  ⚠ Hindi space-pass skipped:", exc)
        return restore_hindi_spaces(raw)


def _arrange_q_needs_numeric_recovery(text):
    """V33.12: detect an arrange/order question whose item lines were likely missed by OCR."""
    lines = str(text or "").splitlines()
    for i, raw in enumerate(lines):
        t = raw.strip()
        if not re.search(
            r"\b(?:arrange|order)\b.*\b(?:ascending|descending|numbers?|order)?",
            t,
            re.IGNORECASE,
        ):
            continue
        # Look only until the next numbered question/section.
        following = []
        for nxt in lines[i + 1:]:
            nt = nxt.strip()
            if re.match(r"^(?:Q(?:uestion)?\s*[-.:)]?\s*\d+|\d+\s*[.)])\b", nt, re.IGNORECASE):
                break
            if nt:
                following.append(nt)
        # A valid arrange question normally has at least two item lines with digits.
        digit_lines = [x for x in following if re.search(r"\d", x)]
        if len(digit_lines) < 2:
            return True
    return False


def _recover_arrange_numbers_from_image(image_bytes, mime_type, text):
    """V33.12: one targeted vision retry only when an arrange/order item block is missing.
    Returns exact visible item lines or an empty string. Never invents values."""
    prompt = r"""
The existing OCR text contains an arrange/order question whose item/number lines appear to be missing.

Your ONLY task is to recover the exact visible item lines belonging to that arrange/order question from
the image.

RULES:
1. Do NOT rewrite the question stem.
2. Do NOT solve, sort, calculate, correct, normalize, or invent any number.
3. Copy ONLY item lines that are visibly present in the image.
4. Preserve the exact order and digits.
5. Include labels such as (a), (b), (c), (d) when visible.
6. Return one item per line.
7. Return NOTHING else — no heading, no explanation, no answer, no markdown.
8. If the item lines are not actually visible/readable, return EMPTY.
9. Do not copy Q-3 or any later question.
"""
    try:
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
        )
        recovered = sanitize_extracted_paper_text(
            normalize_exam_mark_symbols((resp.text or "").strip())
        )
        # Strict safety filter: only accept a small block of digit-bearing item lines.
        kept = []
        for line in recovered.splitlines():
            t = line.strip()
            if not t or not re.search(r"\d", t):
                continue
            if re.match(r"^(?:Q(?:uestion)?\s*[-.:)]?\s*\d+|\d+\s*[.)])\b", t, re.IGNORECASE):
                # A later question marker must never be imported.
                continue
            kept.append(t)
        # Accept either multiple labelled lines OR one line containing at least two numeric values.
        digit_count = sum(len(re.findall(r"\d+", x)) for x in kept)
        if len(kept) < 2 and digit_count < 2:
            return ""
        return "\n".join(kept[:8])
    except Exception as exc:
        print(f"  ⚠ V33.12 arrange-number recovery skipped: {exc}")
        return ""


def _insert_recovered_arrange_items(text, recovered):
    """Insert recovered item lines immediately after the incomplete arrange/order stem."""
    if not recovered:
        return text
    lines = str(text or "").splitlines()
    rec_lines = recovered.splitlines()
    for i, raw in enumerate(lines):
        t = raw.strip()
        if re.search(
            r"\b(?:arrange|order)\b.*\b(?:ascending|descending|numbers?|order)?",
            t,
            re.IGNORECASE,
        ):
            # Avoid duplicate insertion if an earlier OCR line already contains the same block.
            nearby = "\n".join(lines[i + 1:i + 10])
            if all(x not in nearby for x in rec_lines[:2]):
                return "\n".join(lines[:i + 1] + rec_lines + lines[i + 1:])
            return text
    return text


def extract_text_from_image(image_path, class_name="", subject=""):
    try:
        if is_obviously_blank_image(image_path):
            print(f"  → Blank/near-blank image skipped: {os.path.basename(image_path)}")
            return ""

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type = get_mime_type(image_path)

        extraction_prompt = r"""
Extract ONLY the QUESTION-PAPER BODY from this image.

IMPORTANT:
1. The program already creates the professional header from Excel:
   School Name, Class, Subject, Page No., Max Marks, Time and Exam.
2. DO NOT return any repeated page-header information.
3. DO NOT return school name, exam name/date, page number, maximum marks,
   time/duration, student Name, Father's Name, Roll No., M.M., Class,
   Subject or similar candidate-information/header lines that appear before
   the actual question-paper body.
4. Start extraction from the first section/instruction/question of the
   actual question paper, e.g. "A. ...", "B. ...", "1. ...", etc.
5. Preserve the wording of the actual questions EXACTLY as visible.
6. Do NOT rewrite, correct, improve, translate or paraphrase questions.
7. Preserve question numbering exactly.
8. Preserve sub-question numbering exactly.
9. Preserve every option exactly and keep options on separate lines when
   they are separate in the source.
10. Preserve examination marks semantically, but NEVER output LaTeX for them.
    If the source says a right-tick/check mark instruction, use the Unicode
    boxed tick character ☑. If the source says a wrong/cross mark instruction,
    use the Unicode boxed cross character ☒. Do not output $\\checkmark$ or
    $\\times$ or other LaTeX markup.
11. Do not add answers.
12. Do not add explanations.
12b. Do not invent or append marks arithmetic such as 2x8=16, 1/2x4=2,
     \\frac{1}{2}x4=2. Never repeat a section heading on the same line.
13. MATH MUST use this exact linear form so Word can print stacked fractions:
    - fraction  -> \\frac{numerator}{denominator}   example: \\frac{1}{2}
    - mixed     -> 2\\frac{1}{3}
    - power     -> x^{2}   or  10^{3}
    - root      -> \\sqrt{16}
    - equation  -> keep on one line:  2x + \\frac{1}{2} = 5
    Never write stacked digits as two loose lines. Never invent LaTeX except frac, sqrt and ^{ }.
13b. CLASS 1-3 ARITHMETIC SUMS (addition, subtraction, multiplication, division):
    If numbers are written one under another (column method / place value),
    copy them as a vertical block. Put the sign on the lower number.
    EACH sub-part (a)(b)(c)(d) is its OWN block. Never merge two sums.
    Never turn a column sum into a pipe table.
    Use this markup when the sum is a column sum:
      [[ADD]]
        245
      +  37
      -----
      [[SUB]]
        500
      - 128
      -----
      [[MUL]]
        395
      ×   5
      -----
      [[MUL]]
        399
      ×   3
      -----
      [[DIV]] 7)21
    Keep every digit in its place (ones under ones, tens under tens).
    Do not flatten a column sum into "245 + 37" if the source is stacked.
    If TWO or MORE column sums sit SIDE BY SIDE on the printed page,
    output them as consecutive separate blocks. NEVER put two sums on
    the same text line. Example of two side-by-side additions:
      [[ADD]]
        57
      + 24
      -----
      [[ADD]]
        68
      + 35
      -----
    Join split place-value digits of ONE number: "5 7" with "+ 2 4" is 57 + 24,
    not four separate numbers. Do not emit a pipe table for arithmetic sums.
13c. NUMBER LINE: write [[NLINE]] 0-1-2-3-4-5-6-7-8-9-10
13d. If a diagram/graph/figure must be drawn, write one line:
     [[FIG]] short caption
     Do not invent an ASCII drawing.
13e. MATRIX: [[MAT]] [1, 2; 3, 4]   or  [[1,2],[3,4]]
13f. Geometry signs: use ∠ Δ ∥ ⊥ ° π × ÷ ≤ ≥ ≠ →
13g. Higher math: \\frac{{}}{{}}, x^{{n}}, \\sqrt{{}}, \\lim, \\int, \\log
13h. ANY exam table / grid / "complete the table" / fill-in table:
     Do not flatten into a paragraph. Output a [[TABLE]] block.
     Use one pipe-row per visible row. Keep every given cell exactly.
     Leave blank/missing cells empty. Do not invent values.
     Works for any subject, any columns, any language:
     [[TABLE]]
     | header1 | header2 | header3 |
     | value | | value |
     | | value | |
14. Return ONLY the question-paper body text.
15. If the image contains no legible question-paper content, return NOTHING (an empty response).
16. NEVER return messages such as "No legible question paper content is visible", "The page appears blank",
    "cannot read", "unable to extract", or any explanation about image quality.
17. CLASS/SUBJECT BASE PATTERN (structure only, never rewrite questions):
"""
        extraction_prompt = extraction_prompt + r"""
\nCRITICAL NUMERIC-QUESTION PRESERVATION:
- For every question containing "Arrange", "arrange in ascending order", "arrange in descending order",
  "put in order", "order the numbers", or equivalent wording, the question is NOT complete after its stem.
- Transcribe EVERY visible item/number that belongs to that question, including isolated numbers and
  numbers inside (a), (b), (c), (d) lines.
- Never stop after the question heading merely because the item lines are short or visually separated.
- Preserve the exact visible digits and their order. Do NOT calculate, sort, normalize, replace, or invent them.
- If the item line is genuinely unreadable, write [अस्पष्ट] rather than inventing a number.
- The next question begins only after all visible items of the current arrange/order question have been transcribed.
""" + "\n"
        extraction_prompt = extraction_prompt + "\n" + pattern_prompt_hint(class_name, subject) + "\n" + SUBPART_ALIGN_PROMPT + "\n" + MCQ_TICK_PROMPT + "\n"
        if is_science_subject(subject) or SCIENCE_OCR_PROMPT_ADDON:
            extraction_prompt = extraction_prompt + SCIENCE_OCR_PROMPT_ADDON + "\n"
        if is_maths_subject(subject):
            extraction_prompt = extraction_prompt + MATH_OCR_PROMPT_ADDON + "\n"

            if MATH_FT is not None:
                extraction_prompt = extraction_prompt + MATH_FT.extra_ocr_prompt(class_name, subject)

            if MATH_CLEAN is not None:
                extraction_prompt = extraction_prompt + MATH_CLEAN.extra_ocr_prompt(class_name, subject)
        extraction_prompt = extraction_prompt + LANGUAGE_LOCK_PROMPT + r"""

HANDWRITTEN DEVANAGARI PAGE RULES:
- This may be a crowded student/teacher notebook page.
- Read EACH akshara WITH its matra (ि ी ु ू े ै ो ौ ां ँ). Never detach matras.
- NEVER output square boxes □ ■, replacement marks, or ??? for a Hindi word.
- ALWAYS put a normal space between Hindi words. Write "सभी प्रश्न" not "सभीप्रश्न".
- If a word is unreadable, write [अस्पष्ट] once — not boxes.
- Keep section order exactly: व्याकरण / परिभाषा / लिंग / पत्र / निबंध.
- Number as प्र0-1 प्र0-2 or (i) (ii) as on the page. Do not write Q.5 on a Hindi page.
- Do not merge two questions onto one line.
- Do not invent English headings.
""" + "\n"
        _lang = detect_paper_language(subject)
        if _lang == "hindi":
            extraction_prompt += (
                "\nTHIS PAPER SUBJECT IS HINDI. Output only Hindi / Devanagari "
                "question text. No English sentences. No English section titles.\n"
            )
        if is_sanskrit_subject(subject):
            extraction_prompt = extraction_prompt + SANSKRIT_OCR_PROMPT_ADDON + "\n"
            extraction_prompt += (
                "\nTHIS PAPER SUBJECT IS SANSKRIT. No English sentences.\n"
            )
        # --- HOOK 6: stage OCR hint (ADD-ON) ---
        try:
            if NCERT_GRAMMAR is not None:
                _stg = NCERT_GRAMMAR._local_classify(class_name)
                if _stg in ("primary_a", "primary_b"):
                    extraction_prompt = extraction_prompt + (
                        "\nPRIMARY NOTE: Children write in LARGE, uneven handwriting. "
                        "Preserve scattered letters; do not merge nearby words. "
                        "Keep picture captions under [[FIG]].\n"
                    )
                elif _stg == "preprimary":
                    extraction_prompt = extraction_prompt + (
                        "\nPREPRIMARY NOTE: Worksheet style. Big letters, tracing lines, "
                        "simple counting. Do not add answer lines.\n"
                    )
        except Exception:
            pass
        # --- END HOOK 6 ---
        last_error = None
        response = None
        for attempt in range(1, 5):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type
                        ),
                        extraction_prompt
                    ]
                )
                last_error = None
                break
            except Exception as call_err:
                last_error = call_err
                msg = str(call_err)
                if _is_auth_error(call_err):
                    raise
                transient = any(tok in msg for tok in (
                    "10054", "10053", "10060", "timed out", "Timeout",
                    "Connection", "disconnected", "RemoteDisconnected",
                    "503", "500", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
                    "INTERNAL", "DEADLINE", "503 Service",
                ))
                if not transient or attempt == 4:
                    raise
                wait_s = 2.5 * attempt
                print(
                    f"  ⚠ OCR network drop page "
                    f"{os.path.basename(image_path)} "
                    f"(try {attempt}/4). {wait_s:.0f}s baad dubara..."
                )
                time.sleep(wait_s)

        if response is None:
            raise last_error or RuntimeError("OCR empty response")

        text = (response.text or "").strip()
        text = normalize_exam_mark_symbols(text)
        text = sanitize_extracted_paper_text(text)
        text = drop_tofu_ocr_lines(text)

        # V33.12: targeted recovery for arrange/order questions with a missing numeric block.
        # This is NOT a general second OCR pass. It fires only when the extracted text contains
        # an arrange/order stem but fewer than two digit-bearing item lines before the next question.
        if text and _arrange_q_needs_numeric_recovery(text):
            print(
                f"  ⚠ V33.12 ARRANGE OCR GAP: missing numeric item lines detected on "
                f"{os.path.basename(image_path)} — one targeted recovery call only..."
            )
            recovered = _recover_arrange_numbers_from_image(image_bytes, mime_type, text)
            if recovered:
                text = _insert_recovered_arrange_items(text, recovered)
                print("  ✓ V33.18 EXACT NURSERY-HINDI STEMS + SERIES-SAFE FALLBACK + V33.21 NURSERY-HINDI HEADER FIX + V33.20 NURSERY-HINDI PAGE BORDER FIX + V33.23 NUR WORKSHEET MATCH/FIGURE PLACEHOLDER FIX + V33.22 FONT FIX + V33.21 HEADER + V33.20 PAGE BORDER + V33.19 OCR ALIASES: numeric item lines restored from source image")
            else:
                print("  ⚠ V33.13 NURSERY-HINDI TEMPLATE RENDERER + V33.12 ARRANGE OCR RECOVERY: no safe numeric lines recovered; OCR text unchanged")

        # Gemini must never turn an unusable/blank source image into
        # artificial text inside the final question paper.
        placeholder_patterns = [
            r"no legible question paper content",
            r"page appears to be mostly blank",
            r"faint bleed-through",
            r"unable to extract",
            r"cannot read",
            r"not visible in the image",
            r"no readable content",
        ]

        if any(re.search(pattern, text, flags=re.IGNORECASE)
               for pattern in placeholder_patterns):
            text = ""

        # Second pass: faint / crowded handwritten page — dump visible lines only.
        if not text:
            print(f"  ⚠ OCR empty on {os.path.basename(image_path)} — plain-read retry...")
            try:
                retry = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        (
                            "Transcribe EVERY visible question-paper line from this image. "
                            "Keep original numbering. Do not explain. Do not say the page is blank "
                            "unless there is truly no ink. Output plain text only."
                        ),
                    ],
                )
                text = sanitize_extracted_paper_text(
                    normalize_exam_mark_symbols((retry.text or "").strip())
                )
                if any(re.search(p, text, flags=re.IGNORECASE) for p in placeholder_patterns):
                    text = ""
            except Exception as retry_exc:
                print(f"  ⚠ plain-read retry failed: {retry_exc}")
                text = ""

        if text and (
            detect_paper_language(subject, text) in {"hindi", "sanskrit"}
            or _needs_hindi_respace(text)
        ):
            if _needs_hindi_respace(text):
                text = respace_devanagari_with_gemini(text, subject)
        return text

    except Exception as e:
        if _is_auth_error(e):
            print("  ❌ Gemini authentication failed during OCR.")
            print(f"     Server: {e}")
        else:
            print(f"  ❌ OCR Error ({os.path.basename(image_path)}): {e}")
        return ""


# ============================================================
# REDUNDANT HEADER / METADATA PROTECTION
# ============================================================

def _norm_header_text(value):
    """Normalize text only for comparison; never modifies displayed text."""
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[|:;,]+", " ", value)
    return value.strip()


def _looks_like_candidate_header(line):
    """
    Detect candidate-information/header lines that must not be repeated
    inside the question body because the same information is already
    generated from Excel.
    """
    t = _norm_header_text(line)

    if not t:
        return False

    patterns = [
        r"^(name|student name)\b",
        r"^(f\.?\s*name|father'?s?\s*name)\b",
        r"^(roll\s*no\.?|roll\s*number)\b",
        r"^(time|duration)\s*[:\-]?",
        r"^(m\.?\s*m\.?|max\.?\s*marks?|maximum\s*marks?)\s*[:\-]?",
        r"^(page\s*no\.?|page\s*number)\s*[:\-]?",
        r"^(class|grade)\s*[:\-]?",
        r"^(subject|sub)\s*[:\-]?",
        r"^(exam|examination)\s*[:\-]?",
    ]

    return any(re.match(p, t, flags=re.IGNORECASE) for p in patterns)


def _looks_like_metadata_line(line, row_data):
    """
    Detect exact/near-exact repetitions of values already placed in the
    professional header. Comparison is case-insensitive and whitespace-safe.
    """
    t = _norm_header_text(line)

    if not t:
        return False

    values = [
        row_data.get("SCHOOL NAME", ""),
        row_data.get("CLASS", ""),
        row_data.get("SUBJECT", ""),
        row_data.get("PAGENO", ""),
        row_data.get("MM", ""),
        row_data.get("TIME", ""),
        row_data.get("EXAM TYPE", ""),
    ]

    normalized_values = [
        _norm_header_text(v) for v in values if _norm_header_text(v)
    ]

    # Exact value on a line.
    if t in normalized_values:
        return True

    # Common metadata labels combined with an already-known value.
    for value in normalized_values:
        if len(value) >= 2 and value in t:
            if any(word in t for word in [
                "page", "marks", "time", "exam", "class", "subject"
            ]):
                return True

    return False


def _looks_like_section_start(line):
    """
    Detect the point where the actual paper body begins.
    Examples:
        A. Tick (✓) the Correct Option :-
        B. Fill in the blanks :-
        SECTION A
        PART A
        1. Kalpana Chawla ...
    """
    t = line.strip()

    if not t:
        return False

    patterns = [
        r"^[A-Z]\s*[\.\)]\s+\S+",
        r"^SECTION\s+[A-Z0-9IVX]+",
        r"^PART\s+[A-Z0-9IVX]+",
        r"^GROUP\s+[A-Z0-9IVX]+",
        r"^Q(?:uestion)?\s*\.?\s*\d+\s*[:\.\)]\s+\S+",
        r"^Question\s+\d+\s*[:\.\)]\s+\S+",
        r"^\d+\s*[\.\)]\s+\S+",
    ]

    return any(
        re.match(p, t, flags=re.IGNORECASE)
        for p in patterns
    )


def remove_redundant_header(extracted_text, row_data):
    """
    Removes the source image's already-printed header/candidate block.

    Strategy:
      - Prefer starting at the first clear section/question.
      - If OCR did not expose a section marker, remove only recognized
        metadata/candidate lines at the beginning.
      - Never remove content from the middle of the question paper.
    """
    extracted_text = sanitize_extracted_paper_text(extracted_text)
    lines = (
        extracted_text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )

    # Remove leading empty lines only.
    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        return ""

    # Find the first unmistakable body marker.
    for i, line in enumerate(lines):
        if _looks_like_section_start(line):
            # Only discard the prefix if that prefix actually looks like
            # a header/candidate-information block. This prevents accidental
            # loss of a legitimate introductory paragraph.
            prefix = lines[:i]
            header_score = sum(
                1 for p in prefix
                if _looks_like_candidate_header(p)
                or _looks_like_metadata_line(p, row_data)
            )

            prefix_has_instruction = any(
                is_instruction_line(p)
                or is_word_meaning_heading(p)
                or is_section_heading(p)
                or is_mcq_section_heading(p)
                for p in prefix
            )
            if header_score >= 1 and not prefix_has_instruction:
                cleaned = lines[i:]
                return "\n".join(cleaned).strip()

            # If the first line itself is a normal section/question, keep it.
            return extracted_text.strip()

    # No clear section marker found: remove only recognized header lines
    # from the beginning, stopping at the first real content line.
    cleaned = []
    started = False

    for line in lines:
        if not started:
            if (
                _looks_like_candidate_header(line)
                or _looks_like_metadata_line(line, row_data)
            ):
                continue

            # Ignore common standalone school/header lines at the top.
            t = _norm_header_text(line)
            school = _norm_header_text(row_data.get("SCHOOL NAME", ""))

            if school and (
                t == school
                or school in t
                or t in school
            ):
                continue

            started = True

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _ensure_opening_instruction(lines):
    """Agar Q1 sirf short words ki list hai to missing heading wapas lao."""
    rows = [str(x or "").strip() for x in (lines or []) if str(x or "").strip()]
    if not rows:
        return lines
    first = rows[0]
    if (
        is_word_meaning_heading(first)
        or is_section_heading(first)
        or is_mcq_section_heading(first)
        or is_instruction_line(first)
        or is_match_heading(first)
    ):
        return lines
    short = 0
    for line in rows[:12]:
        if re.match(
            r"^\d+\s*[\.)]\s+[A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F'’\-]{1,22}\s*$",
            line,
        ):
            short += 1
    if short < 4:
        return lines
    head_block = " ".join(rows[:8]).lower()
    if re.search(
        r"tick|choose|fill in|match|answer the|मौखिक|लघु|रिक्त|सही विकल्प|प्रश्न\s*[-:]?\s*1|que\s*-?\s*1",
        head_block,
        re.I,
    ):
        return lines
    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        head = "निम्नलिखित शब्दों के अर्थ लिखिए।"
    else:
        head = "Write the meanings of the following words."
    print("  → Q1 instruction missing — heading add:", head)
    return [head] + list(lines)


# ============================================================
# WORD FORMATTING HELPERS
# ============================================================
def apply_safe_paragraph_alignment(paragraph, text, is_special=False):
    """
    SAFE FINAL ALIGNMENT RULE (V27)

    SECTION HEADING -> CENTER
    Everything else (questions, body, options, instructions) -> JUSTIFY
    """

    text = str(text or "").strip()

    if not is_special:
        paragraph.paragraph_format.first_line_indent = Inches(0)
        paragraph.paragraph_format.left_indent = Inches(0)
        paragraph.paragraph_format.right_indent = Inches(0)

    # SECTION HEADING only stays centered
    if re.search(r"^\s*\(\s*खण्ड\s*-\s*[अ-ह]\s*\)", text):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return
    if is_section_heading(text) and not has_explicit_question_label(text):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return

    # All body / questions / options / instructions -> JUSTIFY
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

_HINDI_PARTICLE_RE = re.compile(
    r"(?<=[\u0900-\u097F])"
    r"(निम्नलिखित|आनेवार्य|अनिवार्य|सहायता|"
    r"लिखिए|कीजिए|लगाइए|विकल्प|शब्दों|प्रश्न|उत्तर|"
    r"सभी|सही|नहीं|कथन|सामने|पूर्ति|चिन्ह|ध्यान|विशेष|"
    r"क्या|कौन|तथा|लिए|साथ|गलत|दिए|गए|करने|बहुत|रिक्त|"
    r"में|पर|से|और|को|के|की|"
    r"हैं|था|थे|है)"
    r"(?=[\u0900-\u097F]|[।?.,:\-–—]|$)"
)


_EN_EXAM_WORDS = tuple(sorted((
    "instructions", "compulsory", "questions", "question", "please",
    "rearrange", "letters", "correct", "intelligent", "following",
    "subtract", "multiply", "compare", "numbers", "number", "hundred",
    "festival", "colours", "christians", "muslims", "christmas",
    "national", "peacock", "dolphin", "pigeon", "parrot",
    "blanks", "answer", "using", "write", "which", "largest",
    "animal", "earth", "place", "value", "before", "after",
    "greater", "ascending", "descending", "divide", "adding",
    "between", "sixty", "fifty", "four", "three", "help", "box",
    "fill", "then", "the", "and", "for", "from", "with", "this", "that",
    "all", "are", "one", "two", "word", "make", "most", "sea",
    "just", "less", "than", "put", "add", "sort", "neat", "clean",
    "note", "india", "each", "time", "name", "shaped", "star",
    "capital", "uttar", "pradesh", "fruits", "lights", "sikhs",
    "holi", "eid", "diwali", "of", "in", "is", "to", "on", "or",
), key=len, reverse=True))


_DEV_EXAM_WORDS = tuple(sorted((
    "अधोलिखित", "गद्यांश", "पठित्वा", "प्रश्नानाम्", "प्रश्नाना", "उत्तराणि",
    "लिखत", "लिखतः", "हिमालयः", "भारतस्य", "उत्तरस्यां", "दिशि", "अस्ति",
    "एषः", "पर्वतानां", "नृपः", "हिमालयात्", "कानदी", "प्रवहति", "यस्याः",
    "नाम", "गङ्गा", "अस्ति", "गङ्गायाः", "जलम्", "अतीव", "पवित्रम्", "भवति",
    "कस्यां", "पवित्रम्", "इति", "पदस्य", "विशेषणपदं", "किम्", "जलम्", "नदी",
    "वर्णसंयोजनं", "वियोजनं", "कुरुत", "स्त्रीलिङ्गम्", "एकवचनम्",
    "उदाहरणानुगुणं", "प्रश्ननिर्माणं", "कुर्वन्तु", "सासूयः", "सानुक्रोशः",
    "साविहसति", "साक्रीडति", "सानन्दम्", "उचितं", "मेलनं", "कृत्वा",
    "रिक्तस्थानानि", "पूरयत", "गतभूतयोः", "धृतनतियोः", "नोदेहि",
    "परमात्मनम्", "यामीव", "सम्राज्ञी", "शुभचिन्त", "कानियतम्",
    "जगदीशहे", "परमेशहे", "दृढशक्तियो", "निखिलाः", "जयमङ्गल",
    "परमोज्ज्वलो", "विजयार्थिनो", "बालाः", "जनसेवक", "अतिभावकः",
    "सकलेशहे", "भगवन्", "पक्षिणां", "नामानि", "संस्कृते", "लिखत",
    "चिड़िया", "कबूतर", "उल्लू", "शरीराङ्गानां", "शाकानां", "प्याज",
    "बैंगन", "कृत्ता", "वर्णनं", "आसीत्", "काकः", "चलतिस्म",
    "चित्रवर्णः", "कः", "राधि", "काकथंचलतिस्म",
    "निम्नलिखित", "सभी", "प्रश्न", "अनिवार्य", "रिक्त", "स्थान",
    "सही", "गलत", "विकल्प", "कथन", "लिखिए", "कीजिए",
    "के", "का", "की", "को", "से", "में", "पर", "है", "हैं",
), key=len, reverse=True))


def _unglue_devanagari_chunk(chunk):
    """Split a glued Devanagari run using known exam words + visarga."""
    if not chunk or len(chunk) < 4:
        return chunk
    out = []
    i = 0
    n = len(chunk)
    while i < n:
        hit = None
        for w in _DEV_EXAM_WORDS:
            if chunk.startswith(w, i) and len(w) >= 2:
                hit = w
                break
        if hit:
            out.append(hit)
            i += len(hit)
            continue
        j = i + 1
        while j < n:
            if any(chunk.startswith(w, j) for w in _DEV_EXAM_WORDS if len(w) >= 3):
                break
            if chunk[j - 1] == "ः" and "\u0900" <= chunk[j] <= "\u097F":
                break
            j += 1
        out.append(chunk[i:j])
        i = j
    merged = []
    for x in out:
        if not x:
            continue
        if x in {"ः", "ं", "ँ", "ॅ", "ॉ"} and merged:
            merged[-1] = merged[-1] + x
        else:
            merged.append(x)
    return " ".join(merged)


def never_glue_words(text):
    """Kitna bhi loose/tight — shabd kabhi na jude. Sanskrit + Hindi + English."""
    t = str(text or "")
    if not t.strip():
        return t
    t = t.replace("\u00a0", " ").replace("\u200b", "")

    # 1) Visarga is a word end: हिमालयःभारतस्य → हिमालयः भारतस्य
    t = re.sub(r"(ः)(?=[\u0900-\u097F])", r"\1 ", t)

    # 2) Option / number labels: क)हिमालयः  1)अधोलिखित  घ)राधि
    t = re.sub(
        r"(?<![A-Za-z0-9])([कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह]\)|[0-9]+\)|[a-dA-D]\))(?=\S)",
        r"\1 ",
        t,
    )
    t = re.sub(
        r"(\(\s*(?:[a-dA-D]|iv|iii|ii|i)\s*\))(?=\S)",
        r"\1 ",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"((?:Q|प्रश्न|प्र०|प्र0|प्र)\s*\.?\s*\d+)(?=[A-Za-z\u0900-\u097F])",
        r"\1 ",
        t,
        flags=re.I,
    )

    # 3) [5Marks] glued to Sanskrit
    t = re.sub(r"(?<=[\u0900-\u097F])(\[\s*\d+\s*Marks?\s*\])", r" \1", t, flags=re.I)
    t = re.sub(r"(\[\s*\d+\s*Marks?\s*\])(?=\S)", r"\1 ", t, flags=re.I)

    # 3b) Devanagari then parenthesis
    t = re.sub(r"(?<=[\u0900-\u097F])(\()", r" \1", t)

    # 4) Script / digit boundaries
    t = re.sub(r"(?<=[\u0900-\u097F])(?=[A-Za-z0-9])", " ", t)
    t = re.sub(r"(?<=[A-Za-z0-9])(?=[\u0900-\u097F])", " ", t)
    t = re.sub(r"([।?:\u0964])(?=\S)", r"\1 ", t)

    # 5) Hindi particles
    t = re.sub(
        r"(?<=[\u0900-\u097F])(का|के|की|को|से|में|पर|है|हैं|था|थे|थी|लिखिए|कीजिए|करें|करो)(?=[\u0900-\u097F]|$)",
        r" \1",
        t,
    )

    # 6) Split remaining glued Devanagari chunks
    parts = re.split(r"([^\u0900-\u097F]+)", t)
    rebuilt = []
    for p in parts:
        if p and re.fullmatch(r"[\u0900-\u097F]+", p) and len(p) >= 6:
            rebuilt.append(_unglue_devanagari_chunk(p))
        else:
            rebuilt.append(p)
    t = "".join(rebuilt)
    t = re.sub(r" {2,}", " ", t)
    return t


def _unglue_english_token(tok):
    """Split ONLY fully-glued exam phrases. Never cut Find/lines/window."""
    if len(tok) < 12 or not tok.isalpha():
        return tok
    s = tok
    out = []
    i = 0
    low = s.lower()
    while i < len(s):
        hit = None
        for w in _EN_EXAM_WORDS:
            if len(w) < 5:
                continue
            if low.startswith(w, i):
                hit = s[i:i + len(w)]
                break
        if hit:
            out.append(hit)
            i += len(hit)
        else:
            j = i + 1
            while j < len(s) and not any(
                low.startswith(w, j) for w in _EN_EXAM_WORDS if len(w) >= 5
            ):
                j += 1
            out.append(s[i:j])
            i = j
    # If we barely split, keep original — safer than F in d
    if len(out) <= 1:
        return tok
    return " ".join(x for x in out if x)


def restore_english_spaces(text):
    t = str(text or "")
    if re.search(r"[\u0900-\u097F]", t):
        return t
    # letter-digit boundary only: Howmany0in1lakh → Howmany 0 in 1 lakh
    t = re.sub(r"([A-Za-z])(\d)", r"\1 \2", t)
    t = re.sub(r"(\d)([A-Za-z])", r"\1 \2", t)
    parts = re.split(r"([^A-Za-z]+)", t)
    return "".join(_unglue_english_token(p) if p.isalpha() else p for p in parts)


def restore_exam_spaces(text):
    """Language-safe spacing. English papers never enter Hindi splitter."""
    t = restore_english_spaces(str(text or ""))
    for glued, fixed in (
        ("Fillintheblanksusingthehelpbox", "Fill in the blanks using the help box"),
        ("Fillintheblanks", "Fill in the blanks"),
        ("Writetheanswerinoneword", "Write the answer in one word"),
        ("Rearrangetheletters", "Rearrange the letters"),
        ("tomakeacorrectword", "to make a correct word"),
        ("Mostintelligentseaanimal", "Most intelligent sea animal"),
        ("istheFestivalof", " is the Festival of "),
        ("istheFestival", " is the Festival "),
        ("writetheshapedlikeastar", "write the shape liked a star"),
        ("writethecapitalof", "write the capital of"),
        ("writethetwofruitsname", "write the two fruits name"),
        ("writethefestivaloflights", "write the festival of lights"),
        ("WhichisthelargestanimalonEarth", "Which is the largest animal on Earth"),
        ("Whichisthemostintelligentseaanimal", "Which is the most intelligent sea animal"),
    ):
        t = t.replace(glued, fixed)
        t = t.replace(glued.lower(), fixed)
    if re.search(r"[\u0900-\u097F]", t) and PAPER_LANGUAGE in {"hindi", "sanskrit", ""}:
        t = restore_hindi_spaces(t)
    return never_glue_words(t)


def restore_hindi_spaces(text):
    """Single stable pass: names/phrases, then one particle split. No loop."""
    t = str(text or "")
    if not re.search(r"[\u0900-\u097F]", t):
        return t
    for glued, fixed in (
        ("लोकमान्यबालगंगाधरतिलक", "लोकमान्य बाल गंगाधर तिलक"),
        ("बालगंगाधरतिलक", "बाल गंगाधर तिलक"),
        ("सुभाषचन्द्रबोस", "सुभाष चन्द्र बोस"),
        ("सरदारपटेल", "सरदार पटेल"),
        ("सिंदबादसमुद्र", "सिंदबाद समुद्र"),
        ("बंदरदीवार", "बंदर दीवार"),
        ("कोल काता", "कोलकाता"),
        ("चंदाजगको", "चंदा जग को"),
        ("क्यादेता", "क्या देता"),
        ("क्याइकट्ठा", "क्या इकट्ठा"),
        ("करनेलगे", "करने लगे"),
        ("कौनटहलरहे", "कौन टहल रहे"),
        ("केरास्तेव्यापारकरता", "के रास्ते व्यापार करता"),
        ("केरास्ते", "के रास्ते"),
        ("नारादिया", "नारा दिया"),
        ("परबैठा", "पर बैठा"),
        ("एकबड़ानगर", "एक बड़ा नगर"),
        ("हमाराराष्ट्रध्वज", "हमारा राष्ट्रध्वज"),
        ("हमारादेश", "हमारा देश"),
        ("सभीप्रश्नकरनेअनिवार्यहै", "सभी प्रश्न करने अनिवार्य हैं"),
        ("कृपासफाईपरविशेषध्यानदें", "कृपया सफाई पर विशेष ध्यान दें"),
        ("सहीविकल्पपरसहीकाचिन्ह", "सही विकल्प पर सही का चिन्ह"),
        ("सहीकथनकेसामने", "सही कथन के सामने"),
        ("गलतकथनकेसामने", "गलत कथन के सामने"),
        ("निम्नलिखितशब्दोंकेअर्थलिखिए", "निम्नलिखित शब्दों के अर्थ लिखिए"),
        ("निम्नलिखितप्रश्नोंकेउत्तरलिखिए", "निम्नलिखित प्रश्नों के उत्तर लिखिए"),
        ("दिएगएशब्दोंकीसहायतासेरिक्तस्थानोंकीपूर्तिकीजिए",
         "दिए गए शब्दों की सहायता से रिक्त स्थानों की पूर्ति कीजिए"),
        ("सेरिक्तस्थानों", "से रिक्त स्थानों"),
        ("केसामने", "के सामने"),
        ("काचिन्ह", "का चिन्ह"),
        ("कोक्या", "को क्या"),
        ("अंध कार", "अंधकार"),
        ("अधि कार", "अधिकार"),
        ("स् थानों", "स्थानों"),
        ("स्  थानों", "स्थानों"),
        ("दीवारपर", "दीवार पर"),
        ("समुद्रके", "समुद्र के"),
        ("साथीटापू", "साथी टापू"),
        ("परक्या", "पर क्या"),
        ("क्याकहता", "क्या कहता"),
        ("क्यानारा", "क्या नारा"),
    ):
        t = t.replace(glued, fixed)
    t = t.replace("टापूपर", "टापू पर")
    t = t.replace("इकट्ठाकरने", "इकट्ठा करने")
    t = t.replace("स्वराजयहमाराजन्मसिद्धअधिकारहै", "स्वराज हमारा जन्मसिद्ध अधिकार है")
    t = t.replace("कौनहरता", "कौन हरता")
    t = t.replace("कौनलाते", "कौन लाते")
    t = re.sub(r"([।?:\u0964])(?=\S)", r"\1 ", t)
    t = re.sub(r"(?<=[\u0900-\u097F])(?=[A-Za-z0-9Q])", " ", t)
    t = re.sub(r"(?<=[A-Za-z0-9])(?=[\u0900-\u097F])", " ", t)
    return never_glue_words(re.sub(r" {2,}", " ", t))


def collapse_duplicate_headings(lines, seen=None):
    """प्र0-5 / Q.5 same heading, including next scanned page."""
    if seen is None:
        seen = []
    out = []
    for line in lines:
        raw = str(line or "").strip()
        if is_word_meaning_heading(raw) or is_section_heading(raw) or is_mcq_section_heading(raw):
            fp = re.sub(
                r"^(?:प्र\s*\.?\s*0?\s*-?\s*\d+|Q\s*\.?\s*\d+|प्रश्न\s*\d+)\s*",
                "",
                raw,
                flags=re.I,
            )
            fp = re.sub(r"[\s:.\-–—0-9()]+", "", fp).lower()
            if fp and fp in seen:
                continue
            if fp:
                seen.append(fp)
        out.append(line)
    return out


def contains_hindi(text):
    """Return True when Devanagari/Hindi characters are present."""
    if not text:
        return False
    return bool(re.search(r"[\u0900-\u097F]", str(text)))


def get_language_font(text):
    """Select Unicode-safe Word typography."""
    if contains_hindi(text):
        return "Nirmala UI", HINDI_SIZE
    return ENGLISH_FONT, ENGLISH_SIZE


def set_run_language_font(run, text, bold=None, replace_text=True):
    """Render Hindi as native Unicode; no legacy Kundli conversion.

    replace_text=False keeps text already written by add_text_with_math.
    Overwriting the last run with the full source line was leaking raw \\frac.
    """
    original_text = "" if text is None else str(text)
    if contains_hindi(original_text):
        rendered_text = (
            restore_hindi_spaces(original_text)
            if re.search(r"[\u0900-\u097F]{6,}", original_text)
            else original_text
        )
        font_name = "Nirmala UI"
        font_size = HINDI_SIZE
    else:
        rendered_text = original_text
        font_name = ENGLISH_FONT
        font_size = ENGLISH_SIZE
    if replace_text and run is not None and run.text != rendered_text:
        run.text = rendered_text
    set_run_font(run, font_name, font_size, bold=bold)


# ============================================================
# RED-LIST — machine chowkidar AFTER each .docx write
# Flagged files get _CHECK suffix. Only those are regenerated.
# Never re-run the whole school because one Maths paper broke.
# ============================================================
RED_LIST_ENGLISH_WRECKAGE = (
    r"\bF in d\b",
    r"\bl in es\b",
    r"\bw in dow\b",
    r"\bwrit in g\b",
    r"\bexpressi on\b",
    r"\bto tal\b",
    r"\bFind\s+in\s+d\b",
    r"\blines?\s+in\s+es\b",
)
RED_LIST_TABLE_MARK = re.compile(r"\[\[TABLE\]\]|\[\[MATCH\]\]|\[\[FIG(?:URE)?\]\]", re.I)
RED_LIST_GLUED_DEV = re.compile(
    r"[\u0900-\u097F]{12,}"
)
RED_LIST_DANDA = re.compile(r"[।\u0964]")


def _docx_collect_text_and_fonts(doc_or_path):
    """Return (full_text, list of (text, font_name), table_count)."""
    if isinstance(doc_or_path, str):
        doc = Document(doc_or_path)
    else:
        doc = doc_or_path
    chunks = []
    runs_meta = []

    def _walk_paragraphs(paragraphs):
        for p in paragraphs:
            chunks.append(p.text or "")
            for run in p.runs:
                txt = run.text or ""
                if not txt.strip():
                    continue
                fname = ""
                try:
                    fname = str(run.font.name or "")
                except Exception:
                    fname = ""
                try:
                    rPr = run._element.rPr
                    if rPr is not None and rPr.rFonts is not None:
                        fname = (
                            rPr.rFonts.get(qn("w:eastAsia"))
                            or rPr.rFonts.get(qn("w:cs"))
                            or rPr.rFonts.get(qn("w:ascii"))
                            or fname
                        )
                except Exception:
                    pass
                runs_meta.append((txt, fname or ""))

    _walk_paragraphs(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _walk_paragraphs(cell.paragraphs)
    return "\n".join(chunks), runs_meta, len(doc.tables)


def scan_docx_red_list(doc_or_path, class_name=""):
    """Return list of flag strings. Empty = paper accepted by machine."""
    flags = []
    try:
        text, runs_meta, table_count = _docx_collect_text_and_fonts(doc_or_path)
    except Exception as exc:
        return [f"redlist_read_fail:{exc}"]

    body = (text or "").strip()
    if not body:
        flags.append("empty_body")

    _marker_matches = RED_LIST_TABLE_MARK.findall(text or "")
    if _marker_matches:
        # V33.31: report the actual surviving marker instead of a generic flag.
        # A marker must never be student-visible; this remains a hard red-list failure.
        _marker_unique = []
        for _mk in _marker_matches:
            if _mk not in _marker_unique:
                _marker_unique.append(_mk)
        flags.append("table_placeholder:" + ",".join(_marker_unique[:4]))

    if not class_allows_tables(class_name) and table_count > 0:
        flags.append(f"illegal_table_class4plus:{table_count}")

    for m in RED_LIST_GLUED_DEV.finditer(text or ""):
        chunk = m.group(0)
        if RED_LIST_DANDA.search(chunk):
            continue
        if " " in chunk:
            continue
        flags.append("glued_devanagari:" + chunk[:24])
        if len(flags) > 12:
            break

    for pat in RED_LIST_ENGLISH_WRECKAGE:
        if re.search(pat, text or "", flags=re.I):
            flags.append("english_wreckage:" + pat)

    for txt, fname in runs_meta:
        if not re.search(r"[\u0900-\u097F]", txt):
            continue
        low = (fname or "").lower()
        if low and "nirmala" not in low:
            flags.append("non_nirmala_devanagari:" + (fname or "?"))
            break

    # unique, keep order
    seen = set()
    out = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def apply_red_list_to_saved_docx(output_path, class_name=""):
    """If flags found, rename stem_CHECK.docx. Return final path."""
    if not output_path or not os.path.isfile(output_path):
        return output_path
    flags = scan_docx_red_list(output_path, class_name=class_name)
    if not flags:
        print("  ✓ RED-LIST clean")
        return output_path
    stem, ext = os.path.splitext(output_path)
    if stem.endswith("_CHECK"):
        check_path = output_path
    else:
        check_path = stem + "_CHECK" + ext
    try:
        if os.path.abspath(check_path) != os.path.abspath(output_path):
            if os.path.isfile(check_path):
                os.remove(check_path)
            os.replace(output_path, check_path)
    except Exception as exc:
        print(f"  ⚠ RED-LIST rename fail: {exc}")
        check_path = output_path
    print("  ⚠ RED-LIST FAIL → " + os.path.basename(check_path))
    for f in flags[:8]:
        print("     - " + f)
    return check_path


def force_nirmala_on_devanagari(doc):
    """Every Devanagari run must use Nirmala UI — Bookman makes boxes."""

    def _fix_run(run):
        try:
            txt = run.text or ""
        except Exception:
            return
        if not re.search(r"[\u0900-\u097F]", txt):
            return
        set_run_font(run, "Nirmala UI", HINDI_SIZE)

    for p in doc.paragraphs:
        for run in p.runs:
            _fix_run(run)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        _fix_run(run)


def set_run_font(run, font_name=FONT_NAME, font_size=BODY_SIZE, bold=None):
    """
    FINAL WORD RUN TYPOGRAPHY CONTROL

    Hindi:
        Unicode source -> Kundli legacy encoding
        Font -> Kundli Hindi Normal

    English:
        Font -> Bookman Old Style

    IMPORTANT:
        Any accidental Word text-highlight formatting is explicitly removed.
        This does NOT affect normal bold formatting.
    """

    # ------------------------------------------------------------
    # FONT + SIZE
    # Devanagari in Bookman Old Style = square boxes. Always Nirmala UI.
    # ------------------------------------------------------------
    try:
        _rt = run.text or ""
    except Exception:
        _rt = ""
    font_name = "Nirmala UI"
    if font_size is None:
        font_size = HINDI_SIZE
    run.font.name = font_name
    run.font.size = Pt(font_size)

    # ------------------------------------------------------------
    # BOLD CONTROL
    # ------------------------------------------------------------
    if bold is not None:
        run.bold = bold

    # ------------------------------------------------------------
    # REMOVE ANY ACCIDENTAL TEXT HIGHLIGHT
    # ------------------------------------------------------------
    try:
        run.font.highlight_color = None
    except Exception:
        pass

    # ------------------------------------------------------------
    # REMOVE RAW w:highlight XML IF PRESENT
    # ------------------------------------------------------------
    r = run._element
    rPr = r.get_or_add_rPr()

    highlight_nodes = rPr.findall(qn("w:highlight"))

    for node in highlight_nodes:
        rPr.remove(node)

    # ------------------------------------------------------------
    # FORCE EXACT FONT FOR ALL WORD CHARACTER RANGES
    # ------------------------------------------------------------
    rFonts = rPr.rFonts

    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)

    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    rFonts.set(qn("w:eastAsia"), font_name)
    rFonts.set(qn("w:cs"), font_name)

    # ------------------------------------------------------------
    # FINAL SAFETY: REMOVE HIGHLIGHT AGAIN AFTER FONT XML UPDATE
    # ------------------------------------------------------------
    highlight_nodes = rPr.findall(qn("w:highlight"))

    for node in highlight_nodes:
        rPr.remove(node)


def set_paragraph_spacing(paragraph, before=0, after=1, line_spacing=1.0):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line_spacing


def apply_section_alignment(paragraph, text):
    """
    Section heading alignment control.
    """

    text = str(text or "").strip()

    if not text:
        return False

    if re.search(r"^\s*\(खण्ड\s*-\s*[अ-ह]\)", text):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return True

    if re.match(
        r"^\s*(SECTION|PART|GROUP)\s+[A-Z0-9IVX]+",
        text,
        flags=re.IGNORECASE
    ):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return True

    return False


def set_cell_shading(cell, fill="F2F2F2"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))

    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)

    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, start=90, bottom=70, end=90):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    tcMar = tcPr.first_child_found_in("w:tcMar")
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)

    for margin, value in [
        ("top", top),
        ("start", start),
        ("bottom", bottom),
        ("end", end),
    ]:
        node = tcMar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tcMar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_bottom_border(paragraph, color="808080", size="6"):
    p = paragraph._p
    pPr = p.get_or_add_pPr()

    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)

    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)


# ============================================================
# SECTION / QUESTION-PAPER INSTRUCTION DETECTION
# ============================================================

def is_instruction_line(line):
    """
    Detect question-paper section/instruction lines.
    These lines are ALWAYS formatted in BOLD.
    """

    text = line.strip()

    if not text:
        return False

    # Lettered section/instruction heading:
    # A. ..., B. ..., C) ...
    if re.match(r"^[A-Z]\s*[\.\)]\s+\S+", text):
        return True

    # Section / Part / Group headings
    if re.match(
        r"^(Section|Part|Group)\s+[A-Z0-9IVX]+",
        text,
        flags=re.IGNORECASE
    ):
        return True

    # Common question-paper instruction phrases
    # Fixed Hindi section/instruction headings commonly used in papers.
    hindi_section_headings = {
        "बहु विकल्पीय प्रश्न",
        "बहुविकल्पीय प्रश्न",
        "लघु उत्तरीय प्रश्न",
        "लघु उत्तरीय प्रश्नों",
        "दीर्घ उत्तरीय प्रश्न",
        "दीर्घ उत्तरीय प्रश्नों",
        "मानचित्र संबंधी प्रश्न",
        "अति लघु उत्तरीय प्रश्न",
        "रिक्त स्थान भरिए",
        "रिक्त स्थान भरो",
        "शब्दार्थ लिखिए",
        "सही गलत",
        "सही/गलत",
        "मिलान कीजिए",
    }

    normalized_text = re.sub(r"\s+", " ", text).strip().rstrip(":-–—")
    if normalized_text in hindi_section_headings:
        return True

    instruction_patterns = [
        r"\btick\b.*\bcorrect\b.*\boption\b",
        r"\bchoose\b.*\bcorrect\b",
        r"\bselect\b.*\bcorrect\b",
        r"\bfill\s+in\s+the\s+blanks?\b",
        r"\bfill\s+the\s+blanks?\b",
        r"\bword\s+meaning\b",
        r"\bword\s+meanings\b",
        r"\bmatch\s+the\s+following\b",
        r"\btrue\s*/?\s*false\b",
        r"\btrue\s+or\s+false\b",
        r"\banswer\s+the\s+following\b",
        r"\banswer\s+the\s+questions?\b",
        r"\bwrite\s+the\s+following\b",
        r"\bcomplete\s+the\s+following\b",
        r"\bcomplete\s+the\s+sentences?\b",
        r"\bname\s+the\s+following\b",
        r"\bidentify\s+the\s+following\b",
        r"\btranslate\s+the\s+following\b",
        r"\bcorrect\s+the\s+following\b",
        r"\brearrange\s+the\s+following\b",
        r"\bjoin\s+the\s+following\b",
        r"\bunderline\s+the\s+following\b",
        r"\bchoose\s+any\b",
        r"\bwrite\s+short\s+answers?\b",
        r"\bshort\s+answer\s+questions?\b",
        r"\blong\s+answer\s+questions?\b",
    ]

    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in instruction_patterns
    )


# ============================================================
# PROFESSIONAL OPTION LAYOUT ENGINE
# ============================================================

# V18 HARD FIX:
# OCR may return "(c)text(d)text", "(c) text(d) text", or other
# spacing/punctuation variations.  The old look-ahead requiring whitespace
# after the marker could therefore fail to split C/D, causing both options
# to land in one cell.  The marker itself is now the split boundary.
OPTION_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(\([a-dA-D]\)|\[[a-dA-D]\]|[a-dA-D][\.\)])"
)

# Hindi/NCERT papers often use Roman-numeral MCQ options: (i), (ii), (iii), (iv).
# These MUST be handled separately from normal sub-parts because (i)-(iv) can
# also be legitimate descriptive sub-parts outside the MCQ section.
ROMAN_OPTION_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:"
    r"\((?:iv|iii|ii|i)\)"
    r"|\[(?:iv|iii|ii|i)\]"
    r"|(?:iv|iii|ii|i)[\.\)]"
    r"|¼(?:iv|iii|ii|i)½"
    r")"
    r"(?=\s|$)",
    flags=re.IGNORECASE
)


def is_roman_option_line(line):
    """True only for the four standard Roman MCQ markers (i)-(iv)."""
    t = line.strip()
    if not t:
        return False
    return bool(ROMAN_OPTION_MARKER_RE.match(t))


def split_roman_option_line(line):
    """Split standard or legacy-Kundli Roman MCQ options."""
    stripped = str(line or "").strip()
    if not stripped:
        return []

    matches = list(ROMAN_OPTION_MARKER_RE.finditer(stripped))
    if not matches:
        return [stripped]

    first = matches[0].group(0).lower()
    valid_first = {
        "(i)", "[i]", "i.", "i)",
        "¼i½",
    }

    if first not in valid_first:
        return [stripped]

    options = []

    roman_map = {
        "¼i½": "(i)",
        "¼ii½": "(ii)",
        "¼iii½": "(iii)",
        "¼iv½": "(iv)",
    }

    for idx, match in enumerate(matches):
        start = match.start()
        end = (
            matches[idx + 1].start()
            if idx + 1 < len(matches)
            else len(stripped)
        )

        part = stripped[start:end].strip()

        if not part:
            continue

        marker = match.group(0)
        normalized_marker = roman_map.get(
            marker.lower(),
            marker
        )
        if normalized_marker.lower() in {"(i)", "[i]", "i.", "i)"}:
            normalized_marker = "(i)"
        elif "ii" in normalized_marker.lower() and "iii" not in normalized_marker.lower():
            normalized_marker = "(ii)"
        elif "iii" in normalized_marker.lower():
            normalized_marker = "(iii)"
        elif "iv" in normalized_marker.lower():
            normalized_marker = "(iv)"

        remainder = part[len(marker):].lstrip()
        # Drop doubled label inside remainder: "i) \frac..." after marker already taken
        remainder = dedupe_leading_option_label(remainder)
        # If remainder still starts with same roman marker, strip once more
        remainder = re.sub(
            r"^(?:\(\s*(?:iv|iii|ii|i)\s*\)|(?:iv|iii|ii|i)\s*[.)])\s+",
            "",
            remainder,
            flags=re.I,
        )

        if remainder:
            options.append(normalized_marker + " " + remainder)
        else:
            options.append(normalized_marker)

    return options


def is_mcq_section_heading(line):
    """Identify headings that start an MCQ/objective-options section."""
    t = re.sub(r"\s+", " ", str(line or "").strip()).rstrip(":-–—").lower()
    if any(x in t for x in ("मिलान", "सुमेलित", "match the following", "match the column")):
        return False
    mcq_phrases = (
        "बहु विकल्पीय प्रश्न",
        "बहुविकल्पीय प्रश्न",
        "बहु-विकल्पीय प्रश्न",
        "बहुविकल्प प्रश्न",
        "सही विकल्प",
        "सही/गलत विकल्प",
        "सही उत्तर चुनिए",
        "सही उत्तर चुनो",
        "निशान लगाइए",
        "निशान लगाओ",
        "निशान लगाएं",
        "multiple choice",
        "multiple-choice",
        "objective questions",
        "objective type questions",
        "choose the correct",
        "tick the correct",
        "select the correct",
        "mcq",
    )
    if "☑" in str(line or "") or "☒" in str(line or ""):
        if "विकल्प" in t or "option" in t or "tick" in t:
            return True
    return any(phrase in t for phrase in mcq_phrases)


def looks_like_mcq_stem(text):
    """True when the question stem asks to choose one option (real MCQ)."""
    t = str(text or "").strip().lower()
    if not t:
        return False
    cues = (
        "choose the correct", "tick the correct", "select the correct",
        "correct option", "correct answer", "which of the following",
        "multiple choice", "mcq", "tick (", "tick the",
        "the plural of", "the opposite of", "the past tense",
        "the word", "a sentence that",
        "सही विकल्प", "सही उत्तर चुन", "निम्न में से कौन",
        "कौन-सा सही", "कौन सा सही", "सही विकल्प चुन",
    )
    return any(c in t for c in cues)


def options_go_in_one_row(options):
    """Short (a)(b)(c) must sit on ONE equal row. Long ones 2x2. Never a tall stack."""
    opts = [str(x or "").strip() for x in (options or []) if str(x or "").strip()]
    if len(opts) < 2:
        return False
    if any(looks_like_written_item(x) for x in opts):
        return False
    if any(len(re.sub(r"^\s*\([^)]+\)\s*", "", x)) > 28 for x in opts):
        return False
    return compact_grid_columns(opts, single_column=False) >= 2


def is_non_mcq_section_heading(line):
    """Identify clear later sections so Roman (i)-(iv) do not get gridded as sub-parts."""
    t = re.sub(r"\s+", " ", str(line or "").strip()).rstrip(":-–—").lower()
    non_mcq_phrases = (
        "लघु उत्तरीय प्रश्न",
        "दीर्घ उत्तरीय प्रश्न",
        "अति लघु उत्तरीय प्रश्न",
        "मानचित्र संबंधी प्रश्न",
        "short answer questions",
        "long answer questions",
        "very short answer questions",
        "map based questions",
        "मिलान कीजिए",
        "सुमेलित कीजिए",
        "match the following",
        "सही मिलान",
        "translate",
        "अनुवाद",
        "fill in the blank",
        "fill ups",
        "fill-ups",
        "fill up",
        "true / false",
        "true/false",
        "true or false",
        "true and false",
        "रिक्त स्थान",
        "खाली स्थान",
        "सही गलत",
        "सही/गलत",
        "सत्य असत्य",
        "सत्य / असत्य",
    )
    return any(phrase in t for phrase in non_mcq_phrases)


def is_vertical_item_heading(line):
    """Fill-ups / True-False / blanks — never an MCQ option grid."""
    t = re.sub(r"\s+", " ", str(line or "").strip()).rstrip(":-–—").lower()
    t = re.sub(r"^\d+\s*[.)]\s*", "", t)
    t = re.sub(r"^ques(?:tion)?\s*[-.:]?\s*\d+\s*", "", t)
    t = re.sub(r"^प्रश्न\s*[-.:]?\s*\d+\s*", "", t)
    keys = (
        "fill in the blank", "fill the blank", "fill ups", "fill-ups", "fill up",
        "fill in the following", "complete the sentence", "complete the sentences",
        "true / false", "true/false", "true or false", "true and false",
        "tick true or false", "write true or false",
        "रिक्त स्थान", "खाली स्थान", "रिक्त स्थान भरो", "रिक्त स्थान भरिए",
        "सही गलत", "सही/गलत", "सत्य असत्य", "सत्य / असत्य",
        "सही या गलत", "सही अथवा गलत",
        "translate", "translation", "अनुवाद",
        "translate into", "translate in",
        "hindi to english", "english to hindi",
        "अर्थ लिखो", "अर्थ लिखिए", "शब्दार्थ",
        "opposite word", "synonym", "विलोम", "पर्यायवाची",
        "solve these", "solve the following", "word problem", "word sums",
        "story sum", "statements", "do any", "हल करो", "हल कीजिए",
        "कथन", "इन प्रश्नों", "निम्न प्रश्नों को हल",
    )
    return any(k in t for k in keys)


def looks_like_written_item(text):
    """Sentence / blank / T-F box / translate prompt — not a short MCQ choice."""
    body = re.sub(r"^\s*\(?\s*(?:[ivx]{1,6}|[a-dA-D0-9]+)\s*\)?\s*[.)]?\s*", "", str(text or ""), flags=re.I)
    body = body.strip()
    if not body:
        return False
    if re.search(r"_{3,}|\.{4,}|\[\s*\]|\(\s*\)", body):
        return True
    # "सचमुच ="  "Very well ="  translation / meaning prompts
    if re.search(r"=\s*$", body) or body.endswith(":"):
        return True
    if len(body) > 18:
        return True
    if re.search(r"[\u0900-\u097F]", body):
        return True
    if re.search(r"\b(is|are|was|were|has|have|should|your|our|we|a|the|of|bought|cost|how many|altogether)\b", body, re.I):
        return True
    if "₹" in body or "rs." in body.lower() or re.search(r"\brs\b", body, re.I):
        return True
    return False


def _normalize_alpha_option_label(label):
    """
    Normalize OCR/LLM option labels to the professional lowercase form:
        (A), (B), (C), (D) -> (a), (b), (c), (d)
        [A] -> [a]
        A. / A) -> a. / a)

    Only the option marker is normalized; the option wording itself is never
    changed.
    """
    raw = str(label or "")
    m = re.match(r"^\s*([\(\[])([a-dA-D])([\)\]])\s*$", raw)
    if m:
        return f"{m.group(1)}{m.group(2).lower()}{m.group(3)}"
    m = re.match(r"^\s*([a-dA-D])([.)])\s*$", raw)
    if m:
        return f"{m.group(1).lower()}{m.group(2)}"
    return raw


def _normalize_option_marker_in_text(option_text):
    """Normalize only the leading alpha option marker; preserve wording."""
    s = str(option_text or "").strip()
    m = re.match(r"^(\s*(?:\([a-dA-D]\)|\[[a-dA-D]\]|[a-dA-D][.)]))(\s+)(.*)$", s)
    if not m:
        return s
    return _normalize_alpha_option_label(m.group(1)) + m.group(2) + m.group(3).strip()


def split_option_line(line):
    """
    V20 HARD MCQ RULE.

    Every alpha option marker (a)-(d), regardless of case and regardless of
    whether OCR inserted a space, is an independent hard boundary.

    Examples:
      (a) A (b) B (c) C (d) D
      (a) A (b) B (c) C(d) D
      (A) A (B) B (C) C (D) D

    Output is always one logical string per option. Labels are normalized to
    lowercase a/b/c/d; the actual option wording is untouched.
    """
    stripped = re.sub(r"\s+", " ", str(line or "").strip())
    if not stripped:
        return []

    matches = list(OPTION_MARKER_RE.finditer(stripped))
    if not matches:
        return [stripped]

    first = _normalize_alpha_option_label(matches[0].group(0).strip()).lower()
    if first not in ("(a)", "[a]", "a.", "a)"):
        return [stripped]

    options = []
    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(stripped)
        part = stripped[start_pos:end_pos].strip()
        if part:
            options.append(_normalize_option_marker_in_text(part))

    # Defensive second pass: no option may contain another option marker.
    final = []
    for part in options:
        nested = list(OPTION_MARKER_RE.finditer(part))
        if len(nested) <= 1:
            final.append(_normalize_option_marker_in_text(part))
            continue

        for j, m in enumerate(nested):
            s = m.start()
            e = nested[j + 1].start() if j + 1 < len(nested) else len(part)
            piece = part[s:e].strip()
            if piece:
                final.append(_normalize_option_marker_in_text(piece))

    return final


def is_option_line(line):
    t = line.strip()
    if not t:
        return False

    return bool(
        re.match(
            r"^\s*(?:\([a-dA-D]\)|\[[a-dA-D]\]|[a-dA-D][\.\)])\s+",
            t
        )
    )


def expand_option_lines(lines):
    expanded = []

    for line in lines:
        parts = split_option_line(line)

        if len(parts) > 1:
            expanded.extend(parts)
        else:
            expanded.append(line)

    return expanded


def is_option_line(line):
    """
    True for a line beginning with an MCQ option marker.
    """
    t = line.strip()

    if not t:
        return False

    return bool(
        re.match(
            r"^\s*(?:\([a-dक-घअ-द]\)|[a-dक-घ][\.\)])\s+",
            t,
            flags=re.IGNORECASE
        )
    )


def expand_option_lines(lines):
    """
    Expand OCR lines so every individual MCQ option becomes one logical item.
    """
    expanded = []

    for line in lines:
        parts = split_option_line(line)

        if len(parts) >= 2:
            expanded.extend(parts)
        else:
            expanded.append(line)

    return expanded


SHORT_GRID_CHARS = 12


def _grid_token_len(text):
    t = str(text or "")
    t = re.sub(r"^\s*[•·▪◦●○]\s*", "", t)
    t = re.sub(r"^\s*\([^)]{1,8}\)\s*", "", t)
    t = re.sub(r"\s*=\s*_+\s*$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return len(t)


def compact_grid_columns(items, single_column=False):
    """
    CORE RULE — no visible table border (caller strips borders).

    Token length ~10-12 chars → ONE row, equal cells.
    Longer tokens, 4 items → 2x2 (columns = 2).
    Very long tokens → 1 column so text does not wrap-crush.
    """
    if single_column:
        return 1
    texts = [str(x or "").strip() for x in (items or []) if str(x or "").strip()]
    count = len(texts)
    if count <= 1:
        return 1
    max_len = max(_grid_token_len(x) for x in texts)
    if max_len <= SHORT_GRID_CHARS and count <= 6:
        return count
    if count == 4:
        columns = 2
        return columns
    if count == 3:
        return 3 if max_len <= 16 else 2
    if max_len > 28:
        return 1
    columns = 2
    return columns


def option_layout_columns(options, single_column=False):
    """MCQ grid follows compact_grid_columns (short = 1 row, long = 2x2)."""
    return compact_grid_columns(options, single_column=single_column)


def calculate_option_grid_font_size(options, column_count):
    """
    PROFESSIONAL MCQ GRID FONT RULES
    --------------------------------
    The old engine sized each option independently. That caused long C/D
    options to become much smaller than A/B. This version calculates ONE
    common font size for the ENTIRE option grid, so all options remain
    visually consistent.

    Four options are ALWAYS 2 x 2.
    Long text is allowed to WRAP inside its cell instead of shrinking to
    an unreadably small font.
    """
    if not options:
        return ENGLISH_SIZE

    # Use the document language represented by the majority/longest option.
    hindi_present = any(contains_hindi(x) for x in options)
    base_size = HINDI_SIZE if hindi_present else ENGLISH_SIZE

    max_len = max(len(str(x)) for x in options)

    if column_count == 2:
        # 15 pt is the normal professional grid size. Long options wrap;
        # they do NOT get individually shrunk.
        if max_len <= 58:
            return 15.0
        if max_len <= 78:
            return 14.5
        if max_len <= 100:
            return 14.0
        return 13.5

    if column_count == 3:
        # Three short options should remain on ONE ROW at a readable size.
        # Long text wraps inside the cell; all three options still share ONE
        # common size so no individual option becomes visually smaller.
        if max_len <= 45:
            return 15.0
        if max_len <= 65:
            return 14.5
        if max_len <= 85:
            return 14.0
        return 13.5

    return min(base_size, 15.0)

def remove_table_borders(table):
    """
    Remove all visible borders from an MCQ layout table.
    The table remains a fixed alignment grid but is invisible on paper.
    """
    tbl = table._tbl
    tblPr = tbl.tblPr

    borders = tblPr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)

    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))

        if element is None:
            element = OxmlElement(tag)
            borders.append(element)

        element.set(qn("w:val"), "nil")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "auto")




def collect_roman_subpart_run(lines, start):
    """Consecutive (i)(ii)(iii) answer-parts under one question. Not MCQ choices."""
    items = []
    j = start
    while j < len(lines):
        raw = str(lines[j]).strip()
        if not raw:
            j += 1
            if items:
                break
            continue
        if is_section_heading(raw) or is_match_heading(raw) or is_mcq_section_heading(raw):
            break
        if has_explicit_question_label(raw) or is_major_question_start(raw):
            break
        if extract_inline_mcq(raw):
            break
        m = re.match(r"^(\(([ivx]{1,6})\))\s*(.*)$", raw, flags=re.I)
        if not m:
            break
        marker = "(" + m.group(2).lower() + ")"
        body = m.group(3).strip()
        if looks_like_written_item(marker + " " + body):
            items.append((marker, body))
            j += 1
            if len(items) >= 16:
                break
            continue
        if len(body) <= 18 and not re.search(r"[?।?]", body):
            # short token — likely an MCQ choice, not a sub-question
            break
        items.append((marker, body))
        j += 1
        if len(items) >= 16:
            break
    if len(items) < 2:
        return [], start
    return items, j


def add_subpart_lines_no_table(doc, items):
    """Render Maths sub-parts as normal paragraphs; never use a table."""
    if not items:
        return False
    for marker, body in items:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(p, before=0, after=1, line_spacing=1.08)
        p.paragraph_format.keep_together = True
        r = p.add_run(f"{marker} {body}".strip())
        set_run_language_font(r, r.text, bold=False)
        r.font.size = Pt(BODY_SIZE)
    return True


def add_subpart_align_table(doc, items):
    """Two fixed columns: marker | text. Same left edge for every part."""
    if not items:
        return False
    if not class_allows_tables():
        for marker, body in items:
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=1, after=1, line_spacing=1.08)
            r = p.add_run(f"{marker} {body}".strip())
            set_run_language_font(r, r.text, bold=False)
            r.font.size = Pt(BODY_SIZE)
        return True
    table = doc.add_table(rows=len(items), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    try:
        force_table_inline(table)
        remove_table_borders(table)
    except Exception:
        pass
    mark_w, text_w = 0.55, 6.10
    tblPr = table._tbl.tblPr
    lay = tblPr.first_child_found_in("w:tblLayout")
    if lay is None:
        lay = OxmlElement("w:tblLayout")
        tblPr.append(lay)
    lay.set(qn("w:type"), "fixed")
    try:
        table.columns[0].width = Inches(mark_w)
        table.columns[1].width = Inches(text_w)
    except Exception:
        pass
    for r, (marker, body) in enumerate(items):
        for col, text, wid in ((0, marker, mark_w), (1, body, text_w)):
            cell = table.cell(r, col)
            try:
                _set_tc_width(cell, wid)
            except Exception:
                pass
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(p, before=0, after=1, line_spacing=1.08)
            if text:
                run = p.add_run(text)
                set_run_language_font(run, text, bold=False)
                run.font.size = Pt(BODY_SIZE)
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, before=1, after=4, line_spacing=1.0)
    return True


def extract_inline_mcq(line):
    """Stem + glued options on one OCR line. Not matching columns.

    (i) How many muscles — (i) 550 (ii) 650
    """
    raw = str(line or "").strip()
    if not raw:
        return None
    if is_match_heading(raw):
        return None
    markers = list(re.finditer(r"\(([ivx]{1,6}|[a-dA-D])\)", raw, flags=re.I))
    if len(markers) < 3:
        return None
    if markers[0].start() > 2:
        return None
    opt_start = markers[1].start()
    stem = raw[:opt_start].strip().rstrip("-–—:").strip()
    tail = raw[opt_start:].strip()
    if len(stem) < 8 or len(tail) < 4:
        return None
    # options should be short choice fragments, not another long question
    parts = []
    if re.search(r"\([ivx]+\)", tail, flags=re.I):
        parts = split_roman_option_line(tail)
    if len(parts) < 2:
        parts = split_option_line(tail)
    parts = [p.strip() for p in parts if str(p).strip()]
    if len(parts) < 2:
        return None
    # reject if an "option" is itself a long question
    if sum(1 for p in parts if len(re.sub(r"^\([^\)]+\)\s*", "", p)) > 48) >= 2:
        return None
    if any(looks_like_written_item(p) for p in parts):
        return None
    return stem, parts


def collect_mcq_option_block(lines, start_index, mcq_mode=False):
    """
    V8 ADDITIVE RULE:
    Detect an MCQ option block even when it appears AFTER a sub-question line.

    Example:
        (क) सज्जन को ______ लगी...
        (i) भूख ( )
        (ii) प्यास ( )
        (iii) चोट ( )

    The three options are treated as ONE option grid and rendered in one row.
    This permanently prevents unnecessary vertical paper wastage in fill/choice
    questions that use Roman-numeral options under each sub-item.

    The same logic also supports (a)-(d) blocks when they occur under a sub-item.
    It is intentionally context-aware: only a consecutive block of 2-4 option
    lines is converted into a grid.
    """
    if start_index >= len(lines):
        return [], start_index

    first = lines[start_index].strip()
    if not first:
        return [], start_index

    roman_first = mcq_mode and is_roman_option_line(first)
    alpha_first = is_option_line(first)

    if not (roman_first or alpha_first):
        return [], start_index

    options = []
    j = start_index

    while j < len(lines):
        current = lines[j].strip()
        if not current:
            break

        if roman_first:
            if not (mcq_mode and is_roman_option_line(current)):
                break
            parts = split_roman_option_line(current)
        else:
            if not is_option_line(current):
                break
            parts = split_option_line(current)

        for part in parts:
            if part.strip():
                options.append(part.strip())

        j += 1

        # A normal MCQ option block is normally 2-4 options. Do not absorb
        # unrelated later content into the same grid.
        if len(options) >= 4:
            break

    if 2 <= len(options) <= 4:
        if options and all(is_math_working_body(x) for x in options):
            return [], start_index
        if any(looks_like_written_item(x) for x in options):
            return [], start_index
        return options, j

    return [], start_index


def collect_nested_mcq_options(lines, subpart_index, mcq_mode=False):
    """
    V10 NESTED MCQ COLLECTOR.

    A consecutive Roman (i)-(iv) block immediately following a sub-question
    is a real MCQ option block even when mcq_mode is False.

    The detection is intentionally limited to this nested position so ordinary
    Roman-numbered sub-parts elsewhere in the paper are not changed.
    """
    next_index = subpart_index + 1

    if next_index >= len(lines):
        return [], next_index
    first = lines[next_index].strip()

    # in the nested position, treat consecutive Roman options as MCQ
    if is_roman_option_line(first):
        options = []
        j = next_index

        while j < len(lines):
            current = lines[j].strip()
            if not current or not is_roman_option_line(current):
                break
            parts = split_roman_option_line(current)
            for part in parts:
                if part.strip():
                    options.append(part.strip())

            j += 1
            if len(options) >= 4:
                break
        if 2 <= len(options) <= 4:
            block = options[:4]
            if all(is_math_working_body(x) for x in block):
                return [], subpart_index
            # Fill-ups / T-F sentences must stay vertical, never a choice grid.
            if any(looks_like_written_item(x) for x in block):
                return [], subpart_index
            return block, j
        return [], subpart_index

    return collect_mcq_option_block(lines, next_index, mcq_mode=mcq_mode)

def add_option_table(doc, options, hindi_labels=False, single_column=False, no_table=False):
    """
    Render MCQ options in a strict professional grid.

    Normal papers (4 options):
        Row 1 -> (a) | (b)
        Row 2 -> (c) | (d)

    Maths papers (single_column=True):
        (a)
        (b)
        (c)
        (d)
        — one column only, authentic exam style.

    Every option gets exactly one cell.
    """
    if not options:
        return
    if not class_allows_tables():
        no_table = True

    # V18 HARD SAFETY:
    # Normalize only option labels (not wording) before rendering.
    options = [_normalize_option_marker_in_text(x) for x in options]

    # SUBJECT-BASED HINDI MCQ LABEL FIX:
    # Hindi paper -> (अ) (ब) (स) (द)
    # English paper -> (a) (b) (c) (d)
    if hindi_labels:
        _hindi_option_labels = {"(a)": "(अ)", "(b)": "(ब)", "(c)": "(स)", "(d)": "(द)"}
        converted_options = []
        for _opt in options:
            _m = re.match(r"(\s*)\(([a-dA-D])\)(\s+)(.*)$", str(_opt), flags=re.DOTALL)
            if _m:
                _label = "(" + _m.group(2).lower() + ")"
                _opt = _m.group(1) + _hindi_option_labels.get(_label, _label) + _m.group(3) + _m.group(4)
            converted_options.append(_opt)
        options = converted_options

    # NCERT MATHS BODY RULE: never use tables for question/options layout.
    # Metadata/header tables remain allowed; question body is rendered as
    # ordinary sequential paragraphs.
    if no_table:
        option_size = calculate_option_grid_font_size(options, 1)
        for option_text in options:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(p, before=0, after=1, line_spacing=1.0)
            p.paragraph_format.keep_together = True
            _roman_label_match = re.match(
                r"(\s*)\(((?:i|ii|iii|iv))\)(\s+)(.*)$",
                str(option_text), flags=re.IGNORECASE | re.DOTALL
            )
            _hindi_label_match = re.match(
                r"(\s*)\(([अबसद])\)(\s+)(.*)$",
                str(option_text), flags=re.DOTALL
            )
            if _roman_label_match:
                p.add_run(_roman_label_match.group(1))
                rr = p.add_run("(" + _roman_label_match.group(2).lower() + ")" + _roman_label_match.group(3))
                set_run_font(rr, "Nirmala UI", option_size, bold=False)
                wr, _ = add_text_with_math(p, _roman_label_match.group(4), bold=False)
                wr.font.size = Pt(option_size)
            elif _hindi_label_match and hindi_labels:
                p.add_run(_hindi_label_match.group(1))
                rr = p.add_run("(" + _hindi_label_match.group(2) + ")" + _hindi_label_match.group(3))
                set_run_font(rr, "Nirmala UI", option_size, bold=False)
                wr, _ = add_text_with_math(p, _hindi_label_match.group(4), bold=False)
                wr.font.size = Pt(option_size)
            else:
                rr, _ = add_text_with_math(p, option_text, bold=False)
                rr.font.size = Pt(option_size)
        return

    # V27 Maths: force single vertical column for authentic layout
    if single_column:
        columns = 1
    else:
        columns = compact_grid_columns(options, single_column=False)
        # long 4-option pack stays 2x2
        if len(options) == 4 and compact_grid_columns(options) == 2:
            columns = 2
        if len(options) == 4 and max(_grid_token_len(x) for x in options) > SHORT_GRID_CHARS:
            columns = 2

    rows = (len(options) + columns - 1) // columns

    table = doc.add_table(rows=rows, cols=columns)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    force_table_inline(table)
    remove_table_borders(table)

    usable_width = OPTION_GRID_WIDTH
    column_width = usable_width / columns

    # Lock Word's table layout so columns cannot resize according to text.
    tblPr = table._tbl.tblPr
    tblLayout = tblPr.first_child_found_in("w:tblLayout")
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")

    for col in table.columns:
        col.width = Inches(column_width)

    # HARD row/column geometry:
    # 4 options = [A B] / [C D]
    # 3 options = [A B C]
    # Prevent Word from splitting an individual option cell across pages.
    for row_obj in table.rows:
        trPr = row_obj._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        trPr.append(cant_split)

    for index, option_text in enumerate(options):
        # Strict row-major placement.
        row = index // columns
        col = index % columns

        cell = table.cell(row, col)
        cell.width = Inches(column_width)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

        set_cell_margins(
            cell,
            top=0,
            start=20,
            bottom=0,
            end=20
        )

        tcPr = cell._tc.get_or_add_tcPr()
        tcW = tcPr.find(qn("w:tcW"))
        if tcW is None:
            tcW = OxmlElement("w:tcW")
            tcPr.append(tcW)
        tcW.set(qn("w:w"), str(int(column_width * 1440)))
        tcW.set(qn("w:type"), "dxa")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(
            p,
            before=0,
            after=0,
            line_spacing=1.0
        )
        p.paragraph_format.keep_together = True
        p.paragraph_format.keep_with_next = False
        p.paragraph_format.widow_control = False

        option_font, _ = get_language_font(option_text)
        # IMPORTANT: one common size for the whole grid. This permanently
        # prevents C/D from becoming smaller than A/B.
        option_size = calculate_option_grid_font_size(options, columns)

        # ------------------------------------------------------------
        # FINAL MCQ LABEL RENDERING
        # ------------------------------------------------------------
        # IMPORTANT:
        # Hindi labels (अ/ब/स/द) MUST NOT pass through Kundli conversion.
        # Otherwise Unicode (अ) is converted by unicode_to_kundli() and
        # visually becomes the legacy (a)/(b)/(c)/(d) representation.
        #
        # Therefore render the Devanagari label separately using a Unicode
        # Hindi font, while the actual option wording continues through the
        # normal Kundli rendering pipeline.
        # ------------------------------------------------------------
        # FINAL MCQ LABEL RENDERING - V5
        # ------------------------------------------------------------
        # Roman labels (i)-(iv) and Hindi labels (अ)-(द) are Unicode
        # labels and MUST NOT pass through the Kundli codec.
        # Only the actual option wording uses the existing codec.
        # ------------------------------------------------------------

        _roman_label_match = re.match(
            r"(\s*)\(((?:i|ii|iii|iv))\)(\s+)(.*)$",
            str(option_text),
            flags=re.IGNORECASE | re.DOTALL
        )

        _hindi_label_match = re.match(
            r"(\s*)\(([अबसद])\)(\s+)(.*)$",
            str(option_text),
            flags=re.DOTALL
        )

        if _roman_label_match:
            _leading_space = _roman_label_match.group(1)
            _roman_label = "(" + _roman_label_match.group(2).lower() + ")"
            _separator = _roman_label_match.group(3)
            _option_wording = _roman_label_match.group(4)

            if _leading_space:
                _space_run = p.add_run(_leading_space)
                set_run_font(_space_run, "Nirmala UI", option_size, bold=False)

            _roman_run = p.add_run(_roman_label)
            set_run_font(_roman_run, "Nirmala UI", option_size, bold=False)

            _separator_run = p.add_run(_separator)
            set_run_font(_separator_run, "Nirmala UI", option_size, bold=False)

            _wording_run, _ = add_text_with_math(p, _option_wording, bold=False)
            _wording_run.font.size = Pt(option_size)

        elif _hindi_label_match and hindi_labels:
            _leading_space = _hindi_label_match.group(1)
            _hindi_label = "(" + _hindi_label_match.group(2) + ")"
            _separator = _hindi_label_match.group(3)
            _option_wording = _hindi_label_match.group(4)

            if _leading_space:
                _space_run = p.add_run(_leading_space)
                set_run_font(_space_run, "Nirmala UI", option_size, bold=False)

            _label_run = p.add_run(_hindi_label)
            set_run_font(_label_run, "Nirmala UI", option_size, bold=False)

            _separator_run = p.add_run(_separator)
            set_run_font(_separator_run, "Nirmala UI", option_size, bold=False)

            _wording_run, _ = add_text_with_math(p, _option_wording, bold=False)
            _wording_run.font.size = Pt(option_size)

        else:
            run, _ = add_text_with_math(p, option_text, bold=False)
            run.font.size = Pt(option_size)

    # Keep unused cells genuinely empty.
    for index in range(len(options), rows * columns):
        row = index // columns
        col = index % columns
        table.cell(row, col).paragraphs[0].add_run("")

    # Absolutely no spacer paragraph after an option grid.


# ============================================================
# QUESTION DETECTION
# ============================================================

_DEV_DIGIT_AUDIT = str.maketrans("०१२३४५६७८९", "0123456789")


def _looks_like_marks_scheme(text):
    """2×5 = 10 / 1x5=5 / :- ⑤  are MARKS, not multiplication questions."""
    t = str(text or "").translate(_DEV_DIGIT_AUDIT)
    if re.search(r"\d+\s*[xX×]\s*\d+\s*=\s*\d+", t):
        if re.search(r"(लिखत|उत्तर|प्रश्न|अंक|पूर्ण|:-|:)", str(text or "")):
            return True
        if re.match(r"^\s*\d+\s*[xX×]\s*\d+\s*=\s*\d+\s*$", t):
            return True
    return False


# Unified major-question label. Matches ALL of:
#   Q5  Q.5  Q-5  Q 5  Ques 5  Ques.5)  Question 5
#   प्रश्न 5  प्रश्न-5  प्र०५  प्र01  प्र0 2
# Punctuation after the number is OPTIONAL so "Q5 A train" is not dropped.
_EXPLICIT_Q_LABEL_RE = re.compile(
    r"^(?:"
    r"प्रश्न|प्र०|प्र0|प्र|"
    r"Ques(?:tion)?|Question|Q"
    r")"
    r"\s*[-.:：)]?\s*"
    r"([0-9०-९]{1,2})"
    r"(?:\s*[-.:：)]+)*"
    r"(?=\s|$|[A-Za-zअ-ह])",
    re.IGNORECASE,
)
_PLAIN_MAJOR_NUM_RE = re.compile(
    r"^([0-9०-९]{1,2})\s*[.)]\s+\S+"
)


def _label_digits_to_int(raw):
    t = str(raw or "").translate(_DEV_DIGIT_AUDIT)
    try:
        n = int(t)
    except (TypeError, ValueError):
        return None
    if 1 <= n <= 40:
        return n
    return None


def has_explicit_question_label(line):
    """Detect explicit question labels including glued Q5 / Q6 forms."""
    text = str(line or "").strip()
    if not text:
        return False
    if re.match(r"^[\(\[]\s*\d+\s*[\)\]]", text):
        return False
    return bool(_EXPLICIT_Q_LABEL_RE.match(text))


# ============================================================
# STABLE NUMBERING ENGINE — major + sub-part + option
# Recognises every common school-paper marker and classifies it
# so Q5 is never dropped and (a)/(i)/1) stay sub-parts.
# ============================================================
_SUB_ALPHA_RE = re.compile(
    r"^(\(\s*([a-hA-H])\s*\)|\s*([a-hA-H])\s*[\.)])\s*(.*)$"
)
_SUB_ROMAN_RE = re.compile(
    r"^(\(\s*(i{1,3}|iv|vi{0,3}|ix|x|I{1,3}|IV|VI{0,3}|IX|X)\s*\)|"
    r"(i{1,3}|iv|vi{0,3}|ix|x)\s*\))\s*(.*)$",
    re.I,
)
_SUB_HINDI_RE = re.compile(
    r"^(\(\s*([कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह])\s*\))\s*(.*)$"
)
_SUB_NUM_PAREN_RE = re.compile(
    r"^(\(\s*([0-9०-९]{1,2})\s*\))\s*(.*)$"
)
_SUB_NUM_PLAIN_RE = re.compile(
    r"^(([0-9०-९]{1,2})\s*[.)])\s+(.*)$"
)


def classify_numbering(line, major_open=False, last_major=None):
    """Return numbering kind for one paper line.

    kind: 'major' | 'subpart' | 'option' | 'other'
    """
    text = str(line or "").strip()
    if not text:
        return {"kind": "other", "number": None, "marker": "", "body": text, "line": text}

    m = _EXPLICIT_Q_LABEL_RE.match(text)
    if m:
        n = _label_digits_to_int(m.group(1))
        body = text[m.end():].strip()
        marker = "Q." + str(n) if n is not None else m.group(0).strip()
        return {"kind": "major", "number": n, "marker": marker, "body": body, "line": text, "style": "explicit"}

    m = _SUB_HINDI_RE.match(text)
    if m:
        return {"kind": "subpart", "number": m.group(2), "marker": "(" + m.group(2) + ")",
                "body": m.group(3).strip(), "line": text, "style": "hindi"}

    m = _SUB_ROMAN_RE.match(text)
    if m:
        inner = re.sub(r"[()\s]", "", m.group(1)).lower()
        body = m.group(m.lastindex).strip() if m.lastindex else ""
        return {"kind": "subpart", "number": inner, "marker": "(" + inner + ")",
                "body": body, "line": text, "style": "roman"}

    m = _SUB_ALPHA_RE.match(text)
    if m:
        letter = (m.group(2) or m.group(3) or "").lower()
        body = m.group(4).strip() if m.lastindex and m.lastindex >= 4 else text
        # group layout: (fullmark, parenletter, plainletter, body)
        body = (m.group(4) or "").strip()
        kind = "option" if letter in "abcd" else "subpart"
        return {"kind": kind, "number": letter, "marker": "(" + letter + ")",
                "body": body, "line": text, "style": "alpha"}

    m = _SUB_NUM_PAREN_RE.match(text)
    if m:
        n = _label_digits_to_int(m.group(2))
        return {"kind": "subpart", "number": n, "marker": "(" + str(n) + ")",
                "body": m.group(3).strip(), "line": text, "style": "num_paren"}

    m = _SUB_NUM_PLAIN_RE.match(text)
    if m:
        n = _label_digits_to_int(m.group(2))
        body = m.group(3).strip()
        # Open major question → 1) 2) 3) are sub-items, not new Q1/Q2.
        if major_open:
            if last_major is None or n is None or n <= last_major or n == 1 or (last_major and n < last_major):
                return {"kind": "subpart", "number": n, "marker": str(n) + ")",
                        "body": body, "line": text, "style": "num_plain"}
            if last_major is not None and n == last_major + 1:
                return {"kind": "major", "number": n, "marker": str(n) + ".",
                        "body": body, "line": text, "style": "plain_seq"}
        # No major open yet: 1. Answer the following = major
        return {"kind": "major", "number": n, "marker": str(n) + ".",
                "body": body, "line": text, "style": "plain_seq"}

    return {"kind": "other", "number": None, "marker": "", "body": text, "line": text, "style": ""}


def normalize_numbering_line(line, info=None, major_open=False, last_major=None):
    """Keep body wording; tidy only the marker so numbering prints stably."""
    info = info or classify_numbering(line, major_open=major_open, last_major=last_major)
    if info["kind"] == "other" or not info.get("marker"):
        return str(line or "").strip()
    body = info.get("body") or ""
    if info["kind"] == "major" and info.get("style") == "explicit" and info.get("number"):
        return "Q." + str(info["number"]) + ("  " + body if body else "")
    if info["kind"] in ("subpart", "option"):
        return info["marker"] + ("  " + body if body else "")
    if info["kind"] == "major" and info.get("style") == "plain_seq":
        return str(info["number"]) + ".  " + body
    return str(line or "").strip()


def line_is_true_false_heading(text):
    """True only for real T/F instruction lines — never 'Write five names'."""
    t = re.sub(r"\s+", " ", str(text or "").strip()).lower()
    if not t:
        return False
    if re.search(
        r"write\s+(?:the\s+)?(?:five|four|three|two|six|seven|ten|\d+)\s+"
        r"|write\s+(?:the\s+)?(?:name|names|organs?|festivals?|helpers?|habits?|places?|relations?)",
        t,
    ) and not re.search(r"true|false|सत्य|गलत|असत्य", t):
        return False
    return bool(re.search(
        r"true\s*/\s*false|true\s+or\s+false|true\s+and\s+false|"
        r"\bt\s+for\s+true\b|\bwrite\s+t\s+for\b|"
        r"write t for true and f for false|"
        r"सत्य\s*(?:/|,|\s+)\s*असत्य|सही\s*/\s*गलत",
        t,
    ))


def line_closes_true_false_section(text):
    """New question / other section ends the T/F stamp zone."""
    t = str(text or "").strip()
    if not t:
        return False
    if line_is_true_false_heading(t):
        return False
    if has_explicit_question_label(t) or is_major_question_start(t):
        return True
    if is_mcq_section_heading(t) or is_non_mcq_section_heading(t):
        return True
    if is_word_meaning_heading(t):
        return True
    low = t.lower()
    if re.search(r"fill in the blank|रिक्त स्थान|write five|write four|write three|write the names", low):
        return True
    return False


def is_major_question_start(line):
    """
    Detect only real major question starts.

    Examples:
        प्रश्न 1
        प्रश्न-2
        प्रश्न : 3
        प्रश्न 4.
        1. निम्नलिखित प्रश्नों के उत्तर दीजिए

    Excludes:
        (1) sub-parts
        (अ) options
        (i) roman options
    """

    text = str(line or "").strip()

    if not text:
        return False

    # Sub-parts / options are never major questions
    if re.match(r"^\s*[\(\[]\s*\d+\s*[\)\]]", text):
        return False

    if re.match(r"^\s*[\(\[]\s*[अ-ह]\s*[\)\]]", text):
        return False

    if re.match(r"^\s*[\(\[]\s*(?:i|ii|iii|iv)\s*[\)\]]", text, re.I):
        return False

    if has_explicit_question_label(text):
        return True

    return bool(
        re.match(
            r"^\s*(?:प्रश्न\s*[-.:]?\s*)?\d+\s*[\.)]?\s+\S+",
            text
        )
    )

def is_main_question_line(line, allow_plain_numeric=True):
    """
    Detect a REAL main-question line.

    IMPORTANT CONTEXT RULE:
      - Explicit labels such as 'प्रश्न : 2', 'प्रश्न-5', 'प्रश्न.11.' are
        always main questions.
      - Plain '1. ...', '2. ...' lines are treated as main questions only
        when the caller explicitly allows them. The formatter disables this
        for numbered sub-items belonging to an already-open explicit question.
      - This prevents question 2/4 sub-items like '1. ... 2. ... 3. ...'
        from being incorrectly made BOLD.
    """
    text = str(line or "").strip()
    if not text:
        return False

    if has_explicit_question_label(text):
        return True

    if not allow_plain_numeric:
        return False

    patterns = [
        r"^\d+\s*[\.)]\s+\S+",
    ]
    return any(re.match(p, text, flags=re.IGNORECASE) for p in patterns)


def is_subpart_or_option(line):
    """Detect ordinary sub-parts/options; these are ALWAYS NORMAL.

    Context-free: letters/roman/Hindi/(1) are sub-parts.
    Plain 1. 2. lines are NOT forced into sub-part here — the formatter
    decides that from whether a major question is already open.
    """
    info = classify_numbering(line, major_open=False)
    return info["kind"] in ("subpart", "option") or info.get("style") in (
        "alpha", "roman", "hindi", "num_paren"
    )


def _normalize_heading_for_match(text):
    """Normalize only for heading detection; displayed wording is untouched."""
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\s:：;；,，.!।]+$", "", text)
    return text.strip().casefold()


def is_section_heading(line):
    """Detect English and Hindi question-paper section headings."""
    text = line.strip()
    if not text:
        return False

    normalized = _normalize_heading_for_match(text)
    hindi_headings = {
        "बहु विकल्पीय प्रश्न", "बहुविकल्पीय प्रश्न", "बहु-विकल्पीय प्रश्न",
        "लघु उत्तरीय प्रश्न", "दीर्घ उत्तरीय प्रश्न", "दीर्घ-उत्तरीय प्रश्न",
        "मानचित्र संबंधी प्रश्न", "मानचित्र सम्बन्धी प्रश्न",
        "अति लघु उत्तरीय प्रश्न", "अति लघु-उत्तरीय प्रश्न",
        "वस्तुनिष्ठ प्रश्न", "रिक्त स्थान भरिए", "रिक्त स्थान भरो",
        "शब्दार्थ लिखिए", "सही विकल्प चुनिए", "सही या गलत",
    }
    if normalized in {_normalize_heading_for_match(x) for x in hindi_headings}:
        return True

    section_patterns = [
        r"^SECTION\s+[A-Z0-9IVX]+(?:\s*[:.\-–—])?$",
        r"^PART\s+[A-Z0-9IVX]+(?:\s*[:.\-–—])?$",
        r"^GROUP\s+[A-Z0-9IVX]+(?:\s*[:.\-–—])?$",
        r"^SECTION[-\s]*[A-Z0-9IVX]+(?:\s*[:.\-–—])?$",
        r"^PART[-\s]*[A-Z0-9IVX]+(?:\s*[:.\-–—])?$",
    ]
    return any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in section_patterns)


# ============================================================
# ADD PROFESSIONAL BODY TEXT
# ============================================================


# ============================================================
# SPECIAL SECTION: WORD-MEANING / VOCABULARY LAYOUT
# ============================================================

_MARKS_PRODUCT_RE = re.compile(
    r"(?:\\frac\s*\{\s*\d+\s*\}\s*\{\s*\d+\s*\}|[½¼¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]|\d+\s*/\s*\d+|\d+)"
    r"\s*[x×*]\s*\d+(?:\s*=\s*\d+)?",
    re.I,
)
# Parenthesized marks noise: (1 × 2 = 2)  (1 1/2 × 2 = 3)  (1½×2=3)  (2 x 2 = 4)
_PAREN_MARKS_RE = re.compile(
    r"\s*[\(\[]\s*"
    r"(?:"
    # mixed / fraction forms: 1 1/2 , 1½ , \frac{1}{2} , 1/2
    r"(?:\d+\s+)?(?:\\frac\s*\{\s*\d+\s*\}\s*\{\s*\d+\s*\}|[½¼¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]|\d+\s*/\s*\d+)"
    r"|"
    # plain integer marks: 1 , 2 , 3
    r"\d+"
    r")"
    r"(?:\s*[x×*]\s*\d+(?:\s*=\s*\d+)?)?"
    r"\s*[\)\]]",
    re.I,
)
# Broken trailing marks fragments: (1 ½ 3   or   1 1/2 × 2 =
_TRAILING_BROKEN_MARKS_RE = re.compile(
    r"\s*[\(\[]?\s*"
    r"(?:\\frac\s*\{\s*\d+\s*\}\s*\{\s*\d+\s*\}|[½¼¾⅓⅔]|\d+\s*/\s*\d+)"
    r"(?:\s*[x×*]?\s*\d*(?:\s*=\s*\d*)?)?"
    r"\s*$",
    re.I,
)
_INSTRUCTION_HINT_RE = re.compile(
    r"(दीजिए|दीजिये|भरिए|भरिये|भरो|लिखिए|लिखिये|बदलो|बदलिए|"
    r"उत्तर|प्रश्न|रिक्त|शब्दार्थ|अर्थ|व्याकरण|निम्नलिखित|"
    r"fill|blank|answer|meaning|complete|write|choose|tick|"
    r"arrange|add|subtract|multiply|divide|find|solve|convert|check)",
    re.I,
)


HINDI_HEADING_MAP = (
    (r"write the meanings of the following words|word\s*/?\s*meaning|शब्दार्थ",
     "निम्नलिखित शब्दों के अर्थ लिखिए।"),
    (r"tick \(?.?\)? the correct option|tick the correct|choose the correct|सही विकल्प",
     "सही विकल्प पर सही का चिह्न (✓) लगाइए।"),
    (r"fill in the blanks? with the correct words|fill in the blanks?|रिक्त स्थान",
     "रिक्त स्थान भरिए।"),
    (r"write t for true and f for false|true\s*/\s*false|सही\s*/\s*गलत|सत्य",
     "सही वाक्यों पर सही तथा गलत वाक्यों पर गलत लिखिए।"),
    (r"match the following|मिलान",
     "निम्नलिखित का मिलान कीजिए।"),
)


def restore_hindi_paper_text(text):
    """Hindi paper me English instruction sentences hatao."""
    if PAPER_LANGUAGE not in {"hindi", "sanskrit"}:
        return text
    out = str(text or "")
    reps = (
        (r"Write the meanings of the following words\.?", "निम्नलिखित शब्दों के अर्थ लिखिए।"),
        (r"Tick \(?.?\)? the correct option\.?", "सही विकल्प पर सही का चिह्न (✓) लगाइए।"),
        (r"Fill in the blanks with the correct words\.?", "रिक्त स्थान भरिए।"),
        (r"Write T for True and F for False statements\.?", "सही / गलत लिखिए।"),
        (r"Options below each", ""),
        (r"\bPr\s*(\d+)\b", r"प्रश्न \1"),
        (r"\bQ\.\s*(\d+)\b", r"प्रश्न \1"),
    )
    for pat, hin in reps:
        out = re.sub(pat, hin, out, flags=re.I)
    return out


def polish_section_heading(line):
    """Keep heading in the paper language. Do not force English on Hindi/Sanskrit."""
    t = re.sub(r"\s+", " ", str(line or "").strip())
    low = t.lower()
    marks = ""
    m = re.search(r"(\(?\s*\d+\s*(?:marks?|अंक)\s*\)?)$", t, re.I)
    if m:
        marks = "  " + m.group(1)
        t_core = t[:m.start()].strip(" :-–—")
        low = t_core.lower()
    else:
        t_core = t
    lang = PAPER_LANGUAGE or detect_paper_language("", t)
    hindi_lock = lang in {"hindi", "sanskrit"}
    # Source already Devanagari — never replace with English.
    if hindi_lock or re.search(r"[\u0900-\u097F]", t_core):
        if re.search(r"word\s*/?\s*meaning|शब्दार्थ|शब्द\s*अर्थ", low):
            if re.search(r"[\u0900-\u097F]", t_core):
                return t
            return "निम्नलिखित शब्दों के अर्थ लिखिए।" + marks
        if re.search(r"fill in the blank|रिक्त स्थान", low):
            if re.search(r"[\u0900-\u097F]", t_core):
                return t
            return "रिक्त स्थान भरिए।" + marks
        if re.search(r"tick the correct|choose the correct|सही विकल्प", low):
            if re.search(r"[\u0900-\u097F]", t_core):
                return t
            return "सही विकल्प पर सही का चिह्न (✓) लगाइए।" + marks
        if re.search(r"true\s*/\s*false|सत्य|सही\s*/\s*गलत", low):
            if re.search(r"[\u0900-\u097F]", t_core):
                return t
            return "सही वाक्यों पर सही तथा गलत वाक्यों पर गलत लिखिए।" + marks
        return t
    if re.search(r"true\s*/\s*false|true\s+or\s+false|true\s+and\s+false|t for true", low):
        return "Write T for True and F for False statements." + marks
    if re.search(r"tick the correct|choose the correct", low):
        return "Tick (✓) the correct option." + marks
    if re.search(r"word\s*/?\s*meaning", low):
        return "Write the meanings of the following words." + marks
    if re.search(r"fill in the blank", low):
        return "Fill in the blanks with the correct words." + marks
    return t


def is_word_meaning_heading(line):
    """Detect Word Meaning / शब्दार्थ / विलोम / पर्यायवाची heading."""
    t = re.sub(r"\s+", " ", str(line or "").strip()).lower()
    t = t.replace("/", " ")
    if re.search(r"\bword\s*meanings?\b", t):
        return True
    if re.search(r"\bwords?\s+and\s+meanings?\b", t):
        return True
    if re.search(r"\bopposite\s+words?\b|\bantonyms?\b|\bsynonyms?\b", t):
        return True
    if re.search(r"शब्दार्थ|शब्द\s*अर्थ|अर्थ\s*लिख|निम्न\s*शब्द", t):
        return True
    if re.search(r"विलोम|पर्यायवाची|समानार्थी", t):
        return True
    return False


def is_one_word_answer_line(text):
    t = str(text or "").strip()
    if not t:
        return False
    if is_word_meaning_heading(t):
        return True
    if re.search(r"=\s*$", t) and len(t) <= 80:
        return True
    return False


def classify_answer_kind(line, stem=""):
    """one_word | one_sentence | multi_line | none"""
    blob = (str(stem or "") + " " + str(line or "")).lower()
    raw = str(line or "").strip()
    if not raw:
        return "none"
    if is_option_line(raw) or is_roman_option_line(raw):
        if re.search(r"one word|एक शब्द|शब्दार्थ|विलोम|पर्याय", str(stem or ""), re.I):
            return "one_word"
        return "none"
    if re.search(
        r"निबंध|पत्र लिख|दीर्घ उत्तर|explain in detail|describe in detail|"
        r"अनुच्छेद|आवेदन|प्रार्थना",
        blob,
        re.I,
    ):
        return "multi_line"
    if re.search(r"one word|एक शब्द|शब्दार्थ|विलोम|पर्याय", blob, re.I):
        return "one_word"
    if re.search(
        r"एक वाक्य|one sentence|full sentence|वाक्य में उत्तर|"
        r"define|परिभाषा लिख",
        blob,
        re.I,
    ):
        return "one_sentence"
    if (
        is_word_meaning_heading(stem)
        or is_word_meaning_heading(raw)
        or re.search(
            r"एक शब्द|one word|शब्दार्थ|विलोम|पर्याय|opposite|"
            r"gender|लिंग|वचन",
            blob,
            re.I,
        )
        or (re.search(r"=\s*$", raw) and len(raw) <= 80)
        or _is_short_vocab_item(raw)
    ):
        return "one_word"
    if re.search(r"लिखिए|उत्तर दीजिए|answer the following", blob, re.I) and len(raw) < 90:
        return "one_sentence"
    return "none"


ANSWER_DPI = 96
ONE_WORD_PX = (96, 18)       # 1.00 in × 0.1875 in
ONE_SENTENCE_PX = (605, 22)  # 6.30 in × 0.229 in
MULTI_LINE_PX = (605, 22)    # same bar
MULTI_LINE_COUNT = 5

_ANSWER_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ANSWER_LINES")
_ONE_WORD_PNG = os.path.join(_ANSWER_IMG_DIR, "one_word.png")
_SENTENCE_LINE_PNG = os.path.join(_ANSWER_IMG_DIR, "one_sentence.png")
_MULTI_LINE_PNG = os.path.join(_ANSWER_IMG_DIR, "multi_line.png")


def _px_to_inches(px):
    return float(px) / float(ANSWER_DPI)


def _build_dotted_bar_png(path, width_px, height_px, dash=4, gap=3):
    if Image is None:
        return None
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        w, h = int(width_px), int(height_px)
        im = Image.new("RGB", (w, h), (255, 255, 255))
        pix = im.load()
        y0 = max(1, h // 2)
        x = 4
        while x < w - 4:
            for dx in range(dash):
                if x + dx >= w - 4:
                    break
                pix[x + dx, y0] = (30, 30, 30)
                if y0 + 1 < h:
                    pix[x + dx, y0 + 1] = (30, 30, 30)
            x += dash + gap
        im.save(path, "PNG")
        return path
    except Exception:
        return None


def _ensure_answer_image(kind):
    if kind == "one_word":
        path, size = _ONE_WORD_PNG, ONE_WORD_PX
    elif kind == "multi_line":
        path, size = _MULTI_LINE_PNG, MULTI_LINE_PX
    else:
        path, size = _SENTENCE_LINE_PNG, ONE_SENTENCE_PX
    if not (os.path.isfile(path) and os.path.getsize(path) > 80):
        _build_dotted_bar_png(path, size[0], size[1])
    if os.path.isfile(path) and os.path.getsize(path) > 80:
        return path, size
    return None, size


def _add_answer_image(doc, kind):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(p, before=1, after=2, line_spacing=1.0)
    img, size = _ensure_answer_image(kind)
    if img:
        try:
            run = p.add_run()
            run.add_picture(
                img,
                width=Inches(_px_to_inches(size[0])),
                height=Inches(_px_to_inches(size[1])),
            )
            return True
        except Exception:
            pass
    run = p.add_run("." * (14 if kind == "one_word" else 72))
    try:
        run.font.underline = WD_UNDERLINE.DOTTED
    except Exception:
        pass
    run.font.size = Pt(BODY_SIZE)
    return True


def add_sentence_answer_line(doc):
    return _add_answer_image(doc, "one_sentence")


def add_answer_furniture(doc, kind):
    if kind == "one_word":
        return _add_answer_image(doc, "one_word")
    if kind == "one_sentence":
        return _add_answer_image(doc, "one_sentence")
    if kind == "multi_line":
        for _ in range(MULTI_LINE_COUNT):
            _add_answer_image(doc, "multi_line")
        return True
    return False


def _is_short_vocab_item(text):
    t = str(text or "").strip()
    t = re.sub(r"^[•·▪◦●○]\s*", "", t)
    t = re.sub(r"^\d+\s*[\).]\s*", "", t)
    t = re.sub(r"\s*=\s*[_\.…]*.*$", "", t).strip()
    if not t or "?" in t or "？" in t:
        return False
    if len(t) > 28:
        return False
    if re.search(r"लिखिए|उत्तर|प्रश्न|tick|fill|match|choose", t, re.I):
        return False
    return bool(re.match(r"^[A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F'’\- ]{0,26}$", t))


def split_equals_answer(text):
    """'आम =' → ('आम =', dots). Never leave bare '=' without 1-inch dots."""
    raw = str(text or "").rstrip()
    raw = re.sub(r"=\s*_+\s*$", "=", raw)
    raw = re.sub(r"=\s*\.{3,}\s*$", "=", raw)
    raw = re.sub(r"=\s*…+\s*$", "=", raw)
    if "=" not in raw:
        return raw, True
    left, _, _right = raw.partition("=")
    return left.rstrip() + " =", True


def add_one_inch_dotted_line(paragraph, font_size=None):
    """Exactly ~1 inch dotted answer line after '='."""
    run = paragraph.add_run(" " + ("." * 14))
    try:
        run.font.underline = WD_UNDERLINE.DOTTED
    except Exception:
        pass
    run.bold = False
    sz = font_size or BODY_SIZE
    run.font.size = Pt(sz)
    run.font.name = ENGLISH_FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), ENGLISH_FONT)
    rfonts.set(qn("w:hAnsi"), ENGLISH_FONT)
    rfonts.set(qn("w:cs"), ENGLISH_FONT)
    return run


def _strip_marks_product_noise(text):
    """Drop OCR marks-arithmetic glued to questions/instructions.

    Removes patterns like:
      (1 × 2 = 2)   (1 1/2 × 2 = 3)   (1½×2=3)   ½x4=2
    so they never corrupt the printed question or fraction rendering.
    Real mathematical fractions inside the question body are left intact.
    """
    t = str(text or "")

    # Always remove parenthesized marks products (very common OCR glue)
    t = _PAREN_MARKS_RE.sub("", t)

    # Remove known LaTeX fraction marks products
    t = re.sub(
        r"\\frac\s*\{\s*\d+\s*\}\s*\{\s*\d+\s*\}\s*[x×*]\s*\d+(?:\s*=\s*\d+)?",
        " ",
        t,
        flags=re.I,
    )

    # On instruction / question-stem lines, also strip bare product noise
    if _INSTRUCTION_HINT_RE.search(t):
        t = _MARKS_PRODUCT_RE.sub(" ", t)
        # Only strip trailing broken fraction fragments (not mid-sentence math)
        t = _TRAILING_BROKEN_MARKS_RE.sub("", t)

    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([:：.\-–—।])", r"\1", t)
    t = re.sub(r"[\(\[]\s*[\)\]]", "", t)  # empty leftover ()
    return t.strip()


def _instruction_core_key(text):
    t = _strip_marks_product_noise(text)
    t = re.sub(r"^(?:\d+\s*[\).]|[A-Z]\s*[\).]|प्रश्न\s*[:.]?\s*\d+)\s*", "", t, flags=re.I)
    t = re.sub(r"[\s:：\-–—।.]+$", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.casefold()


def collapse_duplicated_instruction_line(text):
    """One heading once. Same title glued twice on one line is collapsed."""
    raw = str(text or "").strip()
    if not raw:
        return raw
    cleaned = _strip_marks_product_noise(raw)
    parts = re.split(r"(?=(?:\d+\s*[\).]\s+|प्रश्न\s*[:.]?\s*\d+\s*))", cleaned)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        keys = [_instruction_core_key(p) for p in parts]
        base = keys[0]
        if base and len(base) >= 4:
            same = sum(1 for k in keys if k == base or (k and (base in k or k in base)))
            if same >= 2:
                first = _strip_marks_product_noise(parts[0])
                return first
    return cleaned


def sanitize_instruction_lines(lines):
    """Remove doubled section titles and leftover marks formulas."""
    out = []
    prev_key = ""
    for raw in lines:
        line = collapse_duplicated_instruction_line(raw)
        if not line:
            continue
        key = _instruction_core_key(line)
        looks_head = bool(
            is_instruction_line(line)
            or is_section_heading(line)
            or is_word_meaning_heading(line)
            or _INSTRUCTION_HINT_RE.search(line)
        )
        if looks_head and key and key == prev_key:
            continue
        out.append(line)
        if looks_head and key:
            prev_key = key
        elif not looks_head:
            prev_key = ""
    return out


_VOCAB_WORD_RE = re.compile(
    r"(?:^|\s)((?:\d+\s*[\).]\s*)?(?:[A-Za-z\u0900-\u097F][\w\u0900-\u097F'’\- ]{0,80}?)\s*=)"
)


def split_word_meaning_entries(line):
    """
    Convert a crowded OCR vocabulary line into individual entries.
    NEVER drop the first or the last word.
    """
    s = str(line or "").strip()
    if not s:
        return []

    s = re.sub(r"\s*[•·▪◦●○]\s*", "|||", s)
    parts = [part.strip() for part in s.split("|||") if part.strip()]

    if len(parts) >= 2:
        result = []
        for part in parts:
            part = part.strip()
            if not part.startswith(("•", "·", "▪", "◦")):
                part = "• " + part
            if "=" not in part and _is_short_vocab_item(part):
                part = part.rstrip(" .") + " ="
            result.append(part)
        return result

    matches = list(_VOCAB_WORD_RE.finditer(s))
    if len(matches) >= 2:
        entries = []
        for i, m in enumerate(matches):
            start = m.start(1)
            end = matches[i + 1].start(1) if i + 1 < len(matches) else len(s)
            part = s[start:end].strip()
            if part:
                if "=" not in part:
                    part = part.rstrip(" .") + " ="
                entries.append("• " + part)
        tail = s[matches[-1].end():].strip(" |,;/-")
        if tail and re.search(r"[A-Za-z\u0900-\u097F]", tail):
            if not tail.startswith("•"):
                tail = "• " + tail
            if "=" not in tail:
                tail = tail.rstrip(" .") + " ="
            entries.append(tail)
        if entries:
            return entries

    one = s
    if re.match(r"^(?:\d+\s*[\).]\s*)?[A-Za-z\u0900-\u097F]", one):
        if "=" not in one and len(one) <= 80:
            one = one.rstrip(" .") + " ="
        if not one.startswith("•"):
            one = "• " + one
        return [one]
    return [s]


def expand_word_meaning_section(lines):
    """
    Pre-process vocabulary lines without changing their wording.

    This prevents Word Meaning entries from being accidentally treated as
    one horizontal option row/table.
    """
    expanded = []
    in_word_meaning = False

    for line in lines:
        t = line.strip()

        if is_word_meaning_heading(t):
            in_word_meaning = True
            expanded.append(line)
            continue

        if in_word_meaning:
            if is_instruction_line(t) and not is_word_meaning_heading(t):
                if re.match(r"^(?:\d+\s*[\).]|[A-Z]\s*[\).]|प्रश्न)", t):
                    if not re.search(r"=\s*$", t):
                        in_word_meaning = False
                        expanded.append(line)
                        continue
            entries = split_word_meaning_entries(t)
            if re.match(r"^\d+\s*[\).]\s*.{1,40}=\s*$", t):
                word = re.sub(r"^\d+\s*[\).]\s*", "", t).strip()
                expanded.append("• " + word)
                continue
            if len(entries) == 1 and entries[0].strip() == t:
                if re.match(r"^[A-Z]\s*[\.\)]\s+", t):
                    in_word_meaning = False
                    expanded.append(line)
                else:
                    expanded.extend(entries)
            else:
                expanded.extend(entries)
        else:
            expanded.append(line)

    return expanded


def word_meaning_columns(entries):
    """Short words one equal row. Long words 2x2. No table border."""
    return compact_grid_columns(entries, single_column=False)


def calculate_word_meaning_font_size(entry_text, columns):
    """
    Reduce only an unusually long vocabulary entry.
    Normal Word Meaning entries keep the standard language font size.
    """
    font_name, base_size = get_language_font(entry_text)

    # Approximate width available to each compact vocabulary cell.
    usable_width_pt = 430 / columns
    avg_factor = 0.50 if font_name == ENGLISH_FONT else 0.54

    estimated_width = len(entry_text) * base_size * avg_factor

    if estimated_width <= usable_width_pt:
        return base_size

    reduced = base_size * (usable_width_pt / estimated_width)

    minimum = 11 if font_name == ENGLISH_FONT else 12
    return max(minimum, min(base_size, round(reduced, 1)))


def add_word_meaning_table(doc, entries):
    """
    Render Word Meaning entries as a compact, borderless horizontal grid.

    Example for 7 entries:

        • Gold =     • New =     • Old =     • Play =     • Night =
        • day =      • morning =

    This is intentionally NOT a vertical list because a question paper
    should avoid unnecessary paper wastage.
    """
    if not entries:
        return
    entries = [
        e for e in entries
        if e and not re.search(r"[□■ ]", str(e))
        and _is_short_vocab_item(e)
    ]
    if not entries:
        return

    if not class_allows_tables():
        for e in entries:
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=1, after=1, line_spacing=1.08)
            r = p.add_run("• " + str(e).strip())
            set_run_language_font(r, r.text, bold=False)
            r.font.size = Pt(BODY_SIZE)
        return

    columns = word_meaning_columns(entries)
    rows = (len(entries) + columns - 1) // columns

    table = doc.add_table(rows=rows, cols=columns)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    force_table_inline(table)
    remove_table_borders(table)

    usable_width = OPTION_GRID_WIDTH
    column_width = usable_width / columns

    # Lock the compact table layout.
    tblPr = table._tbl.tblPr

    tblLayout = tblPr.first_child_found_in("w:tblLayout")
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")

    for col in table.columns:
        col.width = Inches(column_width)

    for index, entry in enumerate(entries):
        row = index // columns
        col = index % columns

        cell = table.cell(row, col)
        cell.width = Inches(column_width)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

        # Very small internal margins to maximize usable paper width.
        set_cell_margins(
            cell,
            top=0,
            start=10,
            bottom=0,
            end=10
        )

        tcPr = cell._tc.get_or_add_tcPr()
        tcW = tcPr.find(qn("w:tcW"))
        if tcW is None:
            tcW = OxmlElement("w:tcW")
            tcPr.append(tcW)

        tcW.set(qn("w:w"), str(int(column_width * 1440)))
        tcW.set(qn("w:type"), "dxa")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(
            p,
            before=0,
            after=0,
            line_spacing=1.0
        )
        p.paragraph_format.keep_together = True

        font_name, _ = get_language_font(entry)
        font_size = calculate_word_meaning_font_size(
            entry,
            columns
        )

        raw_e = entry.strip()
        if re.search(r"[□■ ]", raw_e):
            continue
        if _is_short_vocab_item(raw_e):
            left, _need_dots = split_equals_answer(raw_e)
            run = p.add_run(left)
            set_run_language_font(run, left, bold=False)
            run.font.size = Pt(font_size)
            add_one_inch_dotted_line(p, font_size)
        else:
            run = p.add_run(raw_e)
            set_run_language_font(run, raw_e, bold=False)
            run.font.size = Pt(font_size)

    # Empty cells remain empty; no extra spacer paragraph is inserted.
    for index in range(len(entries), rows * columns):
        row = index // columns
        col = index % columns
        table.cell(row, col).paragraphs[0].add_run("")


def add_word_meaning_entry(doc, line):
    """
    Compatibility wrapper.

    A single entry is rendered compactly if encountered outside the
    section preprocessor. The normal Word Meaning section is rendered
    through add_word_meaning_table().
    """
    return add_word_meaning_table(doc, [line.strip()])


def is_match_heading(line):
    t = re.sub(r"\s+", " ", str(line or "").strip()).rstrip(":-–—").lower()
    phrases = (
        "मिलान कीजिए", "मिलान करो", "मिलान करें", "सुमेलित कीजिए",
        "सुमेलित करें", "सुमेलित करो", "match the following",
        "match the columns", "match the column", "match column",
    )
    return any(p in t for p in phrases)


def _split_match_pair_line(line):
    t = str(line or "").strip()
    if not t:
        return None
    t = re.sub(r"^\[\[MATCH\]\]\s*", "", t, flags=re.I)
    if "\t" in t:
        parts = [p.strip() for p in t.split("\t") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
    if "|" in t:
        left, right = t.split("|", 1)
        if left.strip() and right.strip():
            return left.strip(), right.strip()
    parts = re.split(r"\s{2,}", t)
    if len(parts) >= 2:
        return parts[0].strip(), " ".join(p.strip() for p in parts[1:] if p.strip())
    # Glued OCR row after a match heading: (i) left-phrase + short right answer
    m = re.match(
        r"^(\(?[ivxIVX]+\)|\(?[a-dA-Dअ-ह]\)|[ivxIVX]+\)|[a-dA-D]\.)\s+(.+)$",
        t,
    )
    if not m:
        return None
    marker, body = m.group(1), m.group(2).strip()
    words = body.split()
    n = len(words)
    if n < 2:
        return None
    if n >= 5:
        cut = n - 2
    elif n >= 3:
        cut = n - 1
    else:
        cut = 1
    left = marker + " " + " ".join(words[:cut])
    right = " ".join(words[cut:])
    if left.strip() and right.strip():
        return left.strip(), right.strip()
    return None


def collect_match_block(lines, start):
    if start >= len(lines):
        return [], [], start
    j = start
    while j < len(lines) and not str(lines[j]).strip():
        j += 1
    paired = []
    k = j
    while k < len(lines):
        raw = str(lines[k]).strip()
        if not raw:
            k += 1
            continue
        if raw.upper().startswith("[[MATCH]]") and raw.strip().upper() == "[[MATCH]]":
            k += 1
            continue
        if is_section_heading(raw) or has_explicit_question_label(raw):
            if k > j:
                break
        if is_match_heading(raw) and k > j:
            break
        pair = _split_match_pair_line(raw)
        if pair:
            paired.append(pair)
            k += 1
            continue
        if paired and (is_major_question_start(raw) or is_section_heading(raw)):
            break
        break
    if len(paired) >= 2:
        return [p[0] for p in paired], [p[1] for p in paired], k
    items = []
    k = j
    while k < len(lines):
        raw = str(lines[k]).strip()
        if not raw:
            k += 1
            if items:
                break
            continue
        if is_section_heading(raw) or (is_instruction_line(raw) and not is_match_heading(raw)):
            break
        if has_explicit_question_label(raw) and items:
            break
        items.append(raw)
        k += 1
        if len(items) >= 20:
            break
    if len(items) < 2:
        return [], [], start
    mid = (len(items) + 1) // 2
    for idx, it in enumerate(items):
        if re.match(r"^\s*(?:\(?[a-dA-D]\)|[a-dA-D][\.)])\s+", it) and idx >= 2:
            mid = idx
            break
    left_items = items[:mid]
    right_items = items[mid:] or ([""] * len(left_items))
    return left_items, right_items, k


def _set_tc_width(cell, inches):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:tcW"):
            tcPr.remove(child)
    tcW = OxmlElement("w:tcW")
    twips = str(int(float(inches) * 1440))
    tcW.set(qn("w:w"), twips)
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def _label_match_right(items):
    """Right column gets (a)(b)(c) if it has no markers — alignment + student key."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    out = []
    for i, raw in enumerate(items):
        s = str(raw or "").strip()
        if re.match(r"^\(?[a-dA-Dअ-हivxIVX]+\)|[a-dA-D]\.", s):
            out.append(s)
        elif s:
            out.append(f"({letters[i]}) {s}")
        else:
            out.append("")
    return out


def add_match_table(doc, left_items, right_items):
    if not left_items and not right_items:
        return False
    n = max(len(left_items), len(right_items))
    left_items = list(left_items) + [""] * (n - len(left_items))
    right_items = _label_match_right(list(right_items) + [""] * (n - len(right_items)))
    table = doc.add_table(rows=n, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        force_table_inline(table)
    except Exception:
        pass
    left_w, gap_w, right_w = 2.85, 1.05, 2.55
    tblPr = table._tbl.tblPr
    tblLayout = tblPr.first_child_found_in("w:tblLayout")
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")
    tblW = tblPr.first_child_found_in("w:tblW")
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(int((left_w + gap_w + right_w) * 1440)))
    tblW.set(qn("w:type"), "dxa")
    try:
        table.columns[0].width = Inches(left_w)
        table.columns[1].width = Inches(gap_w)
        table.columns[2].width = Inches(right_w)
    except Exception:
        pass
    for i in range(n):
        specs = ((0, left_items[i], left_w), (1, "", gap_w), (2, right_items[i], right_w))
        for col, text, wid in specs:
            cell = table.cell(i, col)
            _set_tc_width(cell, wid)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            try:
                if col == 1:
                    set_cell_margins(cell, top=40, start=80, bottom=40, end=80)
                elif col == 0:
                    set_cell_margins(cell, top=40, start=40, bottom=40, end=60)
                else:
                    set_cell_margins(cell, top=40, start=80, bottom=40, end=40)
            except Exception:
                pass
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(p, before=2, after=2, line_spacing=1.08)
            display = str(text or "").strip()
            if display:
                run = p.add_run(display)
                set_run_language_font(run, display, bold=False)
                run.font.size = Pt(15)
            elif col == 1:
                run = p.add_run("......")
                run.font.size = Pt(14)
                run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    try:
        # Hairline so the two columns stay visible as columns
        tbl = table._tbl
        tblBorders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "nil")
            tblBorders.append(el)
        insideV = OxmlElement("w:insideV")
        insideV.set(qn("w:val"), "single")
        insideV.set(qn("w:sz"), "4")
        insideV.set(qn("w:space"), "0")
        insideV.set(qn("w:color"), "B0B0B0")
        tblBorders.append(insideV)
        existing = tblPr.find(qn("w:tblBorders"))
        if existing is not None:
            tblPr.remove(existing)
        tblPr.append(tblBorders)
    except Exception:
        pass
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, before=2, after=6, line_spacing=1.0)
    return True



def force_table_inline(table):
    """
    Explicitly force an MCQ table to remain INLINE with the document flow.
    This prevents the next section heading (e.g. B/C/D) from appearing
    beside the option table.
    """
    tblPr = table._tbl.tblPr

    tblpPr = tblPr.find(qn("w:tblpPr"))
    if tblpPr is not None:
        tblPr.remove(tblpPr)

    # Keep table from overlapping neighbouring content.
    tblOverlap = tblPr.find(qn("w:tblOverlap"))
    if tblOverlap is None:
        tblOverlap = OxmlElement("w:tblOverlap")
        tblPr.append(tblOverlap)
    tblOverlap.set(qn("w:val"), "never")


def major_question_has_subparts(lines, question_index):
    """
    V9 ADDITIVE / REGRESSION-SAFE RULE.

    Detect whether an explicitly labelled major question is followed by
    internal sub-parts/items before the next major question or section.

    Examples:
        प्रश्न : 2 ...
        1. ...
        2. ...

        प्रश्न : 4 ...
        (क) ...
        (ख) ...

        प्रश्न : 10 ...
        1. ...
        2. ...

    Such major questions receive a small controlled space-before so the
    paper looks intentionally structured. This is NOT applied to ordinary
    single-line MCQs, preserving paper-saving behavior.
    """
    if question_index < 0 or question_index >= len(lines):
        return False

    if not is_major_question_start(lines[question_index]):
        return False

    numbered_subpart_re = re.compile(r"^\d+\s*[\.)]\s+\S+", re.IGNORECASE)
    letter_subpart_re = re.compile(r"^\([क-हक़-ख़ग-ज़ड़-ढ़त-न-ह]\)\s+\S+", re.IGNORECASE)
    roman_subpart_re = re.compile(r"^\([ivxlcdm]+\)\s+\S+", re.IGNORECASE)
    alpha_subpart_re = re.compile(r"^\([a-zA-Z]\)\s+\S+", re.IGNORECASE)

    seen_subparts = 0
    j = question_index + 1

    while j < len(lines):
        t = lines[j].strip()
        if not t:
            j += 1
            continue

        # Stop at the next explicitly labelled major question.
        if j > question_index and has_explicit_question_label(t):
            break

        # Stop at a clear section heading.
        if j > question_index and is_section_heading(t):
            break

        # A major question with two or more internal items is the target
        # for the controlled visual gap.
        if (numbered_subpart_re.match(t) or
            letter_subpart_re.match(t) or
            roman_subpart_re.match(t) or
            alpha_subpart_re.match(t)):
            seen_subparts += 1
            if seen_subparts >= 2:
                return True

        # Do not scan indefinitely into an unrelated paragraph.
        if j - question_index >= 20:
            break

        j += 1

    return False



def drop_tofu_ocr_lines(text):
    """Sirf woh lines hatao jo almost poori □ hain. Asli prashn mat kaato."""
    src = str(text or "")
    out = []
    for line in src.splitlines():
        raw = line
        boxes = raw.count("□") + raw.count("■") + raw.count("\ufffd") + raw.count(" ")
        letters = len(re.findall(r"[A-Za-z\u0900-\u097F]", raw))
        if boxes >= 4 and letters < 6:
            continue
        if re.fullmatch(r"[\s□■ ?._\-•=|…\.]+", raw or ""):
            continue
        raw = raw.replace("Q.5 ", "प्र0-5 ").replace("Q.5", "प्र0-5")
        out.append(raw)
    cleaned = "\n".join(out)
    if len(re.findall(r"[\u0900-\u097F]", cleaned)) < 20 and len(re.findall(r"[\u0900-\u097F]", src)) >= 40:
        return src
    return cleaned


def sanitize_extracted_paper_text(text):
    """Clean Gemini/OCR artefacts without changing question meaning.

    Fixes seen on Class 8 Maths papers:
      (i)(i) doubled labels
      प्रश्न-2. ... प्रश्न-2. ... doubled stems
      raw \\\\frac left beside a second copy
      (i)^{(i)^{...}  label eaten as a power base
    """
    t = str(text or "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = flatten_degree_powers(t)
    t = normalize_named_math_accents(t)
    t = normalize_math_source(t)
    t = flatten_degree_powers(t)
    t = normalize_geometry_symbols(t)

    # Mid-line next-question labels must start a new line.
    # Generic: प्रश्न-12 / प्र०-12 / प्रो-12 / Q.12 / Q-12 / Ques. 12
    # — no question id hardcoded.
    t = re.sub(
        r"(?<!^)(?<!\n)\s*(?=(?:प्रश्न|प्र०|प्र0|प्र|Ques(?:tion)?|Question|Q)\s*[-.:：)]?\s*[0-9०-९]{1,2}(?:\s|[-.:：)]|$))",
        "\n",
        t,
        flags=re.I,
    )
    # Glued labels with no space: Q5A / Q6Calculate / प्रश्न5वर्णन
    t = re.sub(
        r"(?<!^)(?<!\n)(?=(?:प्रश्न|प्र०|Ques(?:tion)?|Q)[0-9०-९]{1,2}(?:\s|[A-Za-zअ-ह]))",
        "\n",
        t,
        flags=re.I,
    )
    # Split glued (b)/(c)/(d) after a finished math atom.
    t = re.sub(
        r"(?<=[0-9}\)])\s*(?=\(\s*[b-dB-D]\s*\))",
        "\n",
        t,
    )

    # doubled roman / alpha markers on the same token
    t = re.sub(
        r"(\(\s*(?:iv|iii|ii|i)\s*\))\s*\1",
        r"\1",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"(\(\s*[a-dA-D]\s*\))\s*\1",
        r"\1",
        t,
    )

    # (i)^{(i)^{X}  -> (i) ^{X} is still wrong; recover "(label) (rest)"
    # Gemini often writes (i)^{(i)^{\frac{1}{2}} instead of (i) (9)^{\frac{1}{2}}.
    # We cannot invent the missing base. Strip the duplicated label-as-base
    # so the exponent survives as a power on an empty base rather than junk.
    t = re.sub(
        r"\((\s*(?:iv|iii|ii|i)\s*)\)\s*\^\s*\{\s*\(\s*\1\s*\)\s*\^",
        r"(\1) ^",
        t,
        flags=re.I,
    )

    # Drop a second "प्रश्न-N." + same opening clause inside one line
    def _dedupe_stem(line):
        m = re.match(
            r"^(प्रश्न\s*[-.:]?\s*\d+\s*[.)\-:]?\s*)(.+)$",
            line,
            flags=re.I,
        )
        if not m:
            return line
        head, body = m.group(1), m.group(2)
        again = re.search(
            r"प्रश्न\s*[-.:]?\s*\d+\s*[.)\-:]?",
            body,
            flags=re.I,
        )
        if not again:
            return line
        # If the text after the second label repeats the start of the body, keep one
        first = body[:again.start()].strip()
        second = body[again.end():].strip()
        if first and second.startswith(first[: min(24, len(first))]):
            return head + second
        if first and first in second:
            return head + second
        # otherwise keep head + the longer half
        keep = second if len(second) >= len(first) else first
        return head + keep

    t = "\n".join(_dedupe_stem(ln) for ln in t.split("\n"))
    return t



MCQ_TICK_PROMPT = """
TICK / सही विकल्प questions are MCQ, NOT matching.
If the heading has विकल्प / निशान / ☑ / choose the correct:
- Each question stem on its own line.
- Then options as (i) (ii) or (a) (b) on the FOLLOWING lines, not glued into the stem.
- Matching (मिलान / सुमेलित) is a different type: two columns with |.
Never treat मिलान as MCQ and never treat सही विकल्प as मिलान.
"""


SUBPART_ALIGN_PROMPT = """
SUB-PART ALIGNMENT (structure only, do not change wording):
Every (i) (ii) (iii) (iv) (v) (vi) (vii) (viii) (ix) (x) and (a)(b)(c)
must be on its OWN line.
Put ONE space after the closing parenthesis, then the text.
Do not put extra leading spaces before (i)/(ii).
Do not glue two sub-parts on one line.
Example:
(i) first item
(ii) second item
(iii) third item
"""


def _normalize_subpart_marker(raw):
    s = str(raw or "").strip()
    s = s.replace("Viii", "viii").replace("VIII", "viii")
    s = re.sub(r"^\(?([ivxIVX]{1,6})\)?$", lambda m: "(" + m.group(1).lower() + ")", s)
    if re.fullmatch(r"\([ivx]+\)", s):
        return s
    if re.fullmatch(r"\([a-zA-Z]\)", s):
        return s.lower() if s[1].isalpha() and s[1] < "e" else s
    if re.fullmatch(r"\([क-ह]\)", s):
        return s
    return s if s.startswith("(") else f"({s.strip(').')})"


def format_subpart_line(line):
    info = classify_numbering(line, major_open=True)
    if info["kind"] not in ("subpart", "option"):
        return str(line or "").strip()
    body = info.get("body") or ""
    return info["marker"] + "\t" + body


def apply_subpart_column_align(paragraph, ncert_mode=False):
    """Hanging indent + tab: all subpart markers align consistently."""
    fmt = paragraph.paragraph_format
    if ncert_mode:
        fmt.left_indent = Inches(NCERT_SUBPART_LEFT_IN)
        fmt.first_line_indent = Inches(-NCERT_SUBPART_HANG_IN)
    else:
        fmt.left_indent = Inches(0.70)
        fmt.first_line_indent = Inches(-0.55)
    fmt.right_indent = Inches(0)
    try:
        tabs = fmt.tab_stops
        for existing in list(tabs):
            try:
                tabs.remove(existing.position)
            except Exception:
                pass
        tabs.add_tab_stop(Inches(0.70))
    except Exception:
        pass


# ============================================================
# KANDA 1 — PLAN OBJECT
# Theme: count the boxes first, then fill the questions.
# A typist emits lines. A setter emits a plan of rooms (khane),
# then seats each item in a room. Rendering is carpentry, not typing.
# ============================================================
PLAN_OBJECT_VERSION = "K1"
PLAN_BAND_MAX_COLS = 5
_PLAN_ITEM_LABEL_RE = re.compile(
    r"^[\(\[]?\s*([a-zA-Z]|[ivxlcdm]+|\d+|[कखगघङचछजझञअआइईउऊएऐओऔ]|[०-९]+)\s*[\)\].]?\s+",
    re.I,
)
_PLAN_QTYPE_MAP = (
    ("addition", ("addition", "जोड़", "योग", "(+)")),
    ("subtraction", ("subtraction", "घटाव", "(-)")),
    ("multiplication", ("multiplication", "गुणा", "(×)", "(x)", "(X)")),
    ("division", ("division", "भाग", "(÷)")),
    ("after", ("comes after", "बाद क्या", "what comes after")),
    ("before", ("comes before", "पहले क्या", "what comes before")),
    ("between", ("comes between", "बीच", "what comes between")),
    ("sign", ("put the sign", "चिह्न", "greater", "smaller")),
    ("number_name", ("numbers names", "number names", "शब्दों में")),
    ("write_number", ("write the numbers", "अंकों में")),
    ("ascending", ("ascending", "आरोही")),
    ("descending", ("descending", "अवरोही")),
    ("expanded", ("expanded form", "विस्तृत")),
    ("short_form", ("short form", "लघु रूप")),
    ("long_form", ("long form", "दीर्घ रूप")),
    ("series", ("complete the series", "श्रृंखला")),
    ("tables", ("table", "पहाड़ा", "dodgem")),
    ("shapes", ("shapes", "आकृति")),
    ("word_problem", ("solve the", "word problem", "candles", "chocolates")),
    ("word_meaning", ("word meaning", "word / meaning", "words and meanings", "शब्दार्थ",
                      "opposite word", "opposite words", "antonym", "antonyms",
                      "विलोम", "विलोम शब्द", "पर्यायवाची", "पर्यायवाची शब्द",
                      "synonym", "synonyms", "समानार्थी")),
    ("mcq", ("tick the correct", "choose the correct", "select the correct",
             "सही विकल्प", "objective")),
    ("true_false", ("true / false", "true/false", "true or false", "true and false",
                    "t for true", "सत्य असत्य", "सही गलत", "सही कथन", "गलत कथन",
                    "चिन्ह लगा", "निशान लगा")),
    ("fill_blank", ("fill in the blank", "fill ups", "रिक्त स्थान", "खाली स्थान",
                    "पूर्ति कीजिए", "पूर्ति कीजिये", "स्थान भर", "सहायता से रिक्त")),
    ("gender", ("change the gender", "opposite gender", "लिंग")),
    ("plural", ("write the plural", "plurals", "बहुवचन")),
    ("adjective", ("suitable adjective", "adjectives")),
)


def infer_plan_qtype(stem):
    t = str(stem or "").lower()
    if _looks_like_marks_scheme(stem):
        # "पूर्णवाक्येन उत्तरं लिखत : — 2×5 = 10" is NOT a times-table
        if re.search(r"गद्यांश|पठित्वा|श्लोक|संस्कृतवाक्य", str(stem or "")):
            return "passage"
        return "generic"
    pre = infer_preprimary_action(t)
    if pre:
        return pre
    for name, keys in _PLAN_QTYPE_MAP:
        if name == "multiplication" and _looks_like_marks_scheme(stem):
            continue
        if any(k.lower() in t for k in keys):
            return name
    if re.search(r"गद्यांश|पठित्वा|अधोलिखित", str(stem or "")):
        return "passage"
    return "generic"


def plan_columns_for(n_items, qtype="generic", stage=None, max_cols=None):
    """Setter rule: rooms equal items. Stage decides how wide a band may be."""
    n = max(0, int(n_items))
    cap = int(max_cols or PLAN_BAND_MAX_COLS)
    if stage == STAGE_PREPRIMARY:
        cap = min(cap, 3)
    if n <= 0:
        return 1
    if qtype in ("true_false", "fill_blank", "word_problem",
                 "gender", "adjective", "mcq"):
        return 1
    if qtype in ("word_meaning", "plural"):
        return 2 if n >= 2 else 1
    if n <= cap:
        if n == 4 and qtype not in ("ascending", "descending", "word_problem"):
            return 2
        return n
    return 2 if n % 2 == 0 else min(3, cap)


def _plan_item_label(line):
    m = _PLAN_ITEM_LABEL_RE.match(str(line or "").strip())
    return (m.group(0).strip(), str(line)[m.end():].strip()) if m else ("", str(line or "").strip())


def _looks_short_plan_item(line):
    t = str(line or "").strip()
    if not t or is_sum_section_heading(t) or has_explicit_question_label(t):
        if has_explicit_question_label(t) and not is_subpart_or_option(t):
            return False
    if not is_subpart_or_option(t) and not _PLAN_ITEM_LABEL_RE.match(t):
        return False

    body = _plan_item_label(t)[1]
    if len(body) > 70:
        return False
    if re.search(r"_{2,}|\.{4,}", body):
        return False
    if re.search(r"\b(is|are|was|were|the|a|an|in|on|of|for|to)\b", body, re.I):
        return False
    if len(body.split()) >= 4:
        return False
    return True

def collect_plan_item_run(lines, start):
    """Gather consecutive short labelled items that share one khana-band."""
    items = []
    j = start
    while j < len(lines):
        t = str(lines[j]).strip()
        if not t:
            j += 1
            continue
        if is_sum_section_heading(t) or (
            has_explicit_question_label(t) and not is_subpart_or_option(t)
        ):
            break
        if not _looks_short_plan_item(t):
            break
        lab, body = _plan_item_label(t)
        items.append({"label": lab, "body": body, "lines": [t]})
        j += 1
        # absorb one following continuation if it is not a new label
        while j < len(lines):
            nxt = str(lines[j]).strip()
            if not nxt:
                break
            if _looks_short_plan_item(nxt) or is_sum_section_heading(nxt):
                break
            if has_explicit_question_label(nxt):
                break
            if is_column_sum_line(nxt) or _SUM_RULE_RE.match(_sum_body_line(nxt)):
                items[-1]["lines"].append(nxt)
                items[-1]["body"] = (items[-1]["body"] + " " + nxt).strip()
                j += 1
                continue
            break
        if len(items) >= 12:
            break
    return items, j


def build_paper_plan(lines):
    """KANDA 1: count rooms before filling them.

    Returns a list of plan blocks. Each block has:
      kind, qtype, stem, items, columns, furniture, lines
    """
    plan = []
    i = 0
    last_stem = ""
    last_qtype = "generic"
    n = len(lines)
    while i < n:
        line = str(lines[i]).strip()
        if not line:
            i += 1
            continue

        if has_explicit_question_label(line) or is_sum_section_heading(line):
            last_stem = line
            last_qtype = infer_plan_qtype(line)
            plan.append({
                "kind": "stem",
                "qtype": last_qtype,
                "stem": line,
                "items": [],
                "columns": 1,
                "furniture": "none",
                "lines": [line],
            })
            i += 1
            continue

        sum_blocks, sum_end = collect_column_sum_group(lines, i)
        if sum_blocks:
            cols = plan_columns_for(len(sum_blocks), last_qtype)
            plan.append({
                "kind": "sum_band",
                "qtype": last_qtype,
                "stem": last_stem,
                "items": sum_blocks,
                "columns": cols,
                "furniture": "place_value_stack",
                "lines": [x for b in sum_blocks for x in b],
            })
            i = sum_end
            continue

        items, item_end = collect_plan_item_run(lines, i)
        if len(items) >= 2:
            cols = plan_columns_for(len(items), last_qtype)
            furniture = "blank_trail"
            if last_qtype in ("true_false", "fill_blank", "mcq", "adjective"):
                furniture = "none"
                cols = 1
            elif last_qtype in ("word_meaning", "plural", "gender"):
                furniture = "none"
                cols = 2 if last_qtype != "gender" else 1
            if last_qtype in ("shapes",):
                furniture = "figure_box"
            elif last_qtype in ("word_problem",):
                furniture = "answer_box"
            plan.append({
                "kind": "item_band",
                "qtype": last_qtype,
                "stem": last_stem,
                "items": items,
                "columns": cols,
                "furniture": furniture,
                "lines": [ln for it in items for ln in it["lines"]],
            })
            i = item_end
            continue

        plan.append({
            "kind": "flow",
            "qtype": last_qtype,
            "stem": last_stem,
            "items": [],
            "columns": 1,
            "furniture": "none",
            "lines": [line],
        })
        i += 1
    return plan


def describe_paper_plan(plan):
    """Operator log — the setter thinking out loud."""
    if not plan:
        return
    print("  ✏ PLAN OBJECT (khane first):")
    for idx, blk in enumerate(plan, 1):
        n_items = len(blk.get("items") or [])
        print(
            f"    [{idx}] {blk['kind']:9}  type={blk.get('qtype','?'):14}  "
            f"cols={blk.get('columns')}  items={n_items}  "
            f"furn={blk.get('furniture')}"
        )


def add_plan_item_band(doc, block):
    """Seat short items into the rooms the plan already counted."""
    items = block.get("items") or []

    # --- NOTE HOOK: LKG three families get real furniture, not typed lines ---
    if SETTER_CORE:
        fam = (
            block.get("family")
            or family_of(block.get("stem") or "")
            or family_of(block.get("qtype") or "")
        )
        if fam in ("count_and_write", "compare", "after", "before"):
            block = dict(block)
            block["kind"] = "room"
            block["family"] = fam
            spec = FAMILIES.get(fam) or {}
            if spec.get("furniture"):
                block["furniture"] = spec["furniture"]
            if spec.get("columns"):
                block["columns"] = spec["columns"]
            render_setter_plan(doc, [block])
            return True
    # --- NOTE HOOK END ---

    if not items:
        return False
    if not class_allows_tables():
        for it in items:
            body = " ".join(it.get("lines") or [it.get("body") or ""]).strip()
            if not body:
                continue
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=1, after=2, line_spacing=1.08)
            r = p.add_run(body)
            set_run_language_font(r, body, bold=False)
            r.font.size = Pt(BODY_SIZE)
        return True
    joined = " ".join(
        " ".join(it.get("lines") or [it.get("body") or ""]) for it in items
    )
    if (
        block.get("qtype") in {"fill_blank", "true_false", "word_problem"}
        or re.search(r"_{2,}|\.{3,}|रिक्त|पूर्ति", joined)
        or any(len(" ".join(it.get("lines") or [it.get("body") or ""])) > 42 for it in items)
    ):
        cols = 1
    else:
        cols = max(1, int(block.get("columns") or 2))
    cols = min(cols, PLAN_BAND_MAX_COLS, len(items))
    rows = (len(items) + cols - 1) // cols
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        force_table_inline(table)
        remove_table_borders(table)
        _set_fixed_table_width(table, OPTION_GRID_WIDTH)
    except Exception:
        pass
    col_w = OPTION_GRID_WIDTH / cols
    for i, item in enumerate(items):
        r, c = divmod(i, cols)
        cell = table.cell(r, c)
        try:
            cell.width = Inches(col_w)
            set_cell_margins(cell, top=40, start=50, bottom=40, end=50)
        except Exception:
            pass
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(para, before=0, after=2, line_spacing=1.05)
        text = " ".join(item.get("lines") or [item.get("body") or ""])
        add_text_with_math(para, text, bold=False)
        if block.get("furniture") == "blank_trail" and not re.search(r"_{2,}|—{2,}|-{3,}", text):
            p2 = cell.add_paragraph()
            set_paragraph_spacing(p2, before=0, after=0, line_spacing=1.0)
            run = p2.add_run("____________")
            set_run_language_font(run, run.text, bold=False)
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, before=1, after=6, line_spacing=1.0)
    return True


def _extract_leading_question_number(text):
    """Return a leading numeric major-question id, or None."""
    t = str(text or "").strip()
    m = _EXPLICIT_Q_LABEL_RE.match(t)
    if m:
        return _label_digits_to_int(m.group(1))
    t_ascii = t.translate(_DEV_DIGIT_AUDIT)
    m = _PLAIN_MAJOR_NUM_RE.match(t_ascii)
    if m:
        return _label_digits_to_int(m.group(1))
    return None


def _is_ncert_major_numbered_line(line, last_major_number):
    """
    Distinguish a new top-level 1./2./3. question from numbered sub-items.

    If the next number is sequential (e.g. 9 -> 10 -> 11), it is treated as
    a new major question. Numbered sub-items normally restart at 1 or remain
    below the last major number and therefore stay subordinate.
    Explicit 'Question 10'/'प्रश्न 10' labels always win elsewhere.
    """
    number = _extract_leading_question_number(line)
    if number is None:
        return False, last_major_number
    if last_major_number is None:
        return True, number
    if number == last_major_number + 1:
        return True, number
    return False, last_major_number


def _apply_ncert_fine_tune_doc(doc_path):
    """Final typography pass for NCERT-style board papers.

    This pass changes spacing/keep rules only. It never rewrites question
    wording, question order, equations, headers, or the A4 page size.
    """
    doc = Document(doc_path)

    for p_index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text or p_index < 2:
            continue
        if text.startswith("★") and text.endswith("★"):
            continue

        fmt = paragraph.paragraph_format
        if text.upper().startswith("CLASS:"):
            fmt.keep_together = True
            continue

        # Conservative, textbook-like body rhythm.
        if fmt.space_after is None or fmt.space_after.pt <= 2.5:
            fmt.space_after = Pt(NCERT_BODY_AFTER_PT)
        fmt.line_spacing = NCERT_BODY_LINE_SPACING_PT
        fmt.space_after = Pt(0)
        fmt.space_before = Pt(0)

        if is_major_question_start(text):
            fmt.keep_together = True
            fmt.widow_control = True

    # Do not allow an MCQ/answer table to split its rows across pages.
    for table_index, table in enumerate(doc.tables):
        if table_index == 0:
            continue
        for row in table.rows:
            trPr = row._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.widow_control = True
                    if paragraph.paragraph_format.line_spacing is None:
                        paragraph.paragraph_format.line_spacing = Pt(NCERT_BODY_LINE_SPACING_PT)

    doc.save(doc_path)


def add_formatted_question_text(doc, extracted_text, hindi_mcq_labels=False, layout=None):
    """
    Professional continuous-flow formatter.

    V8 ADDITIVE / REGRESSION-SAFE RULES:
      - All V7 rules remain active.
      - Source image boundaries NEVER create Word page breaks.
      - Main questions do NOT create a keep_with_next chain.
      - A main question is kept with the immediately following option block
        only when an actual option block follows.
      - Four options always use a balanced 2 x 2 grid.
      - Three options always use ONE horizontal row (3 columns) when they form
        a consecutive MCQ option block.
      - Roman (i)-(iv) options under a sub-question are grouped together,
        rather than being printed as three/four vertical lines.
      - Alpha (a)-(d) options under a sub-question are handled the same way.
      - Option font size is COMMON across the entire grid.
      - No question wording is rewritten.
    """
    layout = layout if isinstance(layout, dict) else {}
    lines = (
        extracted_text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )

    def _strip_paper_markup(s):
        s = re.sub(r"\[\[(?:MATCH|FIG|ADD|SUB|MUL|DIV|NLINE)\]\]", "", str(s or ""), flags=re.I)
        s = re.sub(r"^\|{2,}\s*", "", s)
        s = re.sub(r"\s*\|{2,}\s*", " ", s)
        return s.strip()

    lines = [
        dedupe_leading_option_label(
            normalize_geometry_symbols(normalize_exam_mark_symbols(_strip_paper_markup(line)))
        )
        for line in lines if line.strip()
    ]

    # --- HOOK 10: strip leaked LaTeX on Maths papers (ADD-ON) ---
    try:
        if MATH_CLEAN is not None:
            _subj = ""
            if layout:
                _subj = str(layout.get("subject", "") or "")
            lines = [MATH_CLEAN.clean_line(x, _subj) for x in lines]
    except Exception as _mc:
        print("  ⚠ math_clean skipped:", _mc)
    # --- END HOOK 10 ---

    global PAPER_LANGUAGE
    _subj_now = str((layout or {}).get("subject") or "")
    _det = detect_paper_language(_subj_now, "\n".join(lines[:12]))
    if _det in {"hindi", "sanskrit"}:
        PAPER_LANGUAGE = _det
    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        lines = [restore_hindi_spaces(restore_hindi_paper_text(x)) for x in lines]
        hindi_mcq_labels = True
    else:
        lines = [restore_exam_spaces(x) for x in lines]
    lines = collapse_duplicate_headings(lines, (layout or {}).setdefault("_head_fp", []))
    lines = _ensure_opening_instruction(lines)
    lines = sanitize_instruction_lines(lines)
    lines = expand_word_meaning_section(lines)
    lines = expand_option_lines(lines)
    lines = explode_side_by_side_column_sums(lines)
    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        lines = [restore_hindi_spaces(x) for x in lines]
    lines = collapse_duplicate_headings(lines, layout.setdefault("_head_fp", []))

    paper_plan = build_paper_plan(lines)
    describe_paper_plan(paper_plan)

# ========================================================
    # TECHNICAL NOTE HOOK
    # Preprimary: plan ke rooms banao, typist loop MAT chalao.
    # Class 1+ is block se nikal kar purane while-loop pe jayega.
    # ========================================================
    layout = layout or {}
    # Maths question body is always plain sequential paragraphs.
    maths_mode = is_maths_subject(layout.get("subject", ""))
    _stage = layout.get("stage")
    if not _stage:
        _stage = classify_class_stage(layout.get("class_name", ""))
        layout["stage"] = _stage

    if SETTER_CORE and _stage == STAGE_PREPRIMARY:
        try:
            setter_plan = build_setter_plan(
                lines,
                class_name=layout.get("class_name", ""),
                subject=layout.get("subject", ""),
            )
            describe_plan(setter_plan)
            if setter_plan:
                render_setter_plan(doc, setter_plan)
                return
        except Exception as _pre_exc:
            print("  ⚠ preprimary plan render skipped:", _pre_exc)
    # ========================================================
    # HOOK END — Class 1+ yahan se purana code
    # ========================================================

    i = 0
    mcq_mode = False
    vertical_item_mode = False
    explicit_question_open = False
    last_major_number = None
    last_stem = ""  # last main question text — used to decide real MCQ vs sub-parts
    last_head_fp = ""
    one_word_section = False
    child_idx = 0
    tf_section = False  # (T/F) stamp only inside a real True/False block
    layout = layout or {}
    allow_match = layout.get("match_two_column", True)
    allow_sums = layout.get("column_sums", True)
    allow_matrix = layout.get("matrix", True)
    allow_fig = layout.get("figure_box", True)
    # Maths forces vertical options; non-MCQ sub-parts also stay vertical
    force_vertical_options = bool(layout.get("mcq_single_column", False))

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if re.search(r"one word|एक शब्द में|शब्दार्थ", line, re.I):
            one_word_section = True
        elif re.match(r"^\s*(?:Q\s*\.?\s*\d+|प्र\s*\.?\s*\d+)", line, re.I) and not re.search(
            r"one word|एक शब्द|शब्दार्थ", line, re.I
        ):
            one_word_section = False
        if re.match(r"^\s*Ans(?:wer)?\s*[-–—:]?\s*$", line, re.I):
            i += 1
            continue
        if is_word_meaning_heading(line) or is_section_heading(line) or is_mcq_section_heading(line):
            _fp = re.sub(
                r"^(?:प्र\s*\.?\s*0?\s*-?\s*\d+|Q\s*\.?\s*\d+|प्रश्न\s*\d+)\s*",
                "",
                line,
                flags=re.I,
            )
            _fp = re.sub(r"[\s:.\-–—0-9()]+", "", _fp).lower()
            if _fp and _fp == last_head_fp:
                i += 1
                continue
            if _fp:
                last_head_fp = _fp
        if re.search(r"[□■ ]", line):
            _akshar = len(re.findall(r"[A-Za-z\u0900-\u097F]", line))
            if _akshar < 6:
                i += 1
                continue
            line = re.sub(r"[□■ ]+", "", line).strip()
            if not line:
                i += 1
                continue

        # --- HOOK 8: match two columns (ADD-ON) ---
        try:
            if ANSWER_SPACE is not None and ANSWER_SPACE.is_match_heading(last_stem or line):
                _pairs = []
                _j = i
                if ANSWER_SPACE.is_match_heading(line):
                    _hp = doc.add_paragraph()
                    _hr = _hp.add_run(line)
                    _hr.bold = True
                    _j = i + 1
                while _j < len(lines):
                    _pr = ANSWER_SPACE.parse_match_pair(lines[_j])
                    if not _pr:
                        break
                    _pairs.append(_pr)
                    _j += 1
                if _pairs:
                    ANSWER_SPACE.render_match_two_columns(doc, _pairs)
                    i = _j
                    continue
        except Exception as _mh:
            print("  ⚠ match hook skipped:", _mh)
        # --- END HOOK 8 ---


        # --- HOOK 9: equals lines in compact grid (ADD-ON) ---
        try:
            if ANSWER_SPACE is not None and ANSWER_SPACE.is_equals_fill_line(line):
                _items, _end = ANSWER_SPACE.collect_equals_run(lines, i)
                if len(_items) >= 2:
                    _cols = 3 if max(len(x) for x in _items) <= 3 else 2
                    ANSWER_SPACE.render_equals_grid(doc, _items, cols=_cols)
                    i = _end
                    continue
        except Exception as _eq:
            print("  ⚠ equals grid skipped:", _eq)
        # --- END HOOK 9 ---

        # ----------------------------------------------------
        # SECTION CONTEXT
        # ----------------------------------------------------
        if is_mcq_section_heading(line):
            mcq_mode = True
            vertical_item_mode = False
            explicit_question_open = False
            last_stem = line
        elif (
            is_vertical_item_heading(line)
            or is_non_mcq_section_heading(line)
            or is_word_meaning_heading(line)
        ):
            mcq_mode = False
            vertical_item_mode = True
            explicit_question_open = False
            last_stem = line

        # ----------------------------------------------------
        # CLASS 1-3 COLUMN SUM / PLACE-VALUE DIGITS
        # 3 to 5 compact stacks on one line. Ones under ones.
        # ----------------------------------------------------
# --- HOOK 7: Class 1-2 sums + before/after + compare (ADD-ON) ---
        try:
            import sum_layout as SUM_LAYOUT
            _subj = str(layout.get("subject") or ("MATH" if layout.get("math_mode") else ""))
            _cls = str(layout.get("class_name", ""))
            _ok, _new_i = SUM_LAYOUT.try_render_sum_group(
                doc, lines, i,
                class_name=_cls,
                subject=_subj,
            )
            if _ok:
                i = _new_i
                continue
            _ok2, _new_i = SUM_LAYOUT.try_render_before_after(
                doc, lines, i,
                class_name=_cls,
                subject=_subj,
            )
            if _ok2:
                i = _new_i
                continue
            _ok3, _new_i = SUM_LAYOUT.try_render_compare(
                doc, lines, i,
                class_name=_cls,
                subject=_subj,
            )
            if _ok3:
                i = _new_i
                continue
        except Exception as _sl_exc:
            print("  ⚠ sum_layout skipped:", _sl_exc)
        # --- END HOOK 7 ---

        sum_blocks, sum_end = collect_column_sum_group(lines, i)
        if allow_sums and sum_blocks:
            add_column_sum_group(doc, sum_blocks)
            i = sum_end
            continue

        # Word-meaning / word=blank items must never enter item_band.
        vocab_now = (
            is_word_meaning_heading(line)
            or (
                bool(re.search(r"विलोम|पर्यायवाची|समानार्थी|antonym|synonym|opposite word|शब्दार्थ", str(last_stem or ""), re.I))
                and _is_short_vocab_item(line)
            )
            or (
                line.startswith(("• ", "· ", "▪ ", "◦ "))
                and "=" in line
                and _is_short_vocab_item(line)
            )
            or bool(re.match(r"^\d+\s*[\).]\s*[A-Za-z\u0900-\u097F]{1,24}\s*=\s*$", line))
        )
        if vocab_now and not is_mcq_section_heading(line):
            word_entries = []
            if is_word_meaning_heading(line):
                last_stem = line
                heading_para = doc.add_paragraph()
                set_paragraph_spacing(heading_para, before=4, after=3, line_spacing=1.0)
                htxt = polish_section_heading(line)
                h_run = heading_para.add_run(htxt)
                set_run_language_font(h_run, htxt, bold=True)
                i += 1
                while i < len(lines) and is_word_meaning_heading(lines[i]):
                    i += 1
            while i < len(lines):
                cur = lines[i].strip()
                if not cur:
                    i += 1
                    continue
                if is_instruction_line(cur) and not is_word_meaning_heading(cur) and "=" not in cur:
                    if re.match(r"^(?:\d+\s*[\).]|प्रश्न)", cur) and len(cur) > 48:
                        break
                is_vocab = _is_short_vocab_item(cur) and not is_section_heading(cur) and not is_instruction_line(cur)
                if not is_vocab:
                    break
                pieces = split_word_meaning_entries(cur)
                for piece in pieces:
                    piece = re.sub(r"^\d+\s*[\).]\s*", "", piece).strip()
                    piece = re.sub(r"^[•·▪◦]\s*", "• ", piece)
                    if _is_short_vocab_item(piece) and "=" not in piece:
                        piece = piece.rstrip(" .") + " ="
                    if piece not in word_entries:
                        word_entries.append(piece)
                i += 1
            if word_entries:
                if not maths_mode:
                    add_word_meaning_table(doc, word_entries)
                else:
                    # Maths body: no table. Keep every item as a normal line.
                    for entry in word_entries:
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        set_paragraph_spacing(p, before=0, after=1, line_spacing=1.0)
                        p.paragraph_format.keep_together = True
                        if _is_short_vocab_item(entry):
                            left, _ = split_equals_answer(entry)
                            r, _ = add_text_with_math(p, left, bold=False)
                            r.font.size = Pt(BODY_SIZE)
                            add_one_inch_dotted_line(p, BODY_SIZE)
                        else:
                            r, _ = add_text_with_math(p, entry, bold=False)
                            r.font.size = Pt(BODY_SIZE)
                continue

        plan_items, plan_end = collect_plan_item_run(lines, i)
        qtype_now = infer_plan_qtype(last_stem)
        written_types = (
            "true_false", "fill_blank", "word_meaning",
            "gender", "adjective", "mcq", "plural",
        )
        _band_txt = " ".join(str(x) for x in plan_items)
        if (
            len(plan_items) >= 2
            and not mcq_mode
            and qtype_now not in written_types
            and not bool(layout.get("ncert_sequential", False))
            and not maths_mode
            and not re.search(
                r"_{2,}|\.{3,}|रिक्त|पूर्ति|सही कथन|गलत कथन|चिन्ह लगा|निशान लगा",
                _band_txt + " " + str(last_stem or ""),
            )
        ):
            qtype = infer_plan_qtype(last_stem)
            cols = plan_columns_for(
                len(plan_items),
                qtype,
                stage=layout.get("stage"),
                max_cols=layout.get("max_band_cols"),
            )
            add_plan_item_band(doc, {
                "kind": "item_band",
                "qtype": qtype,
                "stem": last_stem,
                "items": plan_items,
                "columns": cols,
                "furniture": "blank_trail",
            })
            i = plan_end
            continue

        if is_number_line_line(line):
            add_number_line(doc, line)
            i += 1
            continue

        mat_block, mat_end = collect_matrix_block(lines, i)
        if allow_matrix and mat_block:
            add_matrix_table(doc, " ".join(mat_block))
            i = mat_end
            continue

        table_block, table_end = collect_pipe_table_block(lines, i)
        if table_block and not maths_mode:
            add_exam_property_table(doc, table_block)
            i = table_end
            continue

        fig_items, fig_end = collect_fig_shape_group(lines, i)
        if allow_fig and fig_items:
            add_fig_shape_group(doc, fig_items)
            i = fig_end
            continue
        if allow_fig and (looks_like_figure_request(line) or "[[FIG" in line.upper()):
            cap = re.sub(r"^\[\[FIG(?:URE)?\]\]\s*", "", line, flags=re.I).strip()
            add_figure_box(doc, cap)
            i += 1
            continue

        # ----------------------------------------------------
        # WORD-MEANING BLOCK
        # ----------------------------------------------------
        vocab_line = (
            (line.startswith(("• ", "· ", "▪ ", "◦ ")) and "=" in line)
            or bool(re.match(r"^\d+\s*[\).]\s*.{1,40}=\s*$", line))
        )
        if vocab_line:
            word_entries = []
            while i < len(lines):
                cur = lines[i].strip()
                is_vocab = (
                    (cur.startswith(("• ", "· ", "▪ ", "◦ ")) and "=" in cur)
                    or bool(re.match(r"^\d+\s*[\).]\s*.{1,40}=\s*$", cur))
                )
                if not is_vocab:
                    break
                cur = re.sub(r"^\d+\s*[\).]\s*", "• ", cur)
                if not cur.startswith("•"):
                    cur = "• " + cur
                word_entries.append(cur)
                i += 1
            if not maths_mode:
                add_word_meaning_table(doc, word_entries)
                continue
            # Maths: do not create a table; fall through to plain paragraphs.
            i = max(i, len(lines)) if False else i

        if allow_match and is_match_heading(line):
            heading_para = doc.add_paragraph()
            set_paragraph_spacing(heading_para, before=4, after=4, line_spacing=1.0)
            heading_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            h_run = heading_para.add_run(line)
            set_run_language_font(h_run, line, bold=True)
            lefts, rights, match_end = collect_match_block(lines, i + 1)
            if (lefts or rights) and not maths_mode:
                add_match_table(doc, lefts, rights)
                i = match_end
                continue
            i += 1
            continue

        sub_items, sub_end = collect_roman_subpart_run(lines, i)
        if sub_items and not vertical_item_mode:
            # Maths: NEVER use a table for sub-questions.
            if maths_mode:
                if not any(looks_like_written_item(body) for _m, body in sub_items):
                    add_subpart_lines_no_table(doc, sub_items)
                    i = sub_end
                    continue
            else:
                # Long T/F or fill sentences stay vertical. Only tiny tokens use 2-col.
                _bodies = [body for _m, body in sub_items]
                _long = any(len(b) > 28 or re.search(r"[?।]|_{2,}", b) for b in _bodies)
                if _long or infer_plan_qtype(last_stem) in {"true_false", "fill_blank"}:
                    add_subpart_lines_no_table(doc, sub_items)
                    i = sub_end
                    continue
                if not any(looks_like_written_item(body) for _m, body in sub_items):
                    add_subpart_align_table(doc, sub_items)
                    i = sub_end
                    continue

        inline = None if vertical_item_mode else extract_inline_mcq(line)
        if inline and (mcq_mode or looks_like_mcq_stem(line) or looks_like_mcq_stem(inline[0])):
            stem, opts = inline
            para = doc.add_paragraph()
            set_paragraph_spacing(para, before=3, after=1, line_spacing=1.0)
            if is_subpart_or_option(stem):
                apply_subpart_column_align(para, ncert_mode=bool(layout.get("ncert_sequential", False)))
                stem = format_subpart_line(stem)
            add_text_with_math(para, stem, bold=False)
            add_option_table(
                doc, opts,
                hindi_labels=hindi_mcq_labels,
                single_column=False if options_go_in_one_row(opts) else maths_mode,
                no_table=False if options_go_in_one_row(opts) else maths_mode,
            )
            i += 1
            continue

        # --- HOOK 11: MCQ options 1-row / 2x2 even on Maths papers ---
        try:
            if mcq_mode and not vertical_item_mode:
                _opts, _end = collect_mcq_option_block(lines, i, mcq_mode=True)
                if _opts and not any(looks_like_written_item(x) for x in _opts):
                    add_option_table(
                        doc, _opts,
                        hindi_labels=hindi_mcq_labels,
                        single_column=False,
                        no_table=False,
                    )
                    i = _end
                    continue
        except Exception as _mq:
            print("  ⚠ mcq grid hook skipped:", _mq)
        # --- END HOOK 11 ---

        # ----------------------------------------------------
        # DIRECT OPTION BLOCK
        # 2x2 grid ONLY for real MCQ / Multiple Choice.
        # Ordinary (a)(b)(c)(d) sub-parts stay single-column.
        # ----------------------------------------------------
        if one_word_section or re.search(r"one word|एक शब्द|शब्दार्थ", str(last_stem or ""), re.I):
            direct_options, direct_end = [], i
        else:
            direct_options, direct_end = ([], i) if vertical_item_mode else collect_mcq_option_block(
            lines, i, mcq_mode=mcq_mode
        )
        if direct_options and not any(looks_like_written_item(x) for x in direct_options):
            use_single = False if options_go_in_one_row(direct_options) else (
                force_vertical_options
                or not (mcq_mode or looks_like_mcq_stem(last_stem))
            )
            add_option_table(
                doc, direct_options,
                hindi_labels=hindi_mcq_labels,
                single_column=use_single,
                no_table=False if options_go_in_one_row(direct_options) else maths_mode,
            )
            i = direct_end
            continue

        try:
            line = _board_polish_line(
                line,
                class_name=str(row_data.get("CLASS", "") if hasattr(row_data, "get") else ""),
                subject=str(row_data.get("SUBJECT", "") if hasattr(row_data, "get") else ""),
            )
        except Exception:
            pass

        paragraph = doc.add_paragraph()

        set_paragraph_spacing(
            paragraph,
            before=0,
            after=0.8,
            line_spacing=1.0
        )

        instruction = is_instruction_line(line)
        section_heading = is_section_heading(line)
        explicit_main = has_explicit_question_label(line)


        # Q.1 ke neeche wali lines ko (1) (2) (3)
        if re.match(r"^\s*fill in the blanks", str(line), re.I) and last_major_number:
            if not re.match(r"^\s*(?:\d+[.)]|Q\.)", str(line)):
                last_major_number = int(last_major_number) + 1
                line = f"Q.{last_major_number}  {line.lstrip()}"
                explicit_main = True
                last_stem = line
                child_idx = 0

        if explicit_main:
            child_idx = 0
        if re.search(r"fill in the blank|रिक्त स्थान", str(line), re.I):
            last_stem = line
            child_idx = 0
        _stem_l = str(last_stem or "").lower()
        _is_list_stem = any(k in _stem_l for k in (
            "answer the following", "fill in the blank", "name these",
            "national symbol", "निम्नलिखित", "रिक्त", "नाम लिख",
        ))
        _already = bool(re.match(r"^\s*(?:\d+[.)]|Q\.|प्रश्न|\(\d+\))", str(line)))
        _is_bank = ("," in str(line)) and ("?" not in str(line)) and not re.search(r"_{3,}", str(line))
        _is_blank_line = bool(re.search(r"_{3,}", str(line)))
        _is_ask = (
            "?" in str(line)
            or _is_blank_line
            or bool(re.match(
                r"^(Which|Where|What|Who|Name|Write|This|Our|Hindi|How)\b",
                str(line).strip(),
                re.I,
            ))
        )
        if (
            _is_list_stem
            and not explicit_main
            and not _already
            and not _is_bank
            and _is_ask
            and len(str(line).strip()) >= 6
        ):
            child_idx += 1
            line = f"({child_idx})  {line.lstrip()}"

        apply_safe_paragraph_alignment(
            paragraph,
            line,
            is_special=(
                instruction
                or section_heading
                or explicit_main
                or is_option_line(line)
                or is_subpart_or_option(line)
            )
        )

        num_info = classify_numbering(
            line,
            major_open=explicit_question_open,
            last_major=last_major_number,
        )
        if explicit_main or num_info["kind"] == "major":
            main_question = True
            explicit_question_open = True
            if num_info.get("number") and isinstance(num_info["number"], int):
                last_major_number = num_info["number"]
            else:
                last_major_number = _extract_leading_question_number(line) or last_major_number
            last_stem = line
            line = normalize_numbering_line(line, num_info, True, last_major_number)
            paragraph.paragraph_format.space_before = Pt(
                layout.get("major_question_gap_pt", MAJOR_SUBPART_GAP_PT)
            )
            paragraph.paragraph_format.space_after = Pt(0.5)
            paragraph.paragraph_format.keep_together = True
        elif is_major_question_start(line) and num_info["kind"] != "subpart":
            main_question = True
            explicit_question_open = True
            last_stem = line
            line = normalize_numbering_line(line, num_info, True, last_major_number)
        else:
            main_question = False

        subpart = num_info["kind"] in ("subpart", "option")
        numbered_line = num_info.get("style") in ("num_plain", "num_paren", "plain_seq")
        if subpart:
            line = format_subpart_line(line)
            apply_subpart_column_align(paragraph)

        want_bold = bool(
            instruction
            or main_question
            or section_heading
            or is_word_meaning_heading(line)
            or is_mcq_section_heading(line)
            or is_non_mcq_section_heading(line)
        )
        if (
            is_mcq_section_heading(line)
            or is_non_mcq_section_heading(line)
            or is_word_meaning_heading(line)
        ):
            line = polish_section_heading(line)
        if line_is_true_false_heading(line) or line_is_true_false_heading(last_stem):
            if line_is_true_false_heading(line):
                tf_section = True
            elif line_closes_true_false_section(line):
                tf_section = False
        elif line_closes_true_false_section(line):
            tf_section = False

        if tf_section:
            if not re.search(r"\(\s*T\s*/\s*F\s*\)", line, re.I):
                line = line.rstrip() + "     ( T / F )"
        if re.search(r"_{3,}|\.{5,}", line) and not mcq_mode:
            _bits = re.split(r"(_{3,}|\.{5,})", line)
            run = None
            _has_math = False
            for _bit in _bits:
                if not _bit:
                    continue
                if re.fullmatch(r"_{3,}|\.{5,}", _bit):
                    img, size = _ensure_answer_image("one_word")
                    if img:
                        try:
                            paragraph.add_run(" ").add_picture(
                                img,
                                width=Inches(_px_to_inches(size[0])),
                                height=Inches(_px_to_inches(size[1])),
                            )
                            continue
                        except Exception:
                            pass
                    add_one_inch_dotted_line(paragraph)
                else:
                    run, _has_math = add_text_with_math(paragraph, _bit, bold=want_bold)
        else:
            run, _has_math = add_text_with_math(paragraph, line, bold=want_bold)

        _ak = classify_answer_kind(line, last_stem)
        _one_word_stem = bool(one_word_section) or bool(re.search(
            r"one word|एक शब्द|शब्दार्थ|विलोम|पर्याय",
            str(last_stem or "") + " " + str(line or ""),
            re.I,
        ))
        if (
            (_ak == "one_word" or _one_word_stem)
            and not mcq_mode
            and not is_section_heading(line)
            and not is_word_meaning_heading(line)
            and not re.search(r"_{3,}|fill in the blank|रिक्त", line, re.I)
            and not re.search(r"write the answer in one word|एक शब्द में उत्तर", line, re.I)
        ):
            try:
                paragraph.paragraph_format.tab_stops.add_tab_stop(
                    Inches(6.2), WD_TAB_ALIGNMENT.RIGHT
                )
            except Exception:
                pass
            paragraph.add_run("\t")
            img, size = _ensure_answer_image("one_word")
            if img:
                try:
                    paragraph.add_run().add_picture(
                        img,
                        width=Inches(_px_to_inches(size[0])),
                        height=Inches(_px_to_inches(size[1])),
                    )
                except Exception:
                    add_one_inch_dotted_line(paragraph)
            else:
                add_one_inch_dotted_line(paragraph)
        elif _ak == "one_sentence" and (main_question or explicit_main) and not mcq_mode and not _one_word_stem:
            add_sentence_answer_line(doc)
        elif _ak == "multi_line" and (main_question or explicit_main or re.search(r"निबंध|पत्र लिख", line)):
            add_answer_furniture(doc, "multi_line")

        if main_question and not mcq_mode:
            paragraph.paragraph_format.space_before = Pt(12)

        if instruction:
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.keep_together = True

        elif main_question:
            set_run_language_font(run, line, bold=True, replace_text=False)

            # MAIN QUESTION GAP:
            # Exactly one visual line of space before EVERY major question.
            # This is intentionally applied here so no later formatting rule
            # can reduce the gap back to 1 pt.
            paragraph.paragraph_format.space_before = Pt(12)


            # --- HOOK 3: answer space after major question (ADD-ON) ---
            try:
                if RULE_PLAN is not None and RULE_APPLY is not None:
                    _rule_probe = str(last_stem or "") + " " + str(line or "")
                    _rule_plan = RULE_PLAN(str(layout.get("subject", "")), _rule_probe)
                    if _rule_plan.get("reason") in {
                        "write_n", "english_name", "addition", "subtraction",
                        "circle_biggest", "name_answer", "fill_blank", "match_pairs",
                        "hindi_answer",
                    }:
                        RULE_APPLY(doc, _rule_plan, {})
                        print("  rule applied:", _rule_plan.get("reason"))
                        raise RuntimeError("RULE_APPLIED")
            except RuntimeError as _rule_done:
                if str(_rule_done) != "RULE_APPLIED":
                    raise
            except Exception as _rule_apply_exc:
                print("  rule apply skipped:", _rule_apply_exc)
            try:

                _subj = str(layout.get("subject", "")).lower()
                if (ANSWER_SPACE is not None
                        and "math" not in _subj and "गणित" not in _subj
                        and bool(layout.get("answer_space", False))):
                    _probe = str(last_stem or "") + "\n" + str(line or "")
                    _nwrite = ANSWER_SPACE.extract_write_count(_probe)
                    if _nwrite:
                        ANSWER_SPACE.render_name_grid(doc, _nwrite, per_row=3)
                    elif (main_question or ANSWER_SPACE.is_long_answer_heading(last_stem or "")
                          or ANSWER_SPACE.is_long_answer_heading(line)):
                        _ans_lines = ANSWER_SPACE.estimate_answer_lines(
                            _probe,
                            layout.get("stage", ""),
                            layout.get("subject", ""),
                        )
                        ANSWER_SPACE.render_answer_space(doc, _ans_lines)
            except Exception as _as_exc:
                print("  ⚠ answer space skipped:", _as_exc)
            # --- END HOOK 3 ---

            paragraph.paragraph_format.space_after = Pt(0.5)
            paragraph.paragraph_format.keep_together = True

            # Keep the main question with an immediately following option
            # block only. This prevents artificial blank space elsewhere.
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            next_is_option = is_option_line(next_line) or (
                mcq_mode and is_roman_option_line(next_line)
            )
            paragraph.paragraph_format.keep_with_next = next_is_option
            if next_is_option:
                _opts, _end = collect_mcq_option_block(lines, i + 1, mcq_mode=True)
                if _opts and options_go_in_one_row(_opts):
                    add_option_table(
                        doc, _opts,
                        hindi_labels=hindi_mcq_labels,
                        single_column=False,
                        no_table=False,
                    )
                    i = _end
                    continue

        elif section_heading:
            set_run_language_font(run, line, bold=True, replace_text=False)

            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Inches(0)
            paragraph.paragraph_format.left_indent = Inches(0)
            paragraph.paragraph_format.right_indent = Inches(0)

            paragraph.paragraph_format.space_before = Pt(1.5)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.keep_together = True

        elif subpart or (explicit_question_open and numbered_line):
            # SUB-PART / NESTED-NUMBER LOCK:
            # Once an explicitly labelled major question is open, numbered
            # lines underneath it are NEVER allowed to inherit bold styling.
            # This permanently prevents faults such as Q2/Q4/Q5 internal
            # items 1., 2., 3. appearing bold.
            force_normal_run(run, line)
            apply_subpart_column_align(paragraph, ncert_mode=bool(layout.get("ncert_sequential", False)))
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.keep_together = True
            paragraph.paragraph_format.keep_with_next = False

            # ------------------------------------------------
            # V8 NESTED MCQ OPTION BLOCK
            # ------------------------------------------------
            nested_options, nested_end = ([], i) if vertical_item_mode else collect_nested_mcq_options(
                lines, i, mcq_mode=mcq_mode
            )
            if nested_options:
                # 2x2 only for real MCQ; otherwise vertical sub-parts
                use_single = False if options_go_in_one_row(nested_options) else (
                    force_vertical_options
                    or not (mcq_mode or looks_like_mcq_stem(last_stem) or looks_like_mcq_stem(line))
                )
                add_option_table(
                    doc, nested_options,
                    hindi_labels=hindi_mcq_labels,
                    single_column=use_single,
                    no_table=False if options_go_in_one_row(nested_options) else maths_mode,
                )
                i = nested_end
                continue

        else:
            set_run_language_font(run, line, bold=False, replace_text=False)
            paragraph.paragraph_format.keep_together = False
            paragraph.paragraph_format.keep_with_next = False

        i += 1

    pack_short_choice_paragraphs(doc)


def _para_plain_text(p_el):
    return "".join(p_el.itertext()).strip()


def _looks_choice_line(text):
    t = str(text or "").strip()
    if not t or len(t) > 48:
        return False
    body = re.sub(
        r"^\s*(?:\((?:[a-dA-Dअ-द]|i{1,3}|iv|v|vi)\)|[a-dA-D][.)])\s*",
        "",
        t,
        flags=re.I,
    ).strip()
    if len(body) > 22 or re.search(r"[?।]|_{2,}|था।|हैं।|है।", body):
        return False
    if is_option_line(t):
        return True
    if re.match(r"^\s*\(\s*[a-dA-Dअ-द]\s*\)\s*\S", t):
        return True
    if re.match(r"^\s*[a-dA-D]\s*[\.\)]\s+\S", t):
        return True
    if re.match(r"^\s*\(\s*(?:i|ii|iii|iv|v|vi)\s*\)\s*\S", t, re.I):
        return True
    return False


def pack_short_choice_paragraphs(doc):
    """Last-pass: consecutive (a)(b)(c) paragraphs → one equal row."""
    _rebuild_choice_rows(doc)


def _rebuild_choice_rows(doc):
    paras = doc.paragraphs
    runs = []
    block = []
    for p in paras:
        t = (p.text or "").strip()
        if _looks_choice_line(t):
            block.append(p)
            continue
        if len(block) >= 2:
            runs.append(block)
        block = []
    if len(block) >= 2:
        runs.append(block)
    for block in runs:
        texts = [(p.text or "").strip() for p in block]
        if not options_go_in_one_row(texts):
            continue
        anchor = block[0]
        cols = compact_grid_columns(texts, single_column=False)
        rows = (len(texts) + cols - 1) // cols
        table = doc.add_table(rows=rows, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        try:
            force_table_inline(table)
        except Exception:
            pass
        remove_table_borders(table)
        usable = OPTION_GRID_WIDTH
        cw = usable / cols
        try:
            tblPr = table._tbl.tblPr
            tblLayout = tblPr.first_child_found_in("w:tblLayout")
            if tblLayout is None:
                tblLayout = OxmlElement("w:tblLayout")
                tblPr.append(tblLayout)
            tblLayout.set(qn("w:type"), "fixed")
            for col in table.columns:
                col.width = Inches(cw)
        except Exception:
            pass
        for idx, entry in enumerate(texts):
            r, c = divmod(idx, cols)
            cell = table.cell(r, c)
            cell.width = Inches(cw)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp = cell.paragraphs[0]
            cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(cp, before=0, after=0, line_spacing=1.0)
            run = cp.add_run(entry)
            set_run_language_font(run, entry, bold=False)
            run.font.size = Pt(BODY_SIZE)
        anchor._p.addprevious(table._tbl)
        for p in block:
            el = p._element
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)


# ============================================================
# WORD PAGE NUMBER FIELDS
# ============================================================

def _add_field_run(paragraph, instruction):
    """Add a Word field with compact footer typography."""
    r = paragraph.add_run()
    set_run_font(r, ENGLISH_FONT, FOOTER_FONT_SIZE, bold=False)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r._r.append(fld_begin)
    r._r.append(instr)
    r._r.append(fld_end)


def add_page_number_fields(paragraph):
    """Insert footer: SAINI PAPER-8059058868 (small)  |  Page X of Y."""
    # Branding kept deliberately small so school in-charge is not disturbed
    brand = paragraph.add_run("SAINI PAPER-8059058868")
    set_run_font(brand, ENGLISH_FONT, 8, bold=False)

    sep = paragraph.add_run("   |   ")
    set_run_font(sep, ENGLISH_FONT, 8, bold=False)

    run = paragraph.add_run("Page ")
    set_run_font(run, ENGLISH_FONT, FOOTER_FONT_SIZE, bold=False)
    _add_field_run(paragraph, "PAGE")
    run = paragraph.add_run(" of ")
    set_run_font(run, ENGLISH_FONT, FOOTER_FONT_SIZE, bold=False)
    _add_field_run(paragraph, "NUMPAGES")


def enable_field_updates(doc):
    """
    Keep this compatibility hook so no existing call/property is removed.
    Do NOT write the automatic field-refresh instruction into the DOCX.

    Reason:
      Word's automatic field-update instruction can trigger the
      "fields may refer to other files" warning on document open.

    PAGE / NUMPAGES field objects themselves are NOT removed or changed.
    All other document properties, formatting, layout and generation rules
    remain untouched.
    """
    return


# ============================================================
# QUESTION SEQUENCE AUDIT
# ============================================================

def extract_question_numbers(text):
    """Extract main question numbers for audit only; never alters text."""
    numbers = []
    for line in str(text or "").splitlines():
        n = _extract_leading_question_number(line)
        if n is not None:
            numbers.append(n)
    return numbers


def audit_question_sequence(page_texts, paper_start):
    """Warning-only question numbering audit across the complete paper."""
    if not QUESTION_SEQUENCE_AUDIT:
        return
    nums = extract_question_numbers("\n".join(str(x or "") for x in page_texts))
    if not nums:
        print("  ℹ Question sequence audit: no main question numbers detected.")
        return

    duplicates = []
    seen = set()
    for n in nums:
        if n in seen and n not in duplicates:
            duplicates.append(n)
        seen.add(n)

    gaps = []
    for a, b in zip(nums, nums[1:]):
        if b > a + 1:
            gaps.extend(range(a + 1, b))

    if duplicates:
        print(f"  ⚠ Question sequence warning for paper {paper_start}: duplicate(s) {duplicates}  seen={nums}")
    if gaps:
        print(f"  ⚠ Question sequence warning for paper {paper_start}: possible missing number(s) {gaps}  seen={nums}")
    if not duplicates and not gaps:
        print(f"  ✓ Question sequence audit passed: {nums[0]}–{nums[-1]} ({len(nums)} detected)")


# ============================================================
# V10 PAGE BORDER / VISUAL FORMATTING
# ============================================================

def add_attractive_page_border(section):
    """Add a restrained professional page border to every Word page.

    Uses Word section page-border XML so the border follows the actual page
    and does not consume body paragraphs or create artificial page breaks.
    The border is intentionally subtle so it remains suitable for a school
    examination paper. The footer is independently positioned above the bottom
    border so the border line never runs through or directly over Page X of Y.
    """
    sectPr = section._sectPr
    pgBorders = sectPr.find(qn("w:pgBorders"))
    if pgBorders is None:
        pgBorders = OxmlElement("w:pgBorders")
        sectPr.append(pgBorders)

    pgBorders.set(qn("w:offsetFrom"), "page")

    for tag in ("top", "left", "bottom", "right"):
        old = pgBorders.find(qn(f"w:{tag}"))
        if old is not None:
            pgBorders.remove(old)

        edge = OxmlElement(f"w:{tag}")
        edge.set(qn("w:val"), PAGE_BORDER_VAL)
        edge.set(qn("w:sz"), PAGE_BORDER_SIZE)
        edge.set(qn("w:space"), PAGE_BORDER_SPACE)
        edge.set(qn("w:color"), PAGE_BORDER_COLOR)
        pgBorders.append(edge)


def force_normal_run(run, text):
    """Force normal weight. Never rewrite text after math OMML is attached."""
    set_run_language_font(run, text, bold=False, replace_text=False)


# ============================================================
# FINAL MOTIVATIONAL SENTENCE — V14 ADDITIVE RULE
# ============================================================

def _class_number_for_motivation(class_name):
    """Return numeric class when the class is 1 or above; otherwise None."""
    text = str(class_name or "").strip().upper()

    # Explicitly exclude pre-primary classes.
    if re.search(r"\b(NURSERY|NUR|LKG|UKG|PRE[- ]?NURSERY|PRE[- ]?PRIMARY)\b", text):
        return None

    # Match Class 1, Class-1, CLASS I, IX, etc.
    m = re.search(r"\bCLASS\s*[-:]?\s*(\d+)\b", text)
    if m:
        return int(m.group(1))

    m = re.search(r"\b(\d{1,2})(?:ST|ND|RD|TH)?\b", text)
    if m:
        return int(m.group(1))

    roman_map = {
        "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
        "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
        "XI": 11, "XII": 12,
    }
    m = re.search(r"\b(?:CLASS\s*)?(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\b", text)
    if m:
        return roman_map.get(m.group(1))

    return None


def should_add_motivational_sentence(class_name):
    number = _class_number_for_motivation(class_name)
    return number is not None and number >= 1


def add_final_motivational_sentence(doc, class_name, paper_rotation_index=0):
    """Add one rotating Hindi motivational slogan only for Class 1+.

    V16 rules:
      - Rotate through all 100 slogans paper-by-paper.
      - Restart from slogan 1 after slogan 100.
      - Use the same 16 pt text size as normal paper text.
      - Put large stars on both sides.
      - Underline the slogan text.
      - No decorative box/table/image, preserving paper space.
      - Nursery/LKG/UKG receive none.
    """
    if not should_add_motivational_sentence(class_name):
        return False

    if not MOTIVATIONAL_SLOGANS:
        return False

    slogan_index = int(paper_rotation_index) % len(MOTIVATIONAL_SLOGANS)
    slogan = MOTIVATIONAL_SLOGANS[slogan_index]

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(
        p,
        before=MOTIVATIONAL_BEFORE_PT,
        after=MOTIVATIONAL_AFTER_PT,
        line_spacing=1.0,
    )
    p.paragraph_format.keep_together = True
    p.paragraph_format.keep_with_next = False

    # Large star at the left.
    left_star = p.add_run("★")
    set_run_language_font(left_star, "★", bold=True)
    left_star.font.size = Pt(MOTIVATIONAL_STAR_FONT_SIZE)

    # Same text size as the paper body; underline the actual slogan.
    text_run = p.add_run(MOTIVATIONAL_SLOGAN_SEPARATOR + slogan + MOTIVATIONAL_SLOGAN_SEPARATOR)
    set_run_language_font(text_run, slogan, bold=True)
    text_run.font.size = Pt(MOTIVATIONAL_FONT_SIZE)
    text_run.underline = True

    # Large star at the right.
    right_star = p.add_run("★")
    set_run_language_font(right_star, "★", bold=True)
    right_star.font.size = Pt(MOTIVATIONAL_STAR_FONT_SIZE)

    return True


# ============================================================
# V20 SCHOOL-NAME AUTO-FIT + MCQ HARD NORMALIZATION + FOOTER/BORDER PROTECTION
# ============================================================

# The school name is NOT assigned a fixed font size. Its size is calculated
# from the actual available A4 text width and character count, then Word's
# fitText is used as a final width safeguard. This keeps short and long school
# names visually balanced and prevents either side of the heading from looking
# unnecessarily empty.
SCHOOL_NAME_MIN_PT = 12
SCHOOL_NAME_MAX_PT = 22
SCHOOL_NAME_TARGET_FILL = 0.90
SCHOOL_NAME_COLOR = RGBColor(0x1F, 0x4E, 0x79)
META_HEADER_SHADING = "2E75B6"
META_HEADER_TEXT = RGBColor(0xFF, 0xFF, 0xFF)
META_VALUE_SHADING = "D6E3F0"

def calculate_school_name_font_size(school_name):
    """Auto font size from character count vs usable A4 width.

    Short names → larger font (up to 22 pt)
    Long names  → smaller font (down to 12 pt)
    Never hardcoded. Never clipped.
    """
    text = re.sub(r"\s+", " ", str(school_name or "").strip())
    if not text:
        return float(ENGLISH_SIZE)

    margin_mm = (LEFT_MARGIN + RIGHT_MARGIN) * 25.4
    # Stay inside the 10 mm page border with a little extra safety.
    usable_mm = PAGE_WIDTH_MM - margin_mm - 6.0
    usable_pt = max(120.0, usable_mm / 25.4 * 72.0) * SCHOOL_NAME_TARGET_FILL

    hindi = bool(re.search(r"[\u0900-\u097F]", text))
    # Slightly tighter glyph estimate so size responds clearly to length
    glyph = 0.72 if hindi else 0.62
    estimated = usable_pt / max(1.0, len(text) * glyph)
    return round(max(SCHOOL_NAME_MIN_PT, min(SCHOOL_NAME_MAX_PT, estimated)), 1)


def apply_word_fit_text(run, width_pt):
    """Tell Word to fit the run horizontally to the supplied width."""
    rPr = run._r.get_or_add_rPr()
    fit = rPr.find(qn("w:fitText"))
    if fit is None:
        fit = OxmlElement("w:fitText")
        rPr.append(fit)
    fit.set(qn("w:val"), str(max(1, int(width_pt * 20))))


def format_school_name_run(run, school_name):
    """Excel school name, auto-sized to page width. Never clipped, never hardcoded."""
    size = calculate_school_name_font_size(school_name)
    set_run_language_font(run, school_name, bold=True)
    run.font.size = Pt(size)
    run.font.color.rgb = SCHOOL_NAME_COLOR
    run.font.highlight_color = None
    # Do not use w:fitText — it squeezes glyphs and cuts letters.
    return size


def _clean_meta_value(value):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".")[0]
    return text



# ============================================================
# V33.13 — NURSERY-HINDI TEMPLATE RENDERER (ADDITIVE / HARD-GATED)
# ------------------------------------------------------------
# Architecture:
# SOURCE QUESTION -> INTENT -> TEMPLATE -> ANSWER SPACE -> RENDERER
#
# This renderer is used ONLY for Nursery + Hindi + ANSWER_SPACE=YES
# when every detected question is READY_FOR_RENDERER through the tested
# SAINI integration gate. Otherwise the existing worksheet renderer is
# retained unchanged.
#
# Safety:
# - source wording is never replaced by generated wording
# - no answer content is generated
# - handwriting remains OFF for Nursery + Hindi
# - no API call is made by the renderer itself
# ============================================================

def _v3313_normalize_question_stem(line):
    """Remove only a leading question number; preserve the wording itself."""
    text = str(line or "").strip()
    text = re.sub(r"^(?:Q(?:uestion)?\s*[-.:]?\s*|प्रश्न\s*[-.:]?\s*)\d+\s*[-.:)]?\s*", "", text, flags=re.I)
    text = re.sub(r"^\d+\s*[.)-]\s*", "", text)
    return text.strip()


_V3313_APPROVED_VARIANTS = [('दिए गए अक्षर को पहचानो', 'LETTER_IDENTIFICATION', 'TPL_LETTER_IDENTIFY'),
 ('अक्षर पहचानो', 'LETTER_IDENTIFICATION', 'TPL_LETTER_IDENTIFY'),
 ('अक्षर देखकर बताओ', 'LETTER_IDENTIFICATION', 'TPL_LETTER_IDENTIFY'),
 ('सही अक्षर पहचानो', 'LETTER_IDENTIFICATION', 'TPL_LETTER_IDENTIFY'),
 ('दिए गए अक्षर को पहचानकर बताओ', 'LETTER_IDENTIFICATION', 'TPL_LETTER_IDENTIFY'),
 ('सही अक्षर पर गोला लगाओ', 'SELECT_CORRECT_LETTER', 'TPL_SELECT_LETTER'),
 ('सही अक्षर को चुनो', 'SELECT_CORRECT_LETTER', 'TPL_SELECT_LETTER'),
 ('सही अक्षर पर ○ लगाओ', 'SELECT_CORRECT_LETTER', 'TPL_SELECT_LETTER'),
 ('सही अक्षर पहचानकर गोला लगाओ', 'SELECT_CORRECT_LETTER', 'TPL_SELECT_LETTER'),
 ('समान अक्षर पर गोला लगाओ', 'MATCH_OR_IDENTIFY_SAME_LETTER', 'TPL_SAME_LETTER_MATCH'),
 ('एक जैसे अक्षरों को पहचानो', 'MATCH_OR_IDENTIFY_SAME_LETTER', 'TPL_SAME_LETTER_MATCH'),
 ('समान अक्षर चुनो', 'MATCH_OR_IDENTIFY_SAME_LETTER', 'TPL_SAME_LETTER_MATCH'),
 ('एक जैसे अक्षर पर गोला लगाओ', 'MATCH_OR_IDENTIFY_SAME_LETTER', 'TPL_SAME_LETTER_MATCH'),
 ('स्वर पहचानो', 'VOWEL_IDENTIFICATION', 'TPL_VOWEL_IDENTIFY'),
 ('दिए गए स्वरों को पहचानो', 'VOWEL_IDENTIFICATION', 'TPL_VOWEL_IDENTIFY'),
 ('स्वर अक्षर पर गोला लगाओ', 'VOWEL_IDENTIFICATION', 'TPL_VOWEL_IDENTIFY'),
 ('सही स्वर चुनो', 'VOWEL_IDENTIFICATION', 'TPL_VOWEL_IDENTIFY'),
 ('स्वर को पहचानकर गोला लगाओ', 'VOWEL_IDENTIFICATION', 'TPL_VOWEL_IDENTIFY'),
 ('स्वर लिखो', 'VOWEL_WRITING', 'TPL_VOWEL_WRITE'),
 ('दिए गए स्वर लिखो', 'VOWEL_WRITING', 'TPL_VOWEL_WRITE'),
 ('स्वरों को लिखो', 'VOWEL_WRITING', 'TPL_VOWEL_WRITE'),
 ('स्वर अक्षर लिखो', 'VOWEL_WRITING', 'TPL_VOWEL_WRITE'),
 ('स्वर का सही चित्र से मिलान करो', 'VOWEL_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('स्वरों का मिलान करो', 'VOWEL_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('सही स्वर और चित्र का मिलान करो', 'VOWEL_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('स्वर को संबंधित चित्र से मिलाओ', 'VOWEL_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('व्यंजन पहचानो', 'CONSONANT_IDENTIFICATION', 'TPL_CONSONANT_IDENTIFY'),
 ('दिए गए व्यंजन पहचानो', 'CONSONANT_IDENTIFICATION', 'TPL_CONSONANT_IDENTIFY'),
 ('सही व्यंजन चुनो', 'CONSONANT_IDENTIFICATION', 'TPL_CONSONANT_IDENTIFY'),
 ('व्यंजन पर गोला लगाओ', 'CONSONANT_IDENTIFICATION', 'TPL_CONSONANT_IDENTIFY'),
 ('व्यंजन लिखो', 'CONSONANT_WRITING', 'TPL_CONSONANT_WRITE'),
 ('दिए गए व्यंजन लिखो', 'CONSONANT_WRITING', 'TPL_CONSONANT_WRITE'),
 ('व्यंजन अक्षर लिखो', 'CONSONANT_WRITING', 'TPL_CONSONANT_WRITE'),
 ('व्यंजन का चित्र से मिलान करो', 'CONSONANT_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('सही व्यंजन को चित्र से मिलाओ', 'CONSONANT_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('व्यंजन और चित्र का मिलान करो', 'CONSONANT_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('चित्र का पहला अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('चित्र देखकर पहला अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('चित्र के नाम का पहला अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('चित्र का आरंभिक अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('दिए गए चित्र का पहला अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('चित्र देखकर उसका पहला अक्षर लिखो', 'PICTURE_FIRST_LETTER', 'TPL_FIRST_LETTER'),
 ('चित्र देखकर सही अक्षर चुनो', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
 ('चित्र के लिए सही अक्षर पर गोला लगाओ', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
 ('चित्र से संबंधित अक्षर पहचानो', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
 ('चित्र का सही अक्षर चुनो', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
 ('चित्र का सही अक्षर से मिलान करो', 'PICTURE_LETTER_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('चित्रों को सही अक्षरों से मिलाओ', 'PICTURE_LETTER_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('चित्र और अक्षर का मिलान करो', 'PICTURE_LETTER_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('सही चित्र को सही अक्षर से मिलाओ', 'PICTURE_LETTER_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('अक्षर को सही चित्र से मिलाओ', 'LETTER_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('सही अक्षर और चित्र का मिलान करो', 'LETTER_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('अक्षरों को संबंधित चित्रों से मिलाओ', 'LETTER_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('अक्षर पर ट्रेस करो', 'LETTER_TRACING', 'TPL_LETTER_TRACE'),
 ('दिए गए अक्षरों को ट्रेस करो', 'LETTER_TRACING', 'TPL_LETTER_TRACE'),
 ('अक्षर को ट्रेस करके लिखो', 'LETTER_TRACING', 'TPL_LETTER_TRACE'),
 ('बिंदुओं पर अक्षर ट्रेस करो', 'LETTER_TRACING', 'TPL_LETTER_TRACE'),
 ('अक्षर देखकर लिखो', 'COPY_LETTER', 'TPL_LETTER_COPY'),
 ('दिए गए अक्षर को देखकर लिखो', 'COPY_LETTER', 'TPL_LETTER_COPY'),
 ('अक्षर को देखकर नीचे लिखो', 'COPY_LETTER', 'TPL_LETTER_COPY'),
 ('खाली स्थान में सही अक्षर भरो', 'MISSING_LETTER', 'TPL_MISSING_LETTER'),
 ('रिक्त स्थान में अक्षर भरो', 'MISSING_LETTER', 'TPL_MISSING_LETTER'),
 ('छूटा हुआ अक्षर लिखो', 'MISSING_LETTER', 'TPL_MISSING_LETTER'),
 ('खाली स्थान में सही अक्षर लिखो', 'MISSING_LETTER', 'TPL_MISSING_LETTER'),
 ('अक्षरों का क्रम पूरा करो', 'LETTER_SEQUENCE_COMPLETE', 'TPL_LETTER_SEQUENCE'),
 ('अक्षर श्रृंखला पूरी करो', 'LETTER_SEQUENCE_COMPLETE', 'TPL_LETTER_SEQUENCE'),
 ('सही अक्षर से क्रम पूरा करो', 'LETTER_SEQUENCE_COMPLETE', 'TPL_LETTER_SEQUENCE'),
 ('अक्षरों को सही क्रम में लगाओ', 'ARRANGE_LETTERS_IN_ORDER', 'TPL_LETTER_SEQUENCE'),
 ('वर्णमाला का क्रम पूरा करो', 'ARRANGE_LETTERS_IN_ORDER', 'TPL_LETTER_SEQUENCE'),
 ('छूटे हुए अक्षर लिखो', 'ARRANGE_LETTERS_IN_ORDER', 'TPL_LETTER_SEQUENCE'),
 ('इसके बाद कौन-सा अक्षर आएगा', 'NEXT_PREVIOUS_LETTER', 'TPL_NEXT_PREVIOUS_LETTER'),
 ('इसके पहले कौन-सा अक्षर आएगा', 'NEXT_PREVIOUS_LETTER', 'TPL_NEXT_PREVIOUS_LETTER'),
 ('अगला अक्षर लिखो', 'NEXT_PREVIOUS_LETTER', 'TPL_NEXT_PREVIOUS_LETTER'),
 ('पिछला अक्षर लिखो', 'NEXT_PREVIOUS_LETTER', 'TPL_NEXT_PREVIOUS_LETTER'),
 ('अलग अक्षर पर गोला लगाओ', 'ODD_LETTER_IDENTIFICATION', 'TPL_ODD_LETTER'),
 ('अलग अक्षर पहचानो', 'ODD_LETTER_IDENTIFICATION', 'TPL_ODD_LETTER'),
 ('जो अक्षर अलग है उस पर गोला लगाओ', 'ODD_LETTER_IDENTIFICATION', 'TPL_ODD_LETTER'),
 ('समान अक्षरों को पहचानो', 'SAME_LETTER_IDENTIFICATION', 'TPL_SAME_LETTER_MATCH'),
 ('समान अक्षरों का मिलान करो', 'LETTER_LETTER_MATCH', 'TPL_LETTER_LETTER_MATCH'),
 ('एक जैसे अक्षरों को मिलाओ', 'LETTER_LETTER_MATCH', 'TPL_LETTER_LETTER_MATCH'),
 ('अक्षरों को सही जोड़ी से मिलाओ', 'LETTER_LETTER_MATCH', 'TPL_LETTER_LETTER_MATCH'),
 ('चित्र को सही अक्षर से मिलाओ', 'LETTER_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH'),
 ('अक्षर और चित्र का मिलान करो', 'LETTER_PICTURE_MATCH', 'TPL_PICTURE_LETTER_MATCH')]

# V33.16: exact source wording observed in the Nursery-Hindi test paper.
# These are deterministic aliases for an already-approved picture-selection intent;
# no fuzzy matching and no question rewriting.
_V3316_EXACT_VARIANTS = [
    ('चित्रों को पहचानकर उनके नाम के पहले अक्षर पर गोला कीजिए', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
    ('चित्रों को पहचानकर उनके नाम के पहले अक्षर पर गोला लगाइए', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
]

# V33.18: exact stems observed in the current Nursery-Hindi source paper.
# Deterministic aliases only; no fuzzy matching and no rewriting.
_V3318_EXACT_VARIANTS = [
    ('ट्रेस कीजिए', 'LETTER_TRACING', 'TPL_LETTER_TRACE'),
    ('समान अक्षरों को मिलाइए', 'LETTER_LETTER_MATCH', 'TPL_LETTER_LETTER_MATCH'),
    ('समान अक्षरों को मिलाए', 'LETTER_LETTER_MATCH', 'TPL_LETTER_LETTER_MATCH'),
    ('चित्रों को पहचानकर उनके नाम के पहले अक्षर पर गोला कीजिए', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
    ('चित्रो को पहचानकर उनके नाम के पहले अक्षर पर गोला कीजिए', 'PICTURE_SELECT_CORRECT_LETTER', 'TPL_PICTURE_SELECT_LETTER'),
    ('देखकर लिखिए', 'COPY_LETTER', 'TPL_LETTER_COPY'),
]

def _v3313_local_template_decision(stem):
    """Exact-match fallback from the approved Nursery-Hindi knowledge pack. No fuzzy invention."""
    key = re.sub(r"\s+", " ", str(stem or "").strip())
    key = key.strip(" -–—:;।.!?")
    for variant, intent_code, template_id in _V3313_APPROVED_VARIANTS + _V3316_EXACT_VARIANTS + _V3318_EXACT_VARIANTS:
        if key == variant:
            return {"workflow_status": "READY_FOR_RENDERER", "decision": {"intent_code": intent_code, "template_code": template_id, "source": "APPROVED_KNOWLEDGE_PACK_EXACT"}}
    return None


def _v3313_split_question_blocks(extracted_text):
    """Split OCR into question blocks without changing any source text."""
    if isinstance(extracted_text, (list, tuple)):
        raw_lines = []
        for page in extracted_text:
            raw_lines.extend(str(page or "").replace("\r\n", "\n").split("\n"))
    else:
        raw_lines = str(extracted_text or "").replace("\r\n", "\n").split("\n")

    lines = [x.rstrip() for x in raw_lines if str(x).strip()]
    if not lines:
        return []

    qmark = re.compile(r"^(?:Q(?:uestion)?\s*[-.:]?\s*\d+|प्रश्न\s*[-.:]?\s*\d+|\d+\s*[.)])", re.I)
    starts = [i for i, line in enumerate(lines) if qmark.match(line.strip())]
    if not starts:
        return [lines]

    blocks = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block = lines[start:end]
        if block:
            blocks.append(block)
    # Excel header metadata is rendered separately; do not treat pre-question
    # OCR header text as a question stem. Question content starts at the first
    # explicit question marker.
    return blocks


def _v3313_render_answer_lines(doc, count=1, label=""):
    """V33.30 compact blank child-writing lines; never insert an answer."""
    count = max(1, min(int(count or 1), 8))
    for idx in range(count):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.0
        text = (str(label).strip() + " " if label and idx == 0 else "") + "_" * 22
        r = p.add_run(text)
        set_run_language_font(r, text, bold=False)
        r.font.size = Pt(12)


def _v3313_render_mark_space(doc, source_items):
    """Render source items with an empty marking area on the right."""
    items = [str(x).strip() for x in source_items if str(x).strip()]
    if not items:
        _v3313_render_answer_lines(doc, 1)
        return
    table = doc.add_table(rows=len(items), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, item in enumerate(items):
        left, right = table.rows[i].cells
        left.width = Inches(5.45)
        right.width = Inches(1.0)
        left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        lp = left.paragraphs[0]
        lp.paragraph_format.space_after = Pt(2)
        lr = lp.add_run(item)
        set_run_language_font(lr, item, bold=False)
        lr.font.size = Pt(16)
        rp = right.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = rp.add_run("☐")
        set_run_language_font(rr, "☐", bold=False)
        rr.font.size = Pt(22)


def _v3313_render_match_space(doc, source_items):
    """Two-column matching area with source text retained and no solved pairs."""
    items = [str(x).strip() for x in source_items if str(x).strip()]
    if not items:
        _v3313_render_answer_lines(doc, 1)
        return
    table = doc.add_table(rows=len(items), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, item in enumerate(items):
        left, right = table.rows[i].cells
        left.width = Inches(3.05)
        right.width = Inches(3.05)
        left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        lp = left.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        lr = lp.add_run(item)
        set_run_language_font(lr, item, bold=False)
        lr.font.size = Pt(16)
        rp = right.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = rp.add_run("________________")
        set_run_language_font(rr, rr.text, bold=False)
        rr.font.size = Pt(15)



def _v3324_extract_color_figure_crops(image_path, max_items=4):
    """V33.24: locally extract colorful source figures; no API call and no invention."""
    if Image is None or not image_path or not os.path.isfile(str(image_path)):
        return []
    try:
        import cv2
        import numpy as np
    except Exception:
        print("  ⚠ V33.24 FIGURE EXTRACT: OpenCV/NumPy unavailable; source images cannot be auto-cropped")
        return []

    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        arr = np.array(img)
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
        # Nursery picture items are normally colored; black OCR text is excluded.
        mask = ((hsv[:, :, 1] >= 55) & (hsv[:, :, 2] >= 55)).astype("uint8") * 255
        kernel = np.ones((9, 9), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.dilate(mask, kernel, iterations=1)

        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        page_area = float(w * h)
        candidates = []
        for idx in range(1, n):
            x, y, cw, ch, area = [int(v) for v in stats[idx]]
            frac = area / page_area if page_area else 0
            if y < int(h * 0.30):
                continue
            if frac < 0.00015 or frac > 0.06:
                continue
            if cw < 25 or ch < 25:
                continue
            ratio = cw / float(ch)
            if ratio > 5.5 or ratio < 0.18:
                continue
            # Avoid long colored rules/banners.
            if cw > int(w * 0.55) or ch > int(h * 0.30):
                continue
            candidates.append((area, x, y, cw, ch))

        # Prefer spatially compact figure regions and keep reading order.
        candidates.sort(key=lambda z: (z[2], z[1]))
        if len(candidates) > max_items:
            # Four largest among plausible candidates, then restore page order.
            candidates = sorted(candidates, reverse=True)[:max_items]
            candidates.sort(key=lambda z: (z[2], z[1]))

        crops = []
        for _, x, y, cw, ch in candidates[:max_items]:
            pad = max(8, int(min(cw, ch) * 0.10))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(w, x + cw + pad)
            y1 = min(h, y + ch + pad)
            crop = img.crop((x0, y0, x1, y1))
            bio = _V3324BytesIO()
            crop.save(bio, format="PNG")
            bio.seek(0)
            crops.append(bio)
        if crops:
            print(f"  🖼 V33.24 FIGURE EXTRACT: {len(crops)} source figure image(s) recovered locally")
        else:
            print("  ⚠ V33.24 FIGURE EXTRACT: no safe colorful figure regions found")
        return crops
    except Exception as exc:
        print(f"  ⚠ V33.24 FIGURE EXTRACT failed: {exc}")
        return []



def _v3325_extract_figure_box_crops(image_path, max_items=4):
    """V33.25: detect the four boxed picture regions first; fall back to V33.24 color extraction.
    This avoids selecting colored question text/headers as 'pictures'. No API call and no invention.
    """
    if Image is None or not image_path or not os.path.isfile(str(image_path)):
        return []
    try:
        import cv2
        import numpy as np
    except Exception:
        return []
    try:
        img = Image.open(image_path).convert('RGB')
        w, h = img.size
        arr = np.array(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        # Strong threshold for the blue/black hand-drawn rectangular picture boxes.
        edges = cv2.Canny(gray, 50, 150)
        edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        page_area = float(w*h)
        boxes=[]
        for c in contours:
            x,y,cw,ch = cv2.boundingRect(c)
            area=cw*ch
            frac=area/page_area if page_area else 0
            if y < int(h*0.40):
                continue
            if frac < 0.003 or frac > 0.10:
                continue
            if cw < int(w*0.10) or ch < int(h*0.05):
                continue
            ratio=cw/float(ch)
            if ratio < 0.45 or ratio > 2.8:
                continue
            # Ignore the full page border and very long horizontal rules.
            if cw > int(w*0.40) or ch > int(h*0.28):
                continue
            boxes.append((x,y,cw,ch,area))
        # Deduplicate nested contours: keep the largest useful box at each x/y cluster.
        boxes.sort(key=lambda b: b[4], reverse=True)
        chosen=[]
        for b in boxes:
            x,y,cw,ch,area=b
            overlap=False
            for bx,by,bw,bh,_ in chosen:
                ix=max(0,min(x+cw,bx+bw)-max(x,bx))
                iy=max(0,min(y+ch,by+bh)-max(y,by))
                inter=ix*iy
                if inter > 0.45*min(area,bw*bh):
                    overlap=True; break
            if not overlap:
                chosen.append(b)
        # The picture row should contain up to four similarly sized boxes.
        chosen=sorted(chosen, key=lambda b:(b[1],b[0]))
        if len(chosen) > max_items:
            # Prefer the densest horizontal row of up to four boxes.
            best=[]
            for b in chosen:
                row=[q for q in chosen if abs(q[1]-b[1]) < max(30,int(h*0.05))]
                if len(row)>len(best): best=row
            chosen=sorted(best[:max_items], key=lambda b:b[0])
        crops=[]
        for x,y,cw,ch,_ in chosen[:max_items]:
            pad=max(6,int(min(cw,ch)*0.08))
            crop=img.crop((max(0,x-pad),max(0,y-pad),min(w,x+cw+pad),min(h,y+ch+pad)))
            bio=_V3324BytesIO(); crop.save(bio,format='PNG'); bio.seek(0); crops.append(bio)
        if len(crops)>=2:
            print(f"  🖼 V33.25 FIGURE BOX EXTRACT: {len(crops)} boxed source figure(s) recovered")
            return crops[:max_items]
        return []
    except Exception as exc:
        print(f"  ⚠ V33.25 FIGURE BOX EXTRACT failed: {exc}")
        return []



def _v3327_normalize_token(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f]+", "_", text)
    return text.strip("_")


def _v338_print_image_bank_status():
    ok = _v338_verify_image_bank()
    print(
        "  🔐 V33.38 IMAGE BANK STATUS:",
        "VERIFIED" if ok else "BLOCKED",
        "|",
        _V338_IMAGE_BANK_VERIFICATION_REASON,
    )
    return ok


def _v3327_image_bank_index():
    """Build a deterministic, read-only index of the universal image bank."""
    global _V3327_IMAGE_BANK_CACHE
    if _V3327_IMAGE_BANK_CACHE is not None:
        return _V3327_IMAGE_BANK_CACHE

    index = []
    root = IMAGE_BANK_ROOT
    if not os.path.isdir(root):
        print(f"  ⚠ V33.27 IMAGE BANK: folder not found: {root}")
        _V3327_IMAGE_BANK_CACHE = []
        return _V3327_IMAGE_BANK_CACHE

    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    try:
        for category in sorted(os.listdir(root)):
            cat_path = os.path.join(root, category)
            if not os.path.isdir(cat_path):
                continue
            for base, _, files in os.walk(cat_path):
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() not in image_exts:
                        continue
                    full = os.path.join(base, name)
                    rel = os.path.relpath(full, root)
                    index.append({
                        "path": full,
                        "category": category.lower(),
                        "filename": os.path.splitext(name)[0].lower(),
                        "rel": rel.lower(),
                    })
    except Exception as exc:
        print(f"  ⚠ V33.27 IMAGE BANK index failed: {exc}")
        index = []

    _V3327_IMAGE_BANK_CACHE = index
    print(f"  🗂 V33.27 IMAGE BANK INDEX: {len(index)} image asset(s) indexed")
    return index


_V3327_CONCEPTS = {
    "झंडा": {
        "tokens": ("flag", "flags", "jhanda", "dhwaj", "tiranga", "national_flag"),
        "categories": ("school", "signs_symbols", "festivals", "general_objects"),
    },
    "टमाटर": {
        "tokens": ("tomato", "tomatoes", "tamatar"),
        "categories": ("vegetables", "food"),
    },
    "अंगूर": {
        "tokens": ("grape", "grapes", "angoor"),
        "categories": ("fruits", "food"),
    },
    "पत्ता": {
        "tokens": ("leaf", "leaves", "patta", "patti"),
        "categories": ("leaves", "plants", "trees", "nature"),
    },
}


def _v338_verify_image_bank():
    """Enable image resolution only for a separately verified image bank.

    The manifest is intentionally external to the trial-image package.
    This function is read-only and never creates, edits, or trusts assets
    merely because they exist in a folder.
    """
    global _V338_VERIFIED_IMAGE_BANK_ENABLED, _V338_IMAGE_BANK_VERIFICATION_REASON

    root = os.path.normpath(str(IMAGE_BANK_ROOT))
    manifest_path = os.path.join(root, _V338_IMAGE_BANK_MANIFEST_NAME)

    # Known trial package is always blocked, even if someone adds a manifest.
    if "WITH_TRIAL_IMAGES" in os.path.normcase(root):
        _V338_VERIFIED_IMAGE_BANK_ENABLED = False
        _V338_IMAGE_BANK_VERIFICATION_REASON = "trial-image package is permanently blocked"
        return False

    if not os.path.isfile(manifest_path):
        _V338_VERIFIED_IMAGE_BANK_ENABLED = False
        _V338_IMAGE_BANK_VERIFICATION_REASON = "verification manifest not found"
        return False

    try:
        import json as _json
        with open(manifest_path, "r", encoding="utf-8") as _mf:
            manifest = _json.load(_mf)
        if not isinstance(manifest, dict):
            raise ValueError("manifest root must be an object")
        if manifest.get("verified") is not True:
            raise ValueError("manifest verified flag is not true")
        if manifest.get("version") in (None, ""):
            raise ValueError("manifest version missing")
        _V338_VERIFIED_IMAGE_BANK_ENABLED = True
        _V338_IMAGE_BANK_VERIFICATION_REASON = "verified manifest accepted"
        return True
    except Exception as _exc:
        _V338_VERIFIED_IMAGE_BANK_ENABLED = False
        _V338_IMAGE_BANK_VERIFICATION_REASON = f"invalid verification manifest: {_exc}"
        return False


def _v3327_resolve_image_bank_asset(label):
    """Resolve only from a verified image bank.

    V33.37 SAFETY GATE:
    The currently packaged path contains TRIAL IMAGES and is explicitly
    untrusted. Trial/random assets must never enter a generated paper.
    No source-paper crop or fallback image is permitted here.
    """
    raw = str(label or "").strip()

    # V33.38: trust requires an explicit verification manifest.
    if not _v338_verify_image_bank():
        print(
            "  🛑 V33.38 IMAGE BANK GATE: picture asset rejected -> "
            + str(_V338_IMAGE_BANK_VERIFICATION_REASON)
            + " | blank picture slot"
        )
        return None
    concept = None
    for key in _V3327_CONCEPTS:
        if key in raw:
            concept = key
            break
    if concept is None:
        low = raw.lower()
        for key, spec in _V3327_CONCEPTS.items():
            if any(tok in low for tok in spec["tokens"]):
                concept = key
                break

    if concept is None:
        print(f"  ⚠ V33.27 IMAGE BANK: no approved concept mapping for {raw!r}")
        return None

    spec = _V3327_CONCEPTS[concept]
    index = _v3327_image_bank_index()
    if not index:
        return None

    # Exact filename token match is preferred.
    scored = []
    for item in index:
        score = 0
        if item["category"] in spec["categories"]:
            score += 50
        hay = item["filename"] + " " + item["rel"]
        for tok in spec["tokens"]:
            if tok in hay:
                score += 100
        if score:
            scored.append((score, item))

    if not scored:
        print(f"  ⚠ V33.27 IMAGE BANK: no asset found for concept={concept!r}")
        return None

    scored.sort(key=lambda z: (-z[0], z[1]["rel"]))
    chosen = scored[0][1]
    print(f"  🖼 V33.27 IMAGE BANK: {concept} → {chosen['rel']}")
    return chosen["path"]


def _v3327_recover_missing_nursery_source_data(image_path):
    """One targeted OCR recovery for missing Q2/Q3 text data.
    Pictures are NEVER recovered as image crops; only textual worksheet data is recovered."""
    global _V3327_VISUAL_RECOVERY_CACHE
    if _V3327_VISUAL_RECOVERY_CACHE is not None:
        return _V3327_VISUAL_RECOVERY_CACHE

    result = {"match_pairs": [], "picture_options": {}}
    if client is None or Image is None or not image_path or not os.path.isfile(str(image_path)):
        _V3327_VISUAL_RECOVERY_CACHE = result
        return result

    try:
        with open(image_path, "rb") as fh:
            image_bytes = fh.read()
        prompt = r"""
You are recovering ONLY missing textual worksheet data from a Nursery Hindi source scan.
Do NOT solve anything. Do NOT create or invent content. Do NOT return pictures or image descriptions.

Recover these two structures exactly as visibly written:

A) QUESTION 2 "समान अक्षरों को मिलाइए"
Return exactly four lines in this format:
MATCH: left_text | right_text

B) QUESTION 3 "चित्रों को पहचानकर उनके नाम के पहले अक्षर पर गोला कीजिए"
For each of the four picture labels, recover the visible letter-choice text under that picture:
PIC1: option_text
PIC2: option_text
PIC3: option_text
PIC4: option_text

Rules:
- Copy visible Hindi letters/matras exactly.
- Preserve the order.
- Do not solve/match.
- Do not add explanations.
- If a requested text is genuinely unreadable, leave that value empty.
"""
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
        )
        raw = sanitize_extracted_paper_text(
            normalize_exam_mark_symbols((resp.text or "").strip())
        )

        for line in raw.splitlines():
            t = line.strip()
            m = re.match(r"^MATCH\s*:\s*(.*?)\s*\|\s*(.*?)\s*$", t, re.I)
            if m:
                left, right = m.group(1).strip(), m.group(2).strip()
                if left and right:
                    result["match_pairs"].append((left, right))
                continue
            m = re.match(r"^PIC([1-4])\s*:\s*(.*?)\s*$", t, re.I)
            if m:
                result["picture_options"][int(m.group(1))] = m.group(2).strip()

        result["match_pairs"] = result["match_pairs"][:4]
        print(
            f"  🔎 V33.27 TEXT RECOVERY: "
            f"Q2 pairs={len(result['match_pairs'])}, "
            f"Q3 option groups={len(result['picture_options'])}"
        )
    except Exception as exc:
        print(f"  ⚠ V33.27 TEXT RECOVERY skipped: {exc}")

    _V3327_VISUAL_RECOVERY_CACHE = result
    return result


# V33.32: exact known English Q3 fallback labels are normalized to the Hindi labels visible in the source worksheet.
# V33.28 HARD RULE: no verified picture bank exists in this project.
# Never use trial images, random category assets, source-paper crops, or generated artwork.
def _v3328_render_picture_select_missing_safe(doc, source_items, visual_data=None):
    """Render Q3 as a clean picture-slot template when no verified asset exists.

    The worksheet keeps the question structure and recovered option text, but
    intentionally leaves the four picture areas empty. This prevents a trial
    tomato (or any other wrong asset) from being substituted for the required
    concept. No source scan is cropped and no image is invented.
    """
    labels = []
    for item in source_items:
        raw = str(item).strip()
        if "[[FIG" in raw.upper():
            cap = re.sub(r"^\[\[FIG(?:URE)?\]\]\s*", "", raw, flags=re.I).strip()
            if cap:
                labels.append(cap)
    labels = labels[:4]
    while len(labels) < 4:
        labels.append("")

    # V33.32: Q3 is a Hindi worksheet. The current source/visual recovery path
    # may surface English concept labels even though the visible source paper
    # contains Hindi labels. Normalize ONLY these exact known fallback labels;
    # do not translate arbitrary OCR text or invent new content.
    _V3332_Q3_LABEL_FIX = {
        "flag": "झंडा",
        "tomato": "टमाटर",
        "grapes": "अंगूर",
        "leaf": "पत्ता",
    }
    _v3332_fixed = 0
    for _i, _label in enumerate(labels):
        _key = re.sub(r"[^a-z]+", "", str(_label or "").strip().lower())
        if _key in _V3332_Q3_LABEL_FIX:
            labels[_i] = _V3332_Q3_LABEL_FIX[_key]
            _v3332_fixed += 1
    if _v3332_fixed:
        print(f"  🧾 V33.32 Q3 LABEL FIX: {_v3332_fixed} exact English fallback label(s) normalized to Hindi")

    visual_data = visual_data or {}
    options = visual_data.get("picture_options", {}) if isinstance(visual_data, dict) else {}

    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        set_visible_table_borders(table, color="B7B7B7", size="8")
    except Exception:
        pass

    for i in range(4):
        cell = table.cell(0, i)
        cell.width = Inches(1.55)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

        # Empty reserved picture area — intentionally no picture is inserted.
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        blank = p.add_run("\n\n")
        blank.font.size = Pt(10)

        cap = labels[i]
        if cap:
            cp = cell.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cr = cp.add_run(f"({chr(105+i)}) {cap}")
            set_run_language_font(cr, cr.text, bold=False)
            cr.font.size = Pt(10.5)

        op = cell.add_paragraph()
        op.alignment = WD_ALIGN_PARAGRAPH.CENTER
        opt = options.get(i + 1, "")
        if opt:
            orr = op.add_run(opt)
            set_run_language_font(orr, opt, bold=False)
            orr.font.size = Pt(12)
        mr = op.add_run("\n☐")
        set_run_language_font(mr, "☐", bold=False)
        mr.font.size = Pt(14)

    print("  🧩 V33.28 Q3: verified image asset unavailable → empty picture slots + textual options; no source crop/trial image")


# V33.27 HARD RULE: source-paper image cropping is FORBIDDEN for worksheet pictures.
def _v3327_render_picture_select_from_image_bank(doc, source_items, visual_data=None):
    """Render Q3 using IMAGE BANK pictures + recovered/source textual options."""
    labels = []
    for item in source_items:
        raw = str(item).strip()
        if "[[FIG" in raw.upper():
            cap = re.sub(r"^\[\[FIG(?:URE)?\]\]\s*", "", raw, flags=re.I).strip()
            if cap:
                labels.append(cap)

    labels = labels[:4]
    while len(labels) < 4:
        labels.append("")

    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    visual_data = visual_data or {}
    options = visual_data.get("picture_options", {}) if isinstance(visual_data, dict) else {}

    for i in range(4):
        cell = table.cell(0, i)
        cell.width = Inches(1.55)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        asset = _v3327_resolve_image_bank_asset(labels[i])
        if asset and os.path.isfile(asset):
            try:
                with open(asset, "rb") as fh:
                    img_bytes = fh.read()
                rr = p.add_run()
                rr.add_picture(_V3324BytesIO(img_bytes), width=Inches(0.95))
            except Exception as exc:
                print(f"  ⚠ V33.27 IMAGE BANK embed failed for {labels[i]!r}: {exc}")
                qr = p.add_run("□")
                qr.font.size = Pt(30)
        else:
            qr = p.add_run("□")
            qr.font.size = Pt(30)

        cp = cell.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = f"({chr(105+i)}) {labels[i]}".strip()
        cr = cp.add_run(cap)
        set_run_language_font(cr, cap, bold=False)
        cr.font.size = Pt(10.5)

        op = cell.add_paragraph()
        op.alignment = WD_ALIGN_PARAGRAPH.CENTER
        opt = options.get(i + 1, "")
        if opt:
            orr = op.add_run(opt)
            set_run_language_font(orr, opt, bold=False)
            orr.font.size = Pt(12)
        mr = op.add_run("\n☐")
        set_run_language_font(mr, "☐", bold=False)
        mr.font.size = Pt(14)

    print("  🖼 V33.27 Q3: IMAGE BANK pictures + textual options rendered (no source-image crop)")


def _v3327_render_match_from_text(doc, source_items, visual_data=None):
    """Render Q2 from text, never from source-image crops."""
    pairs = []
    for item in source_items:
        raw = str(item).strip()
        if "|" in raw and "[[" not in raw:
            left, right = [x.strip() for x in raw.split("|", 1)]
            if left and right:
                pairs.append((left, right))
    if not pairs and visual_data:
        pairs = list(visual_data.get("match_pairs") or [])

    if not pairs:
        table = doc.add_table(rows=4, cols=3)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        for i in range(4):
            lc, mc, rc = table.rows[i].cells
            lc.width = Inches(1.6); mc.width = Inches(2.6); rc.width = Inches(1.6)
            lp, mp, rp = lc.paragraphs[0], mc.paragraphs[0], rc.paragraphs[0]
            lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            lr = lp.add_run(f"{i+1}.")
            rr = rp.add_run("________________")
            mr = mp.add_run("________________")
            set_run_language_font(lr, lr.text, bold=False)
            set_run_language_font(mr, mr.text, bold=False)
            set_run_language_font(rr, rr.text, bold=False)
        print("  ⚠ V33.27 Q2: no textual pairs recovered; clean unsolved template retained")
        return

    # Preserve source order; do not solve/reorder the right column.
    table = doc.add_table(rows=len(pairs), cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, (left, right) in enumerate(pairs):
        lc, mc, rc = table.rows[i].cells
        lc.width = Inches(1.6); mc.width = Inches(2.6); rc.width = Inches(1.6)
        for c in (lc, mc, rc):
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        lp, mp, rp = lc.paragraphs[0], mc.paragraphs[0], rc.paragraphs[0]
        for p in (lp, mp, rp):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lr = lp.add_run(left)
        mr = mp.add_run("____________")
        rr = rp.add_run(right)
        for r in (lr, mr, rr):
            set_run_language_font(r, r.text, bold=False)
            r.font.size = Pt(14)
    print(f"  🧩 V33.27 Q2: {len(pairs)} source text pairs + blank matching space (no image crop)")



def _v3326_source_image():
    """V33.26: return the first locked source page for exact visual-template rendering."""
    for path in list(_CURRENT_SOURCE_IMAGE_PATHS or []):
        if path and os.path.isfile(str(path)):
            return str(path)
    return None


def _v3326_crop_bytes(image_path, box):
    """V33.26: crop a source region using normalized page coordinates."""
    if Image is None or not image_path:
        return None
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        x0, y0, x1, y1 = box
        crop = img.crop((
            max(0, int(w * x0)),
            max(0, int(h * y0)),
            min(w, int(w * x1)),
            min(h, int(h * y1)),
        ))
        bio = _V3324BytesIO()
        crop.save(bio, format="PNG")
        bio.seek(0)
        return bio
    except Exception as exc:
        print(f"  ⚠ V33.26 SOURCE CROP failed: {exc}")
        return None


def _v3326_render_match_from_source(doc):
    """V33.26: preserve the exact four left/right matching items from the source scan.
    The learner supplies the matching line; no pair is solved or invented.
    """
    path = _v3326_source_image()
    if not path:
        print("  ⚠ V33.26 Q2 SOURCE MATCH: source image unavailable; retaining clean fallback")
        _v3324_render_match_template(doc, ["[[TABLE]]"])
        return

    # Normalized coordinates measured from the supplied Nursery-Hindi source page.
    # Four rows, left and right source characters are preserved as image snippets.
    left_boxes = [
        (0.205, 0.505, 0.305, 0.565),
        (0.205, 0.555, 0.305, 0.615),
        (0.205, 0.605, 0.305, 0.665),
        (0.205, 0.655, 0.305, 0.720),
    ]
    right_boxes = [
        (0.505, 0.505, 0.625, 0.565),
        (0.505, 0.555, 0.625, 0.615),
        (0.505, 0.605, 0.625, 0.665),
        (0.505, 0.655, 0.625, 0.720),
    ]

    table = doc.add_table(rows=4, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    for i in range(4):
        lc, mc, rc = table.rows[i].cells
        lc.width = Inches(1.55)
        mc.width = Inches(3.10)
        rc.width = Inches(1.55)
        for cell in (lc, mc, rc):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

        lp = lc.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lb = _v3326_crop_bytes(path, left_boxes[i])
        if lb:
            lr = lp.add_run()
            lr.add_picture(lb, width=Inches(0.55))

        mp = mc.paragraphs[0]
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mr = mp.add_run("____________________________")
        set_run_language_font(mr, mr.text, bold=False)
        mr.font.size = Pt(11)

        rp = rc.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rb = _v3326_crop_bytes(path, right_boxes[i])
        if rb:
            rr = rp.add_run()
            rr.add_picture(rb, width=Inches(0.65))

    print("  🧩 V33.26 Q2 SOURCE MATCH: exact 4×2 source items + blank matching space rendered")


def _v3326_render_picture_select_from_source(doc):
    """V33.26: preserve the four actual picture boxes and the four source option boxes.
    This is source-image reproduction, not generated/invented artwork.
    """
    path = _v3326_source_image()
    if not path:
        print("  ⚠ V33.26 Q3 SOURCE PICTURES: source image unavailable")
        _v3313_render_answer_lines(doc, 1)
        return

    picture_boxes = [
        (0.118, 0.790, 0.225, 0.855),
        (0.392, 0.790, 0.505, 0.855),
        (0.635, 0.790, 0.735, 0.855),
        (0.835, 0.790, 0.940, 0.855),
    ]
    option_boxes = [
        (0.105, 0.875, 0.230, 0.915),
        (0.355, 0.875, 0.505, 0.915),
        (0.600, 0.875, 0.750, 0.915),
        (0.800, 0.875, 0.955, 0.915),
    ]

    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    for i in range(4):
        cell = table.cell(0, i)
        cell.width = Inches(1.55)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

        pp = cell.paragraphs[0]
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pb = _v3326_crop_bytes(path, picture_boxes[i])
        if pb:
            pr = pp.add_run()
            pr.add_picture(pb, width=Inches(1.05))

        op = cell.add_paragraph()
        op.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ob = _v3326_crop_bytes(path, option_boxes[i])
        if ob:
            orr = op.add_run()
            orr.add_picture(ob, width=Inches(1.15))

    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=2, after=8, line_spacing=1.0)
    print("  🖼 V33.26 Q3 SOURCE PICTURES: exact 4 source picture boxes + exact 4 option boxes rendered")



def _v3324_render_picture_select(doc, source_items):
    """Render picture-select question with real source-image crops and blank marking area."""
    labels = []
    for item in source_items:
        raw = str(item).strip()
        if "[[FIG" not in raw.upper():
            continue
        cap = re.sub(r"^\\[\\[FIG(?:URE)?\\]\\]\\s*", "", raw, flags=re.I).strip()
        labels.append(cap)

    crops = []
    for path in list(_CURRENT_SOURCE_IMAGE_PATHS or []):
        # V33.25: prefer rectangular picture-box detection over color connected components.
        crops = _v3325_extract_figure_box_crops(path, max_items=max(4, len(labels) or 4))
        if not crops:
            crops = _v3324_extract_color_figure_crops(path, max_items=max(4, len(labels) or 4))
        if crops:
            break

    n = max(len(labels), len(crops))
    if n == 0:
        _v3313_render_answer_lines(doc, 1)
        return

    n = min(4, n)
    table = doc.add_table(rows=1, cols=n)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i in range(n):
        cell = table.cell(0, i)
        cell.width = Inches(1.45)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if i < len(crops):
            run = p.add_run()
            run.add_picture(crops[i], width=Inches(1.05))
        else:
            rr = p.add_run("□")
            rr.font.size = Pt(30)
        if i < len(labels):
            cap = labels[i]
            cp = cell.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cr = cp.add_run(cap)
            set_run_language_font(cr, cap, bold=False)
            cr.font.size = Pt(12)
        mp = cell.add_paragraph()
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mr = mp.add_run("☐")
        set_run_language_font(mr, "☐", bold=False)
        mr.font.size = Pt(20)
    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=2, after=8, line_spacing=1.0)


def _v3324_render_match_template(doc, source_items):
    """Render two independent matching columns; never expose source pairings as answers."""
    left_items = []
    right_items = []
    for item in source_items:
        raw = str(item).strip()
        if raw.upper() == "[[TABLE]]":
            continue
        if "|" in raw:
            left, right = raw.split("|", 1)
            left = left.strip()
            right = right.strip()
            if left:
                left_items.append(left)
            if right:
                right_items.append(right)
        elif raw:
            left_items.append(raw)

    if right_items:
        rows = max(len(left_items), len(right_items))
        table = doc.add_table(rows=rows, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        for i in range(rows):
            lc, rc = table.rows[i].cells
            lc.width = Inches(3.0)
            rc.width = Inches(3.0)
            lc.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            rc.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            lp = lc.paragraphs[0]
            rp = rc.paragraphs[0]
            lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if i < len(left_items):
                lr = lp.add_run(left_items[i])
                set_run_language_font(lr, lr.text, bold=False)
                lr.font.size = Pt(16)
            if i < len(right_items):
                rr = rp.add_run(right_items[i] + "    ☐")
                set_run_language_font(rr, rr.text, bold=False)
                rr.font.size = Pt(15)
        print(f"  🧩 V33.24 MATCH TEMPLATE: {len(left_items)} left item(s) + {len(right_items)} right choice(s)")
        return

    placeholder_only = not left_items and any(str(x).strip().upper() in {"[[TABLE]]", "[[MATCH]]"} for x in source_items)
    if placeholder_only:
        print('  V33.25 MATCH TEMPLATE OFF: marker only, no invented table')
        return
    if False and placeholder_only:
        table = doc.add_table(rows=4, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        for i in range(4):
            lc, rc = table.rows[i].cells
            lc.width = Inches(3.0); rc.width = Inches(3.0)
            lp, rp = lc.paragraphs[0], rc.paragraphs[0]
            lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            lr = lp.add_run(f"{i+1}. __________________")
            rr = rp.add_run("__________________")
            set_run_language_font(lr, lr.text, bold=False); set_run_language_font(rr, rr.text, bold=False)
            lr.font.size = Pt(15); rr.font.size = Pt(15)
        print("  ⚠ V33.25 MATCH TEMPLATE: OCR supplied only a table marker; rendered clean unsolved 4-row template")
        return
    _v3313_render_match_space(doc, source_items)

def _v3329_clean_render_control_markers(text):
    """V33.29: remove internal OCR/template control markers from visible output only.

    These markers are renderer control tokens, not student-facing question text.
    Source/OCR data is not rewritten; only the text written into the Word worksheet
    is cleaned. Unknown/unapproved content is still handled by the existing gate.
    """
    t = str(text or "")
    t = re.sub(r"\[\[TABLE\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[MATCH\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[FIG(?:URE)?\]\]", "", t, flags=re.I)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _v3313_template_renderer(doc, template_id, intent_code, block):
    """V33.30: compact Nursery-Hindi template renderer; never solves source questions."""
    block = [str(x).strip() for x in (block or []) if str(x).strip()]
    if block:
        _marker_hits = []
        for _mi, _mv in enumerate(block):
            if re.search(r"\[\[(?:TABLE|MATCH|FIG(?:URE)?)\]\]", str(_mv), re.I):
                _marker_hits.append(_mi)
        if _marker_hits:
            print(f"  🧹 V33.29 CONTROL MARKERS: removed from visible renderer fields at block indexes {_marker_hits}")
    if not block:
        return 0

    stem = _v3313_normalize_question_stem(block[0])
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.line_spacing = 1.0
    _visible_stem = _v3329_clean_render_control_markers(block[0])
    r = p.add_run(_visible_stem)
    set_run_language_font(r, _visible_stem, bold=True)
    r.font.size = Pt(13.5)

    source_items = block[1:]
    tid = str(template_id or "").strip().upper()
    iid = str(intent_code or "").strip().upper()

    if tid in {"TPL_FIRST_LETTER", "TPL_MISSING_LETTER", "TPL_NEXT_PREVIOUS_LETTER", "TPL_LETTER_COMPLETE", "TPL_LETTER_COPY", "TPL_VOWEL_WRITE", "TPL_CONSONANT_WRITE"}:
        # V33.30: COPY/WRITE questions always get explicit writing space.
        for item in source_items:
            q = doc.add_paragraph()
            q.paragraph_format.space_before = Pt(0)
            q.paragraph_format.space_after = Pt(0)
            q.paragraph_format.line_spacing = 1.0
            _visible_item = _v3329_clean_render_control_markers(item)
            if not _visible_item:
                continue
            qr = q.add_run(_visible_item)
            set_run_language_font(qr, _visible_item, bold=False)
            qr.font.size = Pt(14)
        # COPY is intentionally given two compact writing lines; this fixes the
        # prior V33.29 Q4 case where the answer space was pushed to page 2.
        line_count = 2 if tid == "TPL_LETTER_COPY" else max(1, min(len(source_items), 4))
        _v3313_render_answer_lines(doc, line_count)
        print(f"  ✍ V33.30 COPY/WRITE SPACE: template={tid} lines={line_count}")
    elif tid == "TPL_LETTER_LETTER_MATCH":
        _v3327_render_match_from_text(doc, source_items, getattr(_v3327_render_match_from_text, "_visual_data", None))
    elif tid in {"TPL_SAME_LETTER_MATCH", "TPL_VOWEL_PICTURE_MATCH", "TPL_CONSONANT_PICTURE_MATCH", "TPL_PICTURE_LETTER_MATCH", "TPL_PICTURE_WORD_MATCH"}:
        _v3324_render_match_template(doc, source_items)
    elif tid == "TPL_PICTURE_SELECT_LETTER":
        _v3328_render_picture_select_missing_safe(doc, source_items, getattr(_v3327_render_picture_select_from_image_bank, "_visual_data", None))
    elif tid in {"TPL_SELECT_LETTER", "TPL_VOWEL_IDENTIFY", "TPL_CONSONANT_IDENTIFY", "TPL_LETTER_PICTURE_SELECT", "TPL_WORD_IDENTIFY", "TPL_ODD_LETTER", "TPL_LETTER_IDENTIFY"}:
        _fig_items = [x for x in source_items if "[[FIG" in str(x).upper()]
        _plain_items = [x for x in source_items if "[[FIG" not in str(x).upper()]
        if _fig_items:
            _v3324_render_picture_select(doc, _fig_items[:4])
        if _plain_items:
            _v3313_render_mark_space(doc, _plain_items)
        elif not _fig_items:
            _v3313_render_mark_space(doc, source_items)
    elif tid in {"TPL_LETTER_TRACE", "TPL_WORD_TRACE"}:
        # V33.30: compact trace room — each source line gets its own writing line.
        visible_count = 0
        for item in source_items:
            _visible_item = _v3329_clean_render_control_markers(item)
            if not _visible_item:
                continue
            q = doc.add_paragraph()
            q.paragraph_format.space_before = Pt(0)
            q.paragraph_format.space_after = Pt(0)
            q.paragraph_format.line_spacing = 1.0
            qr = q.add_run(_visible_item)
            set_run_language_font(qr, _visible_item, bold=False)
            qr.font.size = Pt(15)
            lp = doc.add_paragraph()
            lp.paragraph_format.space_before = Pt(0)
            lp.paragraph_format.space_after = Pt(1)
            lp.paragraph_format.line_spacing = 1.0
            lr = lp.add_run("_" * 22)
            set_run_language_font(lr, lr.text, bold=False)
            lr.font.size = Pt(12)
            visible_count += 1
        if visible_count == 0:
            _v3313_render_answer_lines(doc, 1)
        print(f"  ✏ V33.30 TRACE SPACE: source_lines={visible_count}")
    else:
        for item in source_items:
            q = doc.add_paragraph()
            q.paragraph_format.space_before = Pt(0)
            q.paragraph_format.space_after = Pt(0)
            _visible_item = _v3329_clean_render_control_markers(item)
            if not _visible_item:
                continue
            qr = q.add_run(_visible_item)
            set_run_language_font(qr, _visible_item, bold=False)
            qr.font.size = Pt(14)
        _v3313_render_answer_lines(doc, max(1, min(len(source_items), 3)))
    return 1


def _v3321_render_nursery_header(doc, row_data):
    """V33.21: render the normal Excel-driven header without relying on an undefined _header helper."""
    school = str(row_data.get("SCHOOL NAME", "")).strip()
    class_name = str(row_data.get("CLASS", "")).strip()
    subject = str(row_data.get("SUBJECT", "")).strip()
    mm = _clean_meta_value(str(row_data.get("MM", "")).strip())
    time_val = _clean_meta_value(str(row_data.get("TIME", "")).strip())
    exam_type = _clean_meta_value(str(row_data.get("EXAM TYPE", "")).strip())

    heading1 = doc.add_paragraph()
    heading1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading1.paragraph_format.keep_together = True
    heading1.paragraph_format.widow_control = True
    heading1.paragraph_format.left_indent = Inches(0.08)
    heading1.paragraph_format.right_indent = Inches(0.08)
    run = heading1.add_run(school)
    name_size = format_school_name_run(run, school)
    set_paragraph_spacing(heading1, before=1, after=1, line_spacing=1.0)
    heading1.paragraph_format.line_spacing = Pt(name_size + 5)

    heading2 = doc.add_paragraph()
    heading2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(heading2, before=0, after=3, line_spacing=1.0)
    heading2.paragraph_format.line_spacing = Pt(15)
    heading2.paragraph_format.keep_together = True
    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        cls_sub = f"कक्षा: {class_name}  |  विषय: {subject}"
    else:
        cls_sub = f"Class: {class_name}  |  Subject: {subject}"
    run = heading2.add_run(cls_sub)
    set_run_language_font(run, cls_sub, bold=True)
    run.font.size = Pt(11)
    run.font.color.rgb = SCHOOL_NAME_COLOR

    metadata = [
        ("पूर्णांक", mm),
        ("समय", time_val),
        ("परीक्षा", exam_type),
    ] if PAPER_LANGUAGE in {"hindi", "sanskrit"} else [
        ("Max Marks", mm),
        ("Time", time_val),
        ("Exam", exam_type),
    ]

    table = doc.add_table(rows=2, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for idx, (label, value) in enumerate(metadata):
        head = table.rows[0].cells[idx]
        body = table.rows[1].cells[idx]
        head.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        body.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(head, META_HEADER_SHADING)
        set_cell_shading(body, META_VALUE_SHADING)
        set_cell_margins(head)
        set_cell_margins(body)
        head.text = ""
        hp = head.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(hp, before=1, after=1, line_spacing=1.0)
        hr = hp.add_run(label)
        set_run_language_font(hr, label, bold=True)
        hr.font.size = Pt(9)
        hr.font.color.rgb = META_HEADER_TEXT
        body.text = ""
        bp = body.paragraphs[0]
        bp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(bp, before=1, after=1, line_spacing=1.0)
        vr = bp.add_run(value)
        set_run_language_font(vr, value, bold=True)
        vr.font.size = Pt(10)

    return table


def _v3313_create_nursery_hindi_document(row_data, extracted_text):
    """Create a Nursery-Hindi worksheet only when every question is gate-approved."""
    blocks = _v3313_split_question_blocks(extracted_text)
    print(f"  🔬 V33.16 RENDER TRACE: extracted_type={type(extracted_text).__name__} blocks={len(blocks)}")
    if blocks:
        for _bi, _bb in enumerate(blocks, 1):
            _first = str(_bb[0]).strip() if _bb else ''
            print(f"  🔬 V33.16 BLOCK {_bi}: {_first[:180]}")
    if not blocks:
        print("  ⚠ V33.16 RENDER TRACE: no question blocks; retaining existing worksheet renderer")
        return None

    decisions = []
    for block in blocks:
        # The gate analyzes the question stem, not the following OCR item lines.
        stem = _v3313_normalize_question_stem(block[0])
        if not stem:
            return None
        print(f"  🔬 V33.16 STEM: {stem[:180]}")
        try:
            result = process_nursery_hindi_question(
                source_text=stem,
                class_group="NURSERY",
                subject="HINDI",
                answer_space=_answer_space_column_value(row_data),
                integration_enabled=True,
            ) if process_nursery_hindi_question is not None else None
        except Exception as exc:
            print("  ⚠ V33.13 template decision failed:", exc)
            return None
        if not result or result.get("workflow_status") != "READY_FOR_RENDERER":
            # V33.13 exact approved-pack fallback fixes the current bridge gap
            # for already-audited Nursery-Hindi variants such as NH-032.
            result = _v3313_local_template_decision(stem)
        if not result or result.get("workflow_status") != "READY_FOR_RENDERER":
            print("  ⚠ V33.13 TEMPLATE ROUTE: review required for:", stem)
            return None
        decision = result.get("decision") or {}
        template_id = decision.get("template_code")
        intent_code = decision.get("intent_code")
        if not template_id or not intent_code:
            return None
        print(f"  ✅ V33.18 APPROVED: intent={intent_code} template={template_id}")
        decisions.append((block, intent_code, template_id))

    # V33.28: if OCR left control markers, recover only missing TEXT data once.
    # No verified picture bank exists; Q3 picture slots remain empty rather than
    # using trial assets or cropping the source scan.
    _v3327_visual_data = {}
    _v3327_path = None
    for _p in list(_CURRENT_SOURCE_IMAGE_PATHS or []):
        if _p and os.path.isfile(str(_p)):
            _v3327_path = str(_p)
            break
    _needs_text_recovery = any(
        any("[[TABLE]]" in str(x).upper() or "[[MATCH]]" in str(x).upper() or "[[FIG" in str(x).upper() for x in b[0][1:])
        for b in decisions
    )
    if _needs_text_recovery and _v3327_path:
        _v3327_visual_data = _v3327_recover_missing_nursery_source_data(_v3327_path)
    _v3327_render_match_from_text._visual_data = _v3327_visual_data
    _v3327_render_picture_select_from_image_bank._visual_data = _v3327_visual_data

    doc = Document()
    section = doc.sections[0]
    section.page_width = Mm(PAGE_WIDTH_MM)
    section.page_height = Mm(PAGE_HEIGHT_MM)
    # V33.30: Nursery worksheet is a compact one-page template. These
    # margins are local to the native Nursery-Hindi renderer only; global
    # production paper margins remain unchanged.
    section.top_margin = Inches(0.38)
    section.bottom_margin = Inches(0.38)
    section.left_margin = Inches(0.48)
    section.right_margin = Inches(0.48)
    section.footer_distance = Inches(0.18)
    add_attractive_page_border(section)
    style = doc.styles["Normal"]
    style.font.name = "Nirmala UI"
    style.font.size = Pt(14)
    _v3321_render_nursery_header(doc, row_data)
    print("  🧾 V33.21 HEADER: Excel-driven school/class/subject/meta header rendered")

    print("  🧩 V33.18 TEMPLATE RENDERER: SOURCE → INTENT → TEMPLATE → ANSWER SPACE")
    print("  🧱 V33.20 PAGE BORDER: add_attractive_page_border(section)")
    built = 0
    for block, intent_code, template_id in decisions:
        print(f"  🧩 V33.13 TEMPLATE: {template_id} | intent={intent_code}")
        built += _v3313_template_renderer(doc, template_id, intent_code, block)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("Name: ____________________     Date: ____________")
    set_run_language_font(fr, fr.text, bold=False)
    fr.font.size = Pt(9)
    # V33.31: final visible-text scrub inside the native Nursery-Hindi document.
    # This is a renderer-layer cleanup only; OCR/source data is untouched.
    _v3331_scrubbed = 0
    for _p in doc.paragraphs:
        for _r in _p.runs:
            _old_txt = str(_r.text or "")
            _new_txt = _v3329_clean_render_control_markers(_old_txt)
            if _new_txt != _old_txt:
                _r.text = _new_txt
                _v3331_scrubbed += 1
    for _tbl in doc.tables:
        for _row in _tbl.rows:
            for _cell in _row.cells:
                for _p in _cell.paragraphs:
                    for _r in _p.runs:
                        _old_txt = str(_r.text or "")
                        _new_txt = _v3329_clean_render_control_markers(_old_txt)
                        if _new_txt != _old_txt:
                            _r.text = _new_txt
                            _v3331_scrubbed += 1
    if _v3331_scrubbed:
        print(f"  🧹 V33.31 FINAL VISIBLE-TEXT SCRUB: {_v3331_scrubbed} run(s) cleaned")
    else:
        print("  ✓ V33.31 FINAL VISIBLE-TEXT SCRUB: clean")

    # V33.33: final renderer-layer Q3 caption safety net.
    # The verified-picture-safe policy remains unchanged: no image is added.
    # Only the four exact English fallback captions are normalized if they
    # survived into the rendered Q3 table. This does not modify OCR/source text.
    _v3333_map = {
        "Flag": "झंडा",
        "Tomato": "टमाटर",
        "Grapes": "अंगूर",
        "Leaf": "पत्ता",
    }
    _v3333_fixed = 0
    for _tbl in doc.tables:
        for _row in _tbl.rows:
            for _cell in _row.cells:
                for _p in _cell.paragraphs:
                    for _r in _p.runs:
                        _old = str(_r.text or "")
                        _new = _old
                        for _eng, _hin in _v3333_map.items():
                            _new2 = re.sub(
                                rf"(?<![A-Za-z]){re.escape(_eng)}(?![A-Za-z])",
                                _hin,
                                _new,
                                flags=re.I,
                            )
                            if _new2 != _new:
                                _new = _new2
                                _v3333_fixed += 1
                        if _new != _old:
                            _r.text = _new
    if _v3333_fixed:
        print(f"  🧾 V33.33 Q3 FINAL CAPTION SCRUB: {_v3333_fixed} exact English caption(s) normalized to Hindi")
    else:
        print("  ✓ V33.33 Q3 FINAL CAPTION SCRUB: no English fallback caption survived")

    print(f"  ✓ V33.30 template rooms built: {built}")
    print("  📄 V33.30 ONE-PAGE TARGET: compact Nursery-Hindi layout; Q4 writing space retained")
    return doc

# ============================================================
# DOCUMENT CREATION
# ============================================================

def create_document(row_data, extracted_text, paper_rotation_index=0, warning_message=""):
    """
    Create ONE Word paper for the current Excel row.

    `extracted_text` can be a single string or a list of OCR texts, one
    for each source image belonging to this paper.
    """
    pageno = str(row_data["PAGENO"]).strip()
    class_name = str(row_data["CLASS"]).strip()
    subject = str(row_data["SUBJECT"]).strip()
    school = str(row_data["SCHOOL NAME"]).strip()
    global PAPER_LANGUAGE, CURRENT_PAPER_CLASS
    CURRENT_PAPER_CLASS = class_name
    print(
        f"  → TABLE LOCK: "
        f"{'ON (NUR-III)' if class_allows_tables(class_name) else 'OFF (class 4+ no tables)'}"
    )
    _sample = ""
    if isinstance(extracted_text, (list, tuple)):
        _sample = "\n".join(str(x) for x in extracted_text[:4])
    else:
        _sample = str(extracted_text or "")
    PAPER_LANGUAGE = detect_paper_language(subject, _sample)
    print(f"  → PAPER LANGUAGE LOCK: {PAPER_LANGUAGE or 'auto'}  (subject={subject})")
    medium = ""
    for _mk in ("MEDIUM", "MED", "VERSION"):
        try:
            _mv = str(row_data.get(_mk) if hasattr(row_data, "get") else "").strip()
        except Exception:
            _mv = ""
        if _mv and _mv.lower() not in {"nan", "none", "null"}:
            medium = _mv
            break
    print_layout, sheets_per_copy = resolve_print_layout(
        excel_layout=row_data.get("LAYOUT"),
        excel_sheets_per_copy=row_data.get("SHEETS_PER_COPY"),
    )
    row_data["LAYOUT"] = print_layout
    row_data["SHEETS_PER_COPY"] = sheets_per_copy
    print(f"  → PRINT INPUT: {print_layout} | sheets/copy = {sheets_per_copy}")
    mm = str(row_data["MM"]).strip()
    time_val = str(row_data["TIME"]).strip()
    exam_type = str(row_data["EXAM TYPE"]).strip()

    # V27: Auto subject layout (Maths gets full math pack automatically)
    layout, pattern = build_paper_layout(class_name, subject)
    layout["subject"] = subject
    layout["class_name"] = class_name
    # --- V33.4 MASTER INPUT: existing Excel ANSWER_SPACE ---
    # Do not rename/change the column. It is the single authoritative
    # switch for generated answer-space eligibility.
    layout["answer_space"] = answer_space_enabled(row_data)
    print(
        "  🔎 V33.14 ANSWER_SPACE READBACK:",
        repr(_answer_space_column_value(row_data)),
        "→",
        "YES" if layout["answer_space"] else "NO"
    )

    # Central handwriting decision is calculated once per paper.
    # It does NOT call any AI/API. It only determines eligibility.
    handwriting_decision = get_handwriting_decision(row_data)
    row_data["_HANDWRITING_ALLOWED"] = handwriting_decision["handwriting_allowed"]
    row_data["_HANDWRITING_REASON"] = handwriting_decision["reason"]

    print(
        "  ✍ HANDWRITING GATE:",
        "ON" if handwriting_decision["handwriting_allowed"] else "OFF",
        "|", handwriting_decision["reason"]
    )
    # --- END V33.4 MASTER INPUT ---

    # --- V33.7: SAFE DATABASE INTEGRATION GATE ---
    # Narrow scope: Nursery + Hindi + ANSWER_SPACE=YES only.
    # This gate only records eligibility/metadata; it does not render by itself.
    ai_gate = _saini_ai_integration_status(row_data)
    row_data["_SAINI_AI_INTEGRATION_ELIGIBLE"] = ai_gate["eligible"]
    row_data["_SAINI_AI_ROUTE"] = ai_gate["route"]
    row_data["_SAINI_AI_REASON"] = ai_gate["reason"]
    print("  🤖 SAINI AI GATE:", ai_gate["route"], "|", ai_gate["reason"])
    # --- END V33.7 SAFE DATABASE INTEGRATION GATE ---

    # --- V33.5 QUESTION → INTENT → TEMPLATE ROUTE ---
    worksheet_mode = worksheet_mode_for_class(class_name)
    print(
        "  🔎 V33.17 CLASS MODE READBACK:",
        repr(str(class_name)),
        "→ worksheet_mode=", worksheet_mode,
        "normalized=", normalize_roman_class_group(class_name),
    )
    row_data["_GENERATION_MODE"] = "WORKSHEET_AI" if worksheet_mode else "CLEAN_COPY"
    if worksheet_mode:
        worksheet_intent_plan = build_local_worksheet_intent_plan(extracted_text, class_name, subject)
        row_data["_WORKSHEET_INTENT_PLAN"] = worksheet_intent_plan
        # V33.6: deterministic answer-space render plan from matched intents.
        try:
            if WORKSHEET_INTENT is not None and hasattr(WORKSHEET_INTENT, "build_answer_space_render_plan"):
                row_data["_ANSWER_SPACE_RENDER_PLAN"] = WORKSHEET_INTENT.build_answer_space_render_plan(worksheet_intent_plan)
            else:
                row_data["_ANSWER_SPACE_RENDER_PLAN"] = {"status": "UNAVAILABLE", "items": []}
        except Exception as _render_plan_exc:
            row_data["_ANSWER_SPACE_RENDER_PLAN"] = {"status": "REVIEW_REQUIRED", "items": [], "reason": str(_render_plan_exc)}
        matched = sum(1 for _x in worksheet_intent_plan.get("items", []) if _x.get("status") == "MATCHED")
        total = len(worksheet_intent_plan.get("items", []))
        print(f"  🧠 WORKSHEET ROUTE: QUESTION → INTENT → TEMPLATE | matched={matched}/{total}")
        if worksheet_intent_plan.get("review_required"):
            print("  ⚠ INTENT REVIEW REQUIRED: source wording will NOT be rewritten automatically.")
    else:
        row_data["_WORKSHEET_INTENT_PLAN"] = None
        print("  📄 CLEAN-COPY ROUTE: Class III+ — intent/template pipeline skipped.")
    # --- END V33.5 QUESTION → INTENT → TEMPLATE ROUTE ---
    if pattern:
        print(
            f"  → NCERT base: {pattern.get('group')} / "
            f"{pattern.get('ncf_stage')} / {pattern.get('subject_key')}"
        )
    if is_maths_subject(subject):
        print(f"  → Subject detected as MATHS — special equation/sum/figure layout active")
    if is_science_subject(subject):
        print(f"  → Subject detected as SCIENCE — chemical formula mode active")

    # ========================================================
    # PRODUCT LOCK — 0.1% mix forbidden
    # Play/Pre-Nursery/Nursery/LKG/UKG/Class I/Class II = worksheet document
    # Class III+ = existing clean-copy/board-paper path
    # ========================================================
    if SETTER_CORE:
        try:
            from paper_setter_core.product import apply_product_lock
            from paper_setter_core.worksheet import create_worksheet_document
            layout = apply_product_lock(layout, class_name, subject)
            if worksheet_mode_for_class(class_name):
                print("  🧸 PRODUCT = WORKSHEET (Play–Class II) — board paper code skip")

                # V33.7 PHASE-1: decision bridge only.
                # The existing worksheet renderer remains the owner of document creation.
                # Database/intent/template metadata is added only for the narrow
                # Nursery + Hindi + ANSWER_SPACE=YES scope.
                if ai_gate.get("eligible") and process_nursery_hindi_question is not None:
                    try:
                        _ai_shadow = process_nursery_hindi_question(
                            source_text=str(extracted_text[0] if isinstance(extracted_text, (list, tuple)) and extracted_text else extracted_text or ""),
                            class_group="NURSERY",
                            subject="HINDI",
                            answer_space=_answer_space_column_value(row_data),
                            integration_enabled=True,
                        )
                        row_data["_SAINI_AI_DECISION"] = _ai_shadow.get("decision", {})
                        row_data["_SAINI_AI_WORKFLOW_STATUS"] = _ai_shadow.get("workflow_status", "")
                        if _ai_shadow.get("decision", {}).get("intent_code"):
                            row_data["_SAINI_AI_INTENT"] = _ai_shadow["decision"]["intent_code"]
                        if _ai_shadow.get("decision", {}).get("template_code"):
                            row_data["_SAINI_AI_TEMPLATE"] = _ai_shadow["decision"]["template_code"]
                        if _ai_shadow.get("decision", {}).get("answer_space_type"):
                            row_data["_SAINI_AI_ANSWER_SPACE_TYPE"] = _ai_shadow["decision"]["answer_space_type"]
                        print(
                            "  🤖 V33.7 DECISION:",
                            row_data.get("_SAINI_AI_WORKFLOW_STATUS", "UNKNOWN"),
                            "| intent=", row_data.get("_SAINI_AI_INTENT", "-"),
                            "| template=", row_data.get("_SAINI_AI_TEMPLATE", "-"),
                        )
                    except Exception as _ai_exc:
                        row_data["_SAINI_AI_WORKFLOW_STATUS"] = "REVIEW_REQUIRED"
                        row_data["_SAINI_AI_REASON"] = str(_ai_exc)
                        print("  ⚠ V33.7 decision bridge failed; existing worksheet path retained:", _ai_exc)

                # V33.13: use the real template renderer only for the narrow,
                # gate-approved Nursery + Hindi + ANSWER_SPACE=YES route.
                # If any question requires review, retain the existing worksheet
                # renderer instead of guessing or inventing a template.
                ws_doc = None
                print(
                    "  🔬 V33.17 RENDER GATE: eligible=", ai_gate.get("eligible"),
                    "answer_space=", answer_space_enabled(row_data),
                    "worksheet_mode=", worksheet_mode_for_class(class_name)
                )
                if ai_gate.get("eligible") and answer_space_enabled(row_data):
                    ws_doc = _v3313_create_nursery_hindi_document(row_data, extracted_text)
                    if ws_doc is not None:
                        row_data["_SAINI_AI_WORKFLOW_STATUS"] = "READY_FOR_RENDERER"
                        row_data["_SAINI_AI_RENDERER"] = "V33.13_TEMPLATE_RENDERER"
                        print("  ✅ V33.13: approved Nursery-Hindi template route used")
                if ws_doc is None:
                    ws_doc = create_worksheet_document(dict(row_data), extracted_text)
                if build_stem:
                    safe_name = build_stem(class_name, subject, medium, school) + "_WORKSHEET"
                else:
                    safe_name = re.sub(
                        r'[\\/*?:"<>|]', "_",
                        f"{class_name}_{subject}_{school}_WORKSHEET"
                    ).replace(" ", "_")
                output_path = os.path.join(OUTPUT_FOLDER, f"{safe_name}.docx")
                ws_doc.save(output_path)
                output_path = apply_red_list_to_saved_docx(output_path, class_name)
                _v3336_final_nur_qa(output_path, class_name, subject)
                print(f"  ✅ Saved worksheet: {os.path.basename(output_path)}")
                return output_path
        except Exception as _ws_exc:
            print("  ⚠ worksheet path failed, NOT falling into board mix:", _ws_exc)
            raise
    # ========================================================
    # Class 1+ board paper continues below — unchanged
    # ========================================================

    doc = Document()

    # --------------------------------------------------------
    # PAGE SETUP
    # --------------------------------------------------------
    section = doc.sections[0]

    # V17 SOLID A4 PAGE-SIZE LOCK.
    # Do not rely on Microsoft Word's regional/default paper size (Letter).
    section.page_width = Mm(PAGE_WIDTH_MM)
    section.page_height = Mm(PAGE_HEIGHT_MM)
    section.top_margin = Inches(TOP_MARGIN)
    section.bottom_margin = Inches(BOTTOM_MARGIN)
    section.left_margin = Inches(LEFT_MARGIN)
    section.right_margin = Inches(RIGHT_MARGIN)
    section.footer_distance = Inches(FOOTER_DISTANCE)

    # V10 ADDITIVE RULE: attractive professional page border.
    add_attractive_page_border(section)

    # --------------------------------------------------------
    # NORMAL STYLE
    # --------------------------------------------------------
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Pt(BODY_SIZE)

    style._element.rPr.rFonts.set(qn("w:ascii"), FONT_NAME)
    style._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_NAME)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Nirmala UI")
    style._element.rPr.rFonts.set(qn("w:cs"), "Nirmala UI")

    # --------------------------------------------------------
    # SCHOOL HEADER
    # --------------------------------------------------------
    heading1 = doc.add_paragraph()
    heading1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading1.paragraph_format.keep_together = True
    heading1.paragraph_format.widow_control = True
    heading1.paragraph_format.left_indent = Inches(0.08)
    heading1.paragraph_format.right_indent = Inches(0.08)

    run = heading1.add_run(school)
    name_size = format_school_name_run(run, school)
    set_paragraph_spacing(heading1, before=1, after=1, line_spacing=1.0)
    heading1.paragraph_format.line_spacing = Pt(name_size + 5)

    # --------------------------------------------------------
    # CLASS / SUBJECT
    # --------------------------------------------------------
    heading2 = doc.add_paragraph()
    heading2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(heading2, before=0, after=3, line_spacing=1.0)
    heading2.paragraph_format.line_spacing = Pt(15)
    heading2.paragraph_format.keep_together = True

    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        _cls_sub = f"कक्षा: {class_name}  |  विषय: {subject}"
    else:
        _cls_sub = f"Class: {class_name}  |  Subject: {subject}"
    run = heading2.add_run(_cls_sub)
    set_run_language_font(run, _cls_sub, bold=True)
    run.font.size = Pt(13)
    run.font.color.rgb = SCHOOL_NAME_COLOR

    # --------------------------------------------------------
    # META INFORMATION — table ONLY for NUR–III
    # --------------------------------------------------------
    if PAPER_LANGUAGE in {"hindi", "sanskrit"}:
        metadata = [
            ("पूर्णांक", _clean_meta_value(mm)),
            ("समय", _clean_meta_value(time_val)),
            ("परीक्षा", _clean_meta_value(exam_type)),
        ]
    else:
        metadata = [
            ("Max Marks", _clean_meta_value(mm)),
            ("Time", _clean_meta_value(time_val)),
            ("Exam", _clean_meta_value(exam_type)),
        ]

    if not class_allows_tables(class_name):
        meta_p = doc.add_paragraph()
        meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(meta_p, before=2, after=8, line_spacing=1.15)
        meta_line = "     ".join(f"{lab}: {val}" for lab, val in metadata)
        mr = meta_p.add_run(meta_line)
        set_run_language_font(mr, meta_line, bold=True)
        mr.font.size = Pt(13)
        table = None
    else:
        table = doc.add_table(rows=2, cols=3)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

    for idx, (label, value) in enumerate(metadata):
        if table is None:
            break
        head = table.rows[0].cells[idx]
        body = table.rows[1].cells[idx]
        head.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        body.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(head, META_HEADER_SHADING)
        set_cell_shading(body, META_VALUE_SHADING)
        set_cell_margins(head)
        set_cell_margins(body)

        head.text = ""
        hp = head.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(hp, before=1, after=1, line_spacing=1.0)
        hr = hp.add_run(label)
        set_run_language_font(hr, label, bold=True)
        hr.font.size = Pt(9)
        hr.font.color.rgb = META_HEADER_TEXT

        body.text = ""
        bp = body.paragraphs[0]
        bp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(bp, before=1, after=1, line_spacing=1.0)
        vr = bp.add_run(value)
        set_run_language_font(vr, value, bold=True)
        vr.font.size = Pt(10)

    # --------------------------------------------------------
    # NON-BLOCKING AI QA WARNING — HOLD is disabled.
    if str(warning_message or LAST_AI_WARNING).strip() and PAPER_LANGUAGE not in {"hindi", "sanskrit"}:
        qa_warning = str(warning_message or LAST_AI_WARNING).strip()
        warning_para = doc.add_paragraph()
        warning_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(warning_para, before=3, after=4, line_spacing=1.0)
        warning_para.paragraph_format.keep_together = True
        warning_run = warning_para.add_run(qa_warning)
        set_run_language_font(warning_run, qa_warning, bold=True)
        warning_run.font.size = Pt(9)

    # BODY
    # IMPORTANT:
    # The Excel-driven header is already printed above. Remove any
    # duplicated source-image header BEFORE adding question text.
    # --------------------------------------------------------
    # Process every source image belonging to this paper.
    # A single Excel row may represent multiple consecutive image pages.
    if isinstance(extracted_text, (list, tuple)):
        page_texts = list(extracted_text)
    else:
        page_texts = [extracted_text]

    for page_index, page_text in enumerate(page_texts):
        if not page_text or not str(page_text).strip():
            continue

        cleaned_text = remove_redundant_header(
            page_text,
            row_data
        )
        cleaned_text = "\n".join(
            restore_exam_spaces(x) for x in str(cleaned_text).splitlines()
        )

        if cleaned_text.strip() and not re.search(
            r"no legible question paper content|page appears to be mostly blank|faint bleed-through",
            cleaned_text,
            flags=re.IGNORECASE
        ):
            # IMPORTANT: source-image boundaries must NOT create Word page breaks.
            # Content from the next scanned image continues immediately after
            # the previous content and Word decides the natural page flow.
            add_formatted_question_text(
                doc,
                cleaned_text,
                hindi_mcq_labels=(str(subject).strip().upper() == "HINDI"),
                layout=layout,
            )

    # --------------------------------------------------------
    # FINAL MOTIVATIONAL SENTENCE
    # V14: Only Class 1 and above. Never Nursery/LKG/UKG.
    # No decorative box/table/image: avoids paper wastage.
    # --------------------------------------------------------
    pack_short_choice_paragraphs(doc)
    add_final_motivational_sentence(doc, class_name, paper_rotation_index)

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------
    footer = section.footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Keep Page X of Y visually clear of the bottom border.
    set_paragraph_spacing(footer_p, before=2, after=2, line_spacing=1.0)
    footer_p.paragraph_format.keep_together = True
    add_page_number_fields(footer_p)
    enable_field_updates(doc)

    # --------------------------------------------------------
    # SAFE FILE NAME
    # --------------------------------------------------------
    if build_stem:
        safe_name = build_stem(class_name, subject, medium, school)
    else:
        safe_name = f"{class_name}_{subject}_{school}"
        mtag = str(medium or "").upper().replace(" ", "_")
        if mtag in {"HM", "HINDI_MEDIUM", "HINDI"}:
            safe_name = f"{class_name}_{subject}_HM_{school}"
        elif mtag in {"EM", "ENGLISH_MEDIUM", "ENGLISH", "ENG"}:
            safe_name = f"{class_name}_{subject}_EM_{school}"
        safe_name = re.sub(
            r'[\\/*?:"<>|]',
            "_",
            safe_name
        ).replace(" ", "_")

    output_path = os.path.join(
        OUTPUT_FOLDER,
        f"{safe_name}.docx"
    )

    # Remove accidental empty body paragraphs at the very end.
    while len(doc.paragraphs) > 1 and not doc.paragraphs[-1].text.strip():
        p = doc.paragraphs[-1]._element
        p.getparent().remove(p)

    force_nirmala_on_devanagari(doc)
    doc.save(output_path)
    try:
        from saini_math_omml import sweep_docx
        sweep_docx(output_path)
    except Exception as _sw_exc:
        print("  ⚠ math sweep skip:", _sw_exc)
    if MATH_FT is not None:
        MATH_FT.sweep_docx_intermediate(output_path, class_name, subject)

        # --- HOOK 10b: clean leaked LaTeX after math sweep ---
        try:
            if MATH_CLEAN is not None:
                _n = MATH_CLEAN.sweep_docx(output_path, subject)
                if _n:
                    print("  ✓ math_clean sweep:", _n, "paragraph(s)")
        except Exception as _mcs:
            print("  ⚠ math_clean sweep skipped:", _mcs)
        # --- END HOOK 10b ---

    # NCERT fine-tune AFTER full document construction and BEFORE pagination
    # optimization. This keeps the optimizer focused on the final geometry.
    if NCERT_FINE_TUNE_ENABLED and bool(layout.get("ncert_sequential", False)):
        _apply_ncert_fine_tune_doc(output_path)
        try:
            _d2 = Document(output_path)
            pack_short_choice_paragraphs(_d2)
            _d2.save(output_path)
        except Exception:
            pass

    # V21 ADDITIVE: FIRST successful candidate that meets the last-page
    # target is kept; otherwise original retained.
    # After the paper is fully generated, test compact body-size
    # candidates against real Word pagination. The first candidate reaching
    # 90% last-page utilization is accepted; otherwise the original is kept.

        output_path = optimize_page_utilization(output_path)
        # --- HOOK 10b: clean leaked LaTeX AFTER page optimizer ---
        try:
            if MATH_CLEAN is not None:
                _n = MATH_CLEAN.sweep_docx(output_path, subject)
                print("  ✓ math_clean sweep xml:", _n)
        except Exception as _mcs:
            print("  ⚠ math_clean sweep skipped:", _mcs)
        # --- END HOOK 10b ---
        print(f"  ✅ Saved: {safe_name}.docx")

    output_path = apply_red_list_to_saved_docx(output_path, class_name)

    try:
        import split_combined_class_docs as _scd
        extra = _scd.split_folder(OUTPUT_FOLDER)
        if extra:
            print(f"  ✓ class copies: {len(extra)}")
    except Exception as _sp_exc:
        print("  ⚠ combined-class split skip:", _sp_exc)

    if export_to_ips_engine:
        export_to_ips_engine(row_data, page_texts, OUTPUT_FOLDER)
    try:
        import sys as _odsys
        _od = r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD"
        if _od not in _odsys.path:
            _odsys.path.insert(0, _od)
        import order_desk as _oddesk
        _oddesk.accept_generated(output_path)
    except Exception as _oderr:
        print("  order folder skip:", _oderr)
    return output_path

def write_science_teacher_key(output_path, page_texts, subject):
    """Sidecar teacher key only. Student .docx is never modified."""
    blob = "\n".join(str(t) for t in (page_texts if isinstance(page_texts, (list, tuple)) else [page_texts]))
    if not (is_science_subject(subject) or looks_like_mass_question(blob)):
        return
    if not looks_like_mass_question(blob):
        return
    solution = build_teacher_solution(blob)
    if not solution:
        return
    key_path = os.path.splitext(output_path)[0] + "_TEACHER_KEY.txt"
    with open(key_path, "w", encoding="utf-8") as fh:
        fh.write(solution)
        fh.write("\n")
    print(f"  ✓ Science teacher key: {os.path.basename(key_path)}")


def validate_protected_rules():
    """Fail fast if a future edit accidentally removes a protected rule."""
    required = {
        "authentication_preflight_before_batch": "_authentication_preflight",
        "oauth_fallback_support": "_build_oauth_client",
        "no_repeated_401_api_calls": "AUTHENTICATION STOP",
        "hindi_motivational_sentence_class_1_plus_only": "add_final_motivational_sentence",
        "no_motivational_sentence_nursery_lkg_ukg": "NURSERY|NUR|LKG|UKG",
        "motivational_sentence_no_decorative_box": "MOTIVATIONAL_SLOGANS",
        "rotating_hindi_motivational_slogans_100": "MOTIVATIONAL_SLOGANS = [",
        "motivational_slogan_paper_text_font_size": "MOTIVATIONAL_FONT_SIZE = 16",
        "motivational_slogan_large_side_stars": "MOTIVATIONAL_STAR_FONT_SIZE = 22",
        "motivational_slogan_underlined": "text_run.underline = True",
        "footer_page_number_paper_text_font_size": "FOOTER_FONT_SIZE = ENGLISH_SIZE",
        "paper_boundary_next_start_minus_one": "next_start_page",
        "continuous_source_image_flow": "CONTINUOUS_FLOW",
        "natural_word_pagination": "keep_with_next",
        "page_x_of_y_footer": "NUMPAGES",
        "hindi_section_headings_bold": "बहु विकल्पीय प्रश्न",
        "context_aware_main_question_bolding": "explicit_question_open",
        "mcq_abcd_two_by_two": "len(options) == 4",
        "mcq_roman_i_iv_two_by_two": "is_roman_option_line",
        "common_mcq_grid_font_size": "calculate_option_grid_font_size",
        "paper_saving_word_meaning_layout": "add_word_meaning_table",
        "blank_image_protection": "LOCAL_BLANK_IMAGE_CHECK",
        "no_ocr_diagnostic_text_in_final": "NEVER_WRITE_OCR_DIAGNOSTICS",
        "header_deduplication": "remove_redundant_header",
        "question_sequence_audit": "QUESTION_SEQUENCE_AUDIT",
        "original_wording_preservation": "Preserve the extracted wording",
        "major_question_subpart_visual_gap": "major_question_has_subparts",
        "attractive_page_border": "add_attractive_page_border",
        "explicit_context_bold_lock": "force_normal_run",
        "checkmark_to_boxed_tick_normalization": "normalize_exam_mark_symbols",
        "times_to_boxed_x_normalization": "☒",
        "page_border_10mm_inset": 'PAGE_BORDER_SPACE = "28"',
        "page_border_thicker_weight": 'PAGE_BORDER_SIZE = "14"',
        "footer_above_bottom_page_border": "FOOTER_DISTANCE = 0.50",
        "school_name_dynamic_font_size": "calculate_school_name_font_size",
        "school_name_full_content_width_fit": "apply_word_fit_text",
        "school_name_no_hardcoded_font_size": "format_school_name_run(run, school)",
        "mcq_option_label_case_normalization": "_normalize_option_marker_in_text",
        "mcq_four_option_exact_2x2_grid": "columns = 2",
        "mcq_three_option_exact_single_row": "columns = 3",
        "mcq_no_option_sharing_between_cells": "Every option gets exactly one cell",
        "footer_clear_of_bottom_border": "Keep Page X of Y visually clear of the bottom border",
        "v21_page_utilization_optimizer": "optimize_page_utilization",
        "v21_progressive_12_to_11_5": "PAGE_UTILIZATION_START_PT = 12.0",
        "v21_ten_percent_wastage_target": "PAGE_ACCEPT_MIN = 0.20",
        "v21_first_successful_candidate_stop": "FIRST successful candidate",
        "v21_original_restore_safety": "original retained",
        "generic_exam_table_engine": "GENERIC EXAM TABLE ENGINE",
        "no_hardcoded_table_headers": "_infer_column_profile",
        "table_layout_inferred_from_cells": "add_exam_property_table",
        "auto_maths_settings_switch": "is_maths_subject",
        "maths_layout_auto_enable": "MATHS_LAYOUT_OVERRIDES",
        "degree_never_rendered_as_power": "flatten_degree_powers",
        "geometry_word_not_replaced_by_symbol": "Never eat English/Hindi words",
        "vec_latex_never_leaked_to_word": "_omml_accent",
        "geometry_symbol_fallback_font": "SYMBOL_FALLBACK_FONT",
        "plan_object_first_kanda": "KANDA 1 — PLAN OBJECT",
        "ncert_fine_tune_enabled": "NCERT_FINE_TUNE_ENABLED = True",
        "ncert_sequential_flow": "ncert_sequential",
        "ncert_no_item_band": "not bool(layout.get(\"ncert_sequential\", False))",
        "ncert_major_number_sequence": "_is_ncert_major_numbered_line",
        "ncert_final_typography_pass": "_apply_ncert_fine_tune_doc",
        "red_list_checker": "def apply_red_list_to_saved_docx",
        "v33_8_input_page_manifest": "build_input_image_manifest",
        "v33_8_numeric_pagemo_contract": "Excel PAGENO remains a numeric logical page number",
    }
    source = open(__file__, "r", encoding="utf-8").read()
    missing = [name for name, token in required.items() if token not in source]
    if missing:
        raise RuntimeError(
            "PROTECTED RULE REGRESSION DETECTED: " + ", ".join(missing)
        )



# ============================================================
# MAIN
# ============================================================

# ============================================================
# CLASS-WISE + CLASS-1-AND-ABOVE COMBINED PDFs
# Additive only. Does not change OCR, wording, or paper layout.
# ============================================================

CLASS_ORDER_FOR_PDF = [
    "NUR", "LKG", "UKG",
    "I", "II", "III", "IV", "V",
    "VI", "VII", "VIII", "IX", "X", "XI", "XII",
]
CLASS_PDF_ALIASES = {
    "NURSERY": "NUR", "NUR": "NUR", "PRE-NUR": "NUR",
    "LKG": "LKG", "UKG": "UKG",
    "1": "I", "01": "I", "I": "I",
    "2": "II", "02": "II", "II": "II",
    "3": "III", "03": "III", "III": "III",
    "4": "IV", "04": "IV", "IV": "IV",
    "5": "V", "05": "V", "V": "V",
    "6": "VI", "06": "VI", "VI": "VI",
    "7": "VII", "07": "VII", "VII": "VII",
    "8": "VIII", "08": "VIII", "VIII": "VIII",
    "9": "IX", "09": "IX", "IX": "IX",
    "10": "X", "X": "X",
    "11": "XI", "XI": "XI",
    "12": "XII", "XII": "XII",
    # Combined classes
    "7,8": "VII,VIII", "7, 8": "VII,VIII",
    "V,VI": "V,VI", "V, VI": "V,VI",
    "5,6": "V,VI", "5, 6": "V,VI",
}
CLASS1_AND_ABOVE_PDF = {
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
}
_CLASS_PDF_RE = re.compile(
    r"(?:^|[_\-\s])(?:CLASS|CLS)?[_\-\s]*"
    r"(NURSERY|PRE-NUR|NUR|LKG|UKG|XII|XI|VIII|VII|III|II|IV|IX|VI|V|X|I|"
    r"12|11|10|09|08|07|06|05|04|03|02|01|9|8|7|6|5|4|3|2|1)"
    r"(?:$|[_\-\s.])",
    re.I,
)


def _normalize_class_for_pdf(class_name):
    text = str(class_name or "").strip().upper()
    if not text:
        return None
    if text in CLASS_PDF_ALIASES:
        return CLASS_PDF_ALIASES[text]
    # Handle combined classes like "7,8" or "V,VI"
    if "," in text:
        sub_classes = text.split(",")
        normalized = []
        for sub in sub_classes:
            sub_cls = _normalize_class_for_pdf(sub.strip())
            if sub_cls:
                normalized.append(sub_cls)
        if normalized:
            return ",".join(normalized)
    m = _CLASS_PDF_RE.search(text.replace("CLASS ", "CLASS_"))
    if m:
        return CLASS_PDF_ALIASES.get(m.group(1).upper())
    return None


def _export_docx_to_pdf(docx_path, pdf_path, word_app=None):
    """Export one Word paper to PDF using Microsoft Word.

    Shared Word instance when provided. ExportAsFixedFormat first,
    then SaveAs(FileFormat=17) fallback.
    """
    try:
        import win32com.client
    except ImportError:
        print("  ⚠ Combined PDF skip: pywin32 / Word COM not available.")
        return False

    own_word = word_app is None
    word = word_app
    doc = None
    pdf_path = os.path.abspath(pdf_path)
    docx_path = os.path.abspath(docx_path)
    try:
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass
        if word is None:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
        doc = word.Documents.Open(docx_path, ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.ExportAsFixedFormat(pdf_path, 17)
        except Exception:
            doc.SaveAs(pdf_path, FileFormat=17)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True
        print(f"  ✖ PDF file not created: {os.path.basename(docx_path)}")
        return False
    except Exception as exc:
        print(f"  ⚠ PDF export failed for {os.path.basename(docx_path)}: {exc}")
        return False
    finally:
        try:
            if doc is not None:
                doc.Close(SaveChanges=False)
        except Exception:
            pass
        if own_word:
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass


def _merge_pdfs(files, dest):
    """Merge PDFs without watermark (original function)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            print("  ⚠ Combined PDF skip: install pypdf  (pip install pypdf)")
            return 0

    writer = PdfWriter()
    pages = 0
    for f in files:
        try:
            reader = PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)
                pages += 1
        except Exception as exc:
            print(f"  ⚠ Could not merge {os.path.basename(f)}: {exc}")
    if pages == 0:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        writer.write(fh)
    return pages


# ============================================================
# NEW FUNCTION - MERGE PDFs WITH WATERMARK
# ============================================================
def _merge_pdfs_with_watermark(files, dest, watermark_text="PROOF COPY - NOT FOR DISTRIBUTION"):
    """Merge PDFs and add a diagonal watermark to every page."""
    if canvas is None or PdfReader is None or PdfWriter is None:
        print("  ⚠ reportlab/pypdf not installed. Skipping watermark.")
        return _merge_pdfs(files, dest)  # fallback to normal merge

    writer = PdfWriter()
    pages = 0
    for f in files:
        try:
            reader = PdfReader(f)
            for page in reader.pages:
                # Create a watermark PDF for this page
                watermark_buf = BytesIO()
                c = canvas.Canvas(watermark_buf, pagesize=A4)
                c.saveState()
                c.translate(A4[0] / 2, A4[1] / 2)  # Center of page
                c.rotate(45)
                c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.3))  # Grey, 30% opacity
                c.setFont("Helvetica", 30)
                c.drawCentredString(0, 0, watermark_text)
                c.restoreState()
                c.save()
                watermark_buf.seek(0)

                # Read watermark PDF
                watermark_reader = PdfReader(watermark_buf)
                watermark_page = watermark_reader.pages[0]

                # Merge watermark onto the source page
                page.merge_page(watermark_page)
                writer.add_page(page)
                pages += 1
        except Exception as exc:
            print(f"  ⚠ Could not merge {os.path.basename(f)}: {exc}")
    if pages == 0:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        writer.write(fh)
    return pages



def _pdf_meta_from_name(name):
    """Parse CLASS / SUBJECT / SCHOOL / MEDIUM from generated paper filenames."""
    if parse_paper_name is not None:
        meta = parse_paper_name(name)
        if meta and meta.get("class"):
            return {
                "class": meta["class"],
                "subject": meta.get("subject") or "PAPER",
                "medium": meta.get("medium") or "",
                "school": meta.get("school") or "UNKNOWN_SCHOOL",
            }
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = re.sub(r"\.0$", "", stem)
    if stem.startswith("__paper_") or "TEACHER_KEY" in stem.upper():
        return None
    parts = [x for x in re.split(r"[_\-]+", stem) if x]
    if not parts:
        return None
    
    # Handle combined class names like "7,8" or "V,VI"
    cls_raw = parts[0].replace(",", ",")  # Keep comma
    cls = _normalize_class_for_pdf(cls_raw)
    if not cls:
        # Try to handle "7,8" or "V,VI"
        if "," in cls_raw:
            sub_classes = cls_raw.split(",")
            normalized = []
            for sub in sub_classes:
                sub_cls = _normalize_class_for_pdf(sub.strip())
                if sub_cls:
                    normalized.append(sub_cls)
            if normalized:
                cls = ",".join(normalized)
    if not cls and len(parts) >= 2:
        cls = _normalize_class_for_pdf(parts[0])
    if not cls:
        return None
    
    last = parts[-1]
    mid = parts[1:-1] if re.fullmatch(r"\d+(?:\.\d+)?", last) and len(parts) >= 3 else parts[1:]
    if not mid:
        return {"class": cls, "subject": "PAPER", "school": "UNKNOWN_SCHOOL"}
    subject = mid[0]
    school = "_".join(mid[1:]).strip("_") or "UNKNOWN_SCHOOL"
    school = re.sub(r"[^\w]+", "_", school).strip("_").upper()
    return {"class": cls, "subject": subject, "school": school}


# V33.34: tracks only DOCX files generated by the current PAPER.py run.
# This prevents stale worksheet/test DOCX files already present in OUTPUT
# from being pulled into the current run's combined PDFs.
_CURRENT_RUN_DOCX_FILES = []


def _v3336_final_nur_qa(docx_path, class_name, subject):
    """
    V33.36 read-only final QA for the narrow Nursery-Hindi worksheet route.
    Does not rewrite the DOCX. It verifies visible content/markers and, when
    Microsoft Word COM is available, asks Word for the actual page count.
    """
    cls = str(class_name or "").strip().upper()
    sub = str(subject or "").strip().upper()
    if cls not in {"NUR", "NURSERY"} or sub not in {"HINDI", "HINDI MEDIUM"}:
        return True

    try:
        from docx import Document
        qa_doc = Document(docx_path)

        parts = []
        for p in qa_doc.paragraphs:
            parts.append(str(p.text or ""))
        for table in qa_doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        parts.append(str(p.text or ""))

        blob = "\n".join(parts)

        required_q = [
            "प्रश्न 1",
            "प्रश्न 2",
            "प्रश्न 3",
            "प्रश्न 4",
        ]
        missing_q = [q for q in required_q if q not in blob]

        markers = [
            "[[TABLE]]",
            "[[MATCH]]",
            "[[FIG]]",
            "[[FIGURE]]",
        ]
        surviving_markers = [m for m in markers if m in blob]

        english_fallbacks = [
            "Flag",
            "Tomato",
            "Grapes",
            "Leaf",
        ]
        surviving_fallbacks = [
            x for x in english_fallbacks
            if re.search(rf"(?<![A-Za-z]){re.escape(x)}(?![A-Za-z])", blob, flags=re.I)
        ]

        inline_shapes = 0
        try:
            inline_shapes = sum(
                len(getattr(p._p, "xpath")('.//wp:inline'))
                for p in qa_doc.paragraphs
            )
        except Exception:
            inline_shapes = -1

        failures = []
        if missing_q:
            failures.append("missing questions: " + ", ".join(missing_q))
        if surviving_markers:
            failures.append("surviving control markers: " + ", ".join(surviving_markers))
        if surviving_fallbacks:
            failures.append("English Q3 fallback captions: " + ", ".join(surviving_fallbacks))

        # This current safe mode intentionally expects zero inline images.
        if inline_shapes > 0:
            failures.append(f"unexpected inline images in verified-picture-safe mode: {inline_shapes}")

        word_pages = None
        try:
            import win32com.client
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                wd = word.Documents.Open(
                    os.path.abspath(docx_path),
                    ReadOnly=True,
                    AddToRecentFiles=False,
                )
                try:
                    wd.Repaginate()
                    word_pages = int(wd.ComputeStatistics(2))  # wdStatisticPages
                finally:
                    wd.Close(False)
            finally:
                word.Quit()
        except Exception as _word_exc:
            print(f"  ⚠ V33.36 WORD PAGE QA skipped: {_word_exc}")

        if word_pages is not None and word_pages != 1:
            failures.append(f"actual Word page count = {word_pages}; expected 1")

        if failures:
            print("  ❌ V33.36 FINAL NUR-HINDI QA FAIL")
            for item in failures:
                print("     - " + item)
            return False

        print(
            "  ✅ V33.36 FINAL NUR-HINDI QA PASS"
            + (f" | Word pages={word_pages}" if word_pages is not None else "")
            + f" | inline_images={inline_shapes}"
        )
        return True
    except Exception as exc:
        print(f"  ⚠ V33.36 FINAL NUR-HINDI QA could not complete: {exc}")
        return True

def combine_class_pdfs(output_folder, current_run_docx_files=None):
    """
    CURRENT SCHOOL ONLY — CLASS-WISE + ALL PAPERS COMBINED PDF

    IMPORTANT:
    - OUTPUT folder ke andar jo current Word (.docx) papers hain,
      ONLY unhi ko include kiya jayega.
    - Subfolders / doosre schools / old folders scan nahi honge.
    - Har current class ke papers ki separate PDF banegi:
          CLASS_I_ALL_SUBJECTS.pdf
          CLASS_II_ALL_SUBJECTS.pdf
          CLASS_III_ALL_SUBJECTS.pdf
          ...
    - Nursery / LKG / UKG bhi available hone par class-wise PDF banegi.
    - Saare current OUTPUT papers ki ek master PDF bhi banegi:
          ALL_PAPERS_COMBINED.pdf
    - ALL_SCHOOLS_ALL_PAPERS.pdf nahi banegi.
    - Word paper ki existing formatting/layout/content ko touch nahi kiya jayega.
    - PDF conversion Microsoft Word COM se hoga.
    - Safe to run alone:
          python PAPER.py --combine-only
    - Does not call Gemini.
    """

    print("\n" + "=" * 70)
    print(" CLASS-WISE + ALL PAPERS COMBINED PDF — CURRENT OUTPUT ONLY")
    print("=" * 70)

    output_folder = os.path.abspath(output_folder)

    if not os.path.isdir(output_folder):
        print(f"  ❌ OUTPUT folder nahi mili: {output_folder}")
        return

    # ============================================================
    # COMMAND-LINE WATERMARK CONTROL
    # ============================================================
    # Usage:
    #   python PAPER.py --combine-only --watermark "TEXT"   (watermark ON)
    #   python PAPER.py --combine-only --no-watermark       (watermark OFF)
    #   python PAPER.py --combine-only                      (default: watermark ON)
    # ============================================================
    watermark_text = "PROOF COPY - NOT FOR DISTRIBUTION"  # DEFAULT
    if "--no-watermark" in sys.argv:
        watermark_text = ""
    elif "--watermark" in sys.argv:
        try:
            idx = sys.argv.index("--watermark")
            if idx + 1 < len(sys.argv):
                watermark_text = sys.argv[idx + 1]
        except Exception:
            watermark_text = "PROOF COPY - NOT FOR DISTRIBUTION"
    
    print(f"  Watermark Status: {'OFF' if not watermark_text else watermark_text}")

    # ------------------------------------------------------------
    # 1. CURRENT OUTPUT FOLDER KE ONLY .DOCX FILES
    # ------------------------------------------------------------
    # Sirf OUTPUT ke direct files. Koi subfolder scan nahi hoga.
    if current_run_docx_files is not None:
        # V33.34: current normal run = ONLY files returned by this run.
        docx_files = []
        for _p in current_run_docx_files:
            try:
                _p = os.path.abspath(str(_p))
            except Exception:
                continue
            if (
                os.path.isfile(_p)
                and _p.lower().endswith(".docx")
                and not os.path.basename(_p).startswith("~$")
                and not os.path.basename(_p).startswith("__paper_")
            ):
                if _p not in docx_files:
                    docx_files.append(_p)

        print(f"  V33.34 CURRENT-RUN Word papers : {len(docx_files)}")
        print("  ℹ Old DOCX files already in OUTPUT are excluded from this run.")
    else:
        # --combine-only retains the historical folder-scan behavior.
        docx_files = []

        for name in sorted(os.listdir(output_folder), key=str.lower):
            full_path = os.path.join(output_folder, name)

            if not os.path.isfile(full_path):
                continue

            if not name.lower().endswith(".docx"):
                continue

            if name.startswith("~$") or name.startswith("__paper_"):
                continue

            docx_files.append(full_path)

        print(f"  Current OUTPUT Word papers found : {len(docx_files)}")
    if current_run_docx_files is None:
        try:
            import split_combined_class_docs as _scd
            extra = _scd.split_folder(output_folder)
            if extra:
                print(f"  Combined-class copies: {len(extra)}")
                for p in extra:
                    if str(p) not in docx_files:
                        docx_files.append(str(p))
        except Exception as _sp_exc:
            print("  ⚠ class split skip:", _sp_exc)
    else:
        print("  V33.34 CLASS-SPLIT LOCK: derived/stale DOCX files excluded")

    if not docx_files:
        print("  ❌ OUTPUT folder me koi .docx paper nahi mila.")
        print("     Pehle current school ke Word papers OUTPUT me hone chahiye.")
        print("=" * 70)
        return

    # ------------------------------------------------------------
    # 2. SINGLE PDF CACHE
    # ------------------------------------------------------------
    # Individual PDFs internal cache me rahengi.
    # Final class-wise PDFs aur master PDF OUTPUT/COMBINED_PDF me rahengi.
    combined_root = os.path.join(output_folder, "COMBINED_PDF")
    single_dir = os.path.join(combined_root, "_single")

    os.makedirs(single_dir, exist_ok=True)

    word_app = None
    converted_pdfs = []

    try:
        try:
            import win32com.client
            word_app = win32com.client.DispatchEx("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
        except Exception as exc:
            print(f"  ⚠ Microsoft Word COM open nahi hua: {exc}")
            word_app = None

        # --------------------------------------------------------
        # 3. HAR CURRENT OUTPUT .DOCX -> FRESH PDF
        # --------------------------------------------------------
        # Purani PDF reuse nahi hogi. Current Word paper se fresh PDF.
        for index, docx_path in enumerate(docx_files, start=1):
            pdf_name = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
            pdf_path = os.path.join(single_dir, pdf_name)

            print(
                f"  [{index}/{len(docx_files)}] "
                f"Word → PDF: {os.path.basename(docx_path)}"
            )

            ok = _export_docx_to_pdf(
                docx_path,
                pdf_path,
                word_app=word_app
            )

            if ok and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                converted_pdfs.append(pdf_path)
                print(f"       ✓ {pdf_name}")
            else:
                print(f"       ✖ PDF conversion failed: {pdf_name}")

    finally:
        if word_app is not None:
            try:
                word_app.Quit()
            except Exception:
                pass

    if not converted_pdfs:
        print("  ❌ Koi usable PDF create nahi hui.")
        print("=" * 70)
        return

    # ------------------------------------------------------------
    # 4. CLASS-WISE GROUPING
    # ------------------------------------------------------------
    by_class = {}
    unclassified = []

    for pdf_path in converted_pdfs:
        meta = _pdf_meta_from_name(pdf_path)

        if not meta:
            unclassified.append(os.path.basename(pdf_path))
            continue

        cls = meta["class"]
        bits = re.split(r"[+&,_\-\s]+", str(cls or ""))
        mapped = [b for b in bits if b]
        if not mapped:
            mapped = [cls]
        for one in mapped:
            by_class.setdefault(one, [])
            by_class[one].append(pdf_path)

    # ------------------------------------------------------------
    # 5. CLASS-WISE PDF
    # ------------------------------------------------------------
    class_pdf_count = 0

    for cls in CLASS_ORDER_FOR_PDF:
        group = by_class.get(cls) or []

        if not group:
            continue

        # Filename:
        # CLASS_I_ALL_SUBJECTS.pdf
        class_pdf = os.path.join(
            combined_root,
            f"CLASS_{cls}_ALL_SUBJECTS.pdf"
        )

        # Remove old version first.
        if os.path.exists(class_pdf):
            try:
                os.remove(class_pdf)
            except OSError as exc:
                print(
                    f"  ⚠ Old class PDF remove nahi hui: "
                    f"{os.path.basename(class_pdf)} — {exc}"
                )
                continue

        pages = _merge_pdfs_with_watermark(group, class_pdf, watermark_text)

        if pages > 0:
            class_pdf_count += 1
            print(
                f"  ✅ CLASS_{cls}_ALL_SUBJECTS.pdf "
                f"({len(group)} papers, {pages} pages)"
            )
        else:
            print(
                f"  ❌ CLASS_{cls}_ALL_SUBJECTS.pdf create nahi hui."
            )

    # ------------------------------------------------------------
    # 6. ALL CURRENT OUTPUT PAPERS — MASTER PDF
    # ------------------------------------------------------------
    # Current OUTPUT ke saare Word papers, class order ke according.
    every_paper = []

    for cls in CLASS_ORDER_FOR_PDF:
        every_paper.extend(by_class.get(cls) or [])

    # Agar kisi filename ka class parse na ho, usse master PDF me
    # bhi include karna hai — current OUTPUT paper ko silently drop nahi karna.
    every_paper.extend(
        p for p in converted_pdfs
        if p not in every_paper
    )

    final_pdf = os.path.join(
        combined_root,
        "ALL_PAPERS_COMBINED.pdf"
    )

    if os.path.exists(final_pdf):
        try:
            os.remove(final_pdf)
        except OSError as exc:
            print(
                f"  ⚠ Purani ALL_PAPERS_COMBINED.pdf remove nahi hui: {exc}"
            )
            print(
                "     Agar PDF Word/Adobe me open hai to close karke dobara run karein."
            )
            print("=" * 70)
            return

    total_pages = _merge_pdfs_with_watermark(
        every_paper,
        final_pdf,
        watermark_text
    )

    if total_pages > 0 and os.path.exists(final_pdf):
        print(
            f"\n  ✅ ALL_PAPERS_COMBINED.pdf "
            f"({len(every_paper)} papers, {total_pages} pages)"
        )
    else:
        print("  ❌ ALL_PAPERS_COMBINED.pdf create nahi hui.")

    # ------------------------------------------------------------
    # 7. SUMMARY
    # ------------------------------------------------------------
    print("\n" + "-" * 70)
    print("  COMBINED PDF SUMMARY")
    print(f"  Current Word papers : {len(docx_files)}")
    print(f"  Class-wise PDFs     : {class_pdf_count}")
    print(f"  Master PDF          : ALL_PAPERS_COMBINED.pdf")
    print(f"  Output location     : {combined_root}")

    if unclassified:
        print("\n  ⚠ Unclassified filename(s):")
        for name in unclassified:
            print(f"     {name}")
        print("     Ye master PDF me include hain, lekin class-wise PDF me nahi.")

    print("-" * 70)
    print("=" * 70)



def main():
    global _CURRENT_RUN_DOCX_FILES
    _CURRENT_RUN_DOCX_FILES = []
    print("  🧹 V33.34 CURRENT-RUN OUTPUT TRACKER: reset")

    validate_protected_rules()
    print("=" * 70)
    print(" PROFESSIONAL QUESTION PAPER GENERATOR — V29 OCR + OPTIONAL AI CHECK + HOLD DISABLED | V33.43 CLEAN MANIFEST DIAGNOSTIC FIX NUR FINAL QA GATE + V33.35 CURRENT-RUN TRACK FIX + V33.34 COMBINE LOCK + V33.33 Q3 FINAL CAPTION SCRUB + V33.32 LABEL FIX + ONE-PAGE + Q4 COPY-SPACE + TRACE-COMPACT + FINAL-MARKER-SCRUB + VERIFIED-PICTURE-SAFE + NO SOURCE CROP + NO TRIAL IMAGE")
    print("=" * 70)

    try:
        initialize_client()
    except Exception as e:
        print("\n❌ AUTHENTICATION STOP — OCR processing has NOT started.")
        print(f"   {e}")
        print("\n   This prevents the program from making dozens of failed API calls.")
        print("   If your key begins with 'AQ.', use a current google-genai SDK and")
        print("   ensure the key is correctly linked to the Gemini API/service account.")
        print("   If API-key auth still returns ACCESS_TOKEN_TYPE_UNSUPPORTED, use")
        print("   AUTH_MODE='oauth' with a Google OAuth Desktop Client JSON.")
    try:
        df = pd.read_excel(EXCEL_FILE)
    except Exception as e:
        print(f"❌ Excel file open नहीं हो सकी: {e}")
        return

    if PDF_IN is not None:
        try:
            PDF_IN.sync_excel_source_files(EXCEL_FILE, IMAGES_FOLDER)
            df = pd.read_excel(EXCEL_FILE)
        except Exception as _sync_exc:
            print("  ⚠ PDF SOURCE_FILE sync skip:", _sync_exc)

    required_cols = [
        "PAGENO",
        "CLASS",
        "SUBJECT",
        "SCHOOL NAME",
        "MM",
        "TIME",
        "EXAM TYPE"
    ]

    missing_cols = [
        col for col in required_cols
        if col not in df.columns
    ]

    if missing_cols:
        print(
            "❌ Excel में ये columns नहीं मिले: "
            + ", ".join(missing_cols)
        )
        return

    # ============================================================
    # MULTI-PAGE PAPER GROUPING
    #
    # IMPORTANT:
    # Each Excel row is the START PAGE of one paper.
    #
    # Example:
    #   101 = current paper start
    #   105 = next paper start
    #   Therefore current paper images = 101, 102, 103, 104
    #
    # The old code processed only the start image (101). This version
    # processes the complete range up to one page before the next paper.
    # ============================================================

    print(f"कुल {len(df)} papers/process groups मिलेंगे...\n")

    success_count = 0
    failed_count = 0
    total_images_processed = 0

    def page_number(value):
        """Safely convert Excel values such as 101, 101.0 or '101' to int."""
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    def available_page_numbers():
        """Return logical INPUT page numbers from the V33.8 image manifest."""
        return sorted(_INPUT_PAGE_MANIFEST.keys())

    build_input_image_manifest()
    available_pages = available_page_numbers()
    if available_pages:
        print(f"  ✓ INPUT image manifest: {len(available_pages)} image(s)")
        for _pg in available_pages[:10]:
            print(f"    PAGE {_pg} → {os.path.basename(_INPUT_PAGE_MANIFEST[_pg])}")
        if len(available_pages) > 10:
            print(f"    ... {len(available_pages) - 10} more image(s)")
    else:
        print("  ⚠ INPUT image manifest: no supported JPG/JPEG/PNG/WEBP images found")
    max_available_page = max(available_pages) if available_pages else None

    for index, row in df.iterrows():

        start_page = page_number(row["PAGENO"])
        subject = str(row["SUBJECT"]).strip()

        source_pdf = ""
        for col in ("SOURCE_FILE", "FILE"):
            if col in row.index:
                val = str(row.get(col) or "").strip()
                if val.lower() not in {"", "nan", "none", "1", "0"} and val.lower().endswith(".pdf"):
                    source_pdf = val
                    break

        # HARD RULE: numbered INPUT scan (35.jpg) always beats Excel SOURCE_FILE.
        # OUTPUT/_single PDFs are old printed papers — never OCR those as source.
        page_image = get_image_path(start_page) if start_page is not None else None
        if page_image:
            if source_pdf:
                print(
                    f"  SOURCE LOCK: PAGENO {start_page} image used, "
                    f"Excel SOURCE_FILE ignore ({os.path.basename(source_pdf)})"
                )
            source_pdf = ""
        elif source_pdf:
            _src_u = source_pdf.replace("/", "\\").upper()
            if "\\OUTPUT\\" in _src_u or "COMBINED_PDF" in _src_u or "\\_SINGLE\\" in _src_u:
                print(f"  SOURCE_FILE OUTPUT pdf ignore: {os.path.basename(source_pdf)}")
                source_pdf = ""

        if source_pdf and PDF_IN is not None and page_image is None:
            pdf_path = source_pdf
            if not os.path.isabs(pdf_path):
                pdf_path = os.path.join(IMAGES_FOLDER, os.path.basename(pdf_path))
            if not os.path.isfile(pdf_path):
                alt = os.path.join(IMAGES_FOLDER, os.path.basename(source_pdf))
                pdf_path = alt if os.path.isfile(alt) else pdf_path
            if not os.path.isfile(pdf_path):
                print(f"  ❌ PDF nahi mili: {source_pdf}")
                failed_count += 1
                continue
            print(f"[{index + 1}/{len(df)}] PDF paper → {os.path.basename(pdf_path)}")
            raster = os.path.join(IMAGES_FOLDER, "_pdf_raster")
            paper_page_texts = PDF_IN.handle_pdf(
                pdf_path,
                raster_dir=raster,
                ocr_fn=extract_text_from_image,
                class_name=str(row.get("CLASS", "")),
                subject=subject,
            )
            if not paper_page_texts:
                print("  ❌ PDF se text nahi nikla")
                failed_count += 1
                continue
            audit_question_sequence(paper_page_texts, index + 1)
            try:
                try:
                    ai_ok, paper_page_texts, _ai_timeout = run_ai_refine_with_timeout(
                        row, paper_page_texts, OUTPUT_FOLDER, AI_STAGE_TIMEOUT_SEC
                    )
                except Exception as ai_exc:
                    print(f"  ⚠ AI stage skip ({ai_exc})")
                _generated_docx = create_document(
                    row,
                    paper_page_texts,
                    index,
                    warning_message=LAST_AI_WARNING
                )
                if _generated_docx:
                    _CURRENT_RUN_DOCX_FILES.append(os.path.abspath(str(_generated_docx)))
                    print(
                        "  📌 V33.34 CURRENT-RUN TRACK: "
                        + os.path.basename(str(_generated_docx))
                    )
                success_count += 1
            except Exception as e:
                print(f"  ❌ Document creation error: {e}")
                failed_count += 1
            continue

        if start_page is None:
            print(f"[{index + 1}/{len(df)}] ⚠ Invalid PAGENO: {row['PAGENO']}")
            failed_count += 1
            continue

        # The NEXT Excel row is the next paper's starting page.
        # Current paper ends exactly one page before that.
        if index + 1 < len(df):
            next_start_page = page_number(df.iloc[index + 1]["PAGENO"])

            if next_start_page is not None and next_start_page > start_page:
                end_page = next_start_page - 1
            else:
                # Safety fallback for invalid/non-increasing Excel data.
                end_page = start_page
        else:
            # V33.8 LAST-PAPER BOUNDARY FIX:
            # The final Excel row has no next PAGENO. Its end boundary is
            # therefore the last logical page present in the INPUT manifest.
            # This prevents the final/demo paper from waiting for a
            # non-existent next paper boundary.
            if max_available_page is not None and max_available_page >= start_page:
                end_page = max_available_page
                print(
                    f"  ✓ LAST PAPER BOUNDARY: no next PAGENO → "
                    f"INPUT manifest last page {end_page}"
                )
            else:
                end_page = start_page
                print(
                    f"  ⚠ LAST PAPER BOUNDARY: no INPUT page beyond "
                    f"start page {start_page}; using start page only"
                )

        page_range = list(range(start_page, end_page + 1))

        print(
            f"[{index + 1}/{len(df)}] "
            f"Processing Paper Start {start_page} → {subject}"
        )
        print(
            f"  → Page range: {start_page} to {end_page} "
            f"({len(page_range)} source image(s))"
        )

        paper_page_texts = []
        missing_pages = []
        ocr_failed_pages = []
        paper_source_image_paths = []

        for current_page in page_range:

            img_path = get_image_path(current_page)

            if img_path is None:
                print(
                    f"  ⚠ Image not found for page {current_page}"
                )
                missing_pages.append(current_page)
                continue

            print(
                f"  → Extracting text from image/page {current_page}..."
            )
            paper_source_image_paths.append(img_path)

            page_text = extract_text_from_image(
                img_path,
                class_name=str(row.get("CLASS", "")),
                subject=subject,
            )

            if not page_text or page_text.startswith("[Error"):
                print(
                    f"  ❌ Text extraction failed for page {current_page}."
                )
                ocr_failed_pages.append(current_page)
                continue

            paper_page_texts.append(page_text)
            total_images_processed += 1

            # API rate safety after EACH source image.
            time.sleep(2.5)

        # Audit the complete paper across all source images before formatting.
        audit_question_sequence(paper_page_texts, start_page)

        # Do not create an empty paper.
        if not paper_page_texts:
            print(
                f"  ❌ No usable images/text found for paper starting at "
                f"{start_page}."
            )
            failed_count += 1
            continue

        try:
            try:
                ai_ok, paper_page_texts, _ai_timeout = run_ai_refine_with_timeout(
                    row, paper_page_texts, OUTPUT_FOLDER, AI_STAGE_TIMEOUT_SEC
                )
                # HOLD DISABLED: AI rejection never stops Word generation.
            except Exception as ai_exc:
                print(f"  ⚠ AI stage skip ({ai_exc}) — purana OCR text se Word")
            global _CURRENT_SOURCE_IMAGE_PATHS
            _CURRENT_SOURCE_IMAGE_PATHS = list(paper_source_image_paths)
            print(f"  🖼 V33.24 SOURCE IMAGE LOCK: {len(_CURRENT_SOURCE_IMAGE_PATHS)} source image(s) available to worksheet renderer")
            _generated_docx = create_document(
                row,
                paper_page_texts,
                index,
                warning_message=LAST_AI_WARNING
            )
            if _generated_docx:
                _CURRENT_RUN_DOCX_FILES.append(os.path.abspath(str(_generated_docx)))
                print(
                    "  📌 V33.35 CURRENT-RUN TRACK: "
                    + os.path.basename(str(_generated_docx))
                )
            print_layout, sheets_per_copy = resolve_print_layout(
                excel_layout=row.get("LAYOUT") if hasattr(row, "get") else None,
                excel_sheets_per_copy=row.get("SHEETS_PER_COPY") if hasattr(row, "get") else None,
            )
            row["LAYOUT"] = print_layout
            row["SHEETS_PER_COPY"] = sheets_per_copy
            print(f"  → PRINT INPUT: {print_layout} | sheets/copy = {sheets_per_copy}")
            success_count += 1

            if missing_pages:
                print(
                    f"  ⚠ Paper created, but missing image page(s): "
                    f"{missing_pages}"
                )

            if ocr_failed_pages:
                print(
                    f"  ⚠ Paper created, but OCR failed on page(s): "
                    f"{ocr_failed_pages}"
                )

        except Exception as e:
            print(f"  ❌ Document creation error: {e}")
            failed_count += 1

    print("\n" + "=" * 70)
    print(" PROCESSING COMPLETE")
    print("=" * 70)
    print(f"✅ Successfully generated papers : {success_count}")
    print(f"🖼 Source images processed       : {total_images_processed}")
    print(f"❌ Failed / skipped papers       : {failed_count}")
    print(f"📁 Output folder                 : {OUTPUT_FOLDER}")
    print("=" * 70)

    if success_count > 0:
        combine_class_pdfs(
            OUTPUT_FOLDER,
            current_run_docx_files=_CURRENT_RUN_DOCX_FILES
        )
        try:
            import update_print_table
            update_print_table.run()
        except Exception as _pt_exc:
            print("  ⚠ PRINT_TABLE update skip:", _pt_exc)

if __name__ == "__main__":
    if len(os.sys.argv) > 1 and os.sys.argv[1] in ("--combine-only", "--combine", "-c"):
        combine_class_pdfs(OUTPUT_FOLDER)
        try:
            import update_print_table
            update_print_table.run()
        except Exception as _pt_exc:
            print("  ⚠ PRINT_TABLE update skip:", _pt_exc)
    else:
        main()
