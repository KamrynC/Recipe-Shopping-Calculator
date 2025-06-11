import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
from io import BytesIO
from fpdf import FPDF

# --- Helper Functions ---

fraction_chars = "¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞"

def starts_with_number_or_fraction(text):
    if not text:
        return False
    text = text.strip()
    return bool(re.match(rf"^[\d{re.escape(fraction_chars)}]", text))

def is_category_line(line):
    return (
        line and
        line[0].isupper() and
        not starts_with_number_or_fraction(line) and
        not re.search(r"\d", line) and
        len(line.split()) <= 5
    )

def replace_unicode_fractions(text):
    fraction_replacements = {
        '¼': '1/4', '½': '1/2', '¾': '3/4',
        '⅐': '1/7', '⅑': '1/9', '⅒': '1/10',
        '⅓': '1/3', '⅔': '2/3', '⅕': '1/5',
        '⅖': '2/5', '⅗': '3/5', '⅘': '4/5',
        '⅙': '1/6', '⅚': '5/6', '⅛': '1/8',
        '⅜': '3/8', '⅝': '5/8', '⅞': '7/8'
    }
    for uni_frac, ascii_frac in fraction_replacements.items():
        text = text.replace(uni_frac, ascii_frac)
    return text

def safe_latin1(text):
    return replace_unicode_fractions(text).encode('latin-1', 'replace').decode('latin-1')

def parse_amount_unit_ingredient(line):
    match = re.match(
        r"(?P<amount>[\d\s\/\.\u00bc-\u00be\u2150-\u215e]+)\s+"
        r"(?P<unit>cups?|cup|tbsp|tablespoons?|tsp|teaspoons?|oz|grams?|g|ml|l|stalks?|pieces?|slices?|lbs?|pinch|dash|handfuls?)\s+"
        r"(?P<ingredient>.+)",
        line, re.IGNORECASE
    )
    if match:
        amount = match.group("amount").strip()
        unit = match.group("unit").strip()
        ingredient = match.group("ingredient").strip()
        return ingredient, f"{amount} {unit}"

    fallback_match = re.match(
        r"(?P<amount>[\d\s\/\.\u00bc-\u00be\u2150-\u215e]+)\s+(?P<ingredient>.+)",
        line, re.IGNORECASE
    )
    if fallback_match:
        amount = fallback_match.group("amount").strip()
        ingredient = fallback_match.group("ingredient").strip()
        return ingredient, amount

    return None, None

def parse_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    ignore_patterns = [
        "Created with SamsungFood.com",
        r"Food fact:.*?\."
    ]

    ingredients = []
    buffer_line = ""
    current_category = None

    for page in doc:
        text = page.get_text()
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line or any(re.search(pattern, line) for pattern in ignore_patterns):
                continue

            if is_category_line(line):
                if buffer_line:
                    ingredient, amount = parse_amount_unit_ingredient(buffer_line)
                    if ingredient and amount:
                        ingredients.append({
                            "Ingredient": ingredient,
                            "Amount": amount,
                            "Category": current_category
                        })
                    buffer_line = ""
                current_category = line
                continue

            if starts_with_number_or_fraction(line):
                if buffer_line:
                    ingredient, amount = parse_amount_unit_ingredient(buffer_line)
                    if ingredient and amount:
                        ingredients.append({
                            "Ingredient": ingredient,
                            "Amount": amount,
                            "Category": current_category
                        })
                buffer_line = line
            else:
                buffer_line += " " + line

        if buffer_line:
            ingredient, amount = parse_amount_unit_ingredient(buffer_line)
            if ingredient and amount:
                ingredients.append({
                    "Ingredient": ingredient,
                    "Amount": amount,
                    "Category": current_category
                })
            buffer_line = ""

    return pd.DataFrame(ingredients)

def dataframe_to_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.set_font("Arial", size=12, style="B")
    pdf.cell(70, 10, safe_latin1("Ingredient"), 1)
    pdf.cell(30, 10, safe_latin1("Amount"), 1)
    pdf.cell(60, 10, safe_latin1("Category"), 1)
    pdf.ln()

    pdf.set_font("Arial", size=12)
    for index, row in df.iterrows():
        ingredient = safe_latin1(str(row["Ingredient"]))
        amount = safe_latin1(str(row["Amount"]))
        category = safe_latin1(str(row["Category"]) if row["Category"] else "")
        pdf.cell(70, 10, ingredient, 1)
        pdf.cell(30, 10, amount, 1)
        pdf.cell(60, 10, category, 1)
        pdf.ln()

    pdf_output = pdf.output(dest="S").encode("latin-1")
    buffer = BytesIO(pdf_output)
    return buffer

# --- Streamlit App ---

st.title("🛒 Ingredient List Scanner")

uploaded_file = st.file_uploader("Upload a PDF Shopping List", type=["pdf"])

if uploaded_file:
    df = parse_pdf(uploaded_file)
    st.subheader("Parsed Shopping List")
    st.dataframe(df)

    pdf_bytes = dataframe_to_pdf(df)
    st.download_button(
        label="📥 Download Table as PDF",
        data=pdf_bytes,
        file_name="shopping_list.pdf",
        mime="application/pdf"
    )
