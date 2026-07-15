#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
#  viz_umap_3d.py
# ──────────────────────────────────────────────────────────────────────────
#  Evo-Buch Curriculum-Atlas — Static 3D UMAP Visualization
# ──────────────────────────────────────────────────────────────────────────
#
#  PURPOSE
#  -------
#  Produces static renders of the per-concept 3D UMAP projections generated
#  by `bertopic_pipeline.py`. Two complementary output types are supported:
#
#    1. MULTI-ANGLE CONTACT SHEETS (default)
#       A single 3D scatter viewed from one fixed camera angle is often
#       misleading on paper — occlusion and lack of parallax can make
#       well-separated clusters look tangled or vice versa. Instead, each
#       concept is rendered from several fixed (elevation, azimuth) angles
#       side-by-side in one figure, giving a much more trustworthy static
#       impression of the 3D structure.
#
#    2. ROTATING GIF ANIMATIONS (opt-in, via --animate)
#       Mirrors the web app's orbit-camera control (spec §3.4): the camera
#       sweeps azimuth at a fixed elevation, exactly like the "Start Orbit"
#       feature in curriculum_atlas.html. Useful for confirming a concept's
#       3D layout will read well in motion before a user ever opens the
#       interactive app, and for embedding a quick preview in docs/slides.
#
#  DATA SOURCE & COLOR CONSISTENCY
#  --------------------------------
#  This module deliberately reuses viz_umap_2d.py's data-loading and
#  color-map utilities (`load_manifest`, `load_or_build_color_maps`,
#  `deterministic_palette`, `resolve_color_map`, theme presets) rather than
#  re-implementing them. This guarantees:
#    - Identical subject/state colors across the 2D static plots, the 3D
#      static plots, and the interactive Plotly app (if it also loads
#      data/color_maps.json).
#    - A single place to fix data-loading bugs or schema changes.
#  See viz_umap_2d.py's module docstring for the full rationale.
#
#  OUTPUTS
#  -------
#    out/visualizations/3d/<Concept>/umap3d_<Concept>_<colorby>_<theme>.<ext>
#    out/visualizations/3d/<Concept>/orbit_<Concept>_<colorby>_<theme>.gif
#    out/visualizations/3d/_overview/overview3d_<colorby>_<theme>.<ext>
#
#  USAGE
#  -----
#    python viz_umap_3d.py
#    python viz_umap_3d.py --concepts Evolution --color-by topic
#    python viz_umap_3d.py --animate Evolution,Kultur --n-frames 180 --fps 30
#    python viz_umap_3d.py --view-angles "15:30,15:150,15:270,75:45"
#
# ══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")  # Headless-safe backend; no display server required.
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers '3d' projection)
    from mpl_toolkits.mplot3d.axes3d import Axes3D as Axes3DType
except ImportError as e:
    sys.exit(f"[FATAL] Missing dependency 'matplotlib': {e}. Run: pip install matplotlib")

# ── Reuse the 2D script's data-loading & color infrastructure ───────────────
# This is the key DRY decision described in the module docstring above: we
# import rather than duplicate, so all three visual outputs (2D static,
# 3D static, interactive web app) draw from one authoritative implementation.
try:
    from viz_umap_2d import (
        THEMES,
        NEUTRAL_GRAY,
        GOLDEN_ANGLE_DEG,
        VALID_COLOR_BY,
        load_manifest,
        load_or_build_color_maps,
        deterministic_palette,
        resolve_color_map,
        cap_legend_categories,
    )
except ImportError as e:
    sys.exit(f"[FATAL] Could not import viz_umap_2d.py (must be in the same "
              f"directory): {e}")


# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

# Default camera angles for the multi-angle contact sheet: chosen to give a
# reasonably orthogonal set of vantage points (front-ish, side-ish, and one
# steep top-down view) without any prior knowledge of the data's structure.
DEFAULT_VIEW_ANGLES: list[tuple[float, float]] = [
    (15.0, 30.0), (15.0, 150.0), (15.0, 270.0), (75.0, 45.0),
]

FIGSIZE_PER_PANEL = (5.2, 4.8)
FIGSIZE_OVERVIEW_CELL = (4.0, 3.8)
DEFAULT_DPI = 170
DEFAULT_POINT_SIZE = 9  # 3D points tend to need a touch more area than 2D to
                        # remain visible once perspective shrinks distant ones.

