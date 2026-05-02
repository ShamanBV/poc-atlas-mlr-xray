"""
Layer 2 — regulatory / document-level precheck.

For each rule in the dependency-rule catalog:
  1. Evaluate the rule's predicate against the extracted asset.
     If the predicate is FALSE, the rule does not apply → skip.
  2. Evaluate the rule's `requires`. If TRUE, the requirement is met →
     skip (or emit a `clean` verdict if we want to surface satisfied
     requirements; deferred to v1.1).
  3. If FALSE, emit a `Verdict` with status="miss", severity from the
     rule, and `dependencies_triggered` carrying the rule's predicate +
     coverage so the X-Ray UI can render the "Why required?" chip.

Verdict naming convention:

  layer       = "regulatory"            (Layer 2 produces this)
  sub_layer   = f"{rule.pillar}:{rule.id}"  e.g. "medical:r_abbreviations_defined"
  lanes       = single-element list per pillar
                  medical    → ["M"]
                  legal      → ["L"]
                  regulatory → ["R"]

The asset_builder's pillar router (`verdict.pillar_for`) reads the
`sub_layer` prefix to attribute deductions to the right pillar score.
"""

from __future__ import annotations

from .dependency_rules import Rule, RuleCatalog, evaluate
from .schema import (
    DependencyTrigger,
    DependencyTriggerCoverage,
    ExtractedAsset,
)
from .verdict import Verdict


_LANES_BY_PILLAR: dict[str, list] = {
    "medical": ["M"],
    "legal": ["L"],
    "regulatory": ["R"],
}


# Verdicts ordered by pillar then by rule appearance — tweak via this
# table when the spine wants a specific reading order.
_PILLAR_DOC_POS_BASE: dict[str, float] = {
    "medical": 100.0,
    "legal": 200.0,
    "regulatory": 300.0,
}


def _label_for_rule(rule: Rule) -> str:
    """
    Short, UI-friendly label.

    The YAML descriptions are imperative ("Promotional email must show…").
    The X-Ray spine wants nominal labels ("MAH legal entity in footer").
    Heuristic: drop the leading "When X → ", strip "must", and Title-case
    when convenient. Fallback to the rule id for rules whose descriptions
    are awkward.
    """
    desc = rule.description.strip().rstrip(".")
    # Strip "When/Whenever … →" prefixes some YAML rules use.
    if "→" in desc:
        desc = desc.split("→", 1)[1].strip()
    # Drop leading "must " / "should " / "→ ".
    for prefix in ("must ", "should ", "required ", "needed "):
        if desc.lower().startswith(prefix):
            desc = desc[len(prefix):]
    return desc[:1].upper() + desc[1:] if desc else rule.id


def _evidence_for_unmet_rule(rule: Rule) -> tuple[str, str]:
    """Returns (short_evidence, evidence_detail)."""
    short = "Missing"
    detail = rule.rationale.strip()
    if not detail:
        detail = rule.description
    return short, detail


def _annotation_draft(rule: Rule) -> str:
    """Pre-fill text for the VVPM annotation composer."""
    authority = ""
    overrides = rule.market_overrides or {}
    for market_meta in overrides.values():
        if isinstance(market_meta, dict) and market_meta.get("authority"):
            authority = f" ({market_meta['authority']})"
            break
    return (
        f"{_label_for_rule(rule)}{authority} is required but the asset "
        f"does not contain it. Insert the approved block before submission."
    )


def _dependency_trigger_for_rule(rule: Rule) -> DependencyTrigger:
    """
    Wrap the rule's predicate + coverage as a DependencyTrigger so the
    Zone carries the "Why required?" payload.

    `predicate` here is the rule's prose description (what fired) — a
    structured "this specific predicate node matched" string is future
    work; for the POC the rule-level description is human-readable enough.
    """
    return DependencyTrigger(
        rule_id=rule.id,
        predicate=rule.description,
        rationale=rule.rationale.strip() or rule.description,
        coverage=DependencyTriggerCoverage(
            predicate_hits_in_corpus=rule.coverage.corpus_size_observed,
            requirement_hits=max(
                0,
                rule.coverage.corpus_size_observed - 1,  # placeholder; pattern bank fills in
            ),
            confidence_label=rule.coverage.confidence_label,  # type: ignore[arg-type]
        ),
    )


def _verdict_for_unmet_rule(rule: Rule, asset_pos: int) -> Verdict:
    short_evidence, evidence_detail = _evidence_for_unmet_rule(rule)
    return Verdict(
        layer="regulatory",
        sub_layer=f"{rule.pillar}:{rule.id}",
        label=_label_for_rule(rule),
        status="miss",
        severity=rule.severity,  # type: ignore[arg-type]
        lanes=_LANES_BY_PILLAR.get(rule.pillar, ["R"]),
        evidence=short_evidence,
        evidence_detail=evidence_detail,
        extracted_content=None,
        canonical_content=None,
        diff=None,
        pattern_base=None,
        dependencies_triggered=[_dependency_trigger_for_rule(rule)],
        annotation_draft=_annotation_draft(rule),
        vvpm_anchor=None,
        doc_pos_hint=_PILLAR_DOC_POS_BASE.get(rule.pillar, 300.0) + asset_pos,
    )


# ─── public entrypoint ───────────────────────────────────────────────


def run(asset: ExtractedAsset, catalog: RuleCatalog) -> list[Verdict]:
    """
    Run all dependency rules against the asset; emit one Verdict per
    fired-but-unmet rule.

    Order of emission: by pillar bucket (medical → legal → regulatory),
    rules within a pillar in catalog order.
    """
    verdicts: list[Verdict] = []
    for idx, rule in enumerate(catalog.filter_for_asset(asset)):
        if not evaluate(rule.predicate, asset):
            continue
        if evaluate(rule.requires, asset):
            continue
        verdicts.append(_verdict_for_unmet_rule(rule, asset_pos=idx))
    return verdicts
