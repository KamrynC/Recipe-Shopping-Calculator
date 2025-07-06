import streamlit as st
from fpdf import FPDF
from bs4 import BeautifulSoup
from collections import defaultdict
import pandas as pd
import os

# === UNIT MAP AND CONVERSION ===
UNIT_MAP = {
    "tbs": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp.": "tbsp",
    "tsp.": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "ounces": "oz", "ounce": "oz",
    "cups": "cup", "cup.": "cup", "c.": "cup",
    "": ""
}

UNIT_CONVERSION = {
    ("tsp", "tbsp"): 3,
    ("tbsp", "cup"): 16,
    ("oz", "cup"): 8
}

# === UNIT ELEVATION ===
def convert_unit(quantity, unit):
    for (from_unit, to_unit), factor in UNIT_CONVERSION.items():
        if unit == from_unit and quantity >= factor:
            return round(quantity / factor, 2), to_unit
    return quantity, unit

# === STREAMLIT SETUP ===
st.set_page_config(page_title="Tiny Chefs Shopping Calculator", layout="centered")
st.markdown("<h3 style='text-align: center;'>Tiny Chefs Shopping Calculator 🍎</h3>", unsafe_allow_html=True)

UPLOAD_FOLDER = "./html_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
available_files = sorted([f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".html")])
selected_files = st.multiselect("Select all applicable recipe day files to include in the list:", available_files)
st.markdown("<div style='font-size:14px; font-weight:600;'>Please note that these recipe files are for full-day camps</div><br>", unsafe_allow_html=True)

# === SERVING SIZE ===
default_servings = 10
servings = st.number_input("Adjust Serving Size", value=10, min_value=1, step=1)
scale_factor = servings / default_servings