# Orbit-animation defaults, chosen to mirror sensible defaults for the web
# app's "Speed" / "Elevation" sliders (spec §3.4) so a static preview here
# looks like what a user would see with the default in-browser settings.
DEFAULT_ANIMATION_FRAMES = 120
DEFAULT_ANIMATION_FPS = 24
DEFAULT_ANIMATION_ELEVATION = 20.0


# ══════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════

def parse_view_angles(spec: str) -> list[tuple[float, float]]:
    """Parse a CLI string like "15:30,15:150,75:45" into a list of
    (elevation, azimuth) tuples in degrees.
    """
    angles: list[tuple[float, float]] = []
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        try:
            elev_str, azim_str = pair.split(":")
            angles.append((float(elev_str), float(azim_str)))
        except ValueError:
            sys.exit(f"[FATAL] Malformed --view-angles entry '{pair}'. "
                     f"Expected 'elevation:azimuth', e.g. '15:30'.")
    if not angles:
        sys.exit("[FATAL] --view-angles resolved to an empty list.")
    return angles


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(
        description="Static 3D UMAP visualizations for the Curriculum Atlas.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data-dir", type=Path, default=base_dir / "data",
                    help="Directory containing manifest.json and <Concept>.json.")
    p.add_argument("--out-dir", type=Path, default=base_dir / "out" / "visualizations" / "3d",
                    help="Output directory for rendered figures.")
    p.add_argument("--concepts", type=str, default=None,
                    help="Comma-separated subset of concepts to render. "
                         "Default: all concepts found in manifest.json.")
    p.add_argument("--color-by", type=str, default="subject,topic",
                    help=f"Comma-separated color dimensions to render. "
                         f"Choices: {VALID_COLOR_BY}")
    p.add_argument("--theme", type=str, default="both", choices=["dark", "light", "both"],
                    help="Which visual theme(s) to render.")
    p.add_argument("--formats", type=str, default="png",
                    help="Comma-separated static output formats, e.g. 'png,pdf'.")
    p.add_argument("--point-size", type=float, default=DEFAULT_POINT_SIZE,
                    help="Matplotlib marker size (points^2).")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="Raster output resolution.")
    p.add_argument("--exclude-outliers", action="store_true",
                    help="Drop is_outlier==true records before plotting.")
    p.add_argument("--view-angles", type=str,
                    default="15:30,15:150,15:270,75:45",
                    help="Comma-separated 'elevation:azimuth' pairs (degrees) "
                         "for the multi-angle contact sheet.")
    p.add_argument("--no-overview", dest="overview", action="store_false",
                    help="Skip generating the multi-concept overview grid.")
    p.add_argument("--force-color-maps", action="store_true",
                    help="Regenerate data/color_maps.json even if it already exists.")
    p.add_argument("--max-legend-items", type=int, default=18,
                    help="Cap legend entries per plot (long tails grouped as 'Weitere …').")

    # ── Orbit-animation options (opt-in) ─────────────────────────────────────
    p.add_argument("--animate", type=str, default=None,
                    help="Comma-separated concept names (or 'all') to also "
                         "render as rotating-camera GIF animations.")
    p.add_argument("--n-frames", type=int, default=DEFAULT_ANIMATION_FRAMES,
                    help="Number of frames in the orbit animation (one full "
                         "360° sweep is spread across all frames).")
    p.add_argument("--fps", type=int, default=DEFAULT_ANIMATION_FPS,
                    help="Playback frame rate of the orbit animation.")
    p.add_argument("--animation-elevation", type=float,
                    default=DEFAULT_ANIMATION_ELEVATION,
                    help="Fixed camera elevation (degrees) during the orbit "
                         "animation — mirrors the web app's Elevation slider.")

    p.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args(argv)


def setup_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("viz_umap_3d")
    logger.setLevel(getattr(logging, level))
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s",
                                            datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    return logger


# ══════════════════════════════════════════════════════════════════════════
#  DATA LOADING (3D-specific: explodes 'umap_3d' into x/y/z columns)
# ══════════════════════════════════════════════════════════════════════════

