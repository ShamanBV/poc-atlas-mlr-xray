"""
Canonical acronym glossary.

In v1.5 this auto-derives from approved abbreviation blocks across the
library (per `MLR_PRECHECK_SPEC.md` §5). For the POC slice it's a hand-
curated map of common UK pharma promotional acronyms — sufficient to
prove the Layer 3 verdict shape end-to-end without library infra.

Each entry carries:
- `expansion`: the canonical long form
- `coverage`: fraction of approved UK assets that defined it this way
- `n`: sample size the coverage is computed over
- `pattern_id`: stable id used in `Zone.pattern_base`
- `window_months`: time window the coverage was observed over

When the live glossary lands, this module's API stays the same; only
`_GLOSSARY` swaps out for a loader that reads from the library snapshot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class GlossaryEntry:
    acronym: str
    expansion: str
    coverage: float
    n: int
    window_months: int
    pattern_id: str


_GLOSSARY: dict[str, GlossaryEntry] = {
    e.acronym: e
    for e in [
        # ── general pharmacovigilance / clinical ─────────────────────
        GlossaryEntry("AE", "adverse event", 0.97, 312, 24, "uk_glossary_general_AE"),
        GlossaryEntry("SAE", "serious adverse event", 0.94, 287, 24, "uk_glossary_general_SAE"),
        GlossaryEntry("ADR", "adverse drug reaction", 0.91, 264, 24, "uk_glossary_general_ADR"),
        GlossaryEntry("PV", "pharmacovigilance", 0.86, 198, 24, "uk_glossary_general_PV"),
        GlossaryEntry("HCP", "healthcare professional", 0.99, 312, 24, "uk_glossary_general_HCP"),
        GlossaryEntry("MAH", "Marketing Authorisation Holder", 0.96, 305, 24, "uk_glossary_general_MAH"),
        GlossaryEntry("SmPC", "Summary of Product Characteristics", 0.95, 298, 24, "uk_glossary_general_SmPC"),
        GlossaryEntry("PI", "Prescribing Information", 0.92, 281, 24, "uk_glossary_general_PI"),
        GlossaryEntry("ISI", "Important Safety Information", 0.88, 245, 24, "uk_glossary_general_ISI"),
        GlossaryEntry("SOC", "standard of care", 0.83, 213, 18, "uk_glossary_general_SOC"),
        # ── statistics + endpoints ───────────────────────────────────
        GlossaryEntry("HR", "hazard ratio", 0.96, 287, 18, "uk_glossary_stat_HR"),
        GlossaryEntry("CI", "confidence interval", 0.96, 287, 18, "uk_glossary_stat_CI"),
        GlossaryEntry("OS", "overall survival", 0.94, 273, 18, "uk_glossary_endpoint_OS"),
        GlossaryEntry("PFS", "progression-free survival", 0.93, 268, 18, "uk_glossary_endpoint_PFS"),
        GlossaryEntry("ORR", "objective response rate", 0.91, 251, 18, "uk_glossary_endpoint_ORR"),
        GlossaryEntry("DOR", "duration of response", 0.87, 224, 18, "uk_glossary_endpoint_DOR"),
        GlossaryEntry("CR", "complete response", 0.85, 218, 18, "uk_glossary_endpoint_CR"),
        GlossaryEntry("PR", "partial response", 0.84, 215, 18, "uk_glossary_endpoint_PR"),
        GlossaryEntry("iDFS", "invasive disease-free survival", 0.78, 142, 18, "uk_glossary_endpoint_iDFS"),
        GlossaryEntry("RFS", "recurrence-free survival", 0.76, 134, 18, "uk_glossary_endpoint_RFS"),
        # ── disease areas / treatments (oncology bias of pilot corpus) ─
        GlossaryEntry("ET", "endocrine therapy", 0.82, 198, 18, "uk_glossary_treatment_ET"),
        GlossaryEntry("AI", "aromatase inhibitor", 0.79, 184, 18, "uk_glossary_treatment_AI"),
        GlossaryEntry("BC", "breast cancer", 0.81, 192, 18, "uk_glossary_disease_BC"),
        GlossaryEntry("mBC", "metastatic breast cancer", 0.78, 178, 18, "uk_glossary_disease_mBC"),
        GlossaryEntry("HR+", "hormone receptor-positive", 0.77, 174, 18, "uk_glossary_biomarker_HRpos"),
        GlossaryEntry("HER2-", "human epidermal growth factor receptor 2-negative", 0.74, 165, 18, "uk_glossary_biomarker_HER2neg"),
        GlossaryEntry("HER2+", "human epidermal growth factor receptor 2-positive", 0.74, 165, 18, "uk_glossary_biomarker_HER2pos"),
        GlossaryEntry("MF", "myelofibrosis", 0.71, 152, 18, "uk_glossary_disease_MF"),
        GlossaryEntry("PV", "polycythaemia vera", 0.69, 148, 18, "uk_glossary_disease_PV_pcv"),  # NB: shadows the PV above; canonical-list resolution at lookup time uses the FIRST match
        GlossaryEntry("UC", "ulcerative colitis", 0.72, 156, 18, "uk_glossary_disease_UC"),
        GlossaryEntry("CD", "Crohn's disease", 0.71, 154, 18, "uk_glossary_disease_CD"),
        GlossaryEntry("IBD", "inflammatory bowel disease", 0.74, 162, 18, "uk_glossary_disease_IBD"),
    ]
}

# `PV` collides — the dataclass dict-comp keeps the LAST entry. In the
# live system disambiguation is therapeutic-area-aware (per asset
# brand/indication metadata). For the POC keep the general
# pharmacovigilance reading explicit so KISQALI assets resolve correctly.
_GLOSSARY["PV"] = GlossaryEntry(
    "PV", "pharmacovigilance", 0.86, 198, 24, "uk_glossary_general_PV"
)


# ─── acronym extraction ──────────────────────────────────────────────
#
# An acronym candidate is:
#   - 2–8 chars (counting the optional leading lowercase `i` for things
#     like `iDFS`, but NOT counting trailing biomarker suffix `+/-` or
#     plural `s`)
#   - Starts with an uppercase letter (or `i` followed by uppercase)
#   - Body chars are uppercase letters or digits
#   - Optional trailing `+` or `-` (HR+, HER2-)
#   - Optional trailing lowercase `s` for plurals (AEs, SAEs)
#   - Optional ® or ™ (signals brand, NOT acronym)
#
# Filters applied:
#   - Common-English stopwords (THE, AND, FOR, …)
#   - Document-level brand set (any token EVER followed by ® or ™ in
#     this asset is treated as a brand for ALL its occurrences)
#   - Caller-supplied `brand_tokens` (typically the asset's brand metadata)
#   - Roman numerals up to XII (Phase III etc.)
#
# Plural `s` is stripped from the canonical form: `AEs` → `AE`.
# Biomarker suffix `+`/`-` is preserved: `HR+` stays `HR+`.


_ACRONYM_RE = re.compile(
    r"(?<![A-Za-z0-9])"          # left boundary: no preceding letter/digit
    r"(i?[A-Z][A-Z0-9]{1,6})"    # group 1: core (2–8 chars incl. optional `i`)
    r"([+-])?"                   # group 2: biomarker suffix
    r"(s)?"                      # group 3: plural marker (stripped)
    r"(®|™)?"                    # group 4: trademark (signals brand)
    r"(?![A-Za-z0-9])"           # right boundary
)

_COMMON_WORDS_BLOCK = frozenset({
    "I", "A", "AN", "THE", "AND", "FOR", "OR", "OF", "TO", "IN", "ON", "BY",
    "AS", "AT", "BE", "IS", "IT", "WAS", "WERE", "BEEN", "ARE", "HAS", "HAD",
    "MAY", "CAN", "WILL", "ALL", "NEW", "USE", "USED", "SEE", "VS", "PER",
    "LTD", "INC", "PLC", "GMBH", "BV", "SA",  # legal entity stubs
    # Roman numerals up to XII (trial phases, etc.)
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
})


def extract_acronym_candidates(
    text: str,
    brand_tokens: Iterable[str] = (),
) -> list[tuple[str, int]]:
    """
    Returns `[(canonical_acronym, count), …]` in first-appearance order.

    Args:
      text: extracted block text.
      brand_tokens: tokens that should always be filtered as brand
        (typically `[asset.meta.brand]` plus any in-asset brand
        dictionary). Comparison is case-insensitive against the bare
        token (no suffix, no plural).

    Document-level brand inference: any token observed followed by ®
    or ™ anywhere in `text` is added to a per-call brand set; ALL
    occurrences of that bare token are then filtered (so subsequent
    bare-name mentions of `KISQALI` are filtered too).
    """
    explicit_brands = {b.upper() for b in brand_tokens}

    # ── pass 1: collect document-level brand tokens (anything ®/™-marked)
    document_brands: set[str] = set()
    for match in _ACRONYM_RE.finditer(text):
        if match.group(4):  # ® or ™ present
            document_brands.add(match.group(1).upper())

    # ── pass 2: tally candidates, filtering brands + stopwords
    counts: dict[str, int] = {}
    order: list[str] = []
    for match in _ACRONYM_RE.finditer(text):
        bare = match.group(1)
        suffix = match.group(2) or ""
        canonical = bare + suffix

        bare_upper = bare.upper()
        if bare_upper in document_brands or bare_upper in explicit_brands:
            continue
        if canonical in _COMMON_WORDS_BLOCK or bare in _COMMON_WORDS_BLOCK:
            continue
        if canonical not in counts:
            order.append(canonical)
        counts[canonical] = counts.get(canonical, 0) + 1
    return [(tok, counts[tok]) for tok in order]


def lookup(acronym: str) -> Optional[GlossaryEntry]:
    """Resolve an acronym to its canonical entry. Returns None if unknown."""
    return _GLOSSARY.get(acronym)


def all_known_acronyms() -> list[str]:
    """For tests / debugging."""
    return sorted(_GLOSSARY.keys())
