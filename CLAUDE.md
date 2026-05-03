# Project notes for future Claude Code sessions

This file captures the state of the Atlas MLR X-Ray POC for any future
Claude session picking it up cold. Pair this with `README.md` (the
original product/spec overview) and `backend/DECISIONS.md` (every
tunable choice with current value + revision playbook).

## Goal

A working POC of the **MLR Precheck X-Ray** described in
`MLR_PRECHECK_API.md` and the design handoff at
`design brief/design_handoff_mlr_xray/`. Reviewer opens an extracted
pharma email, sees its structural inventory + claim drift + missing
required items in a right-side drawer, and can browse approved
exemplars from the UK baseline corpus. The POC drives the backend
contract for the production rebuild that will live in Shaman's React
+ Antd v4 codebase.

The repo is on GitHub at `ShamanBV/poc-atlas-mlr-xray`.

## State of play (as of the last session)

### Backend (`backend/`)

Three precheck layers + one structural layer + a baseline corpus,
all running from a FastAPI app:

- **Layer 0** (`structural_check.py`) — emits one `clean / info`
  Verdict per recognised structural block (PROMOTIONAL_NOTICE,
  PRESCRIBING_INFORMATION, AE reporting, etc.) and per visual. Each
  block compared against the UK baseline corpus; status = pattern
  match / drift / novel / extracted.
- **Layer 1** (`claim_check.py` + `library.py` + `similarity.py`) —
  per-claim-module similarity against approved canonicals. Hybrid
  bag-of-tokens cosine + char-ratio. Pluggable Embedder protocol
  (default `HashEmbedder`; sentence-transformers can swap in).
- **Layer 2** (`document_check.py` + `dependency_rules.py`) — runs
  the YAML rule catalog (`../dependency_rules.yaml`) against the
  asset; emits one Verdict per fired-but-unmet rule.
- **Layer 3** (`abbreviation_check.py` + `glossary.py`) — flags
  acronyms used in body text but not defined.

Plus:

- **Baseline corpus** (`baseline.py` + `baseline_bootstrap.py`) —
  per-role exemplar bank. Sources, in order of preference:
  1. Curated `.jsonl` file (extractor-service approval flow output;
     resolves via `MLR_BASELINE_PATH` env var, default
     `backend/baselines/uk_email_baselines.jsonl`).
  2. Bootstrap from existing UK extractor outputs (option B per
     D5/D29 in DECISIONS).
- **Adapter** (`mlr/ingest/extractor_adapter.py`) — converts
  extractor `.extraction.json` → ExtractedAsset. Used by both the
  fixture loader and (potentially) live extraction.
- **PDF preview** (`mlr/preview/render.py` + routes) — PyMuPDF page
  rasteriser for the left-pane preview.

Routes (FastAPI):
- `GET /api/health` — liveness + sizes
- `GET /api/precheck/{asset_id}` — full Asset payload (zones, scores, etc.)
- `GET /api/document-xray/{asset_id}` — alternative payload shape (legacy of the misdirect rebuild; see Caveats)
- `GET /api/assets` — fixture directory for the Library popover
- `GET /api/preview/{asset_id}.pdf` — raw PDF
- `GET /api/preview/{asset_id}/pages` — per-page metadata (width/height in pt + px)
- `GET /api/preview/{asset_id}/page/{n}.png` — page raster
- `GET /api/baseline/visuals` — visual exemplars from the baseline (powers the drawer's Visual Library card)

Tests: 133/133 (`pytest -q` from `backend/`).

### Frontend (`frontend/`)

Self-contained `index.html` (React + Babel-standalone in-browser, no
Node toolchain). Loads the design-handoff JSX components
(`XRayDrawer.jsx`, `XRayEmail.jsx`, `XRayData.jsx`) and an
`adapter.js` that converts the snake_case API shape into the
prototype's camelCase data layer.

Live UI surfaces:
- Apryse-designer-style Shaman header with brand mark, doc name +
  doc-type pill, FS+ML reviewer avatars, primary green Save button,
  Library popover (asset switcher), JD signed-in user.
- Left pane: PDF page render with bbox-bound colored rectangles per
  zone (clean=primary green / attn=warning yellow / miss=critical
  pink). Clean rects carry a small ✓ badge top-right. Click a rect →
  drawer scrolls to + opens the matching zone.
- Right pane (drawer):
  - **HEALTH N% cleared** + status verb (Ready to approve / Review
    pending / Needs revision) + breakdown chips (`N blockers · N
    attention`). Replaces the old 0-100 score (D7/D29).
  - Tabs: All / Medical / Legal / Regulatory.
  - Asset metadata card (collapsible).
  - Visual library card (collapsible) — repurpose lookup of approved
    visuals from the baseline.
  - Zone spine — one row per Verdict; expand for extracted /
    canonical / word-diff / annotation composer.

Cache-busting: scripts loaded with `?v=N` query param. Bump in
`index.html` after any JSX edit (Babel-standalone caches transforms
by URL regardless of HTTP headers).

### Legacy

- `frontend/legacy_document_xray/` — earlier Document X-Ray frontend
  rebuild (different design surface). Archived; not the live UI.
  Keep around in case the extractor-service POC wants to lift bits.

## How to run locally

```bash
# 1. Backend (port 8088)
cd backend
python3 -m venv .venv && source .venv/bin/activate    # first time only
pip install -e ".[dev]"                                # first time only
uvicorn mlr.precheck.api:app --port 8088
# add MLR_BASELINE_PATH=…/curated.jsonl in front of uvicorn to point
# at an extractor-service approved baseline file

# 2. Frontend (port 8089) — in another terminal
cd frontend
python3 -m http.server 8089

# 3. Open
open http://localhost:8089/?asset=real:cosentyx-uk-rheum-mda-001
```

Other handy commands:

```bash
# Run the test suite
cd backend && source .venv/bin/activate && pytest -q

# Re-bootstrap the baseline file from extractor outputs
cd backend && python -m mlr.ingest.seed_baseline --dry-run     # preview
cd backend && python -m mlr.ingest.seed_baseline               # write

# Merge new approvals into existing baseline
cd backend && python -m mlr.ingest.seed_baseline --merge \
    --source /path/to/approvals_dir \
    --out    /path/to/baselines.jsonl
```

## Key docs

- `README.md` — original product / spec overview, ASCII data flow diagram.
- `MLR_PRECHECK_API.md` — frontend ↔ backend contract (Asset / Zone
  shapes, endpoint specs, error envelope).
- `CLASSIFICATION_TO_MLR_MAP.md` — every extractor classification →
  MLR purpose; visual taxonomy is in §5.
- `dependency_rules.yaml` — Layer 2's rule catalog (predicate /
  requires per rule; markets + severities + coverage).
