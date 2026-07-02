#!/usr/bin/env python3
"""
08_visualization/08a_viz_umap_2d.py
Generate high-quality 2D UMAP visualizations for:
  – each individual concept
  – concept groups
  – full corpus
Dark-themed, publication-ready PNG outputs.
"""

import os, sys, pickle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from tqdm import tqdm

from src.utils import CACHE_DIR, log, OUTPUT_DIR, CSV_PATH



# LOG = get_logger("08a_viz_2d", LOG_DIR)

# UMAP2D_DIR = os.path.join(OUTPUTS_ROOT, "umap", "2d")
# VIZ2D_DIR  = os.path.join(OUTPUTS_ROOT, "visualizations", "2d")
# ensure_dir(VIZ2D_DIR)

CONCEPT_COLORS = {"Evolution":"#333333"}

PLOT_BGCOLOR = "#ffffff"
FONT_COLOR   = "#333333"
GRID_COLOR   = "#e0e0e0"
FIGURE_DPI   = 150

FIG_SIZE_WIDE   = (14, 5)
FIG_SIZE_SQUARE = (8, 8)

def topic_color_palette(n: int, concept: str) -> list[str]:
    """Return a list of n hex colours for topic scatter plots."""
    import colorsys

    base_hue = (hash(concept) % 360) / 360.0  # deterministic per concept
    colors = []
    for i in range(n):
        hue        = (base_hue + i / max(n, 1)) % 1.0
        saturation = 0.65
        lightness  = 0.60
        r, g, b    = colorsys.hls_to_rgb(hue, lightness, saturation)
        colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colors

def dark_fig(figsize=FIG_SIZE_WIDE):
    fig, ax = plt.subplots(figsize=figsize, facecolor=PLOT_BGCOLOR)
    ax.set_facecolor(PLOT_BGCOLOR)
    ax.tick_params(colors=FONT_COLOR, labelsize=9)
    ax.xaxis.label.set_color(FONT_COLOR)
    ax.yaxis.label.set_color(FONT_COLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)
    ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.5)
    return fig, ax

def make_dir_if_necessary(concept):
    keyword_dir = OUTPUT_DIR / concept
    keyword_dir.mkdir(parents=True, exist_ok=True)

def load_umap2d_coords(umap_path: Path):
    try:
        coords = np.load(umap_path)
        log.info(f"Loaded umap coords of shape {coords.shape}")
        return coords
    except Exception as e:
        log.info(e)
        return


def plot_concept_2d(doc_df: pd.DataFrame, umap_embeddings: np.ndarray | None, concept: str, color_by: str = "topic") -> None:
    """2D scatter plot coloured by BERTopic topic for a single concept."""
    #topic_model_path = CACHE_DIR / concept / f"topic_model_{concept}.pkl"
    #topic_info_path = OUTPUT_DIR / concept / f"topic_info_{concept}.csv"
    if color_by not in ["subject", "topic"]:
        log.error("Pick subject or topic as color mode")
        return
    
    tdf_path = OUTPUT_DIR / concept / f"document_topics_{concept}.csv"
    doc_path = CACHE_DIR / concept / f"documents_{concept}.csv"
    umap_path        = CACHE_DIR / concept / f"umap2d_{concept}.npy"

    

    try:
        # docs = pd.read_csv(doc_path)[["doc_id", "subject"]].copy()
        # log.info(f"Loaded {len(docs)} documents")
        
        tdf = pd.read_csv(tdf_path)
        topics = list(tdf["bertopic_topic"])
        
        merged_df = pd.merge(doc_df, tdf, left_index=True, right_on="global_doc_id")
        print(merged_df.head(10))
        log.info(f"Loaded {len(merged_df)} documents")

    
        # topic_info = pd.read_csv(topic_info_path)[["Topic", "Name"]].copy()
        # log.info(f"Loaded {len(topic_info)} unique topics")
        
    except Exception as e:
        log.error(f"An error occured: {e}")
        return
    
    if umap_embeddings is None:
        embedding_mode = "local"
        log.info(f"No UMAP embeddings provided, loading from {umap_path} ...")
        try:
            coords = np.load(umap_path)
            log.info(f"Loaded umap coords of shape {coords.shape}")
        except Exception as e:
            log.error(f"An error occured: {e}")
            return
    else:
        embedding_mode = "global"
        log.info(f"Getting coordinates from global embeddings ...")
        coords = umap_embeddings[merged_df["global_doc_id"]]   
        print(merged_df.index)
        log.info(f"Umap coords of shape {coords.shape}")

    assert len(topics) == len(coords) == len(merged_df), f"Length mismatch: {len(topics)} topics vs {len(coords)} coords vs {len(docs)} docs"



    fig, ax = dark_fig(FIG_SIZE_SQUARE)

    # color by topic
    if color_by == "topic":
        # color map
        
        var_name = "Topic"
        topics       = np.array(topics)
        unique_topics = sorted(set(topics))
        colors        = topic_color_palette(max(len(unique_topics), 1), concept)
        color_map     = {t: colors[i % len(colors)] for i, t in enumerate(unique_topics)}
        color_map[-1] = "#888888"  # outliers gray
        # plot
        for tid in unique_topics:
            mask  = topics == tid
            label = f"T{tid}" if tid != -1 else "Outlier"
            ax.scatter(coords[mask, 0], coords[mask, 1],
                    c=color_map[tid], s=7, alpha=0.75, label=label,
                    linewidths=0, rasterized=True)
    
    # color by subject    
    elif color_by == "subject":
        
        var_name = "Subject"
        subjects = merged_df["subject"].fillna("Unknown").unique()
        n = len(subjects)
        
        # from utils.color_utils import generate_palette
        # palette = generate_palette(n)
        colors        = topic_color_palette(max(n, 1), concept)
        color_map     = {t: colors[i % len(colors)] for i, t in enumerate(subjects)}
        color_map[-1] = "#888888"  # outliers gray
        
        
        for subj in sorted(subjects):
            mask = merged_df["subject"].fillna("Unknown") == subj
            ax.scatter(coords[mask, 0], coords[mask, 1],
                    c=color_map[subj], s=7, alpha=0.75, label=subj,
                    linewidths=0, rasterized=True)

    ax.legend(loc="upper right", framealpha=0.2, facecolor=PLOT_BGCOLOR,
              labelcolor=FONT_COLOR, fontsize=7, ncol=2,
              title=var_name, title_fontsize=8)

    ax.set_title(f"UMAP 2D – {concept}", color=FONT_COLOR, fontsize=16, pad=12)
    ax.set_xlabel("UMAP-1", color=FONT_COLOR)
    ax.set_ylabel("UMAP-2", color=FONT_COLOR)
    fig.tight_layout()

    #for suffix in ["png","svg","tiff"]:
    out_path = OUTPUT_DIR / concept / f"umap2d_{concept}_{color_by}_{embedding_mode}.png"
    fig.savefig(out_path, dpi=FIGURE_DPI, facecolor=PLOT_BGCOLOR)
    plt.close(fig)
    log.info(f"  Saved: {out_path}")

