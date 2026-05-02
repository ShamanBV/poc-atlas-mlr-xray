# MLR X-Ray — frontend POC

Self-contained HTML + JSX prototype that consumes the live precheck
backend. Renders the X-Ray drawer and email preview against the
`/api/precheck/{asset_id}` endpoint.

## Stack note

The design handoff (`../design brief/design_handoff_mlr_xray/`) ships
as React+Babel-standalone running entirely in-browser — no build step,
no Node toolchain. This frontend keeps that property: open the HTML in
a browser and it works.

For the production rebuild, the design README is explicit that the
target is React + Ant Design v4. This POC is the bridge — proves the
backend contract end-to-end against the design code; the production
version recreates the visual design in Antd v4.

## Quickstart

Two terminals:

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
uvicorn mlr.precheck.api:app --port 8088

# Terminal 2 — frontend (any static server pointing at frontend/)
cd frontend
python3 -m http.server 8089
```

Then open:

```
http://localhost:8089/
```

### Query-string overrides

- `?api=http://other-host:9000` — point at a different backend URL
- `?asset=tmp:demo-kisqali-uk-001` — load a different asset (default is
  the KISQALI fixture)

## Layout

```
frontend/
├── index.html        ← the live-backend variant of the prototype shell
├── adapter.js        ← snake_case (backend) → camelCase (prototype) mapping
├── XRayData.jsx      ← copied unchanged from design handoff (provides C, statusColor, …)
├── XRayDrawer.jsx    ← copied unchanged from design handoff (right-side X-Ray panel)
├── XRayEmail.jsx     ← copied unchanged from design handoff (left-side email preview)
└── assets/           ← design assets (logo, etc.)
```

The three JSX files are **unmodified from the design handoff** — the
adapter handles all field-name reshaping. When the handoff updates,
copy the new JSX files in and the wiring still works.

## How it runs

1. `index.html` boots, fetches `GET {BACKEND}/api/precheck/{asset_id}`.
2. `adapter.js` reshapes the payload: `doc_pos` → `docPos`, `pattern_base`
   object → human-readable sentence, `ghost_label` → `ghostLabel`, etc.
3. The adapted asset is passed to `EmailPreview` and `Drawer` as a prop.
4. The black banner at the top reports backend status + zone count.

## What works

- All three precheck layers' zones render in the drawer (claim drift,
  regulatory `miss`es, abbreviation findings).
- Diff segments render in the expanded zone view.
- Status filtering by lane (All / Medical / Legal / Regulatory) reads
  from each zone's `lanes` array.
- Score colour, verdict label, and identity line all driven by live data.

## What's missing in this slice

- **Asset switcher** — backend only has one fixture (KISQALI).
  Re-enable the sidebar once we add LEQVIO / JAKAVI fixtures.
- **History panel** — `/api/precheck/{asset_id}/history` not yet
  implemented; UI shows empty strands.
- **VVPM annotation post** — `/api/vvpm/annotate` not yet implemented;
  the drawer's Approve/Annotate flow is local-only.
- **Bbox preview overlay** — backend doesn't yet emit bbox-bound zones
  (depends on pipeline_v5 emails); the email pane uses the prototype's
  hardcoded KISQALI HTML rather than rendering from `email_blocks`.
