# Vision Realization Plan — Closing the Gap to Susan Hanisch's Full Spec

Compiled 2026-07-23. Authoritative source of vision: **`app_specs_SH_notes.md`** (382 lines, Susan's actively-edited, most-current spec — confirmed newer and more detailed than `app_specs.md`, 336 lines, the stale "official" baseline). Every finding below is verified against actual repo state as of this date, not assumed — see the "Verification method" line on each item.

**Context this plan builds on**: `rerun_master_plan.md` (the data-rerun effort — corruption fix, embedding-model swap, stopword unification, adaptive topic-count ceiling, full BERTopic+LDA production rerun) is substantively complete and documented in `METHODOLOGY.md`. A critical, pre-existing bug (BERTopic silently ASCII-stripping every topic label — `METHODOLOGY.md` §4.6) was found and fixed 2026-07-23. A new page (`docs/koharenz.html`, the "Kohärenz dashboard") was added the same day as a prototype, **not yet in Susan's spec** — treat it as a proposal for her, not a completed requirement.

This plan is the next layer: closing the real, verified gap between what `app_specs_SH_notes.md` asks for and what the app actually does today, plus a systematic German-language data-integrity audit motivated directly by the BERTopic bug (if that class of bug existed once, undetected, it's worth checking whether it exists anywhere else).

---

## 1. Verified gaps — concrete, not speculative

Each item below was checked directly against the running code/data this session, not inferred from memory.

### 1.1 Home page — substantial rebuild needed
**Verified**: `renderHomePage()` (`docs/app.js`) renders generic stats ("Konzepte im Fokus", "Ausreißer insgesamt" etc.) with no word cloud anywhere on the page.
**Spec requires** (§3): a left panel (~2/3 width) with a specific header ("Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht – Eine Lehrplananalyse"), a specific paragraph linking to `eva-buch.openevo.net`, and per-page-summary text; a right column of three stacked stat buttons ("5 Fächer", "295 Lehrplandokumente", "35893 extrahierte Textstellen" — note these exact numbers are now stale post-rerun and should be computed live, not hardcoded); below that, a **circular word cloud of every keyword-search concept, sized by frequency**, headed "Schlagwörter", colored per the app's palette (§1.2).
**Action**: rebuild `renderHomePage()` and `docs/index.html` to match. The word cloud can reuse the existing `initWordclouds()`/word-cloud rendering machinery already built for the LDA page (§7.2.3) rather than building new cloud-layout logic from scratch — check `docs/app.js` for that function's signature before restarting it from zero.

### 1.2 State-name normalization is display-only, not applied to the actual data files
**Verified**: `keyword_search/out/results.csv`'s `state` column still contains raw abbreviations — `BaWü`, `MeckPomm`, `NRW`, `None` — checked directly via `pandas.read_csv(...).unique()`. `STATE_ALIASES`/`normalizeState()` in `docs/app.js` only normalizes for on-screen display; the underlying CSV — which the spec explicitly names ("in `results.csv` and any other pipeline output where these raw labels still appear") and which is directly downloadable/linked from the spec itself — is untouched.
**Spec requires** (§2, Global Data Conventions): BaWü→Baden-Württemberg, MeckPomm→Mecklenburg-Vorpommern, None→KMK, and any other abbreviation (e.g. NRW) normalized **everywhere a state name is displayed or exported**, which on a plain reading includes the raw CSV files themselves, not just the UI.
**Action**: normalize at the source — likely in `keyword_search/src/keyword_search.py`'s state-extraction step, or as a dedicated post-processing pass applied to `results.csv`/`doc_word_counts.csv`/`state_subject_count_matrix.csv` before they're written. `bertopic_pipeline_v2.py` already has a `canonicalize_state()` function (confirmed correct, per earlier-session verification) — check whether it can be reused/extracted as the single shared normalization function for keyword_search's own CSV writing too, avoiding a second parallel implementation (`shared_stopwords.py`-style single-source-of-truth pattern, consistent with `METHODOLOGY.md` §2's stopword-unification precedent).

### 1.3 BERTopic page — several controls named in spec, not present in the UI
**Verified** (`docs/bertopic.html`'s full control list checked directly): present — color-by, outlier toggle, projection toggle, point-size slider, dimension toggle, orbit controls. **Missing**, confirmed absent from the controls markup:
- "Option to de-select all concepts" (§6, bullet list)
- "Option to recenter all graphs" (§6, bullet list)
- "Option to download each cloud as image file (png, jpg, tif), in the header bar" (§6)

Also checked: hover-tooltip excerpt clamps to **5 lines** (`docs/styles.css` `-webkit-line-clamp: 5`); spec asks for **"about 8 lines"** (§6) — small, precise fix.

**Action**: add a "Alle abwählen" button next to the concept picker; add a "Ansicht zurücksetzen" button that resets camera/zoom on all active panels (there's already per-panel camera-reset logic for the orbit feature to build on — check `applyBerTopicCameraToAllPanels()`/`seedBerTopicOrbitFromCurrentView()` before writing new code); add a PNG/JPG/TIFF export button per panel (Plotly.js has `Plotly.downloadImage()` built in — this is likely a small, well-contained addition, not a new subsystem); bump the tooltip clamp to 8 lines and verify the tooltip box width/height still reads well at that length.

### 1.4 Schlagwortsuche — entropy column still an explicitly open decision
**Verified**: no entropy column exists in `docs/app.js`'s keyword-page rendering; the spec itself flags this as unresolved ("Open item carried over from the previous revision: whether/how to add an entropy measure column still needs a methodology decision" — §5 notes).
**Not a bug** — a genuine open question for Susan. **Worth surfacing to her now**: this session's Kohärenz dashboard work (§7 below) used per-topic subject-entropy as its core "bridge vs. siloed" signal and it worked well/was interpretable — that's a concrete, tested precedent for what an entropy column here would actually look like and mean, which should make this decision easier for her to make than it was when first raised.

### 1.5 Custom domain not configured
**Verified**: no `CNAME` file anywhere under `docs/`. Spec (§1) names a permanent URL, `lehrplananalyse.openevo.net`.
**Not purely a code fix** — needs the domain's DNS actually pointed at GitHub Pages by whoever administers `openevo.net`, which is outside this repo's control. **Action**: confirm with Susan/OpenEvo admin whether DNS is ready; if so, adding `docs/CNAME` containing the domain is a one-line repo-side step once that's confirmed, not before (an unconfigured CNAME file would break the current `github.io` URL without fixing anything).

### 1.6 Not yet re-checked, flagged rather than assumed either way
These weren't independently re-verified this pass (time-bounded); call them out explicitly rather than silently assuming they're fine or broken:
- LDA §7.2.3 word-cloud fidelity to spec specifics (RGB-spectrum-distinct term coloring, exact 3×4 single-concept-mode matrix, circular layout) — the feature exists (`initWordclouds()` referenced in code) but hasn't been checked line-by-line against the spec's exact requirements this session.
- Full German-language text audit across every UI string (spec §1.1: "All text must be in full, grammatically correct German") — no systematic pass has been done; this session's work was data/bugfix-focused, not a copy audit.
- "The LDA results differ from the previous results" (§7, Susan's still-open comment) — plausibly now explained by the documented, deliberate changes this session (stopword unification, corruption fix, embedding model swap don't affect LDA, but the stopword/corpus changes do) — but this needs her direct side-by-side comparison to actually confirm, not an assumption on my part.

### 1.7 Confirmed correct, no action needed
Checked and verified fine, so not worth re-litigating: nav-highlight (fixed this session), color hex values (`#085e65`/`#272d63` match exactly), CSV field-quoting for "Ethik, Philo" (verified 10 columns parse correctly, comma-containing field is properly quoted), concept co-occurrence network graph (exists — `renderCooccurrenceNetwork()`, force-directed layout — contrary to my own initial assumption before checking), sort arrows on sortable tables (fixed earlier this session), Gesamt row/column semantics (fixed earlier this session).

---

## 2. German-language data-integrity audit — motivated directly by the BERTopic bug

`METHODOLOGY.md` §4.6 documents a serious, previously-undetected bug: BERTopic silently ASCII-stripped every umlaut/ß from every topic label this project has ever produced, because `language` defaulted to `"english"` and nobody had explicitly checked topic-label text at the codepoint level before. **If that class of bug existed once, undetected, for this long, it's worth systematically checking whether it exists anywhere else** in the pipeline, rather than assuming it was a one-off.

**Proposed audit** (not yet executed — scoping it here so it can be picked up directly):
1. Every text-producing code path that isn't already covered by an explicit, verified UTF-8 check: `scripts/generate_document_catalog.py` (untouched this session), any PDF/text extraction beyond `keyword_search.py` (already deeply audited — corruption fix, font-encoding remap), the CSV export functions in `docs/app.js` (client-side, JS's native string handling is Unicode-correct by default, lower risk but worth a spot-check on the actual downloaded file bytes, not just on-screen rendering).
2. A reusable verification script (not ad-hoc one-off checks each time) — something like `scripts/verify_utf8_integrity.py` that walks every tracked output CSV/JSON under `docs/data/` and `bertopic/src/data/`, `.decode("utf-8")`-checks every file, and additionally spot-checks for a curated list of known-umlaut German words expected to appear somewhere in the corpus (Ausreißer, Schülerinnen, Zusammenhänge, etc.) — a positive-presence check, not just an absence-of-corruption check, since §4.6's bug would have passed a naive "no corruption" check while still being wrong (it didn't produce mangled bytes, it silently produced *fewer* bytes). This script becomes a standing regression check, not a one-time audit — cheap to rerun after any future pipeline change.
3. Extend to any *future* library/model integration: this session's concrete lesson (documented in `METHODOLOGY.md` §1.5 and §4.6) is that a library defaulting to English-oriented behavior is not a safe assumption for a German corpus, and the failure mode is silent, not a crash. Any new dependency introduced later should be checked for this specific failure mode as a matter of course, not just tested for happy-path correctness.

---

## 3. The Kohärenz dashboard — status and next decision

Built and Playwright-verified 2026-07-23 (`docs/koharenz.html`, `scripts/build_coherence_dashboard_data.py`, `METHODOLOGY.md` §7). Reframes the app around vertical/horizontal coherence directly, reusing already-computed BERTopic subject-entropy data — no new analysis, just a new lens. **Not in Susan's spec** — added per Dustin's "next-gen app" direction this session, explicitly flagged in `METHODOLOGY.md` as a prototype pending her review, not silently merged into the approved spec.

**Decision needed from Susan**: keep it (and if so, formally add it to `app_specs_SH_notes.md`/eventually `app_specs.md` with her own design refinements — the current version is a functional first pass, not styled/worded to her standard necessarily), revise it, or drop it. Until she weighs in, treat its current form as provisional.

---

## 4. Decisions that are Susan's, not mine — consolidated list

Pulling together every open item across this plan and the prior session that specifically needs her judgment, not more automated work:

1. **BERTopic ceiling deviation** (already flagged inline in `app_specs_SH_notes.md` §6 and `METHODOLOGY.md` §4.4) — her spec says "no more than ten topics," the data-driven decision raised it to 30 for richness. One-line revert available if she prefers the literal cap.
2. **Coherence/agreement statistical results** (`METHODOLOGY.md` §4.5) — low, fairly uniform BERTopic/LDA agreement across all 22 concepts; needs her domain read on whether any specific concept's divergence looks *wrong* rather than just *methodologically different*. Note: these specific numbers were computed **before** the BERTopic language-bug fix (§4.6) and are a plausible lower bound for BERTopic's coherence specifically — rerunning `topic_sweep.py` under the fix (multi-hour job, not yet done) would sharpen this before treating it as final for the book's methods section.
3. **Entropy column for Schlagwortsuche** (§1.4 above) — a methodology decision explicitly deferred in her own notes, now easier to reason about given the Kohärenz dashboard's working precedent.
4. **Kohärenz dashboard** (§3 above) — keep, revise, or drop.
5. **"LDA results differ from previous"** (§1.6 above) — needs her side-by-side comparison against the specific prior run she was looking at.
6. **Custom domain DNS** (§1.5 above) — confirm readiness before adding `CNAME`.
7. **Content-vs-context pilot findings for Verhalten/Mensch/Evolution** (`METHODOLOGY.md` §5, executed 2026-07-23) — a genuinely negative result for the original hypothesis (stripping competency-verb scaffolding didn't meaningfully suppress differentiation); worth her seeing since it was her original flagged concern, even though the ceiling fix already addressed the underlying richness problem a different way.

---

## 5. Proposed execution order

Sequenced so nothing gets built twice and Susan's decision gates don't block unrelated work:

**Phase A — data-layer rigor (no UI dependency, can start immediately)**
1. State-name normalization at the source (§1.2) — touches `keyword_search.py` and possibly `bertopic_pipeline_v2.py`'s existing `canonicalize_state()`, then a full regeneration of every downstream CSV/JSON that carries state names (same regeneration chain discipline as the BERTopic bug fix: production rerun → global projection → docs/data mirror).
2. German-language integrity audit + the standing verification script (§2).

**Phase B — spec-conformance UI work (can run in parallel with Phase A once A's data is ready)**
3. Home page rebuild (§1.1) — the single largest visible gap.
4. BERTopic missing controls: deselect-all, recenter, image export, tooltip line-count fix (§1.3).
5. LDA §7.2.3 word-cloud fidelity check against spec specifics (§1.6) — verify first, fix only what's actually wrong.

**Phase C — gated on Susan (cannot proceed without her input, so surface these early rather than late)**
6. Send her the consolidated decision list (§4) — ideally *before* Phase B finishes, since her answers on items 1 and 4 specifically could change what Phase B is even building (e.g., if she wants the Kohärenz dashboard reworked rather than kept as-is, or wants the literal 10-topic cap back).

**Phase D — closeout**
7. Re-run full QA (corruption grep, topic-count cross-check, Playwright all pages/both themes — same discipline as every prior QA pass this session) after Phase A/B land.
8. Fold `app_specs_SH_notes.md` into `app_specs.md` and delete the notes file — **only after** Susan's Phase C decisions are incorporated, so the folded spec reflects what actually shipped, not what was proposed.
9. Merge `data-rerun-2026-07` → `main`.

---

## 6. What NOT to do without checking first

Consistent with how this session has operated throughout — noting explicitly so a fresh session picking up this plan doesn't relitigate:
- Don't merge to `main` before Susan's Phase C decisions land.
- Don't rerun the multi-hour `topic_sweep.py` sweep speculatively — it's a real time cost; confirm it's actually wanted (e.g., for the book's methods section specifically) before launching it.
- Don't add the `CNAME` file before domain-readiness is confirmed externally.
- Don't treat the Kohärenz dashboard as a permanent fixture in communications with Susan — it's explicitly a proposal.
