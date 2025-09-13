# streamlit_app.py

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import os
import tempfile

st.set_page_config(layout="wide")

# ---------------------------
# File paths (already hosted)
# ---------------------------
BASE_DIR = "data"
baseline_file = os.path.join(BASE_DIR, "OL Complete.csv")
data_file = os.path.join(BASE_DIR, "Corn data.xlsx")

# ---------------------------
# Read files
# ---------------------------
if baseline_file.lower().endswith(".csv"):
    baseline_df = pd.read_csv(baseline_file)
else:
    baseline_df = pd.read_excel(baseline_file)

if data_file.lower().endswith(".csv"):
    data_df = pd.read_csv(data_file)
else:
    data_df = pd.read_excel(data_file)

# ---------------------------
# Fix: Replace "Unspecified" with "Unspec"
# ---------------------------
for col in ["growth_stage", "Stage"]:
    if col in data_df.columns:
        data_df[col] = data_df[col].replace({"Unspecified": "Unspec"})

# ---------------------------
# Normalize baseline columns
# ---------------------------
baseline_df.columns = [c.strip().lower() for c in baseline_df.columns]

baseline_map = {
    "crop": "Crop",
    "crop stage": "Stage",
    "nutrient": "Nutrient",
    "level": "RangeType",
    "value": "Value"
}
for old, new in baseline_map.items():
    if old in baseline_df.columns:
        baseline_df.rename(columns={old: new}, inplace=True)

baseline_df["Nutrient"] = baseline_df["Nutrient"].replace({
    "Total Sugars": "Sugars",
    "Total N": "Nitrogen"
}).str.title()

baseline_pivot = baseline_df.pivot_table(index=["Crop", "Stage", "Nutrient"],
                                         columns="RangeType", values="Value").reset_index()
baseline_pivot.columns.name = None
baseline_pivot = baseline_pivot.rename(columns={"Low": "low", "High": "high"})

stage_order = ['V1','V2','V3','V4','V5','V6','V7','V8','V9','V10','V11','V12',
               'V13','V14','V15','VT','R1','R2','R3','R4','Unspec']
baseline_pivot['Stage'] = pd.Categorical(baseline_pivot['Stage'], categories=stage_order, ordered=True)
baseline_pivot = baseline_pivot.sort_values(['Crop','Nutrient','Stage'])

# ---------------------------
# Normalize crop/test data columns
# ---------------------------
data_df.columns = [c.strip().lower() for c in data_df.columns]
data_map = {
    "grower_contact": "Grower",
    "plant_type": "Crop",
    "growth_stage": "Stage",
    "sample_location": "SampleLocation",
    "new_old": "Status"
}
for old, new in data_map.items():
    if old in data_df.columns:
        data_df.rename(columns={old: new}, inplace=True)

for col in ["Grower", "Crop", "SampleLocation"]:
    if col in data_df.columns:
        data_df[col] = data_df[col].astype(str).str.strip().str.title()

crop_mapping = {"Soybean": "Soybeans", "Soybeans": "Soybeans", "Maize": "Corn", "Corn": "Corn"}
data_df["Crop"] = data_df["Crop"].replace(crop_mapping)

ol_nutrients = baseline_pivot['Nutrient'].unique()
nutrient_cols = [col for col in data_df.columns if col.lower() in [n.lower() for n in ol_nutrients]]
rename_map = {col: col.title() for col in nutrient_cols}
data_df.rename(columns=rename_map, inplace=True)
for col in rename_map.values():
    data_df[col] = pd.to_numeric(
        data_df[col].replace(r'<\s*0\.01', 0.005, regex=True),
        errors='coerce'
    )

# ---------------------------
# Sidebar selectors
# ---------------------------
st.title("Crop Nutrient Visualization")

grower = st.sidebar.selectbox("Select Grower", sorted(data_df["Grower"].dropna().unique()))
crop = st.sidebar.selectbox("Select Crop", sorted(data_df[data_df["Grower"]==grower]["Crop"].dropna().unique()))
nutrient = st.sidebar.selectbox("Select Nutrient", sorted(baseline_pivot[baseline_pivot["Crop"]==crop]["Nutrient"].dropna().unique()))

