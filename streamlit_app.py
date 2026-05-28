# -*- coding: utf-8 -*-
"""
Created on Wed May 27 20:04:33 2026

@author: mcallahan
"""

# -*- coding: utf-8 -*-
"""
Shapefile Feature Browser - Streamlit Web App
Interactive water body labeling tool running in the browser.

Run: streamlit run streamlit_app.py
Deploy: Push to GitHub → Streamlit Cloud auto-deploys
"""

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
SHAPEFILE_PATH = "data/Imperial_waterbodies.shp"
LABEL_OPTIONS = ("Lake", "Reservoir", "Pond", "Canal", "River", "Error")

# Page config
st.set_page_config(
    page_title="Water Body Labeler",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark theme CSS
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    .main {
        background-color: #fafbfc;
    }
    h1, h2, h3 {
        color: #24292e;
    }
    </style>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def load_shapefile():
    """Load shapefile (cached)."""
    if not Path(SHAPEFILE_PATH).exists():
        st.error(f"❌ Shapefile not found: {SHAPEFILE_PATH}")
        st.info("Make sure Imperial_waterbodies.shp is in the data/ folder")
        st.stop()

    gdf = gpd.read_file(SHAPEFILE_PATH)
    if "label" not in gdf.columns:
        gdf["label"] = ""
    return gdf.reset_index(drop=True)

# Initialize session state
if "gdf" not in st.session_state:
    st.session_state.gdf = load_shapefile()

if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0

if "selected_label" not in st.session_state:
    st.session_state.selected_label = None

if "changes" not in st.session_state:
    st.session_state.changes = {}

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR CONTROLS
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.title("🗺️ Feature Browser")

# Feature counter
gdf = st.session_state.gdf
n_features = len(gdf)
saved_count = (gdf["label"] != "").sum() + len(st.session_state.changes)
progress = int(100 * saved_count / n_features)

st.sidebar.metric("Progress", f"{saved_count}/{n_features} ({progress}%)")

# Navigation
col1, col2, col3, col4 = st.sidebar.columns(4)
with col1:
    if st.button("⏮ First"):
        st.session_state.current_idx = 0
        st.rerun()
with col2:
    if st.button("◀ Prev"):
        st.session_state.current_idx = max(0, st.session_state.current_idx - 1)
        st.rerun()
with col3:
    if st.button("Next ▶"):
        st.session_state.current_idx = min(n_features - 1, st.session_state.current_idx + 1)
        st.rerun()
with col4:
    if st.button("Last ⏭"):
        st.session_state.current_idx = n_features - 1
        st.rerun()

# Feature selector
st.sidebar.markdown("---")
feature_idx = st.sidebar.number_input(
    "Jump to feature:",
    min_value=1,
    max_value=n_features,
    value=st.session_state.current_idx + 1
) - 1
st.session_state.current_idx = feature_idx

# Label selection
st.sidebar.markdown("---")
st.sidebar.subheader("Select Label")
selected = st.sidebar.radio(
    "Water Body Type:",
    LABEL_OPTIONS,
    index=0 if st.session_state.selected_label is None else LABEL_OPTIONS.index(st.session_state.selected_label)
)

# Color for label buttons
label_colors = {
    "Lake": "🟦",
    "Reservoir": "🟩",
    "Pond": "🟪",
    "Canal": "🟨",
    "River": "🟦",
    "Error": "🟥"
}

if selected:
    st.session_state.selected_label = selected
    col1, col2 = st.sidebar.columns([1, 1])
    with col1:
        if st.button("✓ Label Feature", use_container_width=True):
            st.session_state.changes[st.session_state.current_idx] = selected
            st.success(f"✓ Labeled as {selected}")
            st.rerun()

# Save button
st.sidebar.markdown("---")
if st.sidebar.button("💾 Save All Changes", use_container_width=True):
    if st.session_state.changes:
        for idx, label in st.session_state.changes.items():
            st.session_state.gdf.at[idx, "label"] = label

        st.session_state.gdf.to_file(SHAPEFILE_PATH)
        st.session_state.changes.clear()
        st.sidebar.success(f"✓ Saved {len(st.session_state.changes)} changes!")
        st.rerun()
    else:
        st.sidebar.info("No unsaved changes")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.title("💧 Water Body Labeler")

# Get current feature
row = gdf.iloc[st.session_state.current_idx]
current_geom = row.geometry

# Status
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Feature", f"{st.session_state.current_idx + 1} / {n_features}")
with col2:
    current_label = st.session_state.changes.get(
        st.session_state.current_idx,
        gdf.at[st.session_state.current_idx, "label"]
    )
    st.metric("Current Label", current_label if current_label else "—")
with col3:
    st.metric("Geometry Type", current_geom.geom_type)

st.markdown("---")

# Map
col_map, col_info = st.columns([2, 1])

with col_map:
    st.subheader("Map")

    # Create map centered on feature
    bounds = current_geom.bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap"
    )

    # Draw all features (context)
    for idx, g in gdf.geometry.items():
        if idx != st.session_state.current_idx:
            folium.GeoJson(
                g,
                style_function=lambda x: {
                    "color": "#999",
                    "weight": 0.5,
                    "opacity": 0.3
                }
            ).add_to(m)

    # Draw current feature (highlight)
    folium.GeoJson(
        current_geom,
        style_function=lambda x: {
            "fillColor": "#00d4ff",
            "color": "#ff6b6b",
            "weight": 3,
            "opacity": 0.8,
            "fillOpacity": 0.6
        }
    ).add_to(m)

    # Display map
    st_folium(m, width=700, height=500)

with col_info:
    st.subheader("Properties")

    # Feature attributes
    info_df = pd.DataFrame({
        "Property": gdf.columns[:-1],  # Exclude geometry
        "Value": [str(row[col]) for col in gdf.columns[:-1]]
    })

    st.dataframe(info_df, use_container_width=True, hide_index=True)

    # Geometry stats
    st.markdown("---")
    st.write(f"**Area**: {current_geom.area:.2f} sq units")
    st.write(f"**Perimeter**: {current_geom.length:.2f} units")

# ══════════════════════════════════════════════════════════════════════════════
# STATISTICS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📊 Statistics")

col1, col2, col3, col4 = st.columns(4)

# Count by label
label_counts = gdf["label"].value_counts()

with col1:
    st.metric("Total Features", n_features)
with col2:
    st.metric("Labeled", (gdf["label"] != "").sum())
with col3:
    st.metric("Unlabeled", (gdf["label"] == "").sum())
with col4:
    st.metric("Unsaved Changes", len(st.session_state.changes))

# Label breakdown
if len(label_counts) > 0:
    st.markdown("**Labels by Type**")
    for label, count in label_counts.items():
        if label:
            st.write(f"{label_colors.get(label, '•')} {label}: {count}")

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #999; font-size: 0.8em;">
    💧 Water Body Labeler | Imperial County | v1.0 |
    <a href="https://github.com">GitHub</a>
    </div>
    """, unsafe_allow_html=True)