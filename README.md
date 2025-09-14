# Crop Nutrient Visualization App

**Interactive Streamlit app to visualize crop nutrient levels against baseline standards, with PDF export functionality.**

---

## Overview

This Streamlit app allows growers, agronomists, and researchers to compare crop nutrient values with baseline (OL Complete) data. Users can:

- Select a **Grower** and **Crop**
- View nutrient levels for different growth stages
- Compare values against the **optimum range** (baseline)
- Export all nutrient charts into a **multi-page PDF**

The app includes a reference **Data** folder, but manual upload is required to run the app.

---

## Data Files

A `Data` folder has been included in the repository for reference.

**To run the app:**

1. Download the `Data` folder from the repository.
2. Upload the two required files (`OL Complete` file and `Corn data file`) using the **file upload widgets** in the app.

> The file upload feature is intentionally kept to allow users to **replace the data** with updated versions anytime, as requested by the client.  
> The app **never reads files directly from GitHub**; it only uses the uploaded files.

---

