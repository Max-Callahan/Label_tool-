# -*- coding: utf-8 -*-
"""
Shapefile Feature Browser - Multi-County Edition
Interactive water body labeling tool for multiple counties.

Folder structure:
data/county_NHD/
├── Imperial/
│   ├── Imperial_waterbodies.shp
│   ├── Imperial_waterbodies.shx
│   ├── Imperial_waterbodies.dbf
│   └── Imperial_waterbodies.prj
├── Kern/
│   ├── Kern_waterbodies.shp
│   └── ...
└── ...

Run: streamlit run streamlit_app.py
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
DATA_ROOT = Path("data/county_NHD")
LABEL_OPTIONS = ("Lake", "Reservoir", "Pond", "Canal", "River", "Error")

# Page config
st.set_page_config(
    page_title="Water Body Labeler",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for maximum contrast
st.markdown("""
    <style>
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0d0d0d !important;
    }

    /* All text in sidebar - bright white */
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* Labels and text */
    [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 14px !important;
    }

    /* Radio buttons */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 15px !important;
        text-shadow: 0 0 2px rgba(0,0,0,0.8) !important;
    }

    /* Headings in sidebar */
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #00d4ff !important;
        font-weight: bold !important;
    }

    /* Select box */
    [data-testid="stSidebar"] div[data-baseweb="select"] label {
        color: #ffffff !important;
        font-weight: bold !important;
    }

    /* Input fields */
    [data-testid="stSidebar"] input {
        color: #ffffff !important;
        background-color: #333333 !important;
    }

    /* Buttons */
    [data-testid="stSidebar"] button {
        font-weight: bold !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def get_available_counties():
    """Get list of available counties from folder structure."""
    if not DATA_ROOT.exists():
        return []

    counties = []
    for county_dir in DATA_ROOT.iterdir():
        if county_dir.is_dir():
            # Check if it has shapefiles
            shapefiles = list(county_dir.glob("*.shp"))
            if shapefiles:
                counties.append(county_dir.name)

    return sorted(counties)

def find_shapefile(county_name):
    """Find the main shapefile in a county directory."""
    county_dir = DATA_ROOT / county_name
    shapefiles = list(county_dir.glob("*.shp"))

    if not shapefiles:
        return None

    # Prefer files with 'waterbodies' or 'water' in name
    for shp in shapefiles:
        if 'water' in shp.name.lower():
            return shp

    # Otherwise return first shapefile
    return shapefiles[0]

@st.cache_resource
def load_shapefile(county_name):
    """Load shapefile for specific county (cached)."""
    shapefile_path = find_shapefile(county_name)

    if not shapefile_path or not shapefile_path.exists():
        raise FileNotFoundError(f"No shapefile found for {county_name}")

    print(f"Loading: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)

    if "label" not in gdf.columns:
        gdf["label"] = ""

    return gdf.reset_index(drop=True)

def get_label(idx):
    """Get label for feature (checks memory buffer first, then disk)."""
    # Check in-memory changes first (fastest)
    if idx in st.session_state.changes:
        return st.session_state.changes[idx]
    # Then check shapefile
    return gdf.at[idx, "label"]

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR - COUNTY SELECTION
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.title("🗺️ County Selector")

# Get available counties
available_counties = get_available_counties()

if not available_counties:
    st.error("❌ No counties found!")
    st.info(f"Expected folder structure: `{DATA_ROOT}/{{County Name}}/{{shapefile.shp}}`")
    st.stop()

# County selection dropdown
selected_county = st.sidebar.selectbox(
    "Select County:",
    available_counties,
    index=0
)

# Initialize/switch county in session state
if "current_county" not in st.session_state or st.session_state.current_county != selected_county:
    st.session_state.current_county = selected_county
    st.session_state.gdf = load_shapefile(selected_county)
    st.session_state.current_idx = 0
    st.session_state.selected_label = None
    st.session_state.changes = {}  # In-memory buffer for labels
    st.session_state.labels_cache = {}  # Cache all labels from disk
    st.rerun()

# Load data for current county
gdf = st.session_state.gdf

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0

if "selected_label" not in st.session_state:
    st.session_state.selected_label = None

if "changes" not in st.session_state:
    st.session_state.changes = {}

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR CONTROLS
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.markdown("---")
st.sidebar.subheader(f"📊 {selected_county} County")

# Feature counter
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
save_col1, save_col2 = st.sidebar.columns([2, 1])
with save_col1:
    if st.button("💾 Save All Changes", use_container_width=True):
        if st.session_state.changes:
            # Get shapefile path
            shapefile_path = find_shapefile(selected_county)

            # Apply changes to GeoDataFrame
            for idx, label in st.session_state.changes.items():
                st.session_state.gdf.at[idx, "label"] = label

            # Save to disk (only once, batched)
            st.session_state.gdf.to_file(shapefile_path)

            changes_count = len(st.session_state.changes)

            # Clear in-memory buffer
            st.session_state.changes.clear()
            st.session_state.labels_cache.clear()

            st.sidebar.success(f"✓ Saved {changes_count} labels!")
            st.rerun()
        else:
            st.sidebar.info("No unsaved changes")
with save_col2:
    unsaved = len(st.session_state.changes)
    if unsaved > 0:
        st.metric("Unsaved", unsaved)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.title("💧 Water Body Labeler")
st.markdown(f"**County**: {selected_county} | **Features**: {n_features:,}")

# Get current feature
row = gdf.iloc[st.session_state.current_idx]
current_geom = row.geometry

# Status
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Feature", f"{st.session_state.current_idx + 1} / {n_features}")
with col2:
    current_label = get_label(st.session_state.current_idx)
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
st.markdown(f"""
    <div style="text-align: center; color: #999; font-size: 0.8em;">
    💧 Water Body Labeler | Multi-County Edition | v1.1 |
    Currently labeling: <b>{selected_county}</b> County
    </div>
    """, unsafe_allow_html=True)
