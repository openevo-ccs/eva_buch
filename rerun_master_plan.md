# Data-Rerun Master Plan — Curriculum Atlas (BERTopic + LDA)

Consolidated plan for the one expensive final rerun. Supersedes the informal phase outline discussed in chat; `phase1_audit_notes.md` holds the detailed corruption/stopword diagnostics referenced below. Living document — update as decisions land.

**Decisions locked in (2026-07-21):**
- Switch the sentence-embedding model to a genuinely multilingual/German-capable one, pending pilot validation (in progress).
- Run the systematic 5–20 topic-count sweep + coherence/agreement validation across **all 22 concepts**, not just the 3 flagship ones.
- Repo strategy: retrofit via git tag + feature branch, not a new repository.

---

## Phase 0 — ship now, no data dependency (independent of everything below)
Nav brand text (`docs/index.html` etc.), sort-arrows-shown-by-default on all sortable tables, BERTopic point-size slider range fix (spec: min 2/max 10/default 4; currently min 1.5/max 7/default 2).

## Phase 1 — diagnostics (in progress, no rerun yet, nothing destructive)
1. **Corruption root cause** — DONE. See `phase1_audit_notes.md` §1. Isolated to one document (`LP RheinPfalz Philosohpie Gym Sek2.pdf`), font-encoding mis-mapping (ü→Ÿ, ä→Š, ö→š, ß→ã), then silently stripped by `clean_hyphenated_text()`'s whitelist regex. Fix is targeted, cheap, doesn't touch the other 294 documents.
2. **Stopword term-frequency audit** — DONE. See `phase1_audit_notes.md` §2. Three-tier classification (admin/pedagogical noise to add globally; target-concept words that must never be stopworded; per-concept self-seed exclusion). Awaiting Susan's sign-off on the Tier 1 list.
3. **Embedding-model pilot** — IN PROGRESS. Comparing `all-MiniLM-L6-v2` (current, likely English-only despite the pipeline comment calling it multilingual) against `paraphrase-multilingual-MiniLM-L12-v2` on the Verhalten corpus (1,155 excerpts — the flagged case), using UMAP+HDBSCAN cluster count / outlier rate / silhouette score as the comparison proxy. Result will determine the embedding model for the full rerun.
4. **Sweep-timing pilot** (not yet run) — before committing to the full 22-concept × wide-K sweep, time a small pilot (2-3 concepts, both methods) to get a real cost estimate rather than guessing.

## Phase 1.5 — flagship deep-dive design (Verhalten, Mensch, Evolution)
Beyond the standard rerun, these three get an additional iterative pass:
1. Baseline: corrected embedding model + fixed corruption + adaptive topic count, same as all 22.
2. Fine-grained K-sweep with coherence scoring specific to these three (part of the all-22 sweep, but read closely here first).
3. **Content-vs-context test**: build a "content-focused" embedding variant that strips generic Bildungsstandards competency-verb templates ("Die Schülerinnen und Schüler [erläutern/beurteilen/...]...") from the excerpt text *before* embedding (not just before vectorizing — stopwords never reach the embedding step in the current pipeline, since BERTopic embeds raw excerpt text). Compare resulting topic structure against the baseline to test whether context-stripping meaningfully improves content differentiation.
4. Manual close-reading pass with Susan on representative excerpts per candidate topic — human-in-the-loop merge/split/relabel, documented as part of the book's methodology.
5. Re-inspect the HDBSCAN outlier bucket for Mensch/Evolution specifically (large corpora — minority themes may be getting absorbed into noise rather than surfaced as small topics).

