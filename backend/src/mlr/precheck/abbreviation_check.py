"""
Layer 3 — abbreviation precheck.

For an extracted asset:

  1. Walk all body / claim / footnote blocks; extract acronym candidates.
  2. Walk the abbreviation-set supportive resource; collect acronyms that
     are already defined in the asset itself.
  3. For each acronym used in body but NOT defined in the asset, look it
     up in the canonical glossary and emit a Verdict.

The Verdict carries `dependencies_triggered` referencing the
`r_abbreviations_defined` rule from `dependency_rules.yaml`, which is
what gives the X-Ray UI's "Why required?" chip its content.

Out of scope for this slice:
  - Verifying that the asset's existing definitions match the canonical
    glossary (drift). Lands when Layer 1 (claim drift) ships and we
    reuse the same diff machinery.
  - First-use-on-page expansion (e.g. "adverse event (AE)") as a valid
    alternative to the abbreviation block. Add when the corpus shows
    that's a stable pattern.
"""

from __future__ import annotations

import re

from .glossary import GlossaryEntry, extract_acronym_candidates, lookup
from .schema import (
    DependencyTrigger,
    DependencyTriggerCoverage,
    ExtractedAsset,
    ExtractedBlock,
    PatternBase,
    SupportiveResource,
)
from .verdict import Verdict


# Used to lift document-level brand inference to the whole asset
# (any uppercase token followed by ® or ™ in ANY block).
_BRAND_MARKED_RE = re.compile(r"\b(i?[A-Z][A-Z0-9]{1,6})(®|™)")


# Roles whose text counts as "body" for acronym usage.
# Footnotes / references shouldn't trigger findings on their own — if an
# acronym appears ONLY in a footnote it's typically defined inline.
_BODY_ROLES = frozenset(
    {"BODY", "CLAIM", "CALLOUT", "CTA", "PARAGRAPH", "HEADER", "SUBJECT"}
)


def _collect_defined_acronyms(
    resources: list[SupportiveResource],
) -> set[str]:
    """
    Pull acronyms from the asset's own abbreviation block.

    Each member of an `abbreviation-set` is a dict like
    `{"acronym": "AE", "expansion": "adverse event"}`. We lower the bar
    on schema strictness and accept any shape that has an `acronym` key.
    """
    defined: set[str] = set()
    for r in resources:
        if r.type != "abbreviation-set":
            continue
        for member in r.members:
            acro = member.get("acronym") if isinstance(member, dict) else None
            if isinstance(acro, str) and acro:
                defined.add(acro)
    return defined


def _collect_used_acronyms(
    blocks: list[ExtractedBlock],
    brand_tokens: tuple[str, ...] = (),
) -> dict[str, tuple[int, list[str]]]:
    """
    Returns `{acronym: (count, [block_ids…])}` for acronyms in body text.

    Block ids let downstream rendering pin a finding back to a specific
    paragraph; we keep them so the future EmailBlock overlay can highlight.

    `brand_tokens` is forwarded to `extract_acronym_candidates` so the
    brand filter has the asset's own brand metadata to work with even
    when the body uses the bare brand name without ®.
    """
    out: dict[str, tuple[int, list[str]]] = {}
    for blk in blocks:
        if blk.role not in _BODY_ROLES:
            continue
        for acro, count in extract_acronym_candidates(blk.text, brand_tokens):
            existing_count, existing_ids = out.get(acro, (0, []))
            out[acro] = (existing_count + count, existing_ids + [blk.id])
    return out


def _make_dependency_trigger(
    acronym: str,
    occurrences: int,
) -> DependencyTrigger:
    """Build the `r_abbreviations_defined` trigger for the verdict."""
    return DependencyTrigger(
        rule_id="r_abbreviations_defined",
        predicate=f"Body text contains acronym '{acronym}' ({occurrences} occurrence{'s' if occurrences != 1 else ''})",
        rationale="All used acronyms must be defined in the abbreviation block.",
        coverage=DependencyTriggerCoverage(
            predicate_hits_in_corpus=308,
            requirement_hits=298,
            confidence_label="high",
        ),
    )


def _make_pattern_base(entry: GlossaryEntry) -> PatternBase:
    """Wrap a glossary entry as the verdict's `pattern_base`."""
    return PatternBase(
        pattern_id=entry.pattern_id,
        description=f"{entry.acronym} — {entry.expansion} (general glossary, all disease areas)",
        coverage=entry.coverage,
        n=entry.n,
        window_months=entry.window_months,
        rule_id=None,
    )


