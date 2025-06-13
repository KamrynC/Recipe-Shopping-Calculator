import streamlit as st
from fpdf import FPDF
from bs4 import BeautifulSoup
from collections import defaultdict
import pandas as pd
import os

# TITLE
st.markdown(
    "<h3 style='text-align: center;'>Tiny Chefs Shopping Calculator 🍎🧮</h3>",
    unsafe_allow_html=True
)

# FILE SELECTION
UPLOAD_FOLDER = "./html_files"
available_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".html")]
selected_files = st.multiselect("Select the Recipe HTML files to include:", available_files)

# SERVING SIZE
default_servings = 10
servings = st.number_input("Adjust Serving Size", value=10, min_value=1, step=1)
scale_factor = servings / default_servings

# GENERATE SHOPPING LIST
if st.button("🧾 Generate Shopping List", key="generate_list_button"):
    ingredient_data = defaultdict(lambda: {"quantity": 0.0, "unit": "", "category": "", "raw": ""})

    for filename in selected_files:
        with open(os.path.join(UPLOAD_FOLDER, filename), "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            current_category = ""

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
                    name = parts[0].get_text(strip=True) if len(parts) > 0 else ""
                    quantity_text = parts[1].get_text(strip=True) if len(parts) > 1 else ""
                    unit = parts[2].get_text(strip=True) if len(parts) > 2 else ""

                    if not name:
                        continue

                    key = (name, unit)

                    try:
                        quantity = float(quantity_text)
                        ingredient_data[key]["quantity"] += quantity
                        ingredient_data[key]["unit"] = unit
                        ingredient_data[key]["category"] = current_category
                        ingredient_data[key]["raw"] = ""
                    except ValueError:
                        ingredient_data[key]["raw"] = f"{quantity_text} {unit}".strip()
                        ingredient_data[key]["category"] = current_category

    final_data = []
    for (name, unit), data in ingredient_data.items():
        if data["raw"]:
            quantity_display = data["raw"]
        else:
            scaled_qty = data["quantity"] * scale_factor
            qty_str = "" if scaled_qty == 0 else f"{scaled_qty:.2f}".rstrip("0").rstrip(".")
            quantity_display = f"{qty_str} {unit}".strip()
        final_data.append({
            "Category": data["category"],
            "Ingredient": name,
            "Quantity": quantity_display
        })

    df = pd.DataFrame(final_data)
    st.session_state["shopping_df"] = df  # ✅ Store it for later
    st.subheader(f"✅ Combined Ingredient List for {servings} Servings")
    st.dataframe(df)

# Optional input for PDF recipe title
st.markdown("---")
recipe_name = st.text_input("Add a recipe name (optional):", "")

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
                    self.cell(10, 8, "[ ]", border=0)
                    self.cell(90, 8, ingredient, border=0)
                    self.cell(0, 8, quantity, ln=True, border=0)

        grouped = defaultdict(list)
        for _, row in df.iterrows():
            grouped[row["Category"]].append((row["Ingredient"], row["Quantity"]))

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