- `profiles/*.yaml` — compliance profile catalog
  (UK-Branded-Promotional active in v1; IE/Event/Non-Branded drafted).
- `backend/DECISIONS.md` — D1–D32, every tunable choice with current
  value, why we picked it, and how to revise. **Read this before
  changing anything that looks "wrong"** — the values are pinned for
  a reason and the doc captures the reasoning.

## Backlog (still TODO)

Sourced from `backend/DECISIONS.md` — full rationale + revision
playbook is there.

**Active:**
- **D31** — edit extracted text + superscript before approving.
  Reviewer needs to clean text before it becomes a baseline exemplar
  (typo fixes, normalisation, ref-marker preservation). Adds an
  edit-mode toggle to the drawer's expanded zone view + a
  persistence endpoint.
- **D32** — group-level claim approval. User clarified the model:
  module = group (the claim concept), fragment = a piece linked into
  the module (claim text linked to a graph; comparator linked to a
  study source). Approval should target modules; precheck would flag
  missing linked pieces in new assets. Bigger Layer 1 enrichment.

**Lower priority / opportunistic:**
- **D9** — `envelope.matches_pattern` predicate is currently
  stub-true. Wire up once the pattern bank is dense enough.
- **D10** — date-of-preparation freshness window (currently regex
  presence only).
- **Cascade adapter** — bridge to the existing 24-rule cascade
  engine to emit `layer:cascade` zones.
- **Visual content matching** (deferred to v2 per the spec) — Layer 1
  on visuals, not just text.

## Caveats / known soft spots

- **/api/document-xray/{asset_id}** is a parallel endpoint shape
  built during a misdirect (the extractor-service POC's Document
  X-Ray UI). Not consumed by the live frontend; kept available for
  the legacy archive.
- The score formula deductions in `verdict.py` (D7) drive both
  precheck score and the older "TOTAL SCORE" pillar values. The new
  HEALTH framing uses a different lens (count-based, severity-
  tiered). Both are correct under their respective definitions.
- Cache-bust on JSX edits: bump `?v=N` in `frontend/index.html` —
  Babel-standalone is sticky.
- `frontend/index.html` mounts an asset-switcher dropdown
  imperatively into the (hidden) backend-status banner; that side-
  channel still exists in the source even though it's invisible
  unless `?debug=1` is passed.
- Backend tests reset library + baseline corpora before each test
  via `tests/conftest.py` autouse fixture. If you add a new corpus,
  add a reset there too.

## How "approval flow" works end-to-end

1. Extractor service (separate repo, lives at
   `/Users/mauricevanleeuwen/Development/dev_projects/extractor-service/`)
   processes a PDF and produces an `extraction.json`.
2. Reviewer opens that asset in the extractor service's "Document
   X-Ray" approval UI, edits / accepts blocks (per-block + group),
   clicks Process.
3. Extractor writes a `.jsonl` baseline file (one approved exemplar
   per line; schema documented in
   `backend/src/mlr/ingest/baseline_bootstrap.py` module docstring).
4. MLR backend started with `MLR_BASELINE_PATH=…that file.jsonl`
   picks it up at startup. `/api/health` reports the resolved path.
5. Future precheck runs match each extracted block against the role's
   exemplar set in the baseline; status reads "Pattern match · 0.97"
   / "Drift · 0.84" / "Novel · 0.30".
6. Use `python -m mlr.ingest.seed_baseline --merge` to append
   subsequent approvals into the same master file (dedupes by
   `pattern_id`).

## Useful conversation context

- The repo went through a brief misdirect when image #4 (Atlas
  Content Ops "Document X-Ray" surface) was mistaken for the MLR
  X-Ray target. The legacy `frontend/legacy_document_xray/` retains
  that work. The actual MLR X-Ray design lives in
  `design brief/design_handoff_mlr_xray/` and was the original brief
  all along.
- The user wants restricted palette: greens (primary 800–300), greys
  (800–50), warning yellow.600, critical pink.600. No purples /
  reds / blues / oranges in UI chrome (the PDF previews of real
  branded content can have any colours — those are the asset's own).
- Backend runs in a venv inside `backend/.venv`. Static frontend
  needs only Python's `http.server`.
