"""
Verdict aggregator + Asset envelope builder.

Takes the extracted asset (input) and the verdict list (output of all
check layers) and produces the public `Asset` JSON shape per
`MLR_PRECHECK_API.md` §2.

Responsibilities:
  - Sort verdicts into spine order via `doc_pos_hint`
  - Assign stable zone ids + 1-indexed `doc_pos`
  - Produce per-pillar scores + verdict label
  - Compose identity string + library + preview + cache_key
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .schema import (
    Asset,
    AssetLibrary,
    AssetPreview,
    AssetProfile,
    AssetScores,
    EmailBlock,
    ExtractedAsset,
    Zone,
)
from .verdict import Verdict, compute_scores, compute_verdict_label


# ─── identity helpers ────────────────────────────────────────────────


def _identity_string(asset: ExtractedAsset, profile_id: str) -> str:
    """
    Server-formatted single-line identity, e.g.
    'KISQALI · UK · en · UK-Branded-Promotional · FA-11551654 · prepared 2026-03-14 (49d)'

    Frontend renders this verbatim — no client-side composition.
    """
    parts: list[str] = [
        asset.meta.brand,
        asset.meta.market,
        asset.meta.language,
        profile_id,
    ]
    if asset.meta.code:
        parts.append(asset.meta.code)
    if asset.meta.prepared:
        if asset.meta.age_days is not None:
            parts.append(f"prepared {asset.meta.prepared} ({asset.meta.age_days}d)")
        else:
            parts.append(f"prepared {asset.meta.prepared}")
    return " · ".join(parts)


# ─── verdicts → zones ────────────────────────────────────────────────


def _verdicts_to_zones(verdicts: Iterable[Verdict]) -> list[Zone]:
    """
    Sort by doc_pos_hint, assign 1-indexed `doc_pos` and `id`.

    Abbreviation findings keep fractional positions (900.xxx) so the UI
    can group them in their own sub-section after the structural zones.

    Sequential `pin` numbers are assigned to bbox-bound zones (1, 2, 3…)
    in spine order — these match the overlay rectangles drawn over the
    PDF page render. Zones without a bbox get `pin: None`.
    """
    sorted_verdicts = sorted(verdicts, key=lambda v: v.doc_pos_hint)
    zones: list[Zone] = []
    next_pin = 1
    for idx, v in enumerate(sorted_verdicts, start=1):
        # Abbreviation zones use a stable id based on acronym; structural
        # zones use a sequential id.
        if v.layer == "abbreviation":
            acronym = v.sub_layer.split(":", 1)[-1]
            zone_id = f"abbr_{acronym}"
            doc_pos: float = float(idx) + 0.5  # interleaved feel; UI sorts on this
        else:
            zone_id = f"z{idx}"
            doc_pos = float(idx)
        pin: int | None = None
        if v.bbox is not None:
            pin = next_pin
            next_pin += 1
        zones.append(
            Zone(
                id=zone_id,
                doc_pos=doc_pos,
                label=v.label,
                lanes=v.lanes,
                status=v.status,
                severity=v.severity,
                layer=v.layer,
                sub_layer=v.sub_layer,
                evidence=v.evidence,
                evidence_detail=v.evidence_detail,
                extracted_content=v.extracted_content,
                canonical_content=v.canonical_content,
                diff=v.diff,
                pattern_base=v.pattern_base,
                dependencies_triggered=v.dependencies_triggered,
                annotation_draft=v.annotation_draft,
                vvpm_anchor=v.vvpm_anchor,
                pin=pin,
                bbox=v.bbox,
                page=v.page,
            )
        )
    return zones


# ─── public entrypoint ───────────────────────────────────────────────


def build_asset(
    extracted: ExtractedAsset,
    verdicts: list[Verdict],
    *,
    profile_selected_by: str = "metadata",
    library_sample_size: int = 0,
    library_last_ingest_at: str | None = None,
    pdf_url: str | None = None,
    page_count: int | None = None,
) -> Asset:
    """Compose the full Asset payload."""
    scores = compute_scores(verdicts)
    verdict_label = compute_verdict_label(scores, verdicts)
    zones = _verdicts_to_zones(verdicts)

    coverage_warning = (
        "Library sample size below 20 for this slice; verdicts marked "
        "as early-signal."
        if library_sample_size < 20
        else None
    )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    library_ts = library_last_ingest_at or now_iso

    return Asset(
        asset_id=extracted.asset_id,
        meta=extracted.meta,
        identity=_identity_string(extracted, extracted.profile_id),
        profile=AssetProfile(
            id=extracted.profile_id,
            selected_by=profile_selected_by,  # type: ignore[arg-type]
        ),
        scores=AssetScores(
            overall=scores["overall"],
            medical=scores["medical"],
            legal=scores["legal"],
            regulatory=scores["regulatory"],
        ),
        verdict=verdict_label,  # type: ignore[arg-type]
        zones=zones,
        email_blocks=_email_blocks_for_extracted(extracted, zones),
        library=AssetLibrary(
            sample_size=library_sample_size,
            last_ingest_at=library_ts,
            coverage_warning=coverage_warning,
        ),
        preview=AssetPreview(
            pdf_url=pdf_url,
            html_url=None,
            page_count=page_count,
        ),
        generated_at=now_iso,
        cache_key=(
            f"v1.0:lib_{library_ts[:10]}:asset:{extracted.asset_id}:"
            f"profile:{extracted.profile_id}"
        ),
    )


def _email_blocks_for_extracted(
    extracted: ExtractedAsset,
    zones: list[Zone],
) -> list[EmailBlock]:
    """
    Minimal EmailBlock list — one per extracted block. Pin/match left as
    defaults; the proper preview-overlay assignment lands when Layer 1
    + Layer 2 attach bbox-bound zones.
    """
    out: list[EmailBlock] = []
    for blk in extracted.blocks:
        out.append(
            EmailBlock(
                id=blk.id,
                type=blk.role.lower(),
                match="clean",  # default; overlays update once bbox-bound zones land
                pin=None,
                bbox=blk.bbox,
                page=blk.page,
                ghost_label=None,
            )
        )
    return out
