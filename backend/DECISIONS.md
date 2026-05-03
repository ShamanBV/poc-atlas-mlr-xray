# Backend POC — Pinned Decisions

Every tunable choice, current value, why we picked it, and how to revise
it if the live results turn out to be off. Add a new entry rather than
changing one in place — keep the audit trail.

Format per entry:

> **Decision N — short title**
> **Current value:** the live setting in code
> **Where:** file path + symbol
> **Why this value:** rationale at time of pinning
> **How to revise:** what to look at if results disagree, with concrete
> levers
> **Status:** `pinned` (not yet measured) / `validated` (measured, holds)
> / `revised` (changed; new entry below)

---

## Layer 1 — claim drift

### D1 — Embedder choice: dependency-free `HashEmbedder`

**Current value:** `HashEmbedder(dim=256)` (deterministic md5-bucket bag-of-tokens, ~30 LoC, no deps).
**Where:** `src/mlr/precheck/similarity.py` → `HashEmbedder`, `default_embedder()`.
**Why this value:**
- POC must run on a fresh checkout in <60s (no model download).
- Tests must be deterministic and fast (no GPU, no model load).
- The `Embedder` Protocol shape is the swap point — production replaces
  the class without touching `claim_check.py`.
**How to revise:** if drift detection misses semantically-equivalent
phrasings ("OS reduction" vs "overall survival reduction" should match
but won't with bag-of-tokens), implement
`SentenceTransformerEmbedder` against the same Protocol and pass it via
`claim_check.run(asset, embedder=…)`. Re-tune thresholds per D2.
**Status:** `pinned`.

### D2 — Similarity thresholds: `CLEAN_MIN=0.98`, `DRIFT_MIN=0.80`

**Current value:** `CLEAN_MIN = 0.98`, `DRIFT_MIN = 0.80`.
**Where:** `src/mlr/precheck/claim_check.py` (module constants;
overridable via `run(..., clean_min=, drift_min=)`).
**Why this value:** calibrated against the §6 fixture. Combined
similarity (mean of bag cosine + char ratio) gives:
- KISQALI claim (1 word + 1 punct drift) vs canonical → **0.97** → drift
  band as designed.
- Identical text → 1.00 → clean.
- Unrelated text → ~0.10 → block.
The spec (`MLR_PRECHECK_SPEC.md` §3) names 0.95 / 0.70 — those are
correct for **sentence-transformer cosines only**. The hybrid scores
higher across the board, hence the bump.
**How to revise:**
- If too many "clean" false positives: lower `CLEAN_MIN` (try 0.95).
- If too many "drift" warnings on innocuous edits: raise `CLEAN_MIN`
  (try 0.99). Edits like trailing period, citation-marker swap should
  not flip a verdict — if they do, that's a tokenisation issue more than
  a threshold one.
- If swapping to sentence-transformers: revert to spec values 0.95 / 0.70.
**Status:** `pinned`.

### D3 — Hybrid similarity = mean(bag cosine, char ratio)

**Current value:** `combined_similarity = (semantic_cos + char_ratio) / 2`.
**Where:** `src/mlr/precheck/similarity.py` → `combined_similarity()`.
**Why this value:** bag cosine catches token overlap regardless of
order; char ratio catches minor edits / punctuation drift. Either alone
is brittle for the POC's use cases.
**How to revise:** weighted average (e.g. `0.7 * sem + 0.3 * char`) if
one signal dominates incorrectly. With sentence-transformers swapped in,
char_ratio becomes ~redundant and weight should drop to ~0.1 or 0.
**Status:** `pinned`.

### D4 — No-candidate modules are skipped silently

**Current value:** modules with no library hit emit no Verdict.
**Where:** `src/mlr/precheck/claim_check.py` → `run()`, `if not candidates: continue`.
**Why this value:** prevents a flood of false-positives on novel claims
the library hasn't yet learned. The library is sparse in v1 (~3 entries
in this slice).
**How to revise:** once the library is dense (>20 patterns per slice),
flip to "novel claim — needs MLR review" warn-severity verdict. Adds a
new Zone with `pattern_base: null` and a distinct `sub_layer:claim:novel`.
**Status:** `pinned`.

