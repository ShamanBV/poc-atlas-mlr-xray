# MLR Precheck — API contract (v1)

API surface between the **MLR X-Ray frontend** (the React UI in
`design brief/design_handoff_mlr_xray/`) and the **Atlas precheck engine**
(server-side, backed by the Vault → Atlas content extractor → library
flow defined in `MLR_PRECHECK_SPEC.md` §6).

This is the contract POC v1 is built against. Designed so frontend +
backend can develop in parallel against the same shapes; mock data lives
in `XRayData.jsx` and matches the `Asset` shape below.

Status: **draft for review.** Forward-references in §11 list things that
will pin down once pipeline_v5 (email) stabilises and the first 20–30
approved UK emails land in the library.

---

## 0. Conventions

- All dates ISO-8601 strings (`YYYY-MM-DD` or `YYYY-MM-DDTHH:mm:ssZ`).
- All ids are opaque strings; the only stable id you can build URLs from
  is `asset_id`.
- All scores are integers `0..100`.
- All similarity values are floats `0..1`, rounded to 2 decimals.
- `null` means "absent / not applicable"; never use `""` or `0` for
  absent values.
- Errors follow `{ error: { code: string, message: string } }`; HTTP
  codes for transport (404 / 422 / 500), `error.code` for app-layer
  failure modes.

---

## 1. Endpoints — overview

| Method | Path                                        | Purpose                                  |
|--------|---------------------------------------------|------------------------------------------|
| GET    | `/api/precheck/{asset_id}`                  | Run precheck and return Asset verdict    |
| GET    | `/api/precheck/{asset_id}/history`          | Three-strand history for the History panel |
| POST   | `/api/precheck`                             | Run precheck on an upload (no asset_id yet) |
| POST   | `/api/vvpm/annotate`                        | Create a Veeva Vault PromoMats annotation |
| POST   | `/api/precheck/{asset_id}/dismiss`          | Persist a dismissal (deferred to v1.5 — see §10) |
| GET    | `/api/precheck/library/coverage`            | Library coverage report (per brand/market/doc_type) |
| GET    | `/api/precheck/patterns/{pattern_id}`       | "Why this pattern?" drilldown            |

All endpoints require auth (Atlas session). Asset-scoped endpoints
verify the user's profile permits the asset's `(brand, market)` slice.

---

## 2. Core types

### 2.1 `Asset` — top-level precheck result

Returned by `GET /api/precheck/{asset_id}` and `POST /api/precheck`.

```ts
interface Asset {
  asset_id: string;                 // stable id; same shape as Vault doc id
  schema_version: "1.0";

  meta: {
    brand:       string;            // "KISQALI"
    market:      string;            // "UK" (ISO-3166-1 alpha-2 OR "EU")
    language:    string;            // "en"
    doc_type:    "email" | "slide" | "leave_behind" | "event_invite";
    channel:     string;            // "HCP email"  (display only)
    code:        string | null;     // approval code, e.g. "FA-11551654"
    prepared:    string | null;     // ISO date — date of preparation
    age_days:    number | null;     // server-computed: today - prepared
  };

  identity: string;                 // single-line display string;
                                    // server-formatted, frontend just renders.
                                    // e.g. "KISQALI · UK · en · UK-Branded-Promotional · FA-11551654 · prepared 2026-03-14 (37d)"

  profile: {                        // compliance profile (see MLR_PRECHECK_SPEC §9.2)
    id:          string;            // "UK-Branded-Promotional"
    selected_by: "metadata" | "user" | "default";
  };

  scores: {
    overall:    number;
    medical:    number;
    legal:      number;
    regulatory: number;
  };

  verdict: "Pass" | "Warn" | "Fail"; // overall_pillar_worst (matches cascade)

  zones: Zone[];                    // ordered by zone.doc_pos asc
  email_blocks: EmailBlock[];       // for the left preview pane (one per render block)
  library: {
    sample_size:    number;         // approved variants used for pattern matching
    last_ingest_at: string;         // most recent library entry timestamp
    coverage_warning?: string;      // shown when sample_size < 20 for any pillar
  };

  preview: {
    pdf_url?: string;               // canonical rendered PDF (preferred)
    html_url?: string;              // legacy fallback if PDF rendering deferred
    page_count?: number;
  };

  generated_at: string;             // when this precheck ran
  cache_key:    string;             // opaque; refresh-busts when library version changes
}
```

