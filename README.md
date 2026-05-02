# Atlas MLR X-Ray — POC bundle

Design + spec bundle for the **Shaman Atlas MLR Precheck** POC. Backend
contract, rule catalog, profile catalog, classification map, and the
high-fidelity UI handoff in one place. Intended as the working folder
for the v1 build (UK email focus, first 20–30 approved emails as the
library corpus).

## Contents

```
.
├── README.md                          ← you are here
├── MLR_PRECHECK_API.md                ← backend ↔ frontend API contract (v1)
├── CLASSIFICATION_TO_MLR_MAP.md       ← every pipeline classification → MLR purpose
├── dependency_rules.yaml              ← v1 precheck rule catalog (17 rules)
├── profiles/
│   ├── README.md                      ← profile catalog explainer
│   ├── UK-Branded-Promotional.yaml    ← v1 ACTIVE — primary corpus profile
│   ├── Event-Promotional.yaml         ← v1 ACTIVE — Jakavi event-invite case
│   ├── IE-Branded-Promotional.yaml    ← drafted, inactive
│   └── Non-Branded-Disease-Awareness.yaml
├── design brief/
│   └── design_handoff_mlr_xray/       ← high-fidelity UI prototype + screenshots
└── input for design/                  ← original brief + wireframes that fed the design
```

## How the pieces fit

```
                    ┌────────────────────────────────┐
                    │   Vault (approved PDFs)        │
                    └───────────────┬────────────────┘
                                    │
                                    ▼
                    ┌────────────────────────────────┐
                    │   Atlas content extractor      │
                    │   (pipeline_v4 / pipeline_v5)  │
                    └───────────────┬────────────────┘
                                    │ structured payload
                                    ▼
       ┌──────────────────────────────────────────────────────────┐
       │   MLR Precheck engine (server)                           │
       │                                                          │
       │   reads CLASSIFICATION_TO_MLR_MAP.md to interpret roles  │
       │   reads dependency_rules.yaml for predicate rules        │
       │   reads profiles/*.yaml for activation per asset         │
       │                                                          │
       │   produces verdicts → flattens to Asset.zones[]          │
       └───────────────────────────┬──────────────────────────────┘
                                   │ MLR_PRECHECK_API.md
                                   ▼
       ┌──────────────────────────────────────────────────────────┐
       │   X-Ray UI (design brief/design_handoff_mlr_xray)        │
       │   reads Asset, renders zones with status / lane / pin    │
       │   posts annotations to Veeva Vault PromoMats             │
       └──────────────────────────────────────────────────────────┘
```

## v1 scope

- **Markets**: UK (active), IE (drafted)
- **Doc type**: email
- **Corpus size**: first 20–30 approved UK emails feed the pattern banks
- **Profiles active**: `UK-Branded-Promotional`, `Event-Promotional`
- **Persistence**: session-only (no server-side dismissal storage)
- **Auto-insert**: payload populated, UI action grey/disabled (v1.5)
- **Visual content matching**: deferred to v2 (v1 compares visual descriptions only)

## Out of scope for v1

See `MLR_PRECHECK_API.md` §10 for the full list. Headlines: dismissal
persistence, base-changes history strand, "Why this pattern?" UI
drilldown, multi-asset campaign view, cross-language drift detection,
reference-paper retrieval.

## Cross-references to upstream specs

The MLR spec architecture and the cascade obligation engine live in
the extractor service repo:

- `extractor-service/MLR_PRECHECK_SPEC.md` — three-layer precheck architecture
- `extractor-service/OBLIGATION_CASCADE_SPEC.md` — 24 cascade rules across 3 pillars
- `extractor-service/CONTENT_MODEL.md` — module / fragment / block shape
- `extractor-service/CLASSIFICATION_TAXONOMY_FLAT.md` — exhaustive role catalog

## Status

Design + spec drafted; ready for parallel backend + frontend build.
Frontend implementation tracks the design handoff in `design brief/`;
backend implementation tracks `MLR_PRECHECK_API.md` + the YAML catalogs.
