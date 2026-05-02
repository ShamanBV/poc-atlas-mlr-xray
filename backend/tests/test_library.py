"""Approved-claim library lookup."""

from mlr.precheck import library


def test_total_size_nonzero():
    assert library.total_size() > 0


def test_find_candidates_filters_by_brand_market_subtype():
    cands = library.find_candidates("KISQALI", "UK", "EFFICACY")
    assert all(c.brand == "KISQALI" and c.market == "UK" and c.subtype == "EFFICACY" for c in cands)
    assert len(cands) >= 1


def test_find_candidates_returns_empty_for_unknown_subtype():
    assert library.find_candidates("KISQALI", "UK", "NOT_A_REAL_SUBTYPE") == []


def test_find_candidates_returns_empty_for_unknown_market():
    assert library.find_candidates("KISQALI", "NZ", "EFFICACY") == []


def test_find_candidates_handles_none_subtype():
    """Modules with unclassified subtype should yield no candidates."""
    assert library.find_candidates("KISQALI", "UK", None) == []


def test_lookup_pattern_returns_first_variant():
    entry = library.lookup_pattern("uk_email_efficacy_HR_CI")
    assert entry is not None
    assert entry.pattern_id == "uk_email_efficacy_HR_CI"


def test_lookup_pattern_returns_none_when_unknown():
    assert library.lookup_pattern("not_a_pattern") is None


def test_coverage_warning_below_threshold():
    msg = library.coverage_warning_for_size(5, threshold=20)
    assert msg is not None
    assert "5" in msg
    assert "20" in msg


def test_coverage_warning_above_threshold_is_none():
    assert library.coverage_warning_for_size(50, threshold=20) is None