# === SHOPPING LIST GENERATION ===
if st.button("🧾 Generate Shopping List", key="generate_list_button"):
    ingredient_data = defaultdict(lambda: {"category": "", "units": defaultdict(float), "raw": []})

    for filename in selected_files:
        with open(os.path.join(UPLOAD_FOLDER, filename), "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

            current_category = None

            # Samsung Food Format (class-based divs)
            category_headers = soup.find_all("div", class_="x245")
            for header in category_headers:
                current_category = header.get_text(strip=True).upper()
                item_blocks = header.find_next_sibling("div", class_="x240")
                if item_blocks:
                    for item in item_blocks.find_all("div", class_="x241"):
                        parts = item.find_all("div", class_="x242")
                        if len(parts) >= 2:
                            name = parts[0].get_text(strip=True).strip().lower()
                            quantity_text = parts[1].get_text(strip=True)
                            unit = parts[2].get_text(strip=True).lower() if len(parts) > 2 else ""
                            unit = UNIT_MAP.get(unit, unit)

                            if not name:
                                continue

                            try:
                                quantity = float(quantity_text)
                                if quantity == 0 and unit:
                                    quantity = 1.0
                                elif quantity == 0:
                                    quantity = 0.0
                                scaled_qty = quantity * scale_factor
                                ingredient_data[name]["units"][unit] += scaled_qty
                            except ValueError:
                                raw = f"{quantity_text} {unit}".strip()
                                ingredient_data[name]["raw"].append(raw)

                            ingredient_data[name]["category"] = current_category or "Uncategorized"

            # Enhanced Legacy Format: x241 contains x247 (category) + x242 wrapper with x243 ingredient rows
            for x241 in soup.find_all("div", class_="x241"):
                category_div = x241.find("div", class_="x247")
                legacy_category = category_div.get_text(strip=True).upper() if category_div else None
                ingredient_container = x241.find("div", class_="x242")
                if ingredient_container:
                    for row in ingredient_container.find_all("div", class_="x243"):
                        cells = row.find_all("div", class_="x244")
                        if len(cells) < 2:
                            continue
                        name = cells[0].get_text(strip=True).strip().lower()
                        quantity_text = cells[1].get_text(strip=True)
                        unit = cells[2].get_text(strip=True).lower() if len(cells) > 2 else ""
                        unit = UNIT_MAP.get(unit, unit)

                        if not name:
                            continue

                        try:
                            quantity = float(quantity_text)
                            if quantity == 0 and unit:
                                quantity = 1.0
                            elif quantity == 0:
                                quantity = 0.0
                            scaled_qty = quantity * scale_factor
                            ingredient_data[name]["units"][unit] += scaled_qty
                        except ValueError:
                            raw = f"{quantity_text} {unit}".strip()
                            ingredient_data[name]["raw"].append(raw)

                        ingredient_data[name]["category"] = ingredient_data[name]["category"] or legacy_category or "Uncategorized"

            # Legacy Format (old div nesting with x241 containing x242 directly)
            legacy_category = None
            for cat_div in soup.find_all("div", class_="x247"):
                legacy_category = cat_div.get_text(strip=True).upper()

            for container in soup.find_all("div", class_="x241"):
                parts = container.find_all("div", class_="x242")
                if len(parts) >= 2:
                    name = parts[0].get_text(strip=True).strip().lower()
                    quantity_text = parts[1].get_text(strip=True)
                    unit = parts[2].get_text(strip=True).lower() if len(parts) > 2 else ""
                    unit = UNIT_MAP.get(unit, unit)

                    if not name:
                        continue

                    try:
                        quantity = float(quantity_text)
                        if quantity == 0 and unit:
                            quantity = 1.0
                        elif quantity == 0:
                            quantity = 0.0
                        scaled_qty = quantity * scale_factor
                        ingredient_data[name]["units"][unit] += scaled_qty
                    except ValueError:
                        raw = f"{quantity_text} {unit}".strip()
                        ingredient_data[name]["raw"].append(raw)

                    # Only assign legacy category if current_category wasn't already set from Samsung format
                    ingredient_data[name]["category"] = ingredient_data[name]["category"] or legacy_category or "Uncategorized"

    # === FORMAT FINAL DATA ===
    final_data = []
    for name, data in ingredient_data.items():
        unit_dict = data["units"]

        # Elevate units where appropriate
        for (from_unit, to_unit), factor in UNIT_CONVERSION.items():
            if from_unit in unit_dict and to_unit in unit_dict:
                elev_qty = unit_dict[from_unit]
                if elev_qty >= factor:
                    unit_dict[to_unit] += elev_qty / factor
                    unit_dict[from_unit] = elev_qty % factor

        combined_parts = []
        for unit, total_qty in unit_dict.items():
            total_qty, unit = convert_unit(total_qty, unit)
            qty_str = "" if total_qty == 0 else f"{total_qty:.2f}".rstrip("0").rstrip(".")
            if qty_str:
                combined_parts.append(f"{qty_str} {unit}".strip())

        combined_parts.extend(data["raw"])
        quantity_display = " and ".join(combined_parts)

        final_data.append({
            "Category": data["category"],
            "Ingredient": name,
            "Quantity": quantity_display
        })

    df = pd.DataFrame(final_data)
    st.session_state["shopping_df"] = df
    st.session_state["show_table"] = True

if st.session_state.get("show_table") and "shopping_df" in st.session_state:
    st.subheader(f"Combined Ingredient List for {servings} Servings")
    st.dataframe(st.session_state["shopping_df"])

# === PDF EXPORT ===
st.markdown("---")
recipe_name = st.text_input("Add a shopping list title (optional):", "")

if st.button("📄 Generate PDF", key="generate_pdf"):
    if "shopping_df" not in st.session_state:
        st.error("⚠️ Please generate the shopping list first.")
    else:
        df = st.session_state["shopping_df"]

        class ShoppingListPDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 14)
                self.cell(0, 10, self.title, ln=True, align="C")
                self.ln(5)

            def category_section(self, category, items):
                self.set_font("Arial", "B", 12)
                self.set_fill_color(230, 230, 230)
                self.cell(0, 8, category or "Uncategorized", ln=True, fill=True)
                self.set_font("Arial", "", 11)
                for ingredient, quantity in items:
                    ingredient = ingredient.replace("’", "'").replace("“", '"').replace("”", '"')
                    quantity = quantity.replace("’", "'").replace("“", '"').replace("”", '"')
                    self.cell(10, 8, "[ ]", border=0)
                    self.cell(90, 8, ingredient, border=0)
                    self.cell(0, 8, quantity, ln=True, border=0)

        grouped = defaultdict(lambda: defaultdict(list))
        for _, row in df.iterrows():
            grouped[row["Category"]][row["Ingredient"]].append(row["Quantity"])

        merged = defaultdict(list)
        for category, ingredients in grouped.items():
            for ingredient, quantities in ingredients.items():
                combined = " and ".join(quantities)
                merged[category].append((ingredient, combined))

        pdf = ShoppingListPDF()
        pdf.title = recipe_name.strip() or "Tiny Chefs Shopping List"
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        for category in sorted(merged.keys()):
            pdf.category_section(category, merged[category])

        pdf_path = "tiny_chefs_shopping_list.pdf"
        pdf.output(pdf_path)

        with open(pdf_path, "rb") as f:
            st.download_button("📥 Download PDF", f, file_name=pdf_path, mime="application/pdf")