def load_concept_frame_3d(
    data_dir: Path, concept: str, log: logging.Logger,
) -> Optional[pd.DataFrame]:
    """Load and validate data/<Concept>.json into a flat, 3D-plot-ready
    DataFrame with explicit x/y/z columns derived from 'umap_3d'.

    Mirrors viz_umap_2d.load_concept_frame() but unpacks the 3-element
    coordinate instead of the 2-element one. Kept as a separate function
    (rather than a shared generic one) because the two call sites diverge
    just enough — 2 vs 3 output columns — that a shared abstraction would
    add more indirection than it saves.
    """
    import json  # local import: only needed here, keeps top-level imports lean

    path = data_dir / f"{concept}.json"
    if not path.exists():
        log.warning(f"[{concept}] No data file at {path} — skipping.")
        return None

    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        log.warning(f"[{concept}] Data file is empty — skipping.")
        return None

    required_keys = {"id", "state", "subject", "grade_band", "topic",
                      "is_outlier", "umap_3d", "excerpt"}
    missing_keys = required_keys - set(records[0].keys())
    if missing_keys:
        log.error(f"[{concept}] Record schema missing key(s) {missing_keys} — skipping.")
        return None

    df = pd.DataFrame.from_records(records)
    xyz = np.array(df["umap_3d"].tolist(), dtype=float)
    df["x"], df["y"], df["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    df["is_outlier"] = df["is_outlier"].astype(bool)

    log.info(f"[{concept}] Loaded {len(df):,} records "
             f"({df['is_outlier'].sum()} outlier).")
    return df


# ══════════════════════════════════════════════════════════════════════════
#  SHARED LEGEND HELPER (manual proxy artists)
# ══════════════════════════════════════════════════════════════════════════

def build_legend_handles(
    color_map: dict[str, str], shown_labels: list[str], n_hidden: int,
) -> list[Line2D]:
    """Construct proxy Line2D legend handles for a color mapping.

    3D scatter legends in matplotlib don't reliably auto-populate the way
    2D ones do once you have many separately-drawn subsets (one call to
    Axes3D.scatter() per category, as we do here for consistent per-category
    styling). Building the legend manually from the color map guarantees
    correct colors/labels regardless of how the scatter calls were split,
    and lets a single legend be shared across a multi-panel contact sheet
    instead of duplicating it per subplot.
    """
    handles = [
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor=color_map[label],
               markeredgecolor="none", markersize=6, label=label)
        for label in shown_labels
    ]
    if n_hidden > 0:
        handles.append(Line2D([0], [0], marker="o", linestyle="", markerfacecolor=NEUTRAL_GRAY,
                               markeredgecolor="none", markersize=6,
                               label=f"Weitere ({n_hidden}) …"))
    return handles


def style_3d_axes(ax: Axes3DType, theme: str) -> None:
    """Apply consistent dark/light theming to a 3D axes instance.

    Matplotlib's 3D axes expose pane/line color knobs separately from the
    standard 2D Axes API, so this needs its own styling routine rather than
    reusing viz_umap_2d.new_themed_axes().
    """
    t = THEMES[theme]
    ax.set_facecolor(t["bg"])
    # Each of the three coordinate planes ("panes") needs its background
    # and edge color set individually in mplot3d.
    for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
        pane.set_facecolor(t["bg"])
        pane.set_edgecolor(t["grid"])
        pane.set_alpha(1.0)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.line.set_color(t["spine"])
        axis._axinfo["grid"]["color"] = t["grid"]
    ax.tick_params(colors=t["fg"], labelsize=6)
    ax.xaxis.label.set_color(t["fg"])
    ax.yaxis.label.set_color(t["fg"])
    ax.zaxis.label.set_color(t["fg"])


def scatter_by_category(
    ax: Axes3DType, df: pd.DataFrame, color_by: str, color_map: dict[str, str],
    point_size: float, counts: pd.Series,
) -> None:
    """Draw one Axes3D.scatter() call per category (largest first), so that
    rarer categories layer on top and remain visible rather than being
    buried under a dominant class.
    """
    for label in counts.index:
        sub = df.loc[df[color_by] == label]
        ax.scatter(
            sub["x"], sub["y"], sub["z"],
            s=point_size, c=color_map.get(label, NEUTRAL_GRAY),
            alpha=0.78, linewidths=0, depthshade=True,
        )


# ══════════════════════════════════════════════════════════════════════════
#  PER-CONCEPT MULTI-ANGLE CONTACT SHEET
# ══════════════════════════════════════════════════════════════════════════

