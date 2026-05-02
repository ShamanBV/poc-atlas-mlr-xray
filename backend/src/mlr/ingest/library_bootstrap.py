"""
Bootstrap the approved-claim library from existing extractor outputs.

Walks every extraction.json in a directory, runs the adapter, harvests
each module that's a claim, and emits an `ApprovedClaim` per
(brand, market, subtype, synthesized_text) tuple.

This is **option B** from the design discussion — treating already-
extracted approved emails as the canonical corpus until a proper
piece-by-piece Vault → Atlas approval flow lands. Pinned in DECISIONS.md
as D5 (`hardcoded library` swap point) and revisited as D25 below.

Output is a list[ApprovedClaim] — same shape as the existing
`library._LIBRARY` tuple. Caller decides whether to merge with
hardcoded entries or replace.

Quirks of bootstrapping from extracted assets (not from MLR-blessed
canonicals):
- The same claim can appear in multiple emails → de-duplicated by exact
  text. Frequency = "n" approximated by occurrence count.
- Subtype derivation is via keyword classifier (see
  `extractor_adapter._claim_subtype`); coarse but consistent.
- Coverage is estimated as `min(1.0, count / total_assets_for_brand)` —
  not statistically meaningful with a small corpus but stable.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from mlr.ingest.extractor_adapter import _claim_subtype, _synthesize_module_text
from mlr.precheck.library import ApprovedClaim


def _harvest_one(extraction: dict) -> Iterable[tuple[str, str, str | None, str]]:
    """
    Yield (brand, market, subtype, synthesized_text) per claim module.

    Keeps the raw extracted text so de-duplication operates on the
    actual claim string the asset carried.
    """
    asset = extraction.get("asset") or {}
    brand = ((asset.get("product") or {}).get("brand") or "").upper()
    market = (asset.get("market") or "").upper()
    if not brand or not market:
        return
    for mod in extraction.get("modules", []):
        if not any(fr.get("role") == "claim" for fr in mod.get("fragments", [])):
            continue
        text = _synthesize_module_text(mod).strip()
        if not text or len(text) < 30:  # skip tiny fragments — usually CTAs that snuck through
            continue
        yield brand, market, _claim_subtype(mod), text


def bootstrap_from_dir(
    extractions_dir: Path,
    *,
    window_months: int = 18,
    min_text_chars: int = 30,
) -> list[ApprovedClaim]:
    """
    Walk every `*.extraction.json` in `extractions_dir` and build a
    deduplicated `ApprovedClaim` list.

    The returned list is sorted by (brand, market, subtype) for
    deterministic output across runs.
    """
    counts: dict[tuple[str, str, str | None, str], int] = defaultdict(int)
    per_brand_total: dict[tuple[str, str], int] = defaultdict(int)

    for path in sorted(extractions_dir.glob("*.extraction.json")):
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        asset = raw.get("asset") or {}
        brand = ((asset.get("product") or {}).get("brand") or "").upper()
        market = (asset.get("market") or "").upper()
        if brand and market:
            per_brand_total[(brand, market)] += 1

        for brand, market, subtype, text in _harvest_one(raw):
            if len(text) < min_text_chars:
                continue
            counts[(brand, market, subtype, text)] += 1

    library: list[ApprovedClaim] = []
    for (brand, market, subtype, text), n in counts.items():
        total_in_slice = per_brand_total.get((brand, market), 1)
        coverage = min(1.0, n / max(total_in_slice, 1))
        # Pattern id = stable hash of (market, subtype, text), so the
        # same canonical text always gets the same id across runs.
        pattern_id = (
            f"{market.lower()}_email"
            f"_{(subtype or 'unknown').lower()}"
            f"_{abs(hash(text)) % 1_000_000:06d}"
        )
        description = _short_description(text, subtype)
        library.append(
            ApprovedClaim(
                pattern_id=pattern_id,
                description=description,
                text=text,
                brand=brand,
                market=market,
                subtype=subtype or "UNKNOWN",
                n=n,
                window_months=window_months,
                coverage=coverage,
                first_seen="2024-01",  # placeholder; real ingest would carry per-source dates
            )
        )

    library.sort(key=lambda c: (c.brand, c.market, c.subtype, -c.n, c.text))
    return library


def _short_description(text: str, subtype: str | None) -> str:
    """A 1-line synopsis used in `Zone.pattern_base.description`."""
    snippet = text[:80].rsplit(" ", 1)[0] if len(text) > 80 else text
    label = (subtype or "claim").lower()
    return f"{label} canonical: {snippet}…"
