# streamlit_app.py

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import os
import tempfile
import time

st.set_page_config(layout="wide")

# ---------------------------
# Persistent folders for storage
# ---------------------------
BASE_DIR = "/home/appuser/data"
BASELINE_FOLDER = os.path.join(BASE_DIR, "baseline")
SAMPLE_FOLDER = os.path.join(BASE_DIR, "sample")
os.makedirs(BASELINE_FOLDER, exist_ok=True)
os.makedirs(SAMPLE_FOLDER, exist_ok=True)

# ---------------------------
# Header
# ---------------------------
st.markdown("<h1 style='text-align: center;'>Crop Nutrient Visualization</h1>", unsafe_allow_html=True)

# ---------------------------
# Upload new data (collapsed)
# ---------------------------
with st.expander("Upload new data files (optional)", expanded=False):
    baseline_file_upload = st.file_uploader("Upload Optimum Levels file", type=["csv", "xlsx"])
    data_file_upload = st.file_uploader("Upload sample results file", type=["csv", "xlsx"])

    if baseline_file_upload:
        # Clear existing files in the folder
        for f in os.listdir(BASELINE_FOLDER):
            os.remove(os.path.join(BASELINE_FOLDER, f))

        baseline_path = os.path.join(BASELINE_FOLDER, baseline_file_upload.name)
        with open(baseline_path, "wb") as f:
            f.write(baseline_file_upload.getbuffer())
        st.session_state['baseline_file_path'] = baseline_path
        st.success(f"Saved Optimum Levels file: {baseline_file_upload.name}")

    if data_file_upload:
        # Clear existing files in the folder
        for f in os.listdir(SAMPLE_FOLDER):
            os.remove(os.path.join(SAMPLE_FOLDER, f))

        data_path = os.path.join(SAMPLE_FOLDER, data_file_upload.name)
        with open(data_path, "wb") as f:
            f.write(data_file_upload.getbuffer())
        st.session_state['data_file_path'] = data_path
        st.success(f"Saved sample results file: {data_file_upload.name}")

# ---------------------------
# Determine last uploaded files
# ---------------------------
def get_latest_file(folder):
    files = os.listdir(folder)
    if files:
        files = [os.path.join(folder, f) for f in files]
        latest_file = max(files, key=os.path.getmtime)
        return latest_file
    return None

baseline_file = st.session_state.get('baseline_file_path', get_latest_file(BASELINE_FOLDER))
data_file = st.session_state.get('data_file_path', get_latest_file(SAMPLE_FOLDER))

# ---------------------------
# Display last uploaded time
# ---------------------------
def get_file_info(file_path):
    if file_path and os.path.exists(file_path):
        modified_time = os.path.getmtime(file_path)
        readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(modified_time))
        return os.path.basename(file_path), readable_time
    return None, None

baseline_name, baseline_time = get_file_info(baseline_file)
data_name, data_time = get_file_info(data_file)

if baseline_name:
    st.markdown(f"**Optimum Levels file:** {baseline_name} (Uploaded: {baseline_time})")
if data_name:
    st.markdown(f"**Sample results file:** {data_name} (Uploaded: {data_time})")

