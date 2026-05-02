# MLR Precheck — design brief

**Audience:** Claude Design
**Owner:** Maurice / Shaman Atlas
**Status:** v1 — based on conversation 2026-05-02
**Scope:** MLR reviewer view (author view is out of scope but flagged)

---

## Context

Shaman Atlas extracts structured content from emails and slide decks: medical claims with their evidence (text, tables, visuals, study design), non-medical content (salutation, signature, navigation), and regulatory/legal items per market. This structured data feeds an **MLR precheck** — automated triage that runs before a human reviewer opens the asset in VVPM.

The precheck answers three questions:

1. **Are the claims defensible?** — provenance verdict per claim (Core / Approved / Partial / New) plus substantiation check.
2. **Is the document complete for its market and channel?** — required regulatory and legal items present.
3. **Is anything stale?** — approved-content drift, retracted references, outdated PI versions.

All knowledge is comparative. Two evidence types stacked together:

- **Claim-level** — semantic match against per-brand/per-market approved claims base (MLR Compare).
- **Pattern-level** — "94% of approved DE HCP emails include this slot." Learned regularity from the approved corpus, not a hand-written rule.

MLR does not edit content. They annotate. The end state of every actionable finding is a placemark-anchored annotation pushed to VVPM via the existing AutoAnnotate pipeline.

## Current state

The existing layout is preview-left / findings-right. It works as a findings list but doesn't yet express two things core to the product:

1. The document has a *structure* MLR is checking against (the X-ray)
2. Findings are a comparative claim — "we expected X here because we see X in approved content" — not a rule violation

## What to keep

- Two-panel layout (preview left, review pane right)
- Score header with Medical / Legal / Regulatory rollups and per-lane filter tabs
- Approve / Request changes / Export footer
- Cross-link on hover between preview blocks and finding rows

## What to change

### 1. Replace the flat findings list with an X-ray spine

The right pane reads top-down as the email's structural skeleton: Header → Hero claim → Supporting claim → Secondary claim → AE reporting → PI link → Audience restriction → Footer. Each zone is one row showing status and a lane pill (M/L/R).

This replaces the current "1 blocker · 3 to review" card stack — those become the expanded issue zones inside the X-ray.

### 2. Function tabs are checklists, not filtered findings

The All / Medical / Legal / Regulatory tabs change the X-ray from a filter operation into *that function's complete checklist*. Each function tab shows every zone that has that lane attached, in three visible states:

- **Clean (green dot)** — present and confirmed. One-line row, no chevron, no expand. Right-side tag carries the evidence type:
  - "Approved verbatim" — exact match to approved component
  - "Pattern match (94% of n=287)" — confirmed by corpus pattern
  - "Rule satisfied (ABPI 26.1)" — explicit rule met
- **Attention (amber dot)** — drift, partial match, stale link. One-line collapsed by default, expands on click.
- **Missing (red dot)** — expected by pattern or rule, not found. One-line, but pre-expanded if there are ≤2 missings on the tab.

Tab counts are *workload*, not *problem count*. "Legal · 6" means six legal-relevant zones in total. A summary row beneath the tabs breaks it down: "6 legal checks · 4 clean · 1 attention · 1 missing."

Zones with no lane relevance disappear from function tabs entirely. A subject-line zone is not on the Legal tab — not greyed out, not present. The function tab is that function's surface area.

A single zone can carry multiple lanes (footer is Legal *and* Regulatory in DE). It appears on both tabs.

### 3. Three kinds of green are not the same

A zone confirmed by exact match to approved content is hard evidence. A zone confirmed by corpus pattern is soft evidence. A zone confirmed by an explicit rule is the strongest. The right-side tag on each clean row makes this visible without needing a click. Pattern-match clean rows expose sample size inline ("n=287, 18 months") so MLR can judge the confidence themselves.

Per-lane score in the summary row derives from the checklist directly: clean = 1, attention = 0.5, missing = 0, weighted by severity. This makes the score legible — Legal can see exactly why their lane is at 78.

### 4. Expand-in-place, not a separate detail panel

Selecting an issue zone expands it inline with:

- The extracted content (claim text, or "missing" for absent zones)
- **The comparative evidence** — for claims, closest approved match + similarity score + diff. For pattern-based findings, "94% of 287 approved DE HCP emails include this." This is the most important addition. It's the *reason* the finding exists.
- A "Why this pattern?" link to the corpus drilldown (sample size, time window, which approved docs)
- An **editable annotation composer** — pre-filled remark text the reviewer edits before pushing. This is the difference between AI-generated and MLR-authored annotations.
- "Annotate in VVPM" action (uses placemark coords + `anchor_persistent_id` from Atlas extraction)