### D5 — Library: 3 hardcoded entries (KISQALI / UK / EFFICACY+SAFETY)

**Current value:** `_LIBRARY` tuple in `src/mlr/precheck/library.py`,
3 entries.
**Why this value:** smallest library that exercises (a) best-of-N
candidate selection (2 EFFICACY variants), (b) cross-subtype filtering
(SAFETY entry), (c) the §6 demo's specific drift case.
**How to revise:** ingest real approved canonicals via the
`MLR_PRECHECK_SPEC.md` §6 ingest path. The `find_candidates` /
`lookup_pattern` API stays the same; `_LIBRARY` swaps for a loaded
JSON / parquet snapshot.
**Status:** `pinned`.

---

## Layer 2 — regulatory dependency rules

### D6 — Pillar attribution via `sub_layer` prefix

**Current value:** Layer 2 emits `sub_layer = f"{rule.pillar}:{rule.id}"`;
`verdict.pillar_for` reads the `medical:` / `legal:` / `regulatory:`
prefix to attribute pillar score deductions.
**Where:** `src/mlr/precheck/document_check.py` → `_verdict_for_unmet_rule`;
`src/mlr/precheck/verdict.py` → `pillar_for`.
**Why this value:** the API contract's `Zone.layer` enum
(`claim/regulatory/abbreviation/cascade`) doesn't carry pillar info, so
sub_layer is the only place to encode it. Prefix-keyed routing is
cheap and makes the source of truth explicit.
**How to revise:** if the contract grows a `Zone.pillar` field, drop
the prefix convention and route off the explicit field. Single touch:
`pillar_for`.
**Status:** `pinned`.

### D7 — Score formula: severity-keyed deduction floor 0

**Current value:** `block: -20pt`, `warn: -8pt`, `info: -2pt`, floor 0,
`overall = min(pillar scores)`.
**Where:** `src/mlr/precheck/verdict.py` → `_DEDUCTION_BY_SEVERITY`,
`compute_scores`.
**Why this value:** ordinal — three blocks already drives a pillar to
40, signalling severe issues without sliding-scale calibration. Min
across pillars matches the cascade engine's "worst-pillar gates the
headline" convention.
**How to revise:**
- If reviewers say scores are too punitive: halve the deductions.
- If scores cluster (everything 60–80): use logistic decay rather than
  linear subtraction.
- If "overall = min" hides a problematic pillar from view: switch to
  weighted average per pillar weight.
Touch point is one dict + one function.
**Status:** `pinned`.

### D8 — Empty predicate / requires evaluates to True

**Current value:** `evaluate(None)` and `evaluate({})` both return True.
**Where:** `src/mlr/precheck/dependency_rules.py` → `evaluate()`.
**Why this value:** lets a rule with `predicate: {}` fire
unconditionally, and a rule with no `requires:` always be satisfied.
Matches the YAML's intent (some rules use empty predicates to mean
"always applies").
**How to revise:** if rule authors are accidentally writing empty
predicates and getting silent always-fires, change to raise on empty —
but expect a wave of catalog edits to fix the affected rules.
**Status:** `pinned`.

### D9 — `envelope.matches_pattern` stub-true

**Current value:** when a predicate has `matches_pattern: {id, threshold}`,
the evaluator skips the actual check and returns True for that leaf.
**Where:** `src/mlr/precheck/dependency_rules.py` → `_eval_envelope()`,
inline comment.
**Why this value:** the live system needs a pattern bank (auto-derived
from the library) to evaluate this. The bank is Layer 1's library; this
slice doesn't index envelope-level canonicals yet.
**How to revise:** wire in a `pattern_bank.match(envelope_text, pattern_id)
→ similarity` function that returns >= threshold or not. Same
threshold-tuning concerns as D2.
**Status:** `pinned`.

### D10 — Date-of-preparation freshness check is regex-only