## Phase 2 — implement fixes (still no rerun)
1. ✅ **Done** — Fix the corruption bug at its source: `remap_font_encoding_artifacts()` in `keyword_search/src/utils.py` (Ÿ→ü, Š→ä, š→ö, ã→ß), applied in both `normalize_text()` (keyword_search.py) and `pdf_dir_to_txt()` (utils.py). `clean_hyphenated_text()` now warns on any unexpected stripped letter. Unit-verified against the actual affected document. See METHODOLOGY.md §1.
2. ✅ **Done** — Adopt the validated embedding model: `EMBEDDING_MODEL_NAME` in `bertopic_pipeline_v2.py` switched to `paraphrase-multilingual-MiniLM-L12-v2`.
3. ✅ **Done** — Shared stopword module: `shared_stopwords.py` (repo root), used by both `bertopic_pipeline_v2.py` and `lda_topic_model.py`.
4. ✅ **Done** — Per-concept self-seed-term exclusion (Tier 3): `stopwords_for_concept()` in `shared_stopwords.py`, derived from `keyword_search/in/keywords.txt`.
5. Implement adaptive `min_cluster_size` / `nr_topics`-as-ceiling logic (Strategy B from the original topic-count discussion) as the baseline, generalized by the full sweep infrastructure below. **Not yet started.**
6. Build the K-sweep + coherence (c_v/c_npmi) + BERTopic/LDA agreement-scoring infrastructure, run across all 22 concepts. **Not yet started.**
7. Roll in already-known fixes: KMK state-label propagation (deferred from 2026-07-20 session). **Not yet started.**
8. Repo hygiene: stop tracking `lda_topic_modelling/out/**/tm/*.pkl` (78 files currently committed — regenerable build artifacts, inconsistent with BERTopic's correctly-gitignored equivalent cache); decide whether to also purge them from git history (invasive — needs separate explicit sign-off, not default). **Not yet started.**

## Phase 3 — the one expensive rerun
Executed entirely on a feature branch (see Phase 5, already set up: `data-rerun-2026-07`).
1. **Corruption fix regeneration — does not need the source PDFs.** `results.csv`'s existing rows for the affected document already lost the mis-mapped characters outright (they went through the old buggy cleaner), so they can't be patched in place — but the raw `.txt` mirror (`data/LP_DE_2026_1_txtfiles/Ethik, Philo/LP RheinPfalz Philosohpie Gym Sek2.txt`) still has the *mis-mapped-but-present* characters, now fixable via the remap. Plan: re-run the match/context-window extraction against this corrected raw text for just this one document (~57 excerpt rows) and splice the results back into `results.csv`, rather than needing to re-run full PDF extraction across all 295 documents. Sidesteps the PDF-backup dependency noted in Phase 5/METHODOLOGY.md §6 entirely.
2. Full `keyword_search.py` extraction rerun (regenerates `doc_word_counts.csv` etc.) is only needed if the source PDFs are restored and a from-scratch reproducibility pass is wanted — not required just to land the corruption fix.
3. Re-run BERTopic: recompute embeddings (new model, `--force-embeddings`), refit topics (`--force-topics`), all 22 concepts, base fit at natural granularity + `reduce_topics()` sweep across K ∈ {5,7,10,12,15,20} for the coherence/agreement analysis, ship the chosen K per concept to the app.
4. Re-run LDA: all 22 concepts × the same K range (cheap relative to BERTopic's embedding step).
5. Regenerate manifest, color maps, `docs/data` mirror via `scripts/build_docs_data.py`.

## Phase 4 — post-rerun QA
1. Re-run today's audit scripts: topic-count distribution per concept, corruption grep (expect zero hits), Kompetenz-family frequency check against the new stopword list.
2. Coherence/agreement report per concept — flag any concept where BERTopic and LDA diverge sharply, for Susan's review.
3. Playwright screenshot pass, all 5 pages, both themes.
4. Update `app_specs.md` revision history; fold in `app_specs_SH_notes.md`.
5. Write `METHODOLOGY.md`: final stopword list, topic-number-selection procedure + sweep results, embedding model choice and why, known limitations (e.g. the RheinPfalz Philosophie document's font issue and how it was handled).

## Phase 5 — repo strategy (runs alongside Phases 2–4, not after)
1. `git tag pre-rerun-2026-07` (or similar), pushed to remote — permanent, retrievable snapshot of the original run.
2. All Phase 2/3/4 work happens on a feature branch (e.g. `data-rerun-2026-07`) — `main`/deployed GitHub Pages site stays untouched until the new run is validated.
3. Merge to `main` once Susan approves and Phase 4 QA passes.
4. `METHODOLOGY.md` (Phase 4.5) plus the repo-hygiene pass (Phase 2.8) are the "clean, fully documented, well-organized" deliverable — no new repository needed.

## Decisions — approved 2026-07-21
1. Tier 1 stopword-addition list and Tier 2 exceptions (`phase1_audit_notes.md` §2) — approved as written. `lernen` resolved: keep (Tier 2).
2. Tier 3 per-concept self-seed exclusion — approved.
3. Corruption fix for the one affected document — remap preferred, fall back to re-OCR only if remapping proves unreliable in practice.

## Still open
1. Review of the coherence/agreement sweep results once available — does the chosen K per concept look right to a domain expert, not just statistically?
2. Whatever the content-vs-context pilot for Verhalten/Mensch/Evolution turns up — may suggest a preprocessing change Susan should weigh in on before it's applied corpus-wide.
3. "LDA results differ from previous" — still needs her clarification on what she's comparing against (a stopword/preprocessing difference could plausibly explain it).