def plot_concept_3d_contact_sheet(
    df: pd.DataFrame,
    concept: str,
    color_by: str,
    theme: str,
    color_maps: dict[str, Any],
    point_size: float,
    max_legend_items: int,
    include_outliers: bool,
    view_angles: list[tuple[float, float]],
    out_dir: Path,
    formats: list[str],
    dpi: int,
    log: logging.Logger,
) -> None:
    """Render a single concept's 3D UMAP from several fixed camera angles,
    arranged side-by-side in one figure with one shared legend.
    """
    plot_df = df if include_outliers else df.loc[~df["is_outlier"]]
    if plot_df.empty:
        log.warning(f"[{concept}] No plottable rows for color_by={color_by} "
                    f"(include_outliers={include_outliers}) — skipping.")
        return

    t = THEMES[theme]
    color_map = resolve_color_map(plot_df, color_by, color_maps, concept)
    counts = plot_df[color_by].value_counts()
    shown_labels, has_overflow = cap_legend_categories(counts, max_legend_items)
    n_hidden = len(counts) - len(shown_labels) if has_overflow else 0

    n_panels = len(view_angles)
    n_cols = min(n_panels, 2)
    n_rows = math.ceil(n_panels / n_cols)

    fig = plt.figure(
        figsize=(FIGSIZE_PER_PANEL[0] * n_cols, FIGSIZE_PER_PANEL[1] * n_rows),
        facecolor=t["bg"],
    )

    # Shared axis limits across all panels so the same cluster occupies the
    # same apparent volume regardless of viewing angle (fair visual comparison).
    pad = 0.05
    x_range = plot_df["x"].max() - plot_df["x"].min() or 1.0
    y_range = plot_df["y"].max() - plot_df["y"].min() or 1.0
    z_range = plot_df["z"].max() - plot_df["z"].min() or 1.0
    xlim = (plot_df["x"].min() - pad * x_range, plot_df["x"].max() + pad * x_range)
    ylim = (plot_df["y"].min() - pad * y_range, plot_df["y"].max() + pad * y_range)
    zlim = (plot_df["z"].min() - pad * z_range, plot_df["z"].max() + pad * z_range)

    for i, (elev, azim) in enumerate(view_angles):
        ax = fig.add_subplot(n_rows, n_cols, i + 1, projection="3d")
        style_3d_axes(ax, theme)
        scatter_by_category(ax, plot_df, color_by, color_map, point_size, counts)
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_zlim(zlim)
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(f"elev={elev:.0f}°, azim={azim:.0f}°",
                     color=t["fg"], fontsize=9, pad=2)
        ax.set_xlabel("UMAP-1", fontsize=7)
        ax.set_ylabel("UMAP-2", fontsize=7)
        ax.set_zlabel("UMAP-3", fontsize=7)

    handles = build_legend_handles(color_map, shown_labels, n_hidden)
    fig.legend(
        handles=handles, loc="center left", bbox_to_anchor=(0.99, 0.5),
        fontsize=7.5, facecolor=t["bg"], edgecolor=t["spine"], labelcolor=t["fg"],
        title=color_by.replace("_", " ").title(), title_fontsize=8.5,
        frameon=True, borderaxespad=0.0,
    )

    fig.suptitle(f"{concept} — UMAP 3D (Mehrwinkelansicht)  ·  eingefärbt nach {color_by}",
                 color=t["fg"], fontsize=14, y=0.995)
    fig.tight_layout(rect=[0, 0, 0.90, 0.97])

    concept_dir = out_dir / concept
    concept_dir.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        out_path = concept_dir / f"umap3d_{concept}_{color_by}_{theme}.{fmt}"
        fig.savefig(out_path, dpi=dpi, facecolor=t["bg"], bbox_inches="tight")
        log.debug(f"  Saved {out_path}")
    plt.close(fig)
    log.info(f"[{concept}] Saved {color_by}/{theme} contact sheet "
             f"({n_panels} angles × {len(formats)} format(s)).")


# ══════════════════════════════════════════════════════════════════════════
#  ORBIT ANIMATION (rotating GIF) — mirrors the web app's orbit-camera control
# ══════════════════════════════════════════════════════════════════════════

