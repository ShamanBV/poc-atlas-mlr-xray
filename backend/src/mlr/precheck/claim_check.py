"""
Layer 1 — claim precheck.

For each claim module in the extracted asset:

  1. Look up canonical candidates from the library by
     (brand, market, subtype).
  2. Score the module's synthesized text against every candidate via
     `combined_similarity` (bag-of-tokens + char-level avg). Pick the
     best.
  3. Emit a Verdict:
       similarity ≥ CLEAN_MIN  → status:clean,  severity:info
       DRIFT_MIN ≤ s < CLEAN   → status:attn,   severity:warn   (drift)
       similarity <  DRIFT_MIN → status:miss,   severity:block  (no canonical match)

  4. Word-level diff, pattern_base, and an annotation_draft are attached
     to non-clean verdicts so the X-Ray UI can render the §6 sample.

Thresholds are tuned for the default `HashEmbedder` + char-ratio
hybrid (see `similarity.py`). Swap for sentence-transformers and the
documented values from `MLR_PRECHECK_SPEC.md` §3 (0.95 / 0.70) become
appropriate again — pass an embedder + thresholds explicitly to `run`.

Out of scope this slice:
  - Per-claim ref-id resolution (cited reference exists in reference-set).
  - Numeric-value spot-check (HR 0.748 must equal canonical's number).
  - Comparator naming (vs ET → must explicitly name the comparator).
  - Module → block bbox bridging beyond the first block_id.
"""

from __future__ import annotations

from . import library
from .schema import (
    ExtractedAsset,
    ExtractedModule,
    PatternBase,
)
from .similarity import (
    Embedder,
    combined_similarity,
    default_embedder,
    word_diff,
)
from .verdict import Verdict


# Thresholds — see module docstring.
CLEAN_MIN: float = 0.98
DRIFT_MIN: float = 0.80


# Module ordering hint: claims should sit at the top of the X-Ray spine.
_DOC_POS_BASE: float = 10.0


def _verdict_for_match(
    module: ExtractedModule,
    canonical: library.ApprovedClaim,
    score: float,
    pos_idx: int,
    *,
    clean_min: float,
    drift_min: float,
) -> Verdict:
    """Build a Verdict for a (module, best_canonical, similarity) triple."""
    subtype = (module.subtype or "claim").lower()
    sub_layer = f"claim:{subtype}"

    if score >= clean_min:
        status, severity = "clean", "info"
        evidence = f"Match · {score:.2f}"
        evidence_detail = (
            f"Closest approved canonical (similarity {score:.2f}): "
            f"{canonical.description}."
        )
        diff = None
        annotation_draft = None
        label = f"{(module.subtype or 'Claim').title()} claim — match"
    elif score >= drift_min:
        status, severity = "attn", "warn"
        evidence = f"Partial match · {score:.2f}"
        evidence_detail = (
            f"Closest approved canonical (similarity {score:.2f}): "
            f"{canonical.description}. Phrasing drift detected; review "
            f"the word diff and decide whether to revert to canonical."
        )
        diff = word_diff(module.synthesized_text, canonical.text)
        annotation_draft = (
            f"{(module.subtype or 'Claim').title()} claim shows phrasing drift "
            f"vs approved canonical (similarity {score:.2f}). Consider reverting "
            f"to: \"{canonical.text}\""
        )
        label = f"{(module.subtype or 'Claim').title()} claim — drift"
    else:
        status, severity = "miss", "block"
        evidence = f"No close match · {score:.2f}"
        evidence_detail = (
            f"Closest approved canonical (similarity {score:.2f}) is below "
            f"the {drift_min:.2f} similarity floor. Either the claim is "
            f"novel and needs MLR approval, or the canonical bank doesn't "
            f"yet cover this phrasing."
        )
        diff = word_diff(module.synthesized_text, canonical.text)
        annotation_draft = (
            f"{(module.subtype or 'Claim').title()} claim does not match any "
            f"approved canonical above the {drift_min:.2f} similarity floor. "
            f"Submit for MLR review or align with: \"{canonical.text}\""
        )
        label = f"{(module.subtype or 'Claim').title()} claim — no canonical match"

    pattern_base = PatternBase(
        pattern_id=canonical.pattern_id,
        description=canonical.description,
        coverage=canonical.coverage,
        n=canonical.n,
        window_months=canonical.window_months,
        rule_id=None,
    )

    vvpm_anchor = f"anchor_{module.block_ids[0]}" if module.block_ids else None

    return Verdict(
        layer="claim",
        sub_layer=sub_layer,
        label=label,
        status=status,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        lanes=["M"],
        evidence=evidence,
        evidence_detail=evidence_detail,
        extracted_content=module.synthesized_text,
        canonical_content=canonical.text,
        diff=diff,
        pattern_base=pattern_base,
        dependencies_triggered=[],
        annotation_draft=annotation_draft,
        vvpm_anchor=vvpm_anchor,
        doc_pos_hint=_DOC_POS_BASE + pos_idx,
    )


# ─── public entrypoint ───────────────────────────────────────────────


def run(
    asset: ExtractedAsset,
    *,
    embedder: Embedder | None = None,
    clean_min: float = CLEAN_MIN,
    drift_min: float = DRIFT_MIN,
) -> list[Verdict]:
    """
    Run Layer 1 over an extracted asset.

    Modules without a library candidate (novel subtype, unknown brand,
    etc.) are SKIPPED in this slice — no verdict emitted. The intent
    will firm up once a "no canonical found" UX exists; for now we
    avoid false-positives on legitimately new claims that haven't been
    learned yet.
    """
    embedder = embedder or default_embedder()
    verdicts: list[Verdict] = []
    for idx, module in enumerate(asset.modules):
        if not module.claim:
            continue
        candidates = library.find_candidates(
            asset.meta.brand,
            asset.meta.market,
            module.subtype,
        )
        if not candidates:
            continue

        # Best-of cosine — score every candidate, pick the highest.
        best_canonical = candidates[0]
        best_score = -1.0
        for cand in candidates:
            s = combined_similarity(
                module.synthesized_text,
                cand.text,
                embedder,
            )
            if s > best_score:
                best_canonical, best_score = cand, s

        verdicts.append(
            _verdict_for_match(
                module,
                best_canonical,
                best_score,
                pos_idx=idx,
                clean_min=clean_min,
                drift_min=drift_min,
            )
        )
    return verdicts
