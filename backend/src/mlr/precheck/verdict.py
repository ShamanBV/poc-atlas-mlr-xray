"""
Internal verdict shape — one per finding emitted by a check layer.

Each layer (`abbreviation_check`, `claim_check`, `document_check`,
`cascade_adapter`) returns a `list[Verdict]`. The asset_builder flattens
verdicts into the public `Zone` payload.

Keeping verdict + zone separate buys two things:
1. Layers don't need to invent zone ids, doc_pos, lanes — those are
   asset-level concerns assigned by the aggregator.
2. The verdict shape can carry layer-specific debug fields (e.g. raw
   similarity scores, regex hits) without polluting the public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schema import (
    BoundingBox,
    DependencyTrigger,
    DiffSegment,
    PatternBase,
    ZoneLane,
    ZoneLayer,
    ZoneSeverity,
    ZoneStatus,
)


@dataclass
class Verdict:
    """One precheck finding, layer-agnostic."""

    layer: ZoneLayer
    sub_layer: str

    label: str
    status: ZoneStatus
    severity: ZoneSeverity
    lanes: list[ZoneLane]

    evidence: str
    evidence_detail: str

    extracted_content: Optional[str] = None
    canonical_content: Optional[str] = None

    diff: Optional[list[DiffSegment]] = None
    pattern_base: Optional[PatternBase] = None
    dependencies_triggered: list[DependencyTrigger] = field(default_factory=list)

    annotation_draft: Optional[str] = None
    vvpm_anchor: Optional[str] = None

    # Spatial anchor for the preview overlay; threaded into Zone.bbox/page.
    bbox: Optional[BoundingBox] = None
    page: Optional[int] = None

    # Layer-internal hint for asset_builder positioning. Bigger anchor →
    # later in the spine. Values are arbitrary; the aggregator sorts them
    # then renumbers to 1.0, 2.0, … or keeps fractional positions for
    # abbreviation findings interleaved between blocks.
    doc_pos_hint: float = 0.0


# ─── pillar derivation from layer ────────────────────────────────────
#
# Each verdict counts towards exactly one pillar score. Mapping:
#
#   layer:claim          → medical
#   layer:regulatory     → regulatory  (sub_layer namespace decides; legal sub_layers
#                                       like regulatory:audience_restriction count
#                                       toward "regulatory" pillar; legal-specific
#                                       sub_layers route to "legal")
#   layer:abbreviation   → medical
#   layer:cascade        → derived from cascade rule's pillar (rule_id prefix)
#
# For the POC slice we only need claim + abbreviation + the regulatory
# bucket; legal is folded in once Layer 2 lands.


def pillar_for(verdict: Verdict) -> str:
    """
    Returns 'medical' | 'legal' | 'regulatory'.

    Layer 2 (`layer:regulatory`) emits sub_layers prefixed with the
    rule's pillar — `medical:r_xxx` / `legal:r_xxx` / `regulatory:r_xxx`
    — so the prefix is the source of truth for routing.
    """
    if verdict.layer == "abbreviation":
        return "medical"
    if verdict.layer == "claim":
        return "medical"
    if verdict.layer == "regulatory":
        if verdict.sub_layer.startswith("medical:"):
            return "medical"
        if verdict.sub_layer.startswith("legal:"):
            return "legal"
        return "regulatory"
    if verdict.layer == "cascade":
        # Same prefix convention as Layer 2 — cascade adapter stamps the
        # pillar in sub_layer when emitting.
        if verdict.sub_layer.startswith("medical:"):
            return "medical"
        if verdict.sub_layer.startswith("legal:"):
            return "legal"
        return "regulatory"
    return "medical"


# ─── score computation ───────────────────────────────────────────────
#
# Scores are 0..100 per pillar + an `overall`. The mapping is:
#
#   For each pillar, count weighted issues:
#     block-severity verdict   → 20pt deduction
#     warn-severity verdict    → 8pt deduction
#     info-severity verdict    → 2pt deduction
#   floor at 0, ceiling at 100. Clean verdicts add nothing (they exist
#   purely so the spine can render satisfied requirements).
#
#   `overall` = min(pillar scores) — worst pillar gates the headline.
#
# The numbers are tuneable; pinned in the spec (§ MLR_PRECHECK_SPEC.md
# pending). For v1 the user-facing meaning is ordinal not absolute.

_DEDUCTION_BY_SEVERITY = {"block": 20, "warn": 8, "info": 2}


def compute_scores(verdicts: list[Verdict]) -> dict[str, int]:
    pillars = {"medical": 100, "legal": 100, "regulatory": 100}
    for v in verdicts:
        if v.status == "clean":
            continue
        pillar = pillar_for(v)
        deduction = _DEDUCTION_BY_SEVERITY.get(v.severity, 0)
        pillars[pillar] = max(0, pillars[pillar] - deduction)
    pillars["overall"] = min(pillars.values())
    return pillars


def compute_verdict_label(scores: dict[str, int], verdicts: list[Verdict]) -> str:
    """Pass / Warn / Fail — overall_pillar_worst, matches cascade convention."""
    if any(v.severity == "block" and v.status != "clean" for v in verdicts):
        return "Fail"
    if any(v.severity == "warn" and v.status != "clean" for v in verdicts):
        return "Warn"
    return "Pass"
