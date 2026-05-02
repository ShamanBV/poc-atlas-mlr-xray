"""
Approved-claim library — the canonical corpus Layer 1 matches against.

In the live system this is built by `ingest/asset_to_library.py` from
approved Vault PDFs piece-by-piece (per `MLR_PRECHECK_SPEC.md` §6). For
the POC slice it's a hand-curated tuple — sufficient to demo claim
drift detection against the KISQALI fixture without library infra.

Each `ApprovedClaim` is one canonical variant of a claim "pattern" —
the thing the X-Ray UI surfaces as `pattern_base.pattern_id`. Multiple
variants can share a `pattern_id` if they're alternate phrasings of
the same approved claim.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedClaim:
    pattern_id: str       # stable id used in Zone.pattern_base.pattern_id
    description: str      # human-readable, "OS efficacy claim with HR + CI in this position"
    text: str             # the canonical claim text
    brand: str
    market: str
    subtype: str          # EFFICACY / SAFETY / COMPARATIVE / DOSING / …
    n: int                # times this variant appeared in approvals
    window_months: int    # window the n was observed over
    coverage: float       # fraction of approved variants matching this pattern
    first_seen: str       # ISO month, "2024-06"


_LIBRARY: tuple[ApprovedClaim, ...] = (
    # KISQALI · UK · efficacy — primary canonical (matches the §6
    # sample's `canonical_content`). The fixture's claim drifts from
    # this by inserting "disease " and swapping the comma after HR for
    # a semicolon — combined_similarity should land in the "drift" band.
    ApprovedClaim(
        pattern_id="uk_email_efficacy_HR_CI",
        description="5-year iDFS efficacy claim with HR + CI",
        text=(
            "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% "
            "vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014)."
        ),
        brand="KISQALI", market="UK", subtype="EFFICACY",
        n=287, window_months=18, coverage=0.94, first_seen="2024-06",
    ),
    # Alternate phrasing of the same pattern — older approved variant.
    # The engine picks the BEST-scoring candidate; the fixture's claim
    # is closer to the primary above so this one shouldn't win.
    ApprovedClaim(
        pattern_id="uk_email_efficacy_HR_CI",
        description="5-year iDFS efficacy claim — older phrasing",
        text=(
            "KISQALI® + ET reduced the risk of disease recurrence by 25.2% versus ET "
            "alone at 5 years (HR 0.748; 95% CI 0.618–0.906; p=0.0014)."
        ),
        brand="KISQALI", market="UK", subtype="EFFICACY",
        n=73, window_months=18, coverage=0.94, first_seen="2024-09",
    ),
    # KISQALI · UK · safety — included for catalog shape variety.
    # The fixture has no safety claim module, so this won't match;
    # it exists so library.total_size + find_candidates exercise > 1
    # subtype path.
    ApprovedClaim(
        pattern_id="uk_email_safety_general",
        description="General safety reminder framing",
        text=(
            "Adverse events in NATALEE were generally consistent with the established "
            "safety profile of KISQALI®; the most common (≥30%) were neutropenia and "
            "infections."
        ),
        brand="KISQALI", market="UK", subtype="SAFETY",
        n=142, window_months=18, coverage=0.81, first_seen="2024-08",
    ),
)


def find_candidates(brand: str, market: str, subtype: str | None) -> list[ApprovedClaim]:
    """
    Return all approved canonical variants for a (brand, market, subtype) slice.

    `subtype` may be None on poorly-classified modules; in that case the
    function returns no candidates — the engine's caller decides whether
    to skip the claim or emit a "no canonical candidate" finding.
    """
    if subtype is None:
        return []
    return [
        c for c in _LIBRARY
        if c.brand == brand and c.market == market and c.subtype == subtype
    ]


def lookup_pattern(pattern_id: str) -> ApprovedClaim | None:
    """Return the FIRST variant of a pattern (used by `GET /api/precheck/patterns/{id}`)."""
    for c in _LIBRARY:
        if c.pattern_id == pattern_id:
            return c
    return None


def total_size() -> int:
    """Surfaces in `Asset.library.sample_size`."""
    return len(_LIBRARY)


def coverage_warning_for_size(size: int, threshold: int = 20) -> str | None:
    """Returns the user-facing warning string when the library is sparse."""
    if size < threshold:
        return (
            f"Library sample size ({size}) is below {threshold}; verdicts "
            f"are early-signal only."
        )
    return None
