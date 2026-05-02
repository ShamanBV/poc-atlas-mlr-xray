"""Glossary lookup + acronym extraction filters."""

from mlr.precheck.glossary import (
    all_known_acronyms,
    extract_acronym_candidates,
    lookup,
)


def test_known_acronym_lookup():
    entry = lookup("AE")
    assert entry is not None
    assert entry.expansion == "adverse event"
    assert entry.pattern_id == "uk_glossary_general_AE"


def test_unknown_acronym_returns_none():
    assert lookup("NOTREAL") is None


def test_glossary_contains_oncology_endpoints():
    known = all_known_acronyms()
    for required in ("OS", "PFS", "ORR", "HR", "CI"):
        assert required in known


def test_extracts_simple_acronyms():
    text = "AE was reported. ORR was 50%. OS data continue to mature."
    results = dict(extract_acronym_candidates(text))
    assert results == {"AE": 1, "ORR": 1, "OS": 1}


def test_acronym_counts_repeats():
    text = "AE, AE, AE — three AEs in this sentence."
    results = dict(extract_acronym_candidates(text))
    # `AEs` is canonicalised to `AE` (plural-s is stripped), so the
    # final count is 4: three bare `AE` plus one from `AEs`.
    assert results["AE"] == 4


def test_filters_brand_tokens_marked_with_registered_symbol():
    """A token followed by ® anywhere in the doc is treated as brand for
    ALL its occurrences."""
    text = "KISQALI® showed efficacy. KISQALI continued to mature. The AE rate was low."
    results = dict(extract_acronym_candidates(text))
    assert "KISQALI" not in results
    assert "AE" in results


def test_filters_explicit_brand_tokens_arg():
    """Brand passed via brand_tokens filters even without ®."""
    text = "ENTRESTO improved outcomes. The AE rate was low."
    results = dict(extract_acronym_candidates(text, brand_tokens=["ENTRESTO"]))
    assert "ENTRESTO" not in results
    assert "AE" in results


def test_filters_brand_tokens():
    """KISQALI is 7 uppercase chars — must NOT be flagged as an acronym."""
    text = "KISQALI® showed efficacy. The AE rate was low."
    results = dict(extract_acronym_candidates(text))
    assert "KISQALI" not in results
    assert "AE" in results


def test_filters_common_english_stopwords():
    text = "AND OR THE FOR — none of these should be flagged."
    results = dict(extract_acronym_candidates(text))
    assert results == {}


def test_filters_roman_numerals():
    text = "Phase III trial; Phase IV follow-up."
    results = dict(extract_acronym_candidates(text))
    assert "III" not in results
    assert "IV" not in results


def test_handles_biomarker_suffixes():
    """HR+ and HER2- are oncology-standard tokens with trailing +/-."""
    text = "Patients with HR+/HER2- early breast cancer."
    results = dict(extract_acronym_candidates(text))
    assert "HR+" in results or "HR" in results  # depends on the regex preferring greedy
    assert "HER2-" in results or "HER2" in results


def test_extraction_preserves_first_appearance_order():
    text = "First we saw OS; then PFS; finally ORR."
    candidates = extract_acronym_candidates(text)
    tokens = [c[0] for c in candidates]
    assert tokens == ["OS", "PFS", "ORR"]