### 2.2 `Zone` — one row of the spine

The mock's `Zone` shape, **extended** with the four reconciliation
fields flagged in the design review (see §3 of the README handoff
review). Backwards-compatible — every field the mock already uses is
preserved; new fields are additive.

```ts
interface Zone {
  id:               string;          // unique within asset; matches data-zone-id in preview
  doc_pos:          number;          // 1-indexed reading-order position
  label:            string;          // human-readable name, e.g. "Key efficacy claim"
  lanes:            ("M" | "L" | "R")[];  // which function tabs include this zone
  status:           "clean" | "attn" | "miss";
  severity:         "info" | "warn" | "block";  // gates Approve button (§4.2)

  // ── Layer + sublayer (from MLR_PRECHECK_SPEC §3–§5) ──
  layer:            "claim" | "regulatory" | "abbreviation" | "cascade";
  sub_layer:        string;          // "claim:efficacy" | "regulatory:audience_restriction"
                                     // | "abbreviation:AE" | "cascade:r_indication_block"

  // ── Evidence (mock-compatible) ──
  evidence:         string;          // short label for collapsed row, e.g. "Pattern match · 0.84"
  evidence_detail:  string;          // long-form text shown in expanded view

  // ── Extracted vs canonical ──
  extracted_content: string | null;  // the text Atlas extracted; null when status=miss
  canonical_content: string | null;  // best-match approved text (when applicable)

  // ── Word diff (when extracted ≠ canonical and the diff is presentable) ──
  diff:             DiffSegment[] | null;

  // ── Pattern base (structured, replaces the freeform string in the mock) ──
  pattern_base:     PatternBase | null;

  // ── Conditional dependencies (which rules triggered this zone) ──
  dependencies_triggered: DependencyTrigger[];

  // ── Annotation defaults ──
  annotation_draft: string | null;   // pre-fill text for the composer
  vvpm_anchor:      string | null;   // id used by POST /api/vvpm/annotate
  pin:              number | null;   // visual pin number (matches preview overlay)
}

interface DiffSegment {
  t: string;                         // text fragment
  s: "k" | "d" | "a";                // keep | delete | add
}

interface PatternBase {
  pattern_id:      string;           // back-link to GET /api/precheck/patterns/{id}
  description:     string;           // "OS efficacy claim with HR + CI in this position"
  coverage:        number;           // 0..1 — fraction of approved variants matching
  n:               number;           // sample size (approved variants)
  window_months:   number;           // time window the pattern was computed over
  rule_id?:        string;           // when the pattern is enforced by a regulatory rule
                                     // (e.g. "ABPI-26.1")
}

interface DependencyTrigger {
  rule_id:     string;               // e.g. "r_indication_when_drug_named"
  predicate:   string;               // human-readable, e.g.
                                     // "Module mentions branded drug 'KISQALI'"
  rationale:   string;               // why the rule requires this zone
  coverage:    {                     // for transparency on rule confidence
    predicate_hits_in_corpus: number;  // how many times we've seen the predicate
    requirement_hits:          number;  // how many of those had the requirement
    confidence_label:          "high" | "medium" | "low";
  };
}
```

### 2.3 `EmailBlock` — left-pane preview hookup

Each block in the rendered email/slide has a stable id matched to a
`Zone.id`. Used by the `BlockWrapper` component to overlay zone status
on the preview.

```ts
interface EmailBlock {
  id:          string;               // matches Zone.id, OR "ghost_<zone_id>" for missing zones
  type:        string;               // "header" | "salutation" | "claim" | "callout" |
                                     // "paragraph" | "cta" | "ae" | "footer" | "ghost" | …
  match:       "clean" | "attn" | "miss";
  pin:         number | null;        // matching pin number on the X-Ray spine
  bbox:        BoundingBox | null;   // PDF coords; null when the preview is HTML-rendered
  page:        number | null;        // 1-indexed; null for HTML preview

  // Ghost-only fields (set when this block represents an absent zone)
  ghost_label: string | null;        // "Audience-restriction bar expected here"
}

interface BoundingBox {
  x0: number; y0: number; x1: number; y1: number;
}
```

