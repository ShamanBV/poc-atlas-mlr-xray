"""
Layer 0 — structural extraction inventory.

Emits one `clean / info` Verdict per recognised structural block in
the asset (header, audience restriction, promotional notice, AE
reporting, approval info, unsubscribe, contact, CTA, references,
footnotes, regulatory menu, safety reminder, …). Complements:

  - Layer 1 (claim_check)        — claim drift / no-canonical
  - Layer 2 (document_check)     — required-but-missing rules
  - Layer 3 (abbreviation_check) — undefined acronyms
  - Layer 0 (this)               — present-and-extracted inventory

Without Layer 0 the X-Ray spine only listed *failures* — the user
correctly noted that real extractions like Cosentyx UK have lots of
clean structural items (PROMOTIONAL_NOTICE, PI, AE reporting, etc.)
that should appear on the spine too. This layer surfaces them.

For the POC the status is naively `clean` and severity `info` — we
state "block of role X was extracted" without verifying against an
approved canonical (that's per-element library work, future). The
evidence reads "Extracted" rather than "Approved verbatim" so it's
honest about what we're claiming.

De-dupe: one zone per role per asset. If a role appears N>1 times
(e.g. PROMOTIONAL_NOTICE twice in Cosentyx UK), the first occurrence
wins for bbox/page/text. The zone label adds a count suffix when N>1
("Promotional notice (2)").

Layer 2 dedupe: when a role corresponds to a Layer 2 rule that fires
miss (e.g. AUDIENCE_RESTRICTION missing → r_audience_bar fires),
Layer 2 emits the miss zone and Layer 0 doesn't emit anything for that
role (because the block isn't present in the asset). No overlap.
"""

from __future__ import annotations

from .schema import ExtractedAsset, ExtractedBlock, ExtractedVisual
from .verdict import Verdict


# Role → (label, lane). Lanes match the cascade convention:
#   M = Medical  (claims, scientific, glossary)
#   L = Legal    (privacy, contact, MAH, unsubscribe)
#   R = Regulatory (audience restriction, PI, AE, approval code)
_ROLE_LABEL_LANE: dict[str, tuple[str, str]] = {
    "HEADER":                  ("Brand header",           "M"),
    "AUDIENCE_RESTRICTION":    ("Audience restriction",   "R"),
    "PROMOTIONAL_NOTICE":      ("Promotional notice",     "L"),
    "PRESCRIBING_INFORMATION": ("Prescribing information","R"),
    "PHARMACOVIGILANCE":       ("AE reporting box",       "R"),
    "APPROVAL_INFO":           ("Approval info",          "R"),
    "UNSUBSCRIBE":             ("Unsubscribe link",       "L"),
    "CONTACT_INFO":            ("Footer / MAH",           "L"),
    "CTA":                     ("Call to action",         "M"),
    "REFERENCE":               ("References",             "M"),
    "FOOTNOTE":                ("Footnote",               "M"),
    "REGULATORY_MENU":         ("Regulatory menu",        "R"),
    "SAFETY":                  ("Safety reminder",        "M"),
    "INDICATION":              ("Indication",             "R"),
    "DISCLAIMERS":             ("Disclaimers",            "L"),
}

# Selected BODY subtypes that earn their own structural zone (otherwise
# raw BODY blocks aren't surfaced — they'd be noisy paragraphs).
_BODY_SUBTYPE_LABEL_LANE: dict[str, tuple[str, str]] = {
    "SALUTATION":      ("Salutation",          "M"),
    "LEARN_MORE":      ("Learn-more link",     "M"),
    "ADVERSE_EVENTS":  ("AE reporting copy",   "R"),
    "PRIVACY":         ("Privacy notice",      "L"),
}

# Roles handled by other layers — never emit Layer 0 zones for them.
_HANDLED_BY_OTHER_LAYERS = frozenset({
    "CLAIM",         # Layer 1 (claim_check)
    "ABBREVIATION",  # Layer 3 (abbreviation_check) + supportive_resources
    "NAVIGATION",    # not part of MLR scope
})


# Visual `kind` → (label, lane). Visuals are emitted in addition to
# block-based structural zones. Lane is Medical by default — visuals
# usually support claims; brand/legal-marked assets (logos, IP marks)
# go to Legal.
_VISUAL_KIND_LABEL_LANE: dict[str, tuple[str, str]] = {
    "banner":     ("Brand banner",     "L"),
    "logo":       ("Brand logo",       "L"),
    "brand-mark": ("Brand mark",       "L"),
    "photo":      ("Photography",      "M"),
    "hero":       ("Hero image",       "M"),
    "patient":    ("Patient image",    "M"),
    "chart":      ("Chart / data viz", "M"),
    "diagram":    ("Diagram",          "M"),
    "icon":       ("Icons",            "M"),
    "infographic":("Infographic",      "M"),
}
_VISUAL_FALLBACK_LABEL_LANE: tuple[str, str] = ("Visual", "M")


