# MLR Precheck — backend POC

Server-side slice for the Atlas MLR X-Ray POC. Implements the API surface
in `../MLR_PRECHECK_API.md` against an in-memory fixture store.

## Status

**v0.2 — Layer 2 (regulatory dependency rules) + Layer 3 (abbreviation precheck) end-to-end.**

What ships in this slice:

- `GET /api/precheck/{asset_id}` returns a full `Asset` payload built from
  fixture-stored extracted assets.
- Layer 2 (`document_check.py` + `dependency_rules.py`) loads
  `../dependency_rules.yaml` at boot, runs each rule's predicate +
  requires against the extracted asset, emits one `Zone` per
  fired-but-unmet rule with `dependencies_triggered` carrying the rule
  id, prose predicate, and corpus coverage. Pillar attribution
  (medical / legal / regulatory) routes via `sub_layer` prefix.
- Layer 3 (`abbreviation_check.py`) walks the asset's blocks, extracts
  acronyms, looks each up in the canonical glossary, and emits one
  `Zone` per acronym used in body text but not defined in the asset's
  abbreviation block.
- Verdict aggregator + asset builder produce the `Asset` envelope per
  `MLR_PRECHECK_API.md` §2 (zones, scores, identity, library, preview).

What's stubbed in this slice (filled in by later layers):

- Layer 1 (claim precheck) — adds `layer:claim` zones via embedding +
  cosine match against approved corpus.
- Pattern-bank match (`envelope.matches_pattern`) — needs library
  ingest infra; predicate currently treats it as always-satisfied.
- Date-of-preparation freshness window — currently checks regex
  presence only; freshness comparison vs `today` lands with the date
  normaliser.
- Cascade adapter — bridges to the existing cascade engine, adds
  `layer:cascade` zones.

## Quickstart

```bash
cd backend
pip install -e ".[dev]"
uvicorn mlr.precheck.api:app --reload --port 8088

# in another shell
curl -s localhost:8088/api/precheck/tmp:demo-kisqali-uk-001 | python -m json.tool
```

## Tests

```bash
cd backend
pip install -e ".[dev]"
pytest -v
```

## Layout

```
backend/
├── pyproject.toml
├── README.md            ← you are here
├── src/mlr/
│   ├── precheck/
│   │   ├── schema.py             ← Pydantic models (Asset/Zone/EmailBlock/...)
│   │   ├── glossary.py           ← canonical acronym → expansion lookup
│   │   ├── abbreviation_check.py ← Layer 3 logic
│   │   ├── dependency_rules.py   ← YAML loader + predicate evaluator
│   │   ├── document_check.py     ← Layer 2 orchestrator
│   │   ├── verdict.py            ← internal verdict shape + aggregator
│   │   ├── asset_builder.py      ← verdicts → Asset envelope
│   │   └── api.py                ← FastAPI routes
│   └── fixtures/
│       └── assets.py             ← in-memory store of extracted assets
└── tests/
    ├── test_glossary.py
    ├── test_abbreviation_check.py
    ├── test_dependency_rules.py
    ├── test_document_check.py
    └── test_api.py
```