### 2.4 `History` — three strands

```ts
interface History {
  asset_edits: {
    date:   string;
    actor:  string;
    action: string;
  }[];
  precheck_runs: {
    date:    string;
    score:   number;
    delta:   string | null;
    summary: string;
  }[];
  base_changes: {
    date:    string;
    item:    string;                  // "KISQALI UK claims base"
    version: string;
    note:    string;
  }[];
}
```

`base_changes` may be empty for v1.0 (library versioning is v1.5 — see
§10). UI hides empty strands.

---

## 3. Endpoint specs

### 3.1 `GET /api/precheck/{asset_id}` — fetch precheck

Returns the full `Asset` for an asset already known to the system.

**Request**: query params

| param        | type    | default | meaning                              |
|--------------|---------|---------|--------------------------------------|
| `force`      | bool    | `false` | bypass cache; re-run extraction + precheck |
| `profile_id` | string  | server-resolved | override the auto-resolved compliance profile |

**Response** `200`:
```jsonc
{
  "asset_id": "vault:00W…XYZ",
  "schema_version": "1.0",
  "meta": { /* … */ },
  "scores": { "overall": 82, /* … */ },
  "verdict": "Warn",
  "zones": [ /* … */ ],
  "email_blocks": [ /* … */ ],
  "library": { "sample_size": 287, /* … */ },
  "preview": { "pdf_url": "/api/preview/vault:00W…XYZ.pdf", "page_count": 2 },
  "generated_at": "2026-05-02T14:33:11Z",
  "cache_key": "v1.0:lib_2026-05-02:asset:00W…XYZ:profile:UK-Branded-Promotional"
}
```

**Errors**:

| HTTP | error.code              | when                                              |
|------|-------------------------|---------------------------------------------------|
| 404  | `asset_not_found`       | asset_id unknown                                   |
| 422  | `profile_required`      | brand+market resolved but no profile selected; UI must prompt user |
| 422  | `extraction_failed`     | upstream pipeline error; `error.message` carries detail |
| 503  | `library_unavailable`   | library snapshot is being rebuilt; retry after `Retry-After` |

### 3.2 `POST /api/precheck` — precheck on upload

For "new draft, no Vault id yet". Multipart form with the PDF + JSON
metadata. Server allocates a transient `asset_id` (prefixed `tmp:`)
that's valid for ~24h.

**Request**:
```
Content-Type: multipart/form-data
  file:        <PDF binary>
  meta:        application/json
                {
                  "brand":     "KISQALI",
                  "market":    "UK",
                  "language":  "en",
                  "doc_type":  "email",
                  "profile_id":"UK-Branded-Promotional"   // optional
                }
```

**Response**: same `Asset` shape as `GET`. The temporary `asset_id`
behaves identically until it expires.

### 3.3 `GET /api/precheck/{asset_id}/history`

```jsonc
{
  "asset_id": "vault:00W…XYZ",
  "asset_edits": [ /* … */ ],
  "precheck_runs": [ /* … */ ],
  "base_changes": [ /* … */ ]
}
```

Empty strands return as empty arrays (not null), so the UI can render
"no events" deterministically.

### 3.4 `POST /api/vvpm/annotate` — write annotation to Veeva

The whole point of v1 — Atlas surfaces findings, the human posts the
annotation into PromoMats.

**Request**:
```jsonc
{
  "asset_id":    "vault:00W…XYZ",
  "zone_id":     "z3",
  "vvpm_anchor": "anchor_blk_003",
  "text":        "Key efficacy claim shows phrasing drift…",
  "severity":    "warn",                    // copied from Zone.severity
  "metadata": {
    "layer":     "claim",
    "sub_layer": "claim:efficacy",
    "pattern_id":"uk_email_efficacy_HR_CI", // when applicable
    "rule_id":   null
  }
}
```

**Response** `201`:
```jsonc
{
  "annotation_id": "vvpm:anno:8431",
  "vvpm_url":      "https://vault.veevavault.com/ui/#anno=8431",
  "created_at":    "2026-05-02T14:35:02Z"
}
```

**Errors**:

