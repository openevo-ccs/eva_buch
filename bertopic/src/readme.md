## Quick summary of how the four pieces fit together

| File | Role | Reads | Writes |
|---|---|---|---|
| `bertopic_pipeline_v2.py` | Master ETL — embeds, clusters, projects, exports | raw CSV | `data/*.json`, `data/manifest.json`, caches |
| `build_global_projection.py` | Shared (non-per-concept) UMAP fit over the full embedding cache | `cache/embeddings_all.npy`, `data/manifest.json` | adds `umap_2d_global`/`umap_3d_global` to `data/*.json`, `bbox_2d_global`/`bbox_3d_global` to `data/manifest.json` |
| `viz_umap_2d_v2.py` | Static 2D QA plots + shared color source | `data/*.json`, `data/manifest.json` | `data/color_maps.json`, PNGs |
| `viz_umap_3d.py` | Static 3D QA plots + orbit GIF preview | same as above (imports `viz_umap_2d_v2.py`'s utilities) | PNGs, GIFs |
| `curriculum_atlas.html` | Interactive web app | `data/*.json`, `manifest.json`, `color_maps.json` | URL hash / localStorage (client-side only) |

Note: `bertopic_pipeline.py` and `viz_umap_2d.py` (without the `_v2` suffix) are earlier, superseded versions kept for reference — the `_v2` scripts are what actually produced the current `data/` contents and are what everything else depends on. Only `viz_umap_2d_v2.py` generates `color_maps.json`; the non-`_v2` `viz_umap_2d.py` has no such logic.

**Suggested run order for a fresh setup:**
```bash
python bertopic_pipeline_v2.py --csv data_raw/results.csv
python build_global_projection.py   # adds the shared/global UMAP coords
python viz_umap_2d_v2.py --force-color-maps   # also (re)generates data/color_maps.json
python viz_umap_3d.py
# then just open/deploy curriculum_atlas.html (with data/ alongside it)
```

A few things worth double-checking on your end before first deploy:
1. **Column names in `COLUMN_MAP`** — confirm they match your actual `results.csv` headers exactly (case/spacing).
2. **`topic_label_overrides.json`** — optional, but worth creating early to hand-curate the more opaque auto-generated topic labels (like your `"Humanadaptation"` example).
3. **GitHub Pages path** — if `data/` lives in a separate repo, flip `DATA_BASE_URL` in the HTML to the raw-GitHub URL pattern from spec §4 (the comment block explains both options).

Let me know if you'd like adjustments to any piece, or a `README.md` tying the whole pipeline together for future maintainers.