# Doc-pos hint puts structural zones interleaved with claims — earlier
# than Layer 2 (200+) and Layer 3 (900+). Header / preamble pieces sit
# at the top, footer-ish pieces near the bottom.
_DOC_POS_BY_ROLE: dict[str, float] = {
    "HEADER":                  1.0,
    "AUDIENCE_RESTRICTION":    2.0,
    "PROMOTIONAL_NOTICE":      3.0,
    "INDICATION":              4.0,
    "SALUTATION":              5.0,  # via BODY subtype
    "LEARN_MORE":             20.0,
    "CTA":                    30.0,
    "SAFETY":                 35.0,
    "FOOTNOTE":               40.0,
    "REFERENCE":              45.0,
    "ADVERSE_EVENTS":         50.0,
    "PHARMACOVIGILANCE":      55.0,
    "PRESCRIBING_INFORMATION":60.0,
    "REGULATORY_MENU":        65.0,
    "APPROVAL_INFO":          70.0,
    "DISCLAIMERS":            75.0,
    "UNSUBSCRIBE":            80.0,
    "CONTACT_INFO":           90.0,
    "PRIVACY":                85.0,  # via BODY subtype
}

# Visual kind → doc-pos hint. Brand-related visuals at the top,
# data/icon visuals interleaved with claims.
_DOC_POS_BY_VISUAL_KIND: dict[str, float] = {
    "logo":       1.5,
    "brand-mark": 1.6,
    "banner":     1.7,
    "hero":       2.5,
    "photo":     10.0,
    "patient":   10.5,
    "chart":     15.0,
    "diagram":   15.5,
    "infographic":16.0,
    "icon":      18.0,
}


def _label_for_block(blk: ExtractedBlock) -> tuple[str, str] | None:
    """Returns (label, lane) for the block, or None if it shouldn't be surfaced."""
    if blk.role in _HANDLED_BY_OTHER_LAYERS:
        return None
    if blk.role == "BODY":
        # Only specific BODY subtypes get a structural zone.
        return _BODY_SUBTYPE_LABEL_LANE.get(blk.subtype) if blk.subtype else None
    return _ROLE_LABEL_LANE.get(blk.role)


def _doc_pos(role: str, subtype: str | None, occurrence_index: int) -> float:
    """Position hint within the spine. Subtype overrides role for BODY."""
    key = subtype if (role == "BODY" and subtype) else role
    base = _DOC_POS_BY_ROLE.get(key, 50.0)
    # Tiny offset per occurrence so multi-block roles stay grouped + ordered.
    return base + occurrence_index * 0.01


def run(asset: ExtractedAsset) -> list[Verdict]:
    """
    Walk extracted blocks AND visuals, emit one verdict per recognised
    structural role / visual kind.
    """
    # ── blocks pass ──────────────────────────────────────────────
    seen: dict[str, list[ExtractedBlock]] = {}
    for blk in asset.blocks:
        ll = _label_for_block(blk)
        if ll is None:
            continue
        key = blk.subtype if (blk.role == "BODY" and blk.subtype) else blk.role
        seen.setdefault(key, []).append(blk)

    verdicts: list[Verdict] = []
    for idx, (key, blocks) in enumerate(seen.items()):
        first = blocks[0]
        ll = _label_for_block(first)
        assert ll is not None
        label, lane = ll
        count = len(blocks)
        label_with_count = label if count == 1 else f"{label} ({count})"
        text_excerpt = (first.text or "").strip()
        if len(text_excerpt) > 200:
            text_excerpt = text_excerpt[:199].rstrip() + "…"
        verdicts.append(
            Verdict(
                layer="cascade",
                sub_layer=f"structural:{key.lower()}",
                label=label_with_count,
                status="clean",
                severity="info",
                lanes=[lane],  # type: ignore[list-item]
                evidence="Extracted",
                evidence_detail=(
                    f"Block role {key} present in this asset "
                    f"({count} occurrence{'s' if count != 1 else ''}). "
                    "Not yet verified against an approved canonical."
                ),
                extracted_content=text_excerpt or None,
                bbox=first.bbox,
                page=first.page,
                doc_pos_hint=_doc_pos(first.role, first.subtype, idx),
            )
        )

    # ── visuals pass ─────────────────────────────────────────────
    # Group by `kind`; one zone per kind. Visuals without a kind fall
    # under the generic "Visual" label.
    visuals_by_kind: dict[str, list[ExtractedVisual]] = {}
    for v in asset.visuals:
        key = (v.kind or "_unknown").lower()
        visuals_by_kind.setdefault(key, []).append(v)

    for v_idx, (kind_key, vs) in enumerate(visuals_by_kind.items()):
        first = vs[0]
        label, lane = _VISUAL_KIND_LABEL_LANE.get(kind_key, _VISUAL_FALLBACK_LABEL_LANE)
        count = len(vs)
        label_with_count = label if count == 1 else f"{label} ({count})"
        # Use the visual's description as the excerpt; fall back to its kind.
        excerpt = (first.description or "").strip() or (first.kind or "Visual")
        if len(excerpt) > 200:
            excerpt = excerpt[:199].rstrip() + "…"
        verdicts.append(
            Verdict(
                layer="cascade",
                sub_layer=f"visual:{kind_key}",
                label=label_with_count,
                status="clean",
                severity="info",
                lanes=[lane],  # type: ignore[list-item]
                evidence="Extracted",
                evidence_detail=(
                    f"Visual of kind '{kind_key}' present in this asset "
                    f"({count} occurrence{'s' if count != 1 else ''}). "
                    "Not yet verified against an approved canonical."
                ),
                extracted_content=excerpt,
                bbox=first.bbox,
                page=first.page,
                doc_pos_hint=_DOC_POS_BY_VISUAL_KIND.get(kind_key, 12.0) + v_idx * 0.001,
            )
        )

    return verdicts