Do not split this into a third panel. If the detail is rich enough to need width, the X-ray column expands; the preview width doesn't shrink.

### 5. Missing zones in the preview as ghost placeholders

The current preview can only render what's there. Missing AE reporting and missing footer are invisible in the rendition. Add dashed-outline ghost blocks sized to the expected zone, positioned where the missing content would have lived. This is what makes the preview honest — the gap shows up *in the rendition*, not only in the X-ray.

### 6. Pin numbers shared between preview and X-ray

In-content findings get numbered pins on the preview (small colored circles inline with the text). The same number appears on the corresponding X-ray row. Pins are the shared ID across the two panes and carry through to the VVPM annotation.

### 7. Pattern confidence must be visible everywhere

Every pattern-based finding — clean, attention, or missing — exposes sample size and time window inline. "94% of n=287, last 18 months." Refuse to surface a pattern when the corpus is too thin. This is what earns MLR's trust. Without it, pattern findings read as opaque AI claims.

## Audit trail → History

Rename and rescope. The current "Audit trail" block is duplicating findings sliced by category, which is redundant once the X-ray is the checklist. Replace it with a version-history panel that has three distinct strands:

- **Asset edits** — author actions on the document (claim text changed, footnote removed, visual swapped)
- **Precheck runs** — each run with delta vs. previous ("+2 clean, −1 blocker, 1 new attention"). This is verdict drift, which can change without the document changing if the approved base grew.
- **Base & rule changes** — when the corpus or rules this run depended on were updated. Claims base v.2026-04-30, DE regulatory rules v.12, pattern corpus snapshot. This is the defensibility trail — "I approved on these grounds, against this base, on this date."

The three strands answer different reader questions: what changed in the asset, what changed in the verdict, what changed in the ground truth.

History is not a permanent footer block. Move to a secondary panel or drawer that swaps in over the X-ray when opened. MLR doesn't need it visible while reviewing — they open it when they want to compare versions or check what's new since they last looked.

## What to drop

- The separate "1 blocker · 3 to review" finding cards — they become expanded X-ray rows
- The "Audit trail" footer in its current form
- Any treatment that puts the finding list ahead of the structural view; the X-ray *is* the finding list, organized by where the issue lives in the document

## Author view (out of scope, but flagging)

Same X-ray engine drives an author-facing view where the action is "fix" or "request approval for new claim" instead of "annotate." Not for v1, but don't make design choices that break it later. Keep the X-ray and finding composer logic separable from the VVPM annotation action.

---

## Wireframes

Three reference sketches from the working session. All built in HTML/CSS, all behave as prototypes — clickable rows, working sendPrompt actions.

### Wireframe 1 — Two-pane layout: preview + X-ray with pin cross-linking

Establishes the overall layout. Preview left with numbered pins inline with content and ghost placeholders for missing zones. X-ray right as structural spine with status dots and lane pills. Selected zone expands inline (not a third panel).

[`wireframe_1_preview_xray.html`]

### Wireframe 2 — Function tab (Legal) showing all three states

Demonstrates the function-tab-as-checklist principle. Six legal-relevant zones, all visible: four clean (with three different evidence-type tags), one attention, one missing pre-expanded with comparative evidence and editable annotation composer.

[`wireframe_2_legal_tab.html`]

### Wireframe 3 — All-tab X-ray with full document spine

Reference for the All view: every zone across every lane, with multi-lane zones showing both pills. Useful for understanding how Medical / Legal / Regulatory tabs derive from this.

[`wireframe_3_all_tab.html`]

---

## Visual references

Color tokens used in the wireframes (Anthropic ramps):

- Clean: `#639922` (green 600)
- Attention: `#BA7517` (amber 600)
- Missing / Blocker: `#A32D2D` (red 600)
- Medical lane: `#EEEDFE` bg / `#3C3489` text (purple 50/800)
- Legal lane: `#FAECE7` bg / `#712B13` text (coral 50/800)
- Regulatory lane: `#E1F5EE` bg / `#085041` text (teal 50/800)

Lane colors are deliberately not the same as severity colors. Lane pills are taxonomy; status dots are state. Don't conflate.
