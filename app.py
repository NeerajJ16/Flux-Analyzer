# app.py  – full rewrite with:
# · drop empty rows
# · replace sentinel –9999 with NaN
# · 1-hour resample when time is X-axis
# · Z-score normalisation
# · outlier removal |z| > 3
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
SENTINEL      = -9999            # “no-data” flag in source files
Z_OUTLIER_CUT = 3                # keep rows where |z| ≤ 3
TIME_FMT      = "%Y-%m-%dT%H:%M:%SZ"

st.set_page_config(page_title="CSV Explorer", layout="wide")
st.title("📊 CSV Visualizer (cleaning · resample 1 h · Z-score · outliers)")

# ────────────────────────────────────────────────────────────────
# 1 · Upload CSV
# ────────────────────────────────────────────────────────────────
file = st.file_uploader("Upload your CSV file", type="csv")
if not file:
    st.info("⬆️  Upload a CSV to begin.")
    st.stop()

df = pd.read_csv(file)

# ────────────────────────────────────────────────────────────────
# 2 · Basic cleaning – drop empty lines, sentinel → NaN
# ────────────────────────────────────────────────────────────────
df.dropna(how="all", inplace=True)          # remove completely blank rows
df.replace(SENTINEL, np.nan, inplace=True)  # convert sentinel to NaN

# ────────────────────────────────────────────────────────────────
# 3 · Trim columns ≤ 'hbb'
# ────────────────────────────────────────────────────────────────
if "hbb" in df.columns:
    df = df.loc[:, :"hbb"]

# ────────────────────────────────────────────────────────────────
# 4 · Parse ISO-UTC time
# ────────────────────────────────────────────────────────────────
if "time" in df.columns:
    df["time"] = pd.to_datetime(df["time"], format=TIME_FMT, errors="coerce")

# ────────────────────────────────────────────────────────────────
# 5 · Determine axis-eligible columns: time + latitude → hbb
# ────────────────────────────────────────────────────────────────
cols     = df.columns.tolist()
lat_idx  = cols.index("latitude") if "latitude" in cols else 0
axis_cols = (["time"] + cols[lat_idx:]) if "time" in cols else cols[lat_idx:]

for col in axis_cols:
    if col != "time":
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ────────────────────────────────────────────────────────────────
# 6 · UI widgets
# ────────────────────────────────────────────────────────────────
platforms = sorted(df["platform_name"].dropna().unique())
platform  = st.selectbox("platform_name", platforms)

x_axis = st.selectbox("X-axis", axis_cols, index=0)
y_axis = st.selectbox("Y-axis", axis_cols, index=1)

# ────────────────────────────────────────────────────────────────
# 7 · Filter → drop NaNs on chosen axes
# ────────────────────────────────────────────────────────────────
data = df[df["platform_name"] == platform].copy()

for col in [x_axis, y_axis]:
    if col != "time":
        data[col] = pd.to_numeric(data[col], errors="coerce")

data.dropna(subset=[x_axis, y_axis], inplace=True)
if data.empty:
    st.warning("No data left after filtering / NaN dropping.")
    st.stop()

# ────────────────────────────────────────────────────────────────
# 8 · Optional 1-hour resample when time is X-axis
# ────────────────────────────────────────────────────────────────
if x_axis == "time":
    data = (data
            .set_index("time")
            .resample("15T")[y_axis]
            .mean()
            .dropna()
            .reset_index())

# ────────────────────────────────────────────────────────────────
# 9 · Z-score normalisation + outlier removal |z| > 3
# ────────────────────────────────────────────────────────────────
for col in [x_axis, y_axis]:
    if col == "time":
        continue
    mu, sigma = data[col].mean(), data[col].std()
    if sigma != 0:
        z = (data[col] - mu) / sigma
        data = data[z.abs() <= Z_OUTLIER_CUT].copy()
        data[col] = (data[col] - mu) / sigma
    else:
        data[col] = 0.0

if data.empty:
    st.warning("All rows removed as outliers.")
    st.stop()

# ────────────────────────────────────────────────────────────────
# 10 · Plot
# ────────────────────────────────────────────────────────────────
fig = px.line(data, x=x_axis, y=y_axis)

if x_axis == "time":
    # Custom hover for time axis
    fig.update_traces(
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:.2f}"
    )

    # X-axis: one label per day
    fig.update_xaxes(
        title="Date",
        tickformat="%b %d",       # Apr 05
        dtick="D1",               # one per day
        ticklabelmode="period",   # no repeats
        tickangle=0,
        showgrid=True
    )
else:
    # Generic hover for non-time X axis
    fig.update_traces(
        hovertemplate=f"{x_axis}: "+"%{x}<br>"+f"{y_axis}: "+"%{y:.2f}"
    )

    fig.update_xaxes(
        title=x_axis,
        showgrid=True
    )


st.plotly_chart(fig, use_container_width=True)
st.dataframe(data[[x_axis, y_axis]].head(100), use_container_width=True)