# def plot_concept_2d_alt(concept: str, umap2d_all: np.ndarray, by_topic: bool = True) -> None:
#     """2D scatter plot coloured by BERTopic topic for a single concept."""
#     #topic_model_path = CACHE_DIR / concept / f"topic_model_{concept}.pkl"
#     doc_path = CACHE_DIR / concept / f"documents_{concept}.csv"
#     tdf_path = OUTPUT_DIR / concept / f"document_topics_{concept}.csv"

#     log.info(f"Attempting to load docs from {doc_path}")
    
#     try:
#         docs = pd.read_csv(doc_path)[["doc_id", "subject"]].copy()
#         log.info(f"Loaded {len(docs)} documents")
        
#         tdf = pd.read_csv(tdf_path)
#         topics = list(tdf["bertopic_topic"])
#         log.info(f"Loaded {len(topics)} topics")
#         df = pd.merge(docs, tdf, left_on="doc_id", right_on="global_doc_id")

#     except Exception as e:
#         log.error(f"An error occured: {e}")
#         return
    
#     coords = umap2d_all[df["doc_id"].to_numpy()]
#     assert len(df) == len(coords), f"Length mismatch: {len(df)} topics vs {len(coords)} coords"


#     fig, ax = dark_fig(FIG_SIZE_SQUARE)

#     # color by topic
#     if by_topic:
#         # color map
#         var = "topic"
#         var_name = "Topic"
#         topics       = np.array(topics)
#         unique_topics = sorted(set(topics))
#         colors        = topic_color_palette(max(len(unique_topics), 1), concept)
#         color_map     = {t: colors[i % len(colors)] for i, t in enumerate(unique_topics)}
#         color_map[-1] = "#888888"  # outliers gray
#         # plot
#         for tid in unique_topics:
#             mask  = topics == tid
#             label = f"T{tid}" if tid != -1 else "Outlier"
#             ax.scatter(coords[mask, 0], coords[mask, 1],
#                     c=color_map[tid], s=12, alpha=0.75, label=label,
#                     linewidths=0, rasterized=True)
    
#     # color by subject    
#     # else:
#     #     var = "subject"
#     #     var_name = "Subject"
#     #     subjects = docs["subject"].fillna("Unknown").unique()
#     #     n = len(subjects)
        
#     #     # from utils.color_utils import generate_palette
#     #     # palette = generate_palette(n)
#     #     colors        = topic_color_palette(max(n, 1), concept)
#     #     color_map     = {t: colors[i % len(colors)] for i, t in enumerate(subjects)}
#     #     color_map[-1] = "#888888"  # outliers gray
        
        
#     #     for subj in sorted(subjects):
#     #         mask = docs["subject"].fillna("Unknown") == subj
#     #         ax.scatter(coords[mask, 0], coords[mask, 1],
#     #                 c=color_map[subj], s=7, alpha=0.6, label=subj,
#     #                 linewidths=0, rasterized=True)

#     ax.legend(loc="upper right", framealpha=0.2, facecolor=PLOT_BGCOLOR,
#               labelcolor=FONT_COLOR, fontsize=7, ncol=2,
#               title=var_name, title_fontsize=8)

#     ax.set_title(f"UMAP 2D – {concept}", color=FONT_COLOR, fontsize=16, pad=12)
#     ax.set_xlabel("UMAP-1", color=FONT_COLOR)
#     ax.set_ylabel("UMAP-2", color=FONT_COLOR)

#     out_path = OUTPUT_DIR / concept / f"umap2d_{concept}_{var}_global_umap.png"
#     fig.tight_layout()
#     fig.savefig(out_path, dpi=FIGURE_DPI, facecolor=PLOT_BGCOLOR)
#     plt.close(fig)
#     log.info(f"  Saved: {out_path}")



def main():
    log.info("=== Step 08a: 2D UMAP Visualizations ===")

    # for concept in tqdm(CONCEPTS, desc="Per-concept 2D"):
    #     try:
    #         plot_concept_2d(concept)
    #     except Exception as e:
    #         LOG.error(f"  Error {concept}: {e}", exc_info=True)
    concept = "Konkurrenz"
    df = pd.read_csv(CSV_PATH)
    make_dir_if_necessary(concept)
    plot_concept_2d(df, None, concept)
        

    log.info("=== Step 08a complete ===")

if __name__ == "__main__":
    main()
