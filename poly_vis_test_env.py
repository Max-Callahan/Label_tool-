# -*- coding: utf-8 -*-
"""
browse_shapefile.py
Professional shapefile feature browser and labeler.
Dark theme with sleek interface. Fully optimized for speed.
"""
import os
os.add_dll_directory(r"C:\Users\mcallahan\anaconda3\envs\WattsOnWater2\Library\bin")
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.widgets import Button
from shapely.validation import make_valid
import contextily as ctx
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════════════════
# DARK PROFESSIONAL COLOR SCHEME
# ══════════════════════════════════════════════════════════════════════════════
COLORS = {
    "bg":           "#1a1a1a",
    "panel_bg":     "#252525",
    "border":       "#404040",
    "text_primary": "#ffffff",
    "text_secondary": "#b0b0b0",
    "accent":       "#00d4ff",
    "accent_hover": "#00a8cc",
    "success":      "#00ff88",
    "success_hover": "#00cc66",
    "unsaved":      "#ff6b6b",
    "map_bg":       "#1f1f1f",
}

# ══════════════════════════════════════════════════════════════════════════════
# ERROR CLASSES
# ══════════════════════════════════════════════════════════════════════════════
class FeatureBrowserError(Exception):
    """Base error class for FeatureBrowser."""
    pass

class ShapefileError(FeatureBrowserError):
    """Error loading or saving shapefile."""
    pass

class InvalidLabelError(FeatureBrowserError):
    """Error with label selection or validation."""
    pass

class SaveError(FeatureBrowserError):
    """Error saving changes to shapefile."""
    pass

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
SHAPEFILE = r"Y:\personal\mcallahan\Business\WattsonWater\DATA\Hydrography\County_NHD\Imperial\Imperial_waterbodies.shp"
LABEL_OPTIONS = ("Lake", "Reservoir", "Pond", "Canal", "River", "Error")
LABEL_COLORS = {
    "Lake": COLORS["border"],
    "Reservoir": COLORS["border"],
    "Pond": COLORS["border"],
    "Canal": COLORS["border"],
    "River": COLORS["border"],
    "Error": "#ff4444",  # Red for errors
}
SHOW_COLS = None
BASEMAP = ctx.providers.Esri.WorldImagery
CACHE_DIR = Path.home() / ".shapefile_cache"
CACHE_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
def load(path):
    """Load and validate shapefile."""
    try:
        print(f"Loading {path}...")
        gdf = gpd.read_file(path)
        bad = (~gdf.geometry.is_valid).sum()
        if bad:
            print(f"  Repairing {bad} invalid geometries...")
            gdf["geometry"] = gdf.geometry.apply(make_valid)
        print(f"  {len(gdf)} features loaded, CRS: {gdf.crs}")
        return gdf.reset_index(drop=True)
    except FileNotFoundError:
        raise ShapefileError(f"Shapefile not found: {path}")
    except Exception as e:
        raise ShapefileError(f"Error loading shapefile: {str(e)}")

