#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
#  build_global_projection.py
# ──────────────────────────────────────────────────────────────────────────
#  Evo-Buch Curriculum-Atlas — Global UMAP Projection
# ──────────────────────────────────────────────────────────────────────────
#
#  bertopic_pipeline_v2.py fits one UMAP projection per concept ("local":
#  each concept's documents projected into their own 2D/3D space). The web
#  app also wants a "global" projection — every concept's documents placed
#  in one shared coordinate space, fit once over the full embedding cache
#  (`cache/embeddings_all.npy`) — so a user can toggle between "how this
#  concept's documents cluster on their own" and "where this concept's
#  documents sit relative to every other concept".
#
#  This script deliberately reuses `compute_or_load_umap` from
#  bertopic_pipeline_v2.py (same caching behaviour, same UMAP hyperparameters,
#  same random seed) rather than re-implementing UMAP-fitting a second time.
#  Each per-document record's "id" field is a doc_id — a row index into
#  embeddings_all.npy — which is the join key back from a concept's local
#  JSON into the single global projection.
#
#  USAGE
#  -----
#    python build_global_projection.py
#    python build_global_projection.py --force
#
# ══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from bertopic_pipeline_v2 import compute_or_load_umap, setup_logging, RANDOM_SEED, embedding_model_slug


def round_pair(coords: np.ndarray, i: int, ndim: int) -> list[float]:
    return [round(float(coords[i, d]), 4) for d in range(ndim)]


def bbox(coords: np.ndarray) -> list[list[float]]:
    return [[round(float(coords[:, d].min()), 4), round(float(coords[:, d].max()), 4)]
            for d in range(coords.shape[1])]


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    p = argparse.ArgumentParser(description="Fit one shared UMAP projection over the full embedding cache.")
    p.add_argument("--cache-dir", type=Path, default=base_dir / "cache")
    p.add_argument("--web-data-dir", type=Path, default=base_dir / "data")
    p.add_argument("--out-dir", type=Path, default=base_dir / "out")
    p.add_argument("--force", action="store_true", help="Recompute the global UMAP fit even if cached.")
    p.add_argument("--pretty-json", dest="pretty_json", action="store_true", default=True)
    args = p.parse_args()

    log = setup_logging(args.out_dir, "INFO")

    # Cache paths are namespaced by embedding model (see
    # bertopic_pipeline_v2.embedding_model_slug()) so switching models
    # can't silently resurrect a stale fit from the previous one.
    slug = embedding_model_slug()
    embeddings_path = args.cache_dir / f"embeddings_all__{slug}.npy"
    if not embeddings_path.exists():
        raise SystemExit(f"[FATAL] {embeddings_path} not found — run bertopic_pipeline_v2.py first.")

    log.info("Loading global embeddings cache …")
    embeddings_all = np.load(embeddings_path)
    log.info(f"  Loaded embeddings: shape {embeddings_all.shape}")

    umap2d_global = compute_or_load_umap(
        embeddings_all, args.cache_dir / f"umap2d_global__{slug}.npy",
        n_components=2, log=log, force=args.force,
    )
    umap3d_global = compute_or_load_umap(
        embeddings_all, args.cache_dir / f"umap3d_global__{slug}.npy",
        n_components=3, log=log, force=args.force,
    )

    manifest_path = args.web_data_dir / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    concept_order = manifest["concept_order"]
    dump_kwargs = dict(ensure_ascii=False, indent=2) if args.pretty_json else dict(ensure_ascii=False)

    for concept in concept_order:
        concept_path = args.web_data_dir / f"{concept}.json"
        with open(concept_path, encoding="utf-8") as f:
            records = json.load(f)

        for record in records:
            doc_id = record["id"]
            record["umap_2d_global"] = round_pair(umap2d_global, doc_id, 2)
            record["umap_3d_global"] = round_pair(umap3d_global, doc_id, 3)

        with open(concept_path, "w", encoding="utf-8") as f:
            json.dump(records, f, **dump_kwargs)
        log.info(f"  [{concept}] Merged global coords into {len(records):,} records -> {concept_path.name}")

    manifest["bbox_2d_global"] = bbox(umap2d_global)
    manifest["bbox_3d_global"] = bbox(umap3d_global)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, **dump_kwargs)
    log.info(f"Wrote global bbox -> {manifest_path}")
    log.info("DONE.")


if __name__ == "__main__":
    main()