def animate_concept_3d(
    df: pd.DataFrame,
    concept: str,
    color_by: str,
    theme: str,
    color_maps: dict[str, Any],
    point_size: float,
    max_legend_items: int,
    include_outliers: bool,
    elevation: float,
    n_frames: int,
    fps: int,
    out_dir: Path,
    log: logging.Logger,
) -> None:
    """Render a rotating-camera GIF of a single concept's 3D UMAP.

    The camera holds a fixed elevation (mirroring the web app's "Elevation"
    slider) and sweeps azimuth through a full 360° over `n_frames` frames
    (mirroring the "Speed" slider — more frames per rotation = smoother/
    slower apparent motion at a fixed fps). Uses Pillow's GIF writer, which
    ships with matplotlib's dependencies, so no external ffmpeg binary is
    required.
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    plot_df = df if include_outliers else df.loc[~df["is_outlier"]]
    if plot_df.empty:
        log.warning(f"[{concept}] No plottable rows for animation — skipping.")
        return

    t = THEMES[theme]
    color_map = resolve_color_map(plot_df, color_by, color_maps, concept)
    counts = plot_df[color_by].value_counts()
    shown_labels, has_overflow = cap_legend_categories(counts, max_legend_items)
    n_hidden = len(counts) - len(shown_labels) if has_overflow else 0

    fig = plt.figure(figsize=(7.5, 7.0), facecolor=t["bg"])
    ax = fig.add_subplot(111, projection="3d")
    style_3d_axes(ax, theme)
    scatter_by_category(ax, plot_df, color_by, color_map, point_size, counts)

    handles = build_legend_handles(color_map, shown_labels, n_hidden)
    fig.legend(
        handles=handles, loc="upper right", fontsize=7, facecolor=t["bg"],
        edgecolor=t["spine"], labelcolor=t["fg"],
        title=color_by.replace("_", " ").title(), title_fontsize=8, framealpha=0.85,
    )
    ax.set_title(f"{concept} — Orbit (elev={elevation:.0f}°)  ·  {color_by}",
                 color=t["fg"], fontsize=12, pad=10)

    def _update(frame_idx: int):
        azim = (frame_idx / n_frames) * 360.0
        ax.view_init(elev=elevation, azim=azim)
        return ()

    anim = FuncAnimation(fig, _update, frames=n_frames, interval=1000 / fps, blit=False)

    concept_dir = out_dir / concept
    concept_dir.mkdir(parents=True, exist_ok=True)
    out_path = concept_dir / f"orbit_{concept}_{color_by}_{theme}.gif"
    try:
        anim.save(out_path, writer=PillowWriter(fps=fps))
        log.info(f"[{concept}] Saved orbit animation "
                 f"({n_frames} frames @ {fps}fps) -> {out_path}")
    except Exception as e:
        log.error(f"[{concept}] Failed to save orbit animation: {e}")
    finally:
        plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════
#  MULTI-CONCEPT OVERVIEW GRID (single fixed angle per concept)
# ══════════════════════════════════════════════════════════════════════════

def plot_overview_grid_3d(
    frames: dict[str, pd.DataFrame],
    color_by: str,
    theme: str,
    color_maps: dict[str, Any],
    point_size: float,
    include_outliers: bool,
    out_dir: Path,
    formats: list[str],
    dpi: int,
    log: logging.Logger,
) -> None:
    """Render a small-multiples overview: one 3D mini-scatter per concept at
    a single fixed angle, for a fast bird's-eye QA pass across the whole
    Curriculum Atlas. Unlike the per-concept contact sheets, this uses only
    one view angle per cell to keep the grid legible at a glance.
    """
    concepts = list(frames.keys())
    if not concepts:
        log.warning("No concept data available — skipping 3D overview grid.")
        return

    n = len(concepts)
    n_cols = math.ceil(math.sqrt(n))
    n_rows = math.ceil(n / n_cols)
    t = THEMES[theme]
    fixed_elev, fixed_azim = 20.0, 45.0

    fig = plt.figure(
        figsize=(FIGSIZE_OVERVIEW_CELL[0] * n_cols, FIGSIZE_OVERVIEW_CELL[1] * n_rows),
        facecolor=t["bg"],
    )

    for idx, concept in enumerate(concepts):
        ax = fig.add_subplot(n_rows, n_cols, idx + 1, projection="3d")
        style_3d_axes(ax, theme)

        df = frames[concept]
        plot_df = df if include_outliers else df.loc[~df["is_outlier"]]
        if plot_df.empty:
            ax.text2D(0.5, 0.5, "Keine Daten", ha="center", va="center",
                      color=t["fg"], fontsize=8, transform=ax.transAxes)
        else:
            color_map = resolve_color_map(plot_df, color_by, color_maps, concept)
            counts = plot_df[color_by].value_counts()
            scatter_by_category(ax, plot_df, color_by, color_map,
                                 max(point_size * 0.6, 2), counts)

        ax.view_init(elev=fixed_elev, azim=fixed_azim)
        ax.set_title(concept, color=t["fg"], fontsize=9, pad=0)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])

    fig.suptitle(f"Evo-Buch Curriculum-Atlas — 3D-Übersicht ({color_by})",
                 color=t["fg"], fontsize=16, y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    overview_dir = out_dir / "_overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        out_path = overview_dir / f"overview3d_{color_by}_{theme}.{fmt}"
        fig.savefig(out_path, dpi=dpi, facecolor=t["bg"], bbox_inches="tight")
        log.info(f"Saved 3D overview grid -> {out_path}")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = parse_args()
    log = setup_logging(args.log_level)

    log.info("=" * 78)
    log.info("  Curriculum Atlas — Static 3D UMAP Visualizations")
    log.info("=" * 78)

    color_by_list = [c.strip() for c in args.color_by.split(",") if c.strip()]
    invalid = [c for c in color_by_list if c not in VALID_COLOR_BY]
    if invalid:
        sys.exit(f"[FATAL] Invalid --color-by value(s) {invalid}. "
                 f"Choices: {VALID_COLOR_BY}")

    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    formats = [f.strip().lstrip(".") for f in args.formats.split(",") if f.strip()]
    view_angles = parse_view_angles(args.view_angles)

    manifest = load_manifest(args.data_dir, log)
    available_concepts = list(manifest.get("concepts", {}).keys())

    if args.concepts:
        requested = [c.strip() for c in args.concepts.split(",") if c.strip()]
        concepts = [c for c in requested if c in available_concepts]
        skipped = set(requested) - set(concepts)
        if skipped:
            log.warning(f"Requested concept(s) not in manifest, skipping: {skipped}")
    else:
        concepts = manifest.get("concept_order", available_concepts)
        concepts = [c for c in concepts if c in available_concepts]

    log.info(f"Rendering {len(concepts)} concept(s) × {len(color_by_list)} color "
             f"scheme(s) × {len(themes)} theme(s) × {len(view_angles)} view angle(s).")

    color_maps = load_or_build_color_maps(manifest, args.data_dir, log,
                                           force=args.force_color_maps)

    frames: dict[str, pd.DataFrame] = {}
    for concept in concepts:
        df = load_concept_frame_3d(args.data_dir, concept, log)
        if df is not None:
            frames[concept] = df

    for concept, df in frames.items():
        for color_by in color_by_list:
            if color_by not in df.columns:
                log.warning(f"[{concept}] Column '{color_by}' not present — skipping.")
                continue
            for theme in themes:
                plot_concept_3d_contact_sheet(
                    df, concept, color_by, theme, color_maps,
                    args.point_size, args.max_legend_items,
                    include_outliers=not args.exclude_outliers,
                    view_angles=view_angles, out_dir=args.out_dir,
                    formats=formats, dpi=args.dpi, log=log,
                )

    if args.overview:
        for color_by in color_by_list:
            if color_by == "topic":
                log.info("Skipping 3D overview grid for 'topic' — topic IDs are "
                         "concept-scoped and not visually comparable across "
                         "concepts in a single shared figure.")
                continue
            for theme in themes:
                plot_overview_grid_3d(
                    frames, color_by, theme, color_maps, args.point_size,
                    include_outliers=not args.exclude_outliers,
                    out_dir=args.out_dir, formats=formats, dpi=args.dpi, log=log,
                )

    # ── Optional orbit-animation pass ────────────────────────────────────────
    if args.animate:
        animate_targets = (
            list(frames.keys()) if args.animate.strip().lower() == "all"
            else [c.strip() for c in args.animate.split(",") if c.strip() in frames]
        )
        log.info(f"Rendering orbit animations for {len(animate_targets)} concept(s) …")
        for concept in animate_targets:
            df = frames[concept]
            for color_by in color_by_list:
                if color_by not in df.columns:
                    continue
                for theme in themes:
                    animate_concept_3d(
                        df, concept, color_by, theme, color_maps,
                        args.point_size, args.max_legend_items,
                        include_outliers=not args.exclude_outliers,
                        elevation=args.animation_elevation,
                        n_frames=args.n_frames, fps=args.fps,
                        out_dir=args.out_dir, log=log,
                    )

    log.info("=" * 78)
    log.info(f"DONE. Rendered {len(frames)}/{len(concepts)} concept(s) successfully.")
    log.info("=" * 78)


if __name__ == "__main__":
    main()
