import streamlit as st
from fpdf import FPDF
from bs4 import BeautifulSoup
from collections import defaultdict
import pandas as pd
import os

UNIT_MAP = {
    "tsp.": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp.": "tbsp", "tbs": "tbsp", "tb": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "cups": "cup",
    "ounce": "oz", "ounces": "oz", "oz.": "oz",
    "lbs": "lb", "pound": "lb", "pounds": "lb", "lb.": "lb",
    "gram": "g", "grams": "g", "g.": "g",
    "kilogram": "kg", "kilograms": "kg", "kg.": "kg",
    "milliliter": "ml", "milliliters": "ml", "ml.": "ml",
    "liter": "l", "liters": "l", "l.": "l",
    "inch": "in", "inches": "in", "in.": "in",
    "cloves": "clove",
    "pinches": "pinch", "a pinch": "pinch",
    "dashes": "dash", "a dash": "dash",
    "cans": "can",
    "jars": "jar",
    "package": "pkg", "packages": "pkg", "pkg.": "pkg",
    "sheets": "sheet",
    "sticks": "stick"
}

# TITLE
st.markdown(
    "<h3 style='text-align: center;'>Tiny Chefs Shopping Calculator 🍎🧮</h3>",
    unsafe_allow_html=True
)

# FILE SELECTION
UPLOAD_FOLDER = "./html_files"
available_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".html")]
selected_files = st.multiselect("Select all applicable recipe day files to include in the list:", available_files)

# SERVING SIZE
default_servings = 10
servings = st.number_input("Adjust Serving Size", value=10, min_value=1, step=1)
scale_factor = servings / default_servings

# GENERATE SHOPPING LIST
if st.button("🧾 Generate Shopping List", key="generate_list_button"):
    ingredient_data = defaultdict(lambda: {"category": "", "units": defaultdict(float), "raw": []})
    current_category = ""

    for filename in selected_files:
        with open(os.path.join(UPLOAD_FOLDER, filename), "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

            for div in soup.find_all("div"):
                div_class = div.get("class", [])
                text = div.get_text(strip=True)

                if text.lower() == "recipes":
                    break
                if "x245" in div_class:
                    current_category = text.strip().upper()
                    continue
                if "x241" in div_class:
                    parts = div.find_all("div", class_="x242")
                    if not parts:
                        continue

                    name = parts[0].get_text(strip=True).strip().lower() if len(parts) > 0 else ""
                    quantity_text = parts[1].get_text(strip=True) if len(parts) > 1 else ""
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

                    ingredient_data[name]["category"] = current_category

    # Format for display
    final_data = []
    for name, data in ingredient_data.items():
        combined_parts = []

        for unit, total_qty in data["units"].items():
            qty_str = "" if total_qty == 0 else f"{total_qty:.2f}".rstrip("0").rstrip(".")
            combined_parts.append(f"{qty_str} {unit}".strip())

        combined_parts.extend(data["raw"])  # Add any unparsed entries
        quantity_display = " and ".join(combined_parts)

        final_data.append({
            "Category": data["category"],
            "Ingredient": name,
            "Quantity": quantity_display
        })

    df = pd.DataFrame(final_data)
    st.session_state["shopping_df"] = df
    st.session_state["show_table"] = True  # ✅ Set the flag to display table

if st.session_state.get("show_table") and "shopping_df" in st.session_state:
    st.subheader(f"✅ Combined Ingredient List for {servings} Servings")
    st.dataframe(st.session_state["shopping_df"])


# Optional input for PDF recipe title
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
                    # Replace curly apostrophes and other smart punctuation
                    ingredient = ingredient.replace("’", "'").replace("“", '"').replace("”", '"')
                    quantity = quantity.replace("’", "'").replace("“", '"').replace("”", '"')

                    self.cell(10, 8, "[ ]", border=0)
                    self.cell(90, 8, ingredient, border=0)
                    self.cell(0, 8, quantity, ln=True, border=0)

        # Group and combine quantities by ingredient name and category for the PDF
        pdf_grouped = defaultdict(lambda: defaultdict(list))

        for _, row in df.iterrows():
            category = row["Category"]
            name = row["Ingredient"]
            quantity = row["Quantity"]
            pdf_grouped[category][name].append(quantity)

        # Format the final grouped list
        grouped = defaultdict(list)
        for category, ingredients in pdf_grouped.items():
            for name, quantities in ingredients.items():
                combined_quantity = " and ".join(quantities)
                grouped[category].append((name, combined_quantity))


        pdf = ShoppingListPDF()
        pdf.title = recipe_name.strip() or "Tiny Chefs Shopping List"  # ✅ Set before add_page
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        for category in sorted(grouped.keys()):
            pdf.category_section(category, grouped[category])

        pdf_path = "tiny_chefs_shopping_list.pdf"
        pdf.output(pdf_path)

        with open(pdf_path, "rb") as f:
            st.download_button("📥 Download PDF", f, file_name=pdf_path, mime="application/pdf")