**Current value:** the rule predicate verifies a date-shaped substring
exists; no comparison against today.
**Where:** `dependency_rules.yaml` (`r_date_of_preparation_present_and_fresh`),
evaluated by `_eval_envelope`.
**Why this value:** date normalisation across "March 2026" /
"03/2026" / "2026-03-14" is its own task; deferred to keep this slice
focused.
**How to revise:** add a `date_freshness` leaf type to the predicate
vocabulary that takes `key`, `freshness_days_warn`, `freshness_days_block`;
implement a date parser that handles the three formats. Splits
`r_date_of_preparation_present_and_fresh` into a
`present` rule (current) and a separate `fresh` rule.
**Status:** `pinned`.

### D11 — Predicate `predicate` string in DependencyTrigger uses
rule description, not specific match

**Current value:** the human-readable `DependencyTrigger.predicate`
field is the rule's `description`, not a structured "this specific
predicate node matched" string.
**Where:** `src/mlr/precheck/document_check.py` →
`_dependency_trigger_for_rule`.
**Why this value:** generating a per-instance predicate string from an
arbitrary tree of `any_of`/`all_of`/`not` is templating work that
doesn't change the demo. Description is human-readable enough.
**How to revise:** when reviewers ask "what specifically fired this?",
write a `humanise_predicate(node, asset)` that walks the matched
subtree and reports e.g. `"Module 'mod_efficacy_001' matched
text_matches=HR|95%CI"`.
**Status:** `pinned`.

### D12 — Rule pillars come from YAML top-level structure

