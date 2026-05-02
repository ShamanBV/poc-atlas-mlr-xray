# Handoff: Shaman Atlas MLR X-Ray

**Feature:** MLR Precheck — X-Ray review panel  
**Owner:** Shaman Atlas  
**Design date:** May 2026  
**Fidelity:** High-fidelity — pixel-accurate colours, typography, spacing, and interactions. Recreate in the target codebase using its established patterns and libraries.

---

## About the Design Files

The files in this bundle (`MLR X-Ray.html`, `XRayData.jsx`, `XRayEmail.jsx`, `XRayDrawer.jsx`) are **design references built as HTML/React prototypes**. They are not production code to copy directly. The task is to **recreate these designs in the target codebase** (Shaman's existing React + Ant Design v4 environment) using its established components, routing, and data layer — replacing the inline mock data with real API calls to the Shaman Atlas precheck engine.

Open `MLR X-Ray.html` in a browser to see the full interactive prototype. Use the **Tweaks** panel (toolbar) to switch between the three asset examples and toggle reviewer/author roles.

---

## Product context

Shaman Atlas extracts structured content from pharma marketing emails and slides. The MLR Precheck runs before a human reviewer opens the asset in Veeva Vault PromoMats (VVPM). It answers:

1. **Are claims defensible?** — provenance verdict per claim vs. the approved claims base
2. **Is the document complete?** — required regulatory and legal items present for the market/channel
3. **Is anything stale?** — approved-content drift, retracted references, outdated PI versions

The X-Ray panel is the reviewer's primary interface. It sits as a right-side drawer (520px wide) over the rendered asset preview. Both panes cross-link by zone.

---

## Screens / Views

### 1. Application shell (`MLR X-Ray.html`)

**Layout:** Full viewport. Two vertical regions separated by a 1px `#EFEFEF` border:
- **Left — Email preview** (`flex: 1`): grey `#ECEFF1` background, centred email card max-width 430px, 20px padding, vertically scrollable
- **Right — X-Ray drawer** (width: `520px`, fixed, `flex-shrink: 0`): white background, `box-shadow: -3px 0 12px rgba(0,0,0,0.07)`

**Top header bar:**
- Height: 56px
- Background: `#C1E8D6` (Shaman green-100)
- Logo block: 56×56px, background `#00A66F`, white Shaman SVG icon 32×32px (filter: brightness(0) invert(1))
- Title: "Shaman Atlas MLR X-Ray" — Noto Sans 18px/500, colour `#00A66F`, padding-left 16px
- Right side: MLR precheck status pill — score + verdict label, background = verdict background colour, clicking re-opens drawer if closed

---

### 2. X-Ray drawer — Header (§0)

Height: ~130px, `border-bottom: 1px solid #EFEFEF`, `box-shadow: none`

**Identity line:**  
JetBrains Mono 9px, colour `#9FA3A4`, single line, truncated with ellipsis  
Format: `BRAND · MARKET · lang · CHANNEL · CODE · prepared DATE`

**Score:**  
- Large number: 42–46px, `font-weight: 700`, `font-variant-numeric: tabular-nums`  
- Colour: `scoreColor(score)` — `#639922` ≥90, `#BA7517` ≥75, `#A32D2D` <75  
- `/100` suffix: 12px, `#9FA3A4`
- Verdict chip beneath the number

**History button:** top-right, icon + "History" label, `border: 1px solid #EFEFEF`, border-radius 5px  
**Close button:** top-right X, `color: #9FA3A4`

**Tab bar:** inline pill tabs — All / Medical / Legal / Regulatory  
- Container: `background: rgba(0,0,0,0.04)`, `border-radius: 8px`, `padding: 3px`
- Active tab: white background, `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`, `border-radius: 6px`
- Each tab: label + count. Lane dot (7×7px circle) for Medical/Legal/Regulatory tabs
- Lane colours (text only, NOT status colours — see Design Tokens):
  - Medical: `#3C3489`
  - Legal: `#712B13`  
  - Regulatory: `#085041`

---

### 3. X-Ray drawer — Check summary bar

Height: ~36px, `border-bottom: 1px solid #EFEFEF`, white background  
Shows: `{total} {lane} checks · {N} clean · {N} attention · {N} missing · {N} dismissed`  
Right side: `{lane label} · {score}` in score colour  
**Important:** Dismissed zones are excluded from counts.

---

### 4. X-Ray drawer — Zone spine (scrollable body)

Each zone is one row. Rows are ordered by `docPos` (document top-to-bottom). Zones with no lane relevance disappear from function tabs entirely — they are not greyed out, just absent.

#### Zone row — Clean state
- Padding: `8px 14px`
- Left border: `3px solid transparent`
- No chevron (not expandable)
- Layout: `StatusDot · ZoneLabel · [EvidenceTag] · LanePills`
- Status dot: 9×9px circle, colour `#639922`
- Zone label: 13px/400, `#454747`
- Evidence tag: 10px, `#6F7E7F`, background `#FBFBFB`, border `1px solid #EFEFEF`, border-radius 3px
  - Three types: "Approved verbatim", "Pattern match (n=N, M months)", "Rule satisfied (RULE-ID)"
- Lane pills: 10px/600, per-lane background + text colour, border-radius 3px

#### Zone row — Attention state (amber)
- Status dot colour: `#BA7517`
- Zone label: 13px/**600**, colour `#BA7517`
- Evidence sub-line: 11px/500, `#BA7517` (e.g. "Partial match · 0.84")
- Cursor: pointer; hover background: `${attnBg}66` = `#FEF3E208`
- Has chevron: 15px, `#9FA3A4`, rotates 180° when open
- Left border on selected: `3px solid #BA7517`

#### Zone row — Missing state (red)
- Status dot colour: `#A32D2D`
- Zone label: 13px/**600**, colour `#A32D2D`
- Evidence sub-line: 11px/500, `#A32D2D` (e.g. "Missing")
- Same expand/hover behaviour as attention
- ≤2 missing zones auto-expand when their tab is selected

#### Zone row — Dismissed state
- Single muted line: status dot replaced by grey, label 12px/italic/`#879091`, "Dismissed" label + "undo" link
- Opacity: 0.6, background `#FBFBFB`

#### Zone row — Annotated state
- Status dot turns green `#639922`
- "Annotated in VVPM ✓" green chip appears next to label
- Evidence sub-line has `text-decoration: line-through`, colour `#879091`
- Expanded: shows "Annotation created in VVPM · undo" instead of composer

---

### 5. Zone expanded detail

Padding: `10px 14px 14px 32px` (left indent aligns content past dot)  
Background: `${statusBg}55` (very faint status tint)  
`border-top: 1px solid {col}22`

Sections in order:
1. **Extracted content** — label + content box (12px, white background, `border: 1px solid #EFEFEF`, border-radius 4px, padding 6px 10px). If missing: italic red, dashed border.
2. **Comparative evidence** — label + text with `border-left: 2px solid #D7D7D7`, padding-left 10px
3. **Pattern base** (if present) — 11px, `#6F7E7F`, white box with analytics icon. Shows corpus size + time window inline: `"94% of n=287, last 18 months"`
4. **Word diff** (if present) — JetBrains Mono 11.5px, line-height 1.9. Deletions: `background #FFEBEE, color #A32D2D, text-decoration line-through`. Additions: `background #E8F5E9, color #2E7D32`.
5. **Annotation composer** — see §6

---

### 6. Annotation composer

Appears at bottom of expanded zone (attention/missing only, not yet annotated).  
`border-top: 1px solid #EFEFEF`, padding-top 12px

**Label:** "Add annotation in Veeva" — 10px/700, `#879091`, uppercase, letter-spacing 0.5px

**Textarea:**  
- Pre-filled with `annotationDraft` from zone data  
- Font: Noto Sans 12px, colour `#454747`  
- Border: `1px solid #D7D7D7`, border-radius 5px, padding 8px 10px  
- Focus: border `#00A66F`  
- min-height: 72px, resize: vertical  

**Buttons row:**
- **Create annotation** (primary): `background: #323232`, white text, 12px/500, border-radius 5px, padding 6px 14px, `add_comment` icon. Disabled (grey) when empty. Loading state: spinner icon + "Creating…" for ~900ms simulating API call. On success → zone state becomes `'annotated'`.
- **Dismiss** (text): 12px, `#879091`, no border, no background. On click → zone state becomes `'dismissed'`, row collapses.
- **Why this pattern?** (right-aligned link): 11px, `#879091`, `help_outline` icon

---

### 7. Email preview — Zone overlays

Each content block in the email is wrapped in a `BlockWrapper` that:
- Sets `data-zone-id` attribute for cross-linking
- On hover: shows a `2px solid {laneOrStatusColor}` outline and reveals a lane chip overlay (top-right, absolute)
- On click (non-clean zones): selects the zone, highlights corresponding X-ray row

**Lane chip overlay:**
- Position: absolute, top 4px, right 6px
- Opacity: 0 → 1 on hover/selected, transition 0.15s
- Status dot (6×6px) + lane pill(s)
- Lane pills: 9px/700, per-lane background + text, border-radius 3px

**Ghost blocks** (missing zones):
- `border: 1.5px dashed {laneColor}44`  
- Background: `{laneColor}04`  
- On hover: border opacity increases, background `{laneColor}08`  
- Label: italic, colour `{laneColor}CC`, `add_box` icon  
- Clicking a ghost block opens the corresponding X-ray zone row

---

### 8. History panel

Slides over the X-ray body (position: absolute, full overlay within drawer).  
Three strands displayed as labelled sections:
1. **Asset edits** — date + actor + action
2. **Precheck runs** — date + score + delta + summary  
3. **Base & rule changes** — date + item + version + note

Each item: 12px, `#545A5B`, `background: #FBFBFB`, border-radius 4px, padding 6px 10px. Date in JetBrains Mono 10px `#879091`.

---

### 9. Footer actions

Height: 40px, `border-top: 1px solid #EFEFEF`, white background, padding 9px 14px

**Reviewer view:**
- **Approve asset** (flex: 1): primary when no missing zones (`background: #00A66F, color: white`); disabled when missing zones exist (`background: #EFEFEF, color: #D7D7D7, cursor: not-allowed`)
- **Request changes**: secondary, `border: 1px solid #D7D7D7`, `color: #323232`
- **Export**: icon + label, `color: #636E6F`

**Author view:**
- **Submit for MLR review** (flex: 1): same gating logic
- **Export**: same

Both: "Read-only · v1" caption in 10px `#9FA3A4` at far right.

---

## Interactions & Behaviour

| Trigger | Action |
|---------|--------|
| Hover email block | Highlight matching X-ray row (background tint) + reveal lane chip overlay |
| Click email block (non-clean) | Select zone → left border on X-ray row, expand row, scroll X-ray to row |
| Hover X-ray row | Highlight row + scroll email to block |
| Click X-ray row (non-clean) | Toggle expand; select zone; scroll email to block |
| Tab switch (All/M/L/R) | Filter spine to that lane's zones; update summary bar; auto-expand ≤2 missing |
| Click mini-bar pillar | Switch to that pillar's tab |
| "Create annotation" | 900ms loading state → zone becomes `annotated` → composer collapses |
| "Dismiss" | Zone collapses to muted dismissed row; excluded from counts |
| "undo" | Restores zone to default state |
| "History" button | History panel slides over drawer body |
| Switch asset (tweaks) | Reset all state: tab → All, openZone → null, zoneActions → {} |
| Close drawer | Drawer unmounts; re-open tab appears at right edge |

---

## Data model

### Zone object
```typescript
interface Zone {
  id: string;                    // unique, matches data-zone-id in email
  docPos: number;                // 1-indexed document position
  label: string;                 // human-readable zone name
  lanes: ('M' | 'L' | 'R')[];  // which function tabs this zone appears on
  status: 'clean' | 'attn' | 'miss';
  evidence: string;              // short evidence label shown on collapsed row
  evidenceDetail: string;        // full comparative evidence (expanded)
  extractedContent: string | null;
  patternBase?: string;          // corpus confidence note with n= and time window
  diff?: DiffSegment[];          // word-level diff against canonical
  annotationDraft?: string;      // pre-filled annotation text
  vvpmAnchor?: string;           // anchor ID for VVPM API call
}

interface DiffSegment {
  t: string;   // text
  s: 'k' | 'd' | 'a';  // keep | delete | add
}
```

### Zone action state (session-only, not persisted)
```typescript
type ZoneActionState = Record<string, 'annotated' | 'dismissed'>;
```

### Asset object
```typescript
interface Asset {
  meta: { brand, market, channel, code, prepared, age };
  identity: string;  // single-line display string
  scores: { overall, medical, legal, regulatory };  // 0–100
  zones: Zone[];
  history: {
    assetEdits: { date, actor, action }[];
    precheckRuns: { date, score, delta, summary }[];
    baseChanges: { date, item, version, note }[];
  };
}
```

---

## API integration points

| Action | Endpoint (TBD) |
|--------|----------------|
| Load precheck result | `GET /api/precheck/{assetId}` → Asset object |
| Create VVPM annotation | `POST /api/vvpm/annotate` `{ assetId, zoneId, anchor, text }` |
| Dismiss finding (session) | Client-side only in v1 — no persistence |
| Load history | `GET /api/precheck/{assetId}/history` |

The "Why this pattern?" link should deep-link to the corpus drilldown for the zone's pattern base (endpoint TBD — out of scope v1).

---

## Design Tokens

### Status colours (severity — green/amber/red only)
| Token | Hex | Use |
|-------|-----|-----|
| `clean` | `#639922` | Confirmed, approved, satisfied |
| `cleanBg` | `#F1F7E8` | Clean row backgrounds |
| `attn` | `#BA7517` | Drift, partial match, attention |
| `attnBg` | `#FEF3E2` | Attention row backgrounds |
| `miss` | `#A32D2D` | Missing, new content, blockers |
| `missBg` | `#FAEAEA` | Missing row backgrounds |

### Lane colours (taxonomy — deliberately different from status)
| Lane | Background | Text |
|------|-----------|------|
| Medical | `#EEEDFE` | `#3C3489` |
| Legal | `#FAECE7` | `#712B13` |
| Regulatory | `#E1F5EE` | `#085041` |

> **Critical:** Lane colours and status colours must never be conflated. Lane pills identify which regulatory function owns a zone. Status dots indicate whether a zone passed, needs attention, or is missing.

### Shaman brand colours
| Token | Hex | Use |
|-------|-----|-----|
| `green600` | `#00A66F` | Primary actions, header title, approve button |
| `green100` | `#C1E8D6` | Header bar background |
| `grey900` | `#323232` | Primary text |
| `grey500` | `#6F7E7F` | Secondary text |
| `grey50` | `#EFEFEF` | Borders, dividers |
| `grey25` | `#FBFBFB` | Alternate backgrounds |

### Typography
| Element | Font | Size | Weight | Colour |
|---------|------|------|--------|--------|
| Header title | Noto Sans | 18px | 500 | `#00A66F` |
| Score number | Noto Sans | 42–46px | 700 | score colour |
| Zone label (clean) | Noto Sans | 13px | 400 | `#454747` |
| Zone label (attn/miss) | Noto Sans | 13px | 600 | status colour |
| Evidence tag | Noto Sans | 10px | 400 | `#6F7E7F` |
| Body / detail text | Noto Sans | 12px | 400 | `#545A5B` |
| Code / diff / IDs | JetBrains Mono | 10–12px | 400 | varies |
| Asset identity line | JetBrains Mono | 9px | 400 | `#9FA3A4` |

### Spacing
8px grid. Key values: 4, 8, 10, 12, 14, 16, 20, 24px.

### Border radius
- Zone rows: 0 (full-bleed list)
- Chips/pills: 3px
- Buttons: 5–6px
- Cards/panels: 8px
- Tab bar: 8px (container), 6px (active pill)

### Shadows
- Drawer: `box-shadow: -3px 0 12px rgba(0,0,0,0.07)`
- History panel: none (full overlay)
- Tab active pill: `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`

---

## Assets & Icons

- **Shaman logo:** `assets/shaman-icon.svg` — render white using `filter: brightness(0) invert(1)` on `#00A66F` background
- **Icons:** Google Material Icons Filled (loaded via `fonts.googleapis.com/icon?family=Material+Icons`)
  - Key icons used: `expand_more`, `check`, `check_circle`, `add_comment`, `help_outline`, `autorenew`, `history`, `close`, `analytics`, `add_box`, `open_in_new`, `edit_note`, `database`

---

## Screenshots

Reference screenshots are in `screenshots/`:
- `01-kisqali-all-tab.png` — Full layout, Kisqali asset, All tab
- `02-legal-tab.png` — Legal tab selected, filtered checklist
- `03-zone-expanded.png` — Zone row expanded with annotation composer

---

## Files in this package

| File | Purpose |
|------|---------|
| `MLR X-Ray.html` | Full interactive prototype — open in browser |
| `XRayData.jsx` | All mock data + colour tokens + helper functions |
| `XRayEmail.jsx` | Left-pane email renderer with zone overlays + ghost blocks |
| `XRayDrawer.jsx` | Right-pane X-ray spine, tabs, zone rows, composer, history |
| `assets/shaman-icon.svg` | Shaman logo SVG |
| `screenshots/` | Reference screenshots of key states |

---

## Out of scope for v1

- Editing asset content from within the X-Ray
- "Why this pattern?" corpus drilldown
- Dismissal persistence (server-side) — session-only in v1
- Author view (same engine, different actions — keep logic separable)
- Cross-asset consistency ("this claim rendered differently in 3 other assets")
