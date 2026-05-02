"""
Adapter: ExtractedAsset → Document X-Ray payload.

Target shape is the data the Document X-Ray prototype consumes
(`design_handoff_atlas_extraction/design_handoff_document_xray/
README.md` § "State Shape"):

  {
    asset:    AssetMeta-ish + page_count + asset_id,
    pages:    [{page, width_pt, height_pt}],
    claims:   Claim[],          # one per claim module
    elements: OtherElement[],   # one per non-claim block + standalone visual
    compliance_findings: [...]  # MLR Precheck side-channel (D-spec 2B)
  }

Per-element coordinate system: PDF points (top-left origin), `{t,l,w,h}`
shape that the prototype's annotation rect renderer expects. The
frontend scales them to pixels at render time using page width.

Status mapping (Document X-Ray vocab is `edited / accepted / new /
processing`):
  - All extracted items default to `edited` (the design's "extracted
    but not yet reviewed" baseline — matches the prototype's mock data).
  - Items where Layer 1 (claim drift) reported `clean` could later
    auto-promote to `accepted`; for v1 we leave that to the user.
  - Layer 2 envelope misses don't have a target element to badge —
    they surface in `compliance_findings`, NOT inline.
  - Layer 3 abbreviation findings: also surfaced in
    `compliance_findings`, not inline (acronyms in body text aren't
    selectable rows in this UI).

Confidence:
  - Block.confidence (when present in upstream data) maps to the
    element's `conf` percentage.
  - For claim modules, we use the precheck's similarity score (combined
    semantic + char ratio) when available; falls back to module-level
    avg confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mlr.precheck import claim_check, library
from mlr.precheck.schema import (
    BoundingBox,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedModule,
    ExtractedVisual,
)
from mlr.precheck.similarity import combined_similarity, default_embedder
from mlr.precheck.verdict import Verdict


# Mapping from our extraction roles → Document X-Ray element types.
# Roles not in this map are skipped (e.g. ABBREVIATION blocks aren't
# X-Ray rows; they live in supportive_resources).
_ROLE_TO_TYPE: dict[str, str] = {
    # Promotional / audience
    "PROMOTIONAL_NOTICE": "AUD_RESTR",
    "AUDIENCE_RESTRICTION": "AUD_RESTR",
    # Body / content
    "BODY": "BODY",
    "HEADER": "BODY",
    "PARAGRAPH": "BODY",
    "CALLOUT": "BODY",
    "SUBJECT": "BODY",
    "CTA": "BODY",
    # Regulatory / safety
    "INDICATION": "REGULATORY",
    "SAFETY": "REGULATORY",
    "PHARMACOVIGILANCE": "REGULATORY",
    "PRESCRIBING_INFORMATION": "REGULATORY",
    "APPROVAL_INFO": "REGULATORY",
    "REGULATORY_MENU": "REGULATORY",
    # Legal / contact
    "DISCLAIMERS": "LEGAL",
    "CONTACT_INFO": "LEGAL",
    "UNSUBSCRIBE": "LEGAL",
    # Refs / footnotes
    "REFERENCE": "REFERENCE",
    "FOOTNOTE": "FOOTNOTE",
}


# Roles to omit entirely from the outline.
_SKIP_ROLES = frozenset({"ABBREVIATION", "NAVIGATION"})


# ─── helpers ─────────────────────────────────────────────────────────


def _bbox_to_rect(bb: Optional[BoundingBox]) -> Optional[dict]:
    if bb is None:
        return None
    return {
        "t": bb.y0,
        "l": bb.x0,
        "w": max(0.0, bb.x1 - bb.x0),
        "h": max(0.0, bb.y1 - bb.y0),
    }


def _conf_pct_from_block(blk: ExtractedBlock) -> int:
    """Block confidence is 0..1 in the extractor; default to 100 if missing."""
    raw = getattr(blk, "confidence", None)
    if raw is None:
        return 100
    try:
        return int(round(float(raw) * 100))
    except (TypeError, ValueError):
        return 100


def _short(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


# ─── element + claim builders ────────────────────────────────────────


def _block_to_element(blk: ExtractedBlock, *, eid_prefix: str) -> Optional[dict]:
    """Map a non-claim ExtractedBlock to an OtherElement dict."""
    if blk.role in _SKIP_ROLES:
        return None
    el_type = _ROLE_TO_TYPE.get(blk.role)
    if el_type is None:
        return None
    sub = blk.subtype  # may be None; prototype handles that
    text = _short(blk.text, 200)
    return {
        "id": f"{eid_prefix}_{blk.id}",
        "type": el_type,
        "sub": sub,
        "conf": _conf_pct_from_block(blk),
        "status": "edited",
        "text": text,
        "fullText": blk.text,
        "refs": [],
        "rect": _bbox_to_rect(blk.bbox),
        "page": blk.page,
    }


def _visual_to_element(v: ExtractedVisual, *, eid_prefix: str) -> dict:
    """Standalone visual (not tied to a claim) → DATA_VIS OtherElement."""
    sub = v.kind  # LOGO / BANNER / HERO / DIAGRAM / None
    text = v.description or (sub.title() + " visual" if sub else "Figure")
    return {
        "id": f"{eid_prefix}_{v.id}",
        "type": "DATA_VIS",
        "sub": sub,
        "conf": 80,  # placeholder until visual confidences land
        "status": "edited",
        "text": _short(text, 200),
        "fullText": text,
        "refs": [],
        "rect": _bbox_to_rect(v.bbox),
        "page": v.page,
        "ocr": v.link_visible_text or None,
        "link": v.link_uri or None,
    }


def _claim_to_payload(
    module: ExtractedModule,
    *,
    block_lookup: dict[str, ExtractedBlock],
    visual_lookup: dict[str, ExtractedVisual],
    drift_score: Optional[float],
    drift_canonical: Optional[str],
    eid_prefix: str,
) -> dict:
    """One claim module → one Claim dict with assets[]."""
    # The headline = module.synthesized_text trimmed; the name is a
    # short tag derived from subtype + first words.
    headline = module.synthesized_text.strip()
    short_name = (module.subtype or "claim").title()

    # Collect references aggregated from blocks' markers.refs (when present).
    ref_ids: list[str] = []
    for bid in module.block_ids:
        blk = block_lookup.get(bid)
        if blk is None:
            continue
    # The block-level ref_numbers field isn't on our schema; lifted from
    # original extractor JSON would require an extension. Skip for v1 —
    # the prototype handles empty refs[].

    # Module bbox: union of its blocks' bboxes (first present block for v1).
    module_bbox: Optional[BoundingBox] = None
    module_page: Optional[int] = None
    assets: list[dict] = []
    for bid in module.block_ids:
        blk = block_lookup.get(bid)
        if blk is None:
            continue
        if module_bbox is None and blk.bbox is not None:
            module_bbox = blk.bbox
            module_page = blk.page
        assets.append({
            "id": f"{eid_prefix}_a_{blk.id}",
            "kind": "text",
            "text": _short(blk.text, 200),
            "conf": _conf_pct_from_block(blk),
            "status": "edited",
            "rect": _bbox_to_rect(blk.bbox),
            "page": blk.page,
        })

    # Wire in any visuals tagged to this module (via fragment.visual_ids).
    for frag in module.fragments:
        # Fragment shape didn't carry visual_ids in our schema yet — skip.
        # When the extractor adapter is extended to populate them, we can
        # extend a visual asset per visual_id here.
        pass

    # Confidence: derive from drift score if Layer 1 had a candidate.
    if drift_score is not None:
        conf = max(0, min(100, int(round(drift_score * 100))))
    else:
        # Average over the module's blocks.
        block_confs = [_conf_pct_from_block(block_lookup[bid]) for bid in module.block_ids if bid in block_lookup]
        conf = int(round(sum(block_confs) / len(block_confs))) if block_confs else 100

    return {
        "id": f"{eid_prefix}_{module.id}",
        "type": "CLAIM",
        "name": short_name,
        "headline": _short(headline, 240),
        "status": "edited",
        "conf": conf,
        "refs": ref_ids,
        "rect": _bbox_to_rect(module_bbox),
        "page": module_page,
        "assets": assets,
        "drift_canonical": drift_canonical,  # side-channel; UI may show in detail panel
    }


# ─── compliance findings (MLR Precheck side-channel) ─────────────────


def _compliance_findings_from_verdicts(verdicts: list[Verdict]) -> list[dict]:
    """
    Surface envelope-level + abbreviation-level precheck findings as a
    flat list. Per the design directive (option 2B) these don't get
    inline rows in the X-Ray outline — they live in the asset metadata
    card / footer.
    """
    out: list[dict] = []
    for v in verdicts:
        if v.layer == "regulatory":
            out.append({
                "rule_id": v.dependencies_triggered[0].rule_id if v.dependencies_triggered else None,
                "pillar": v.sub_layer.split(":", 1)[0] if v.sub_layer else "regulatory",
                "label": v.label,
                "severity": v.severity,
                "evidence": v.evidence,
                "rationale": v.evidence_detail,
            })
        elif v.layer == "abbreviation":
            acronym = v.sub_layer.split(":", 1)[-1] if v.sub_layer else "?"
            out.append({
                "rule_id": "r_abbreviations_defined",
                "pillar": "medical",
                "label": f"Acronym `{acronym}` not defined",
                "severity": v.severity,
                "evidence": v.evidence,
                "rationale": v.evidence_detail,
            })
    return out


# ─── public entrypoint ───────────────────────────────────────────────


@dataclass(frozen=True)
class _DriftHit:
    score: float
    canonical: str


def _claim_drift_hits(asset: ExtractedAsset) -> dict[str, _DriftHit]:
    """
    Run claim_check's similarity scoring per claim module. Returns
    `{module_id → _DriftHit}` for downstream conf% / canonical display.
    Only modules with a library candidate get an entry.
    """
    out: dict[str, _DriftHit] = {}
    embedder = default_embedder()
    for mod in asset.modules:
        if not mod.claim:
            continue
        cands = library.find_candidates(asset.meta.brand, asset.meta.market, mod.subtype)
        if not cands:
            continue
        best = cands[0]
        best_score = -1.0
        for c in cands:
            s = combined_similarity(mod.synthesized_text, c.text, embedder)
            if s > best_score:
                best, best_score = c, s
        out[mod.id] = _DriftHit(score=best_score, canonical=best.text)
    return out


def to_document_xray(asset: ExtractedAsset, verdicts: list[Verdict]) -> dict:
    """
    Build the Document X-Ray payload for one asset.

    `verdicts` is the union of all precheck-layer verdicts (claim,
    regulatory, abbreviation) — used to populate compliance_findings.
    """
    block_lookup = {b.id: b for b in asset.blocks}
    visual_lookup = {v.id: v for v in asset.visuals}
    drifts = _claim_drift_hits(asset)

    # Collect block ids that belong to a claim module — these are NOT
    # surfaced as standalone OtherElements (they're shown nested under
    # their Claim).
    claim_block_ids: set[str] = set()
    for mod in asset.modules:
        if mod.claim:
            claim_block_ids.update(mod.block_ids)

    eid_prefix = "el"
    claims: list[dict] = []
    for mod in asset.modules:
        if not mod.claim:
            continue
        d = drifts.get(mod.id)
        claims.append(_claim_to_payload(
            mod,
            block_lookup=block_lookup,
            visual_lookup=visual_lookup,
            drift_score=d.score if d else None,
            drift_canonical=d.canonical if d else None,
            eid_prefix=eid_prefix,
        ))

    elements: list[dict] = []
    for blk in asset.blocks:
        if blk.id in claim_block_ids:
            continue
        el = _block_to_element(blk, eid_prefix=eid_prefix)
        if el is not None:
            elements.append(el)

    # Standalone visuals (visuals not used by any claim module).
    used_visual_ids: set[str] = set()
    for mod in asset.modules:
        for frag in mod.fragments:
            # Fragments don't carry visual_ids in our schema yet; nothing to mark used.
            pass
    for v in asset.visuals:
        if v.id in used_visual_ids:
            continue
        # Skip visuals without a bbox (they can't be drawn on the page).
        if v.bbox is None:
            continue
        elements.append(_visual_to_element(v, eid_prefix=eid_prefix))

    findings = _compliance_findings_from_verdicts(verdicts)

    return {
        "asset_id": asset.asset_id,
        "meta": asset.meta.model_dump(),
        "profile_id": asset.profile_id,
        "claims": claims,
        "elements": elements,
        "compliance_findings": findings,
        "compliance_summary": {
            "total": len(findings),
            "block": sum(1 for f in findings if f["severity"] == "block"),
            "warn": sum(1 for f in findings if f["severity"] == "warn"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
    }