**Current value:** `dependency_rules.yaml` groups rules under
`medical:` / `legal:` / `regulatory:` top-level keys; the loader
attributes pillar accordingly.
**Where:** `src/mlr/precheck/dependency_rules.py` → `load_catalog`.
**Why this value:** matches the spec's three-pillar mental model;
authors edit one section without ambiguity.
**How to revise:** if a rule belongs to multiple pillars (e.g. a
labelling rule that's both legal AND regulatory), add an explicit
`pillars: [legal, regulatory]` field per rule. The verdict aggregator
already de-dupes by zone signature.
**Status:** `pinned`.

---

## Layer 3 — abbreviation precheck

### D13 — Glossary: 31 hand-curated entries (UK pharma, oncology bias)

**Current value:** `_GLOSSARY` dict in `src/mlr/precheck/glossary.py`,
31 entries reflecting the pilot UK email batch.
**Why this value:** the glossary is meant to auto-derive from approved
abbreviation blocks (`MLR_PRECHECK_SPEC.md` §5) once corpus density
allows. Hardcoded list is the bridge. Oncology bias because the pilot
KISQALI / Jakavi assets land there.
**How to revise:**
- For new therapy areas: add entries OR auto-derive once the corpus
  density is ≥10 approved assets per area.
- Per-asset disambiguation (PV = "pharmacovigilance" vs "polycythaemia
  vera") is currently resolved by general-domain default; revisit when
  ≥5 polycythaemia-vera assets are ingested.
**Status:** `pinned`.

### D14 — Acronym extraction regex

**Current value:**
```
(?<![A-Za-z0-9]) (i?[A-Z][A-Z0-9]{1,6}) ([+-])? (s)? (®|™)? (?![A-Za-z0-9])
```
**Where:** `src/mlr/precheck/glossary.py` → `_ACRONYM_RE`.
**Why this value:**
- Captures 2–8 char tokens starting with uppercase (or lowercase `i`
  for `iDFS`).
- Preserves biomarker suffix `+/-` in canonical form (`HR+` ≠ `HR`).
- Strips plural `s` so `AEs` canonicalises to `AE`.
- Tracks ®/™ as brand-token signal (consumed by document-pass filter).
**How to revise:** if real assets use 9-char acronyms (rare in pharma),
bump the inner `{1,6}` → `{1,7}`. If trailing-`s` stripping is wrong
for any specific term (e.g. `MS` "multiple sclerosis" must NOT lose its
`S`), guard the strip behind a non-glossary-collision check.
**Status:** `pinned`.

### D15 — Brand filter: ®/™ detection across the document + asset.meta.brand

**Current value:** two-pass: (1) any token followed by ® or ™ anywhere
in the asset is added to a per-asset brand set; (2) `asset.meta.brand`
is also filtered. All occurrences of those tokens are skipped.
**Where:** `src/mlr/precheck/abbreviation_check.py` →
`_BRAND_MARKED_RE`, `run()` document-pass.
**Why this value:** the original heuristic ("≥4 uppercase chars =
brand") false-positived on `XQVZ` and similar legitimate acronyms.
The ® signal is unambiguous and matches real pharma copy.
**How to revise:** expand to a per-customer brand dictionary once we
have multiple brands per asset (e.g. comparator names). Keep the ®
signal as the catch-all.
**Status:** `pinned`.

### D16 — Footnote-only acronyms don't trigger findings

**Current value:** acronyms appearing only in `FOOTNOTE` / `REFERENCE`
blocks emit no verdict; `_BODY_ROLES` excludes those roles.
**Where:** `src/mlr/precheck/abbreviation_check.py` → `_BODY_ROLES`.
**Why this value:** footnotes typically define their own terms inline
(`AE = adverse event`). Flagging would be noise.
**How to revise:** if a customer's footnote convention DOESN'T inline-
define, add `FOOTNOTE` back to `_BODY_ROLES` and accept the noise
trade-off. Or implement a smarter "is this acronym defined in any
in-block parenthetical" check.
**Status:** `pinned`.

### D17 — Unknown acronyms also emit a Verdict

**Current value:** an acronym in body text but not in the glossary still
emits a `warn / attn` zone (with `pattern_base: null`).
**Where:** `src/mlr/precheck/abbreviation_check.py` →
`_verdict_for_undefined_acronym`.
**Why this value:** safer to surface a stray uppercase token for human
review than silently drop it. Reviewer can confirm intent + add to
glossary in one step.
**How to revise:** if reviewers complain of noise from typos
(`XQVZ`-style hits), gate the verdict behind a "looks like a real term"
check (e.g. prior corpus seen-count ≥ 1).
**Status:** `pinned`.

---

## Asset envelope + scoring

### D18 — Library `coverage_warning` triggers below 20 samples

**Current value:** `coverage_warning_for_size(threshold=20)` returns the
warning string for samples < 20.
**Where:** `src/mlr/precheck/library.py` → `coverage_warning_for_size`.
**Why this value:** the spec calls 20 the "early signal" floor for
treating verdicts as low-confidence. Matches `dependency_rules.yaml`
per-rule `coverage.minimum` typical value (5–15).
**How to revise:** raise to 50 once corpus is mature; lower to per-rule
minimum to derive per-zone confidence.
**Status:** `pinned`.

### D19 — Verdict label: `Fail / Warn / Pass` derived from worst severity

**Current value:** any `block` non-clean verdict → Fail; else any `warn`
non-clean → Warn; else Pass.
**Where:** `src/mlr/precheck/verdict.py` → `compute_verdict_label`.
**Why this value:** matches cascade engine convention; matches the
score gating reviewers expect.
**How to revise:** if scores and labels diverge in confusing ways
(e.g. score 95 but verdict Fail because of one block), introduce a
`severity_threshold_for_fail` floor that requires N blocks not 1.
**Status:** `pinned`.

### D20 — Pin numbers + bbox overlays not yet assigned

**Current value:** `Zone.pin = None` for all zones; `EmailBlock.match
= "clean"` default; no bbox-bound zones emitted.
**Where:** `src/mlr/precheck/asset_builder.py` → `_verdicts_to_zones`,
`_email_blocks_for_extracted`.
**Why this value:** the preview-overlay assignment needs PDF coords from
the extractor; pipeline_v5 (emails) is in progress and doesn't deliver
bboxes for emails yet. Slides have them via pipeline_v4.
**How to revise:** once pipeline_v5 emits bboxes, populate
`EmailBlock.bbox` from the extracted block; assign `Zone.pin = N` per
zone with a bbox-bound block; populate `EmailBlock.pin` to match.
**Status:** `pinned`.

---

## Fixture choices

### D22 — PDF preview served via FastAPI; rendered with browser-native viewer

**Current value:** `GET /api/preview/{asset_id}.pdf` streams the file
mapped from `ExtractedAsset.pdf_path`; frontend renders via `<iframe
src="…#view=FitH&toolbar=0">`.
**Where:** `src/mlr/precheck/api.py` → `get_preview_pdf`;
`frontend/index.html` → `PdfEmailPreview`.
**Why this value:** zero deps (no PDF.js bundle), works in every modern
browser, demos the real pharma email rather than a synthetic mock-up
HTML. Native browser viewer handles scroll/zoom/print for free.
**How to revise:** if reviewers need overlay annotations on the PDF
(zone hotspots, comment pins), drop in PDF.js with a transparent
overlay div and one absolute-positioned hotspot per `Zone.bbox`.
**Status:** `pinned`.

### D24 — Claim subtype derived via keyword classifier in adapter

**Current value:** the extractor service doesn't yet stamp
EFFICACY/SAFETY/COMPARATIVE/DOSING on claim blocks, so the adapter
applies a small regex-based classifier on `synthesized_text`
(SAFETY: `adverse|safety|tolerab|...`; DOSING: `\d+\s*mg|dose|...`;
COMPARATIVE: `vs|versus|...`; EFFICACY: `HR|95% CI|reduced|response|...`).
Modules that don't match any pattern get `subtype = None`.
**Where:** `src/mlr/ingest/extractor_adapter.py` → `_claim_subtype`.
**Why this value:** lets Layer 1 + the bootstrapped library bucket
claims even when the upstream extractor doesn't classify. Verified on
the Scemblix UK fixture — the heuristic correctly identifies efficacy
/ dosing / safety claims.
**How to revise:** once the extractor emits `block.subtype` for CLAIM
blocks, prefer the upstream value and use the heuristic only as a
fallback when subtype is missing. For now the heuristic is the only
source.
**Status:** `pinned`.

### D25 — Library bootstrapped from extractor outputs (option B)

**Current value:** `mlr.ingest.library_bootstrap.bootstrap_from_dir`
walks every `*.extraction.json` in `eval_atlas_20260430T172755Z/` and
turns each claim module's `synthesized_text` into an `ApprovedClaim`
(deduped by exact text within each `(brand, market, subtype)` slice).
The active library is set to the bootstrap result on app boot if the
directory exists; otherwise the hardcoded 3-entry fallback stays.
**Where:** `src/mlr/ingest/library_bootstrap.py`,
`src/mlr/precheck/library.py` → `set_library` /  `reset_library`,
`src/mlr/precheck/api.py` → `_bootstrap_library_at_startup`.
**Why this value:** we don't yet have a curated MLR-blessed canonical
corpus per (brand, market, subtype). Treating the existing 24 UK
extractions as "approved" gives Layer 1 a real population to compare
against — noisy but better than no library. With the Cosentyx demo
asset, this produces a mix of clean matches + drift verdicts on real
text (verified end-to-end).
**How to revise:** once a real MLR-approved canonical corpus lands
(via the Vault → Atlas piece-by-piece approval flow per
`MLR_PRECHECK_SPEC.md` §6), swap `bootstrap_from_dir` for a loader
that reads the curated store. The `library.set_library` API stays
the same.
**Status:** `pinned` (intentional temporary state).

### D28 — Structural zones: one per block (no role-level dedupe)

**Current value:** `structural_check.run()` emits one `clean / info`
Verdict per *block*, not per role. When N>1 blocks share a role, the
labels carry an "(K of N)" suffix and `sub_layer` gets a `:K` suffix
to keep zone ids stable.
**Where:** `src/mlr/precheck/structural_check.py` → `run()`.
**Why this value:** the legal/MLR reviewer needs to validate every
granular structural item individually — the top of a Cosentyx UK
email decomposes into `promotional_notice`, `PI_link`,
`adverse_events_reporting`, `another promotional_notice`, and each is
a separate compliance check. Aggregating them under a single
"Promotional notice (2)" row hides the individual reviewability.
**How to revise:** if reviewers prefer fewer rows for icons / minor
visuals, keep them deduped (visuals path still dedupes by `kind`)
while leaving text blocks granular. Or add a UI-side toggle:
"compact" (deduped) vs "granular" (per-block).
**Status:** `pinned`.

### D32 — Group-level claim approval (deferred)

**Current value:** Layer 1 (`claim_check`) compares one extracted
module's `synthesized_text` against approved canonicals as a single
text blob. There is no concept of "group has X parts; flag missing
parts".
**Where to wire when needed:** `mlr.precheck.claim_check` →
new `claim_group_check.py`; the Verdict surfaces missing fragments
("Approved KISQALI efficacy claim group typically includes a
comparator fragment — current asset is missing it").
**User's clarification of the model:**
- **Module = group.** A module is the claim concept (one efficacy
  story; one safety story; etc.). Approval should target modules,
  not individual fragments.
- **Fragment = a piece linked into the module.** Fragments represent
  links — "this claim text is linked to this graph"; "this comparator
  number is linked to this study source". The link itself carries
  meaning.
- For approval: we approve a MODULE (the group). When precheck runs on
  a new asset, it detects: "module X matches the approved KISQALI
  efficacy module template, but is missing the comparator-graph link".
**Status:** `deferred` per user; will pick up when the structural
baseline path is exercised end-to-end.

### D31 — Edit extracted text + superscript (TODO)

**Current value:** the X-Ray drawer's annotation composer pre-fills
text from the verdict but does NOT support inline editing of the
extracted text (only bbox coordinates can be edited via the prototype
layer, not the text content). Superscripts (reference markers like
`²`, `⁴,⁵`) are extracted as inline characters but not editable.
**Why it matters:** the MLR reviewer needs to clean up the extracted
text before approving (typo fixes, normalisation, fixing OCR slips).
The cleaned text becomes the canonical exemplar in the baseline (D29);
quality of the baseline depends on this cleanup step.
**Where to wire:** new edit-mode toggle in the drawer's expanded zone
view; rich-text or contenteditable for the extracted_content field;
superscript-aware tokeniser for ref-marker preservation. Backend route
to persist edits (`POST /api/precheck/{asset_id}/zones/{zone_id}/edit`).
**Status:** `deferred — TODO`. Not blocking the structural baseline
demo but will be needed before the curated approval path can be used
for production-grade pattern matching.

### D30 — Baseline file location is env-var configurable

**Current value:** `mlr.ingest.baseline_bootstrap.curated_path()`
returns `MLR_BASELINE_PATH` env var if set, else
`backend/baselines/uk_email_baselines.jsonl`.
**Why this value:** the MLR Precheck POC and the extractor service
live in separate repos. Letting the extractor service write to its
own path (e.g.
`extractor-service/data/approved/uk_email_baselines.jsonl`) and
having our backend read via env var avoids both duplication and
symlinks. `/api/health` reports the resolved path so it's discoverable
at runtime.
**How to revise:** swap to a small HTTP endpoint that pulls from the
extractor service if cross-machine deploys ever matter. For local POC
the env var is enough.
**Status:** `pinned`.

### D29 — UK baseline pattern bank (implemented)

**Current value:** structural zones emit `Extracted` (status `clean`,
severity `info`) without verifying the block's text against an
approved canonical. The status text is honest about this limited
claim.
**Where to wire:** would extend `structural_check.run()` to query a
new `mlr.precheck.baseline` module; `mlr/ingest/baseline_bootstrap.py`
walks the ~25 approved UK emails, harvests text per `(role,
brand?)` slice, builds a `BaselinePattern` corpus.
**Why this matters:** "Extracted" → "Pattern match · 0.94 (n=23,
24 months)" — the same drift signal Layer 1 produces for claims, but
applied to every structural element. Drives reviewers to "yes this
matches the approved standard" vs "extracted but novel — needs review".
The bootstrapping flow already exists for claims (D5/D25); the
structural path mirrors it.
**Implementation sketch:**
1. `BaselinePattern { role: str, exemplars: list[str], n: int,
   coverage: float, window_months: int }`
2. `baseline_bootstrap.bootstrap_from_dir(path, role_set)` —
   per-role ApprovedClaim-like corpus, deduped by exact text.
3. `structural_check` calls `baseline.match(role, blk.text)` →
   returns best similarity + matched exemplar id; status maps:
   `≥ 0.95 → clean / "Pattern match · X.XX"`,
   `≥ 0.80 → attn  / "Drift · X.XX"`,
   `< 0.80 → miss  / "Novel · X.XX"`.
4. Pin the same hybrid similarity used by Layer 1 (cosine + char
   ratio); revisit thresholds per role.
**Status:** `documented` (not implemented).

### D27 — Adapter downgrades reference-shaped BODY blocks to REFERENCE

**Current value:** when the upstream extractor labels a citation
("12. Author et al. Journal. 2024;...") as `BODY`, the adapter detects
the citation pattern via regex and stamps `role=REFERENCE`. This
prevents Layer 3 (which excludes REFERENCE / FOOTNOTE roles from
acronym scanning) from scraping author initials and journal codes
(`LC`, `RMD`, `SVJS`, …) as undefined acronyms.
**Where:** `src/mlr/ingest/extractor_adapter.py` →
`_REFERENCE_LIKE_RE`, `_looks_like_reference_entry`,
`_block_from_extractor`.
**Why this value:** observed on the Cosentyx UK fixture — 3 false-
positive abbreviation findings collapsed to 0 after this fix.
Defending in the adapter (rather than in `abbreviation_check`) keeps
the Layer 3 logic clean and means anything else downstream that cares
about role gets the corrected classification too.
**How to revise:** when the upstream extractor classifies references
correctly (the role is provided by `pipeline_email_v3`'s classifier
already, so this is a band-aid), the adapter check becomes a no-op.
Drop it once misclassification rate is verified to be near-zero.
**Status:** `pinned` (band-aid for upstream noise).

### D26 — Real-data fixtures loaded via adapter at app boot

**Current value:** `mlr.fixtures.assets._load_real_assets` lazily loads
3 real fixtures (COSENTYX, SCEMBLIX, KISQALI) from the
extractor-service eval directory at module import. Synthetic KISQALI
fixture stays in the store too.
**Where:** `src/mlr/fixtures/assets.py`.
**Why this value:** fastest path from extractor JSON to live demo.
Failing-soft on missing files lets the test suite (and CI / fresh
checkouts) keep working without the extractor data on disk.
**How to revise:** swap for an Atlas-API client once a live extractor
service is reachable from the precheck backend.
**Status:** `pinned`.

### D23 — Real PDF preview + synthetic extracted content (temporary mismatch)

**Current value:** the left pane renders the *real* KISQALI 5-year-data
PDF; the right-pane verdicts are computed from *synthetic* fixture data
that doesn't match the PDF's actual claim text (PDF: "28.4% with NSAI";
fixture: "25.2% with ET alone").
**Where:** `src/mlr/fixtures/assets.py` → `KISQALI_UK_001`.
**Why this value:** demonstrates the API + UI shape end-to-end while
keeping the §6 sample-payload-aligned drift case for the demo. Running
the actual extractor pipeline on the PDF and feeding real extracted
text into the precheck is the next slice.
**How to revise:** wire `pipeline_v5` (or `pipeline_v4` for slides)
output into the fixture builder; replace the hardcoded `modules` /
`blocks` / `envelope` with the live extractor's output for this PDF.
The library's canonical KISQALI claim text will need to be updated to
match a real approved variant once we ingest one.
**Status:** `pinned` (intentional temporary state).

### D21 — KISQALI fixture intentional gaps

**Current value:** `envelope.audience_restriction` and the SAFETY block
are intentionally omitted; `envelope.disclaimers` uses lowercase
"privacy policy" so the legal regex matches.
**Where:** `src/mlr/fixtures/assets.py`.
**Why this value:** aligned with `MLR_PRECHECK_API.md` §6 — the sample
shows audience_restriction as missing. Lets Layer 2 demo a `block` and
a `warn` finding.
**How to revise:** when adding fixtures for other assets, decide which
gaps to demo and document in the fixture comment.
**Status:** `pinned`.