# ---------------------------
# Plotting
# ---------------------------
if st.button("Plot Chart"):
    def plot_chart(grower, crop, nutrient):
        df_crop = data_df[(data_df["Grower"]==grower) & (data_df["Crop"]==crop)]
        if df_crop.empty:
            st.warning("No data for this selection.")
            return

        baseline = baseline_pivot[(baseline_pivot["Crop"]==crop) & (baseline_pivot["Nutrient"].str.lower()==nutrient.lower())]
        if baseline.empty:
            st.warning("No baseline data for this crop/nutrient.")
            return

        baseline = baseline.dropna(subset=["Stage"])
        baseline["Stage"] = baseline["Stage"].astype(str)
        df_crop = df_crop.dropna(subset=["Stage"])
        df_crop["Stage"] = df_crop["Stage"].astype(str)

        stage_order_filtered = [s for s in stage_order if s in baseline["Stage"].values]
        baseline["Stage"] = pd.Categorical(baseline["Stage"], categories=stage_order_filtered, ordered=True)
        baseline = baseline.sort_values("Stage")

        stages = baseline["Stage"]
        low = baseline["low"]
        high = baseline["high"]

        fig, ax = plt.subplots(figsize=(12,6))
        ax.fill_between(stages, low, high, color="green", alpha=0.2, label="Optimum Range")

        color_map = {loc: plt.cm.tab10(i % 10) for i, loc in enumerate(df_crop["SampleLocation"].unique())}
        for loc, group in df_crop.groupby("SampleLocation"):
            color = color_map[loc]
            for status, g2 in group.groupby("Status"):
                style = "-" if pd.isna(status) or str(status).strip()=="" or str(status).lower()=="new" else "--"
                y_values = pd.to_numeric(g2[nutrient], errors='coerce')
                ax.plot(g2["Stage"], y_values, linestyle=style, marker="o", color=color, label=loc)

        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), title="Dotted=Old, Solid=New", fontsize=9)

        ax.set_title(f"{crop} - {nutrient} levels for {grower}")
        ax.set_xlabel("Stage")
        ax.set_ylabel(f"{nutrient} value")
        ax.grid(True)
        st.pyplot(fig)

    plot_chart(grower, crop, nutrient)

# ---------------------------
# PDF generation
# ---------------------------
if st.button("Generate PDF of all nutrients"):
    st.info("Generating PDF... Please wait.")
    def generate_pdf_all_nutrients(grower, crop):
        df_crop = data_df[(data_df["Grower"]==grower) & (data_df["Crop"]==crop)]
        nutrients = sorted(baseline_pivot[baseline_pivot["Crop"]==crop]["Nutrient"].dropna().unique())
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        charts_per_page = 2
        chart_count = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            for nutrient in nutrients:
                fig, ax = plt.subplots(figsize=(10,5))
                base = baseline_pivot[(baseline_pivot["Crop"]==crop) & (baseline_pivot["Nutrient"]==nutrient)]
                stage_order_filtered = [s for s in stage_order if s in base["Stage"].values]
                base = base.copy()
                base["Stage"] = pd.Categorical(base["Stage"], categories=stage_order_filtered, ordered=True)
                base = base.sort_values("Stage")

                ax.fill_between(base["Stage"], base["low"], base["high"], color="green", alpha=0.2, label="Optimum Range")

                color_map = {loc: plt.cm.tab10(i % 10) for i, loc in enumerate(df_crop["SampleLocation"].unique())}
                for loc, group in df_crop.groupby("SampleLocation"):
                    color = color_map[loc]
                    for status, g2 in group.groupby("Status"):
                        style = "-" if pd.isna(status) or str(status).strip()=="" or str(status).lower()=="new" else "--"
                        y_values = pd.to_numeric(g2[nutrient], errors='coerce')
                        ax.plot(g2["Stage"], y_values, linestyle=style, marker="o", color=color, label=loc)

                handles, labels = ax.get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), title="Dotted=Old, Solid=New", fontsize=9)

                ax.set_title(f"{crop} - {nutrient} levels for {grower}")
                ax.set_xlabel("Stage")
                ax.set_ylabel(nutrient)
                ax.grid(True)

                tmp_file = os.path.join(tmpdir, f"{nutrient}.png")
                fig.savefig(tmp_file, bbox_inches='tight', dpi=150)
                plt.close(fig)

                if chart_count % charts_per_page == 0:
                    pdf.add_page()

                page_height_available = pdf.h - 20
                chart_height = (page_height_available / charts_per_page) - 5
                y_pos = 10 + (chart_count % charts_per_page) * (chart_height + 5)

                pdf.image(tmp_file, x=10, y=y_pos, w=pdf.w - 20, h=chart_height)
                chart_count += 1

            final_pdf_path = f"{grower}_{crop}_nutrients.pdf"
            pdf.output(final_pdf_path)

        return final_pdf_path

    pdf_file_path = generate_pdf_all_nutrients(grower, crop)
    with open(pdf_file_path, "rb") as f:
        st.download_button("Download PDF", f, file_name=pdf_file_path)