| HTTP | error.code               | when                                              |
|------|--------------------------|---------------------------------------------------|
| 401  | `vvpm_auth_failed`       | session lacks Veeva token; UI redirects to OAuth  |
| 422  | `anchor_invalid`         | anchor doesn't resolve in current Vault doc       |
| 502  | `vvpm_upstream_error`    | Veeva API failure; surface message for retry     |

### 3.5 `POST /api/precheck/{asset_id}/dismiss` — defer to v1.5

Returns `501 not_implemented` in v1. UI handles dismissal in session
state only (per the mock's `ZoneActionState`).

### 3.6 `GET /api/precheck/library/coverage`

```jsonc
{
  "library_version": "v2026-05-02",
  "slices": [
    {
      "brand": "KISQALI", "market": "UK", "doc_type": "email", "language": "en",
      "approved_assets":     287,
      "approved_modules":    1248,
      "approved_envelope_items": { "indication": 287, "approval_info": 287, "audience_restriction": 287 },
      "abbreviation_pairs":  142,
      "first_ingested":      "2025-08-12",
      "last_ingested":       "2026-04-30"
    },
    /* … */
  ]
}
```

Used by an admin/coverage view; not on the X-Ray drawer's hot path.

### 3.7 `GET /api/precheck/patterns/{pattern_id}`

"Why this pattern?" link target. Returns the corpus drilldown for a
single `PatternBase.pattern_id`.

```jsonc
{
  "pattern_id": "uk_email_efficacy_HR_CI",
  "description":"OS efficacy claim with HR + CI in this position",
  "coverage":   0.94,
  "n":          287,
  "window_months": 18,
  "variants": [
    { "text": "At 5 years, KISQALI® + ET reduced…", "count": 162, "first_seen": "2024-06" },
    { "text": "KISQALI® + ET reduced the risk of disease recurrence…", "count": 73, "first_seen": "2024-09" }
  ],
  "rule_id":  "ABPI-26.1",                    // when pattern enforces a regulatory rule
  "examples": [
    { "asset_id": "vault:…", "approved_at": "2026-04-12" },
    /* up to 5 sample asset_ids */
  ]
}
```

Out of scope for v1 *UI* (the link is grey/disabled), but the endpoint
ships in v1 so the data is queryable from the admin coverage view.

---

## 4. Frontend mapping notes

### 4.1 Zone display logic

| field           | UI rendering                                                             |
|-----------------|--------------------------------------------------------------------------|
| `status`        | dot colour + row weight (clean=400, attn/miss=600 with status colour)    |
| `severity`      | gates Approve button + filters History panel "blockers only" view        |
| `layer`         | not directly rendered, but enables sub-grouping on the spine when ≥2 layers fire on a zone |
| `sub_layer`     | shown in the row's evidence tag prefix when not obvious from the label   |
| `evidence`      | collapsed-row right-side tag (clean) or amber/red sub-line (attn/miss)   |
| `evidence_detail` | expanded row "Comparative evidence" body                               |
| `pattern_base`  | expanded row analytics row; `Why this pattern?` link → §3.7              |
| `dependencies_triggered` | new "Why required?" chip in expanded row when present           |
| `diff`          | expanded row "Word diff" section                                         |
| `annotation_draft` | textarea pre-fill                                                     |

### 4.2 `canApprove` gating (replaces mock's "no missing zones" rule)

```
canApprove =
  asset.zones
    .filter(z => zoneActions[z.id] !== 'dismissed' && zoneActions[z.id] !== 'annotated')
    .every(z => z.severity !== 'block')
```

`drift` with `severity: 'block'` (orphaned-ref, metric value mismatch,
broken approval-code regex) gates approval just like `missing`.

### 4.3 Sort toggle

Spine renders `zones` in `doc_pos` order by default. Toggle to status
priority sorts: `severity=block` first, then `warn`, then `info`,
within each status by `doc_pos`.

### 4.4 Abbreviation rendering

Abbreviation findings (`layer === "abbreviation"`) get their own
sub-section inside the All / Medical lane. Each finding is one zone
with `label = "AE — used but not defined"` style format. They don't
have `bbox` overlays on the preview (acronyms are inline text, not
block-level), so `EmailBlock` may omit them.

### 4.5 Cascade rule findings (`layer === "cascade"`)

Cascade-rule failures (e.g. `r_audience_restriction_bar` not satisfied)
also surface as zones, with `sub_layer: "cascade:<rule_id>"`. Their
`evidence` reads `Rule violated (RULE-ID)`. Auto-inserted satisfactions
read `Rule satisfied (auto)` on a clean zone.

---

## 5. Backend → frontend data flow

```
Vault PDF
  │
  │  GET /api/preview/{asset_id}.pdf  ← rendered for left pane
  ▼
Atlas content extractor (pipeline_v4 slides / pipeline_v5 emails)
  │
  ├─► structured payload (modules / fragments / blocks / supportive_resources / envelope)
  │
  ▼
MLR precheck engine (src/mlr/precheck/)
  │
  ├─► claim_check.py      → per-claim verdicts (layer="claim")
  ├─► document_check.py   → per-envelope-item verdicts (layer="regulatory")
  ├─► abbreviation_check.py → per-acronym verdicts (layer="abbreviation")
  └─► cascade_engine      → per-cascade-rule verdicts (layer="cascade")
  │
  ▼
verdict aggregator
  │
  ├─► flatten verdicts into Zone[] (one zone per verdict)
  ├─► attach EmailBlock[] (zone_id → bbox/type for the preview overlay)
  ├─► compute scores (per pillar + overall)
  └─► serialise to Asset shape
  │
  ▼
GET /api/precheck/{asset_id}
```

Single Atlas-side cache key per (asset_id × library_version × profile_id);
invalidated on library ingest events.

---

## 6. Minimal sample payload (KISQALI v1)

A real-shape fixture for the frontend to develop against before the
backend is live. Frontend should be able to load this JSON and render
exactly the mock screenshots.

```jsonc
{
  "asset_id": "tmp:demo-kisqali-uk-001",
  "schema_version": "1.0",
  "meta": {
    "brand": "KISQALI", "market": "UK", "language": "en", "doc_type": "email",
    "channel": "HCP email", "code": "FA-11551654",
    "prepared": "2026-03-14", "age_days": 49
  },
  "identity": "KISQALI · UK · en · UK-Branded-Promotional · FA-11551654 · prepared 2026-03-14 (49d)",
  "profile": { "id": "UK-Branded-Promotional", "selected_by": "metadata" },
  "scores": { "overall": 82, "medical": 88, "legal": 78, "regulatory": 80 },
  "verdict": "Warn",
  "zones": [
    {
      "id": "z3", "doc_pos": 3,
      "label": "Key efficacy claim",
      "lanes": ["M"],
      "status": "attn", "severity": "warn",
      "layer": "claim", "sub_layer": "claim:efficacy",
      "evidence": "Partial match · 0.84",
      "evidence_detail": "Closest approved: …",
      "extracted_content": "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014).",
      "canonical_content": "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014).",
      "diff": [
        {"t":"At 5 years, KISQALI® + ET reduced the risk of ","s":"k"},
        {"t":"disease recurrence","s":"d"}, {"t":"recurrence","s":"a"},
        {"t":" by 25.2% vs ET alone (HR 0.748","s":"k"},
        {"t":"; 95% CI","s":"d"}, {"t":", 95% CI","s":"a"},
        {"t":" 0.618–0.906; p=0.0014).","s":"k"}
      ],
      "pattern_base": {
        "pattern_id": "uk_email_efficacy_HR_CI",
        "description": "OS efficacy claim with HR + CI in this position",
        "coverage": 0.94, "n": 287, "window_months": 18,
        "rule_id": null
      },
      "dependencies_triggered": [],
      "annotation_draft": "Key efficacy claim shows phrasing drift vs approved canonical (similarity 0.84). …",
      "vvpm_anchor": "anchor_blk_003",
      "pin": 1
    },
    {
      "id": "z8", "doc_pos": 8,
      "label": "Audience restriction",
      "lanes": ["R","L"],
      "status": "miss", "severity": "block",
      "layer": "regulatory", "sub_layer": "regulatory:audience_restriction",
      "evidence": "Missing",
      "evidence_detail": "All UK HCP-targeted promotional materials must display a 'For UK Healthcare Professionals Only' restriction bar. Absent entirely from this asset.",
      "extracted_content": null,
      "canonical_content": "FOR UK HEALTHCARE PROFESSIONALS ONLY",
      "diff": null,
      "pattern_base": {
        "pattern_id": "uk_email_audience_bar",
        "description": "UK HCP audience-restriction bar at the top of the email",
        "coverage": 1.0, "n": 312, "window_months": 24,
        "rule_id": "ABPI-26.1"
      },
      "dependencies_triggered": [{
        "rule_id": "r_audience_bar_when_hcp_only_profile",
        "predicate": "Profile = UK-Branded-Promotional",
        "rationale": "HCP-only profiles must show the audience-restriction bar.",
        "coverage": {
          "predicate_hits_in_corpus": 312,
          "requirement_hits": 312,
          "confidence_label": "high"
        }
      }],
      "annotation_draft": "Audience-restriction bar required for all UK HCP promotional emails (ABPI Code Clause 26.1) is entirely absent. Insert approved UK HCP restriction block before submission.",
      "vvpm_anchor": "anchor_missing_audience_bar",
      "pin": 4
    },
    {
      "id": "abbr_AE", "doc_pos": 9.5,
      "label": "AE — used but not defined",
      "lanes": ["M"],
      "status": "attn", "severity": "warn",
      "layer": "abbreviation", "sub_layer": "abbreviation:AE",
      "evidence": "Acronym used 3× without definition",
      "evidence_detail": "AE appears in body text but no abbreviation block defines it. Suggested expansion (from approved corpus): 'adverse event'.",
      "extracted_content": "AE",
      "canonical_content": "AE — adverse event",
      "diff": null,
      "pattern_base": {
        "pattern_id": "uk_glossary_general_AE",
        "description": "AE — adverse event (general glossary, all disease areas)",
        "coverage": 0.97, "n": 312, "window_months": 24,
        "rule_id": null
      },
      "dependencies_triggered": [{
        "rule_id": "r_abbreviations_defined",
        "predicate": "Body text contains acronym 'AE' (3 occurrences)",
        "rationale": "All used acronyms must be defined in the abbreviation block.",
        "coverage": {
          "predicate_hits_in_corpus": 308,
          "requirement_hits": 298,
          "confidence_label": "high"
        }
      }],
      "annotation_draft": "Acronym 'AE' used in body text without definition. Add to abbreviations block: 'AE — adverse event'.",
      "vvpm_anchor": null,
      "pin": null
    }
  ],
  "email_blocks": [
    { "id":"z1","type":"header","match":"clean","pin":null,"bbox":null,"page":1,"ghost_label":null },
    { "id":"z3","type":"claim","match":"attn","pin":1,"bbox":null,"page":1,"ghost_label":null },
    { "id":"ghost_z8","type":"ghost","match":"miss","pin":4,"bbox":null,"page":1,
      "ghost_label":"Audience-restriction bar expected here" }
    /* … */
  ],
  "library": {
    "sample_size": 287,
    "last_ingest_at": "2026-04-30T22:14:00Z",
    "coverage_warning": null
  },
  "preview": {
    "pdf_url": "/api/preview/tmp:demo-kisqali-uk-001.pdf",
    "page_count": 1
  },
  "generated_at": "2026-05-02T14:33:11Z",
  "cache_key": "v1.0:lib_2026-04-30:asset:tmp:demo-kisqali-uk-001:profile:UK-Branded-Promotional"
}
```

---

## 7. Versioning

`schema_version: "1.0"` is part of every `Asset` payload. Frontend MUST
fail closed on unknown major versions:

```ts
if (asset.schema_version.split('.')[0] !== '1') {
  throw new IncompatibleSchemaError();
}
```

Additive minor changes (new optional fields) bump the minor only and
the frontend ignores unknown fields.

Field-level deprecation: never delete; mark `deprecated: true` on a
sibling field for one minor cycle, then remove in the next major.

---

## 8. Authentication + authorisation

- Atlas session cookie required on all endpoints.
- Per-asset access enforced server-side via the user's `(brand, market)`
  permission set on their Atlas profile.
- Veeva OAuth handled separately; the precheck endpoints don't need it.
  The `POST /api/vvpm/annotate` endpoint requires both Atlas session AND
  a valid Veeva session token (server brokers; refresh on 401).

---

## 9. Caching + freshness

| layer                       | TTL / invalidator                                         |
|-----------------------------|-----------------------------------------------------------|
| `Asset` payload             | invalidate on `(asset_id, library_version)` change        |
| Library snapshot            | rebuilt on every library ingest                           |
| Pattern bank derived view   | rebuilt incrementally per ingest event                    |
| Glossary derived view       | rebuilt incrementally per ingest event                    |
| Preview PDF                 | invalidate on asset upload                                |

`cache_key` in the Asset payload encodes `library_version` + `asset_id`
+ `profile_id` so the frontend can detect a stale cached payload (e.g.
when polling history) without re-fetching.

---

## 10. Out of scope for v1

| feature                                     | reason                                                  |
|---------------------------------------------|---------------------------------------------------------|
| Server-side dismissal persistence           | session-only is enough for v1; needs review workflow before persisting |
| `base_changes` strand on history            | requires library versioning infra (v1.5)                |
| "Why this pattern?" deep drilldown UI       | endpoint ships, but UI link is grey/disabled            |
| Multi-asset campaign view                   | cross-asset consistency checks defer to v2              |
| Cross-language drift detection              | v1 compares within-language only                        |
| Reference-paper retrieval                   | "does the cited paper actually support this claim" — v3 |

---

## 11. Forward references — to pin down

1. **Pipeline_v5 envelope keys** — once v5 stabilises, confirm the
   exact set of `document_regulatory` keys it emits and align with
   `MLR_PRECHECK_SPEC.md` §4 envelope list. Update `Zone.sub_layer`
   namespace if v5 names diverge.
2. **PDF preview URL endpoint** — `/api/preview/{asset_id}.pdf` is
   placeholder; align with whatever Atlas serves today (probably
   `/api/render-page-by-name` or similar).
3. **Veeva anchor format** — `vvpm_anchor` is opaque per spec; confirm
   whether VVPM expects `block_id` / `xpath` / `region_id`. May force a
   per-doc-type variant.
4. **Profile catalog** — the canonical list of `profile.id` values
   (`UK-Branded-Promotional`, `IE-Branded-Promotional`,
   `Event-Promotional`, …) lives in the cascade obligation spec; ensure
   the precheck engine reads the same catalog.
5. **Default-then-override profile selection** — if `selected_by` is
   `default` (no metadata + no user pick), the UI must prompt the user
   before a precheck score is shown. Current design: server returns
   `422 profile_required`; nail down the prompt UX.
6. **PDF coordinate space for `bbox`** — top-left vs bottom-left origin,
   pt vs px. Atlas already standardises on PyMuPDF top-left in pt for
   slides; assume same for emails until v5 decides otherwise.

---

## 12. Implementation seed (server-side directory)

Sketch only — extends `MLR_PRECHECK_SPEC.md` §11.

```
src/mlr/
  precheck/
    api.py                # FastAPI routes for the endpoints above
    asset_builder.py      # turns engine verdicts → Asset payload (zones + email_blocks + scores)
    claim_check.py        # Layer 1 (MLR_PRECHECK_SPEC §3)
    document_check.py     # Layer 2 (§4)
    abbreviation_check.py # Layer 3 (§5)
    cascade_adapter.py    # bridges to existing cascade engine, emits layer="cascade" zones
    library.py            # corpus loader / lookup / cache
    pattern_bank.py       # pattern-bank builder + lookup
    glossary.py           # acronym glossary loader (auto-derived per spec §5)
    dependency_rules.py   # YAML loader + predicate evaluator
    similarity.py         # embed + cosine + fingerprint
    verdict.py            # unified verdict shape + aggregator
  ingest/
    asset_to_library.py   # Atlas-extracted approved payload → library JSON
    library_index.py      # rebuild _index.parquet
mlr/
  dependency_rules.yaml
  profiles/
    UK-Branded-Promotional.yaml
    IE-Branded-Promotional.yaml
    Event-Promotional.yaml
library/                  # the actual approved corpus
```

Routes wire into `src/api/routes.py` under the `/api/precheck/` prefix.