def _verdict_for_undefined_acronym(
    acronym: str,
    occurrences: int,
    glossary_entry: GlossaryEntry | None,
    block_ids: list[str],
    block_lookup: dict | None = None,
) -> Verdict:
    """One Zone per undefined acronym."""
    if glossary_entry is not None:
        canonical = f"{acronym} — {glossary_entry.expansion}"
        evidence_detail = (
            f"{acronym} appears in body text but no abbreviation block "
            f"defines it. Suggested expansion (from approved corpus): "
            f"'{glossary_entry.expansion}'."
        )
        annotation_draft = (
            f"Acronym '{acronym}' used in body text without definition. "
            f"Add to abbreviations block: '{acronym} — {glossary_entry.expansion}'."
        )
        pattern_base = _make_pattern_base(glossary_entry)
    else:
        # Acronym used but not in the canonical glossary either. Flag for
        # human review — could be a legitimate disease-area term we
        # haven't seen yet, or a typo / stray uppercase token.
        canonical = None
        evidence_detail = (
            f"{acronym} appears in body text but no abbreviation block "
            f"defines it AND the acronym is not in the approved glossary. "
            f"Either add a definition or confirm the term is intended."
        )
        annotation_draft = (
            f"Acronym '{acronym}' used in body text without definition; "
            f"not found in the approved glossary. Confirm intent + add a "
            f"definition to the abbreviations block."
        )
        pattern_base = None

    severity = "warn" if glossary_entry is not None else "warn"  # both are warn in v1
    occurrence_label = f"{occurrences}×" if occurrences > 1 else "1×"

    # Spatial anchor — first block in which this acronym appears.
    # Multi-occurrence acronyms still pin to one bbox for simplicity;
    # the drawer's evidence_detail names the count.
    bbox = None
    page = None
    if block_lookup and block_ids:
        for bid in block_ids:
            blk = block_lookup.get(bid)
            if blk is not None and blk.bbox is not None:
                bbox = blk.bbox
                page = blk.page
                break

    return Verdict(
        layer="abbreviation",
        sub_layer=f"abbreviation:{acronym}",
        label=f"{acronym} — used but not defined",
        status="attn",
        severity=severity,
        lanes=["M"],
        evidence=f"Acronym used {occurrence_label} without definition",
        evidence_detail=evidence_detail,
        extracted_content=acronym,
        canonical_content=canonical,
        diff=None,
        pattern_base=pattern_base,
        dependencies_triggered=[_make_dependency_trigger(acronym, occurrences)],
        annotation_draft=annotation_draft,
        vvpm_anchor=None,
        bbox=bbox,
        page=page,
        # Push abbreviation findings to the end of the spine; per the
        # design they live in their own Medical-lane sub-section. Unique
        # fractional offset per acronym so ordering is stable.
        doc_pos_hint=900.0 + sum(ord(c) for c in acronym) * 0.001,
    )


# ─── public entrypoint ───────────────────────────────────────────────


def run(asset: ExtractedAsset) -> list[Verdict]:
    """
    Run Layer 3 over an extracted asset, return one Verdict per
    undefined acronym.

    The order is reading-order of first appearance (matches what the
    UI shows in its abbreviation sub-section).
    """
    defined = _collect_defined_acronyms(asset.supportive_resources)

    # Asset-wide brand tokens: meta.brand plus any token that appears
    # with ® or ™ in any block. This handles the common case where the
    # brand is marked with ® on first use (header) but appears bare in
    # subsequent body paragraphs.
    document_brands: set[str] = {asset.meta.brand.upper()}
    for blk in asset.blocks:
        for m in _BRAND_MARKED_RE.finditer(blk.text):
            document_brands.add(m.group(1).upper())

    used = _collect_used_acronyms(asset.blocks, brand_tokens=tuple(document_brands))

    block_lookup = {b.id: b for b in asset.blocks}
    verdicts: list[Verdict] = []
    for acronym, (occurrences, block_ids) in used.items():
        if acronym in defined:
            continue
        glossary_entry = lookup(acronym)
        verdicts.append(
            _verdict_for_undefined_acronym(
                acronym=acronym,
                occurrences=occurrences,
                glossary_entry=glossary_entry,
                block_ids=block_ids,
                block_lookup=block_lookup,
            )
        )
    return verdicts