class FeatureBrowser:
    def __init__(self, gdf, show_cols=None):
        self.gdf  = gdf
        self.n    = len(gdf)
        self.idx  = 0
        self.cols = show_cols or [c for c in gdf.columns if c != "geometry"]
        self.selected_label = LABEL_OPTIONS[0]
        self.saved_count = 0

        # In-memory changes (fast)
        self.changes = {}  # {idx: label}
        self.dirty = False  # Track if unsaved changes

        # Add label column if it doesn't exist
        if "label" not in self.gdf.columns:
            self.gdf["label"] = ""
        else:
            self.saved_count = (self.gdf["label"] != "").sum()

        # Pre-compute Web Mercator projections (huge speedup)
        print("Pre-computing projections...")
        self.gdf_wm = self.gdf.to_crs(epsg=3857)
        print("Ready!")

        # ── Figure setup ──────────────────────────────────────────────────────
        self.fig = plt.figure(figsize=(16, 10), facecolor=COLORS["bg"])
        self.fig.canvas.manager.set_window_title("Feature Browser")

        # Map on left
        self.ax_map = self.fig.add_axes([0.01, 0.05, 0.57, 0.90])
        self.ax_map.set_facecolor(COLORS["map_bg"])

        # Current label box
        ax_label_box = self.fig.add_axes([0.59, 0.35, 0.10, 0.30])
        ax_label_box.set_facecolor(COLORS["panel_bg"])
        ax_label_box.set_xticks([])
        ax_label_box.set_yticks([])
        for spine in ax_label_box.spines.values():
            spine.set_edgecolor(COLORS["success"])
            spine.set_linewidth(2)

        self.current_label_top = ax_label_box.text(
            0.5, 0.5, "", transform=ax_label_box.transAxes,
            fontsize=14, fontweight="bold", color=COLORS["success"],
            ha="center", va="center"
        )

        # Right panel
        ax_panel = self.fig.add_axes([0.71, 0.05, 0.27, 0.90])
        ax_panel.set_facecolor(COLORS["panel_bg"])
        ax_panel.set_xticks([])
        ax_panel.set_yticks([])
        for spine in ax_panel.spines.values():
            spine.set_edgecolor(COLORS["border"])
            spine.set_linewidth(1)
        self.ax_panel = ax_panel

        # ── Navigation buttons ────────────────────────────────────────────────
        btn_w, btn_h = 0.10, 0.06
        btn_y = 0.88

        ax_back = self.fig.add_axes([0.73, btn_y, btn_w, btn_h])
        self.btn_back = Button(ax_back, "< Back", color=COLORS["accent"],
                               hovercolor=COLORS["accent_hover"])
        self.btn_back.label.set_color(COLORS["bg"])
        self.btn_back.label.set_fontsize(11)
        self.btn_back.label.set_fontweight("bold")
        self.btn_back.on_clicked(lambda e: self.go(self.idx - 1))

        ax_fwd = self.fig.add_axes([0.84, btn_y, btn_w, btn_h])
        self.btn_fwd = Button(ax_fwd, "Forward >", color=COLORS["accent"],
                              hovercolor=COLORS["accent_hover"])
        self.btn_fwd.label.set_color(COLORS["bg"])
        self.btn_fwd.label.set_fontsize(11)
        self.btn_fwd.label.set_fontweight("bold")
        self.btn_fwd.on_clicked(lambda e: self.go(self.idx + 1))

        # Feature counter
        self.counter_text = ax_panel.text(
            0.5, 0.945, "", transform=ax_panel.transAxes,
            fontsize=12, fontweight="bold", color=COLORS["text_primary"],
            ha="center", va="top"
        )

        # ── Label selection buttons ───────────────────────────────────────────
        btn_spacing = 0.12
        btn_height = 0.08
        self.label_buttons = {}

        for i, label in enumerate(LABEL_OPTIONS):
            y_pos = 0.80 - (i * btn_spacing)
            ax_btn = self.fig.add_axes([0.73, y_pos, 0.24, btn_height])

            # Use custom color for Error button
            btn_color = LABEL_COLORS.get(label, COLORS["border"])
            btn = Button(ax_btn, label, color=btn_color,
                        hovercolor=COLORS["accent"])
            btn.label.set_color(COLORS["text_primary"])
            btn.label.set_fontsize(11)
            btn.label.set_fontweight("bold")

            btn.on_clicked(lambda e, lbl=label: self.select_label_fast(lbl))
            self.label_buttons[label] = (btn, ax_btn)

        # Save button
        ax_save = self.fig.add_axes([0.73, 0.10, 0.24, 0.08])
        self.btn_save = Button(ax_save, "Save Changes", color=COLORS["success"],
                               hovercolor=COLORS["success_hover"])
        self.btn_save.label.set_color(COLORS["bg"])
        self.btn_save.label.set_fontsize(12)
        self.btn_save.label.set_fontweight("bold")
        self.btn_save.on_clicked(lambda e: self.save_changes())

        # Status message
        self.status_text = ax_panel.text(
            0.05, 0.02, "", transform=ax_panel.transAxes,
            fontsize=9, color=COLORS["text_secondary"], va="bottom",
            style="italic"
        )

        # Keyboard shortcuts
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)

        self.draw()
        plt.tight_layout()
        plt.show()

    def select_label_fast(self, label):
        """Select label instantly (no disk write)."""
        self.selected_label = label
        self.changes[self.idx] = label  # Store in memory
        self.dirty = True

        # Update button colors instantly
        for lbl, (btn, ax) in self.label_buttons.items():
            if lbl == label:
                btn.color = COLORS["accent"]
                btn.hovercolor = COLORS["accent_hover"]
                btn.label.set_color(COLORS["bg"])
            else:
                btn.color = COLORS["border"]
                btn.hovercolor = COLORS["accent"]
                btn.label.set_color(COLORS["text_primary"])

        # Update label display
        self.current_label_top.set_text(label)
        self.status_text.set_text("✎ Unsaved changes (Press Space to save)")
        self.status_text.set_color(COLORS["unsaved"])

        self.fig.canvas.draw_idle()

    def save_changes(self):
        """Write all changes to shapefile at once."""
        if not self.dirty:
            self.status_text.set_text("No changes to save")
            return

        try:
            # Apply all changes
            changes_count = len(self.changes)
            for idx, label in self.changes.items():
                self.gdf.at[idx, "label"] = label

            # Write once
            self.gdf.to_file(SHAPEFILE)
            self.saved_count = (self.gdf["label"] != "").sum()
            pct = int(100 * self.saved_count / self.n)

            self.dirty = False
            self.changes.clear()
            self.status_text.set_text(f"✓ Saved {changes_count} labels ({pct}% complete)")
            self.status_text.set_color(COLORS["success"])
            print(f"  ✓ Saved {changes_count} changes to shapefile")
        except PermissionError:
            raise SaveError(f"Permission denied: Cannot write to {SHAPEFILE}")
        except Exception as e:
            raise SaveError(f"Error saving shapefile: {str(e)}")

    def go(self, new_idx):
        """Navigate to feature."""
        self.idx = new_idx % self.n
        self.draw_map_only()  # Only redraw map, not everything

    def on_key(self, event):
        """Handle keyboard."""
        if event.key in ("right", "down"):
            self.go(self.idx + 1)
        elif event.key in ("left", "up"):
            self.go(self.idx - 1)

    def draw_map_only(self):
        """Fast redraw - only map changes, not UI."""
        self.ax_map.clear()
        self.ax_map.set_facecolor(COLORS["map_bg"])

        row = self.gdf_wm.iloc[self.idx]
        current = self.gdf_wm.iloc[[self.idx]]
        others = self.gdf_wm.drop(index=self.idx)

        # Draw context
        if not others.empty:
            others.plot(ax=self.ax_map, color="#404040", edgecolor="#505050",
                       linewidth=0.2, alpha=0.3)

        # Draw current
        current.plot(ax=self.ax_map, color="#00d4ff", edgecolor="#00ff88",
                    linewidth=2.5, alpha=0.8)

        # Zoom
        bounds = current.total_bounds
        xpad = max((bounds[2] - bounds[0]) * 0.4, 100)
        ypad = max((bounds[3] - bounds[1]) * 0.4, 100)
        self.ax_map.set_xlim(bounds[0] - xpad, bounds[2] + xpad)
        self.ax_map.set_ylim(bounds[1] - ypad, bounds[3] + ypad)

        # Basemap (cached)
        try:
            ctx.add_basemap(self.ax_map, source=BASEMAP, zoom="auto", alpha=0.7)
        except Exception as e:
            pass  # Skip basemap if network issue

        self.ax_map.set_title(f"Feature {self.idx + 1} of {self.n}",
                             fontsize=14, fontweight="bold",
                             color=COLORS["text_primary"], pad=10)
        self.ax_map.tick_params(labelsize=8, color=COLORS["text_secondary"])
        for spine in self.ax_map.spines.values():
            spine.set_color(COLORS["border"])

        # Update counter and label
        self.counter_text.set_text(f"{self.idx + 1} / {self.n}")

        # Check if this feature has been labeled (in memory or disk)
        current_label = self.changes.get(self.idx, self.gdf.at[self.idx, "label"])
        if current_label:
            self.current_label_top.set_text(current_label)
            self.selected_label = current_label
            # Highlight corresponding button
            if current_label in LABEL_OPTIONS:
                for lbl, (btn, ax) in self.label_buttons.items():
                    if lbl == current_label:
                        btn.color = COLORS["accent"]
                        btn.label.set_color(COLORS["bg"])
                    else:
                        btn.color = COLORS["border"]
                        btn.label.set_color(COLORS["text_primary"])
        else:
            self.current_label_top.set_text("(none)")
            # Reset all buttons
            for lbl, (btn, ax) in self.label_buttons.items():
                btn.color = COLORS["border"]
                btn.label.set_color(COLORS["text_primary"])

        self.fig.canvas.draw_idle()

    def draw(self):
        """Initial draw."""
        self.draw_map_only()

# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    gdf = load(SHAPEFILE)
    browser = FeatureBrowser(gdf, show_cols=SHOW_COLS)