# ---------------------------
# Load and process files
# ---------------------------
if baseline_file and data_file:
    # --- Load baseline ---
    if baseline_file.lower().endswith(".csv"):
        baseline_df = pd.read_csv(baseline_file)
    else:
        baseline_df = pd.read_excel(baseline_file, engine="openpyxl")  # fixed

    # --- Load sample data ---
    if data_file.lower().endswith(".csv"):
        data_df = pd.read_csv(data_file)
    else:
        data_df = pd.read_excel(data_file, engine="openpyxl")  # fixed

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

    baseline_pivot = baseline_df.pivot_table(
        index=["Crop", "Stage", "Nutrient"],
        columns="RangeType", 
        values="Value"
    ).reset_index()
    baseline_pivot.columns.name = None
    baseline_pivot = baseline_pivot.rename(columns={"Low": "low", "High": "high"})

    # ---------------------------
    # Dynamic stage order
    # ---------------------------
    v_stages = [s for s in baseline_pivot['Stage'].unique() if str(s).startswith('V')]
    r_stages = [s for s in baseline_pivot['Stage'].unique() if str(s).startswith('R')]

    def sort_stage(stages):
        numeric = sorted([s for s in stages if s[1:].isdigit()], key=lambda x: int(x[1:]))
        non_numeric = sorted([s for s in stages if not s[1:].isdigit()])
        return numeric + non_numeric

    v_stages_sorted = sort_stage(v_stages)
    r_stages_sorted = sort_stage(r_stages)
    stage_order = v_stages_sorted + r_stages_sorted

    baseline_pivot['Stage'] = pd.Categorical(
        baseline_pivot['Stage'], categories=stage_order, ordered=True
    )
    baseline_pivot = baseline_pivot.sort_values(['Crop','Nutrient','Stage'])

    # ---------------------------
    # Normalize sample data columns
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
    grower = st.sidebar.selectbox("Select Grower", sorted(data_df["Grower"].dropna().unique()))
    crop = st.sidebar.selectbox(
        "Select Crop", 
        sorted(data_df[data_df["Grower"]==grower]["Crop"].dropna().unique())
    )
    nutrient = st.sidebar.selectbox(
        "Select Nutrient", 
        sorted(baseline_pivot[baseline_pivot["Crop"]==crop]["Nutrient"].dropna().unique())
    )

    # ---------------------------
    # Plotting function
    # ---------------------------
    def plot_chart(grower, crop, nutrient):
        df_crop = data_df[(data_df["Grower"]==grower) & (data_df["Crop"]==crop)]
        if df_crop.empty:
            st.warning("No data for this selection.")
            return

        baseline = baseline_pivot[
            (baseline_pivot["Crop"]==crop) & (baseline_pivot["Nutrient"].str.lower()==nutrient.lower())
        ]
        if baseline.empty:
            st.warning("No baseline data for this crop/nutrient.")
            return

        baseline = baseline.dropna(subset=["Stage","low","high"]).copy()
        baseline["Stage"] = baseline["Stage"].astype(str)

        stage_to_num = {s: i for i, s in enumerate(stage_order)}
        baseline["Stage_num"] = baseline["Stage"].map(stage_to_num)

        fig, ax = plt.subplots(figsize=(12,6))

        if not baseline.empty:
            ax.fill_between(
                baseline["Stage_num"], baseline["low"], baseline["high"], 
                color="green", alpha=0.2, label="Optimum Range"
            )
            ax.set_xticks(baseline["Stage_num"])
            ax.set_xticklabels(baseline["Stage"], rotation=45)

        color_map = {loc: plt.cm.tab10(i % 10) for i, loc in enumerate(df_crop["SampleLocation"].unique())}
        for loc, group in df_crop.groupby("SampleLocation"):
            color = color_map[loc]
            for status, g2 in group.groupby("Status"):
                style = "-" if pd.isna(status) or str(status).strip()=="" or str(status).lower()=="new" else "--"
                y_values = pd.to_numeric(g2[nutrient], errors='coerce')
                stage_vals = g2["Stage"].map(stage_to_num)
                ax.plot(stage_vals, y_values, linestyle=style, marker="o", color=color, label=loc)

        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), title="Dotted=Old, Solid=New", fontsize=9)

        ax.set_title(f"{crop} - {nutrient} levels for {grower}")
        ax.set_xlabel("Stage")
        ax.set_ylabel(f"{nutrient} value")
        ax.grid(True)
        st.pyplot(fig)

    if st.button("Plot Chart"):
        plot_chart(grower, crop, nutrient)

    # ---------------------------
    # PDF generation function (fully temporary)
    # ---------------------------
    if st.button("Generate PDF of all nutrients"):
        st.info("Generating PDF... Please wait.")

        def generate_pdf_all_nutrients_temp(grower, crop):
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
                    base = base.dropna(subset=["Stage","low","high"]).copy()
                    base["Stage"] = base["Stage"].astype(str)
                    stage_to_num = {s: i for i, s in enumerate(stage_order)}
                    base["Stage_num"] = base["Stage"].map(stage_to_num)

                    if not base.empty:
                        ax.fill_between(base["Stage_num"], base["low"], base["high"], 
                                        color="green", alpha=0.2, label="Optimum Range")
                        ax.set_xticks(base["Stage_num"])
                        ax.set_xticklabels(base["Stage"], rotation=45)

                    color_map = {loc: plt.cm.tab10(i % 10) for i, loc in enumerate(df_crop["SampleLocation"].unique())}
                    for loc, group in df_crop.groupby("SampleLocation"):
                        color = color_map[loc]
                        for status, g2 in group.groupby("Status"):
                            style = "-" if pd.isna(status) or str(status).strip()=="" or str(status).lower()=="new" else "--"
                            y_values = pd.to_numeric(g2[nutrient], errors='coerce')
                            stage_vals = g2["Stage"].map(stage_to_num)
                            ax.plot(stage_vals, y_values, linestyle=style, marker="o", color=color, label=loc)

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

                temp_pdf_path = os.path.join(tmpdir, f"{grower}_{crop}_nutrients.pdf")
                pdf.output(temp_pdf_path)

                with open(temp_pdf_path, "rb") as f:
                    pdf_bytes = f.read()
            return pdf_bytes

        pdf_bytes = generate_pdf_all_nutrients_temp(grower, crop)
        st.download_button("Download PDF", pdf_bytes, file_name=f"{grower}_{crop}_nutrients.pdf")
