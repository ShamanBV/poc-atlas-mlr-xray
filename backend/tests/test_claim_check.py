"""Layer 1 (claim_check) — drift / clean / no-candidate paths."""

import pytest

from mlr.fixtures import assets as fixture_assets
from mlr.precheck import claim_check
from mlr.precheck.schema import (
    AssetMeta,
    ExtractedAsset,
    ExtractedModule,
)


def _asset(modules: list[ExtractedModule], brand="KISQALI", market="UK") -> ExtractedAsset:
    return ExtractedAsset(
        asset_id="tmp:test",
        meta=AssetMeta(
            brand=brand,
            market=market,
            language="en",
            doc_type="email",
            channel="HCP email",
        ),
        profile_id="UK-Branded-Promotional",
        modules=modules,
        blocks=[],
        supportive_resources=[],
        envelope={},
    )


# Canonical claim text from the library (UK / KISQALI / EFFICACY pattern).
_CANONICAL_KISQALI_EFFICACY = (
    "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% "
    "vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014)."
)


# ─── isolated paths ──────────────────────────────────────────────────


def test_clean_match_when_text_identical_to_canonical():
    asset = _asset(modules=[
        ExtractedModule(
            id="m1",
            claim=True,
            subtype="EFFICACY",
            synthesized_text=_CANONICAL_KISQALI_EFFICACY,
            block_ids=["blk_002"],
        ),
    ])
    verdicts = claim_check.run(asset)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.layer == "claim"
    assert v.sub_layer == "claim:efficacy"
    assert v.status == "clean"
    assert v.severity == "info"
    assert v.diff is None
    assert v.canonical_content == _CANONICAL_KISQALI_EFFICACY


def test_drift_when_text_drifts_slightly():
    """The fixture's claim is a drift case vs the canonical — should be warn/attn."""
    drifted = (
        "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
        "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
    )
    asset = _asset(modules=[
        ExtractedModule(
            id="m1", claim=True, subtype="EFFICACY",
            synthesized_text=drifted, block_ids=["blk_002"],
        ),
    ])
    verdicts = claim_check.run(asset)
    v = verdicts[0]
    assert v.status == "attn"
    assert v.severity == "warn"
    assert v.diff is not None and len(v.diff) > 0
    assert v.canonical_content == _CANONICAL_KISQALI_EFFICACY
    assert v.extracted_content == drifted


def test_block_when_no_close_match():
    """A novel claim with no close canonical → status:miss / severity:block."""
    novel = (
        "Patients reported subjective wellbeing improvements during the open-label phase."
    )
    asset = _asset(modules=[
        ExtractedModule(
            id="m1", claim=True, subtype="EFFICACY",
            synthesized_text=novel, block_ids=["blk_002"],
        ),
    ])
    verdicts = claim_check.run(asset)
    v = verdicts[0]
    assert v.status == "miss"
    assert v.severity == "block"
    assert v.diff is not None  # still useful so reviewers can see the gap


def test_no_verdict_when_no_library_candidates():
    """Brand without library entries → no verdict (don't false-positive on novel)."""
    asset = _asset(
        brand="UNKNOWN_BRAND",
        modules=[
            ExtractedModule(
                id="m1", claim=True, subtype="EFFICACY",
                synthesized_text="Any text", block_ids=["b1"],
            ),
        ],
    )
    assert claim_check.run(asset) == []


def test_non_claim_modules_skipped():
    """Modules without claim=True are not evaluated (e.g. pure-context modules)."""
    asset = _asset(modules=[
        ExtractedModule(
            id="m1", claim=False, subtype="CONTEXT",
            synthesized_text="Context-only module — not a claim.",
        ),
    ])
    assert claim_check.run(asset) == []


def test_pattern_base_attached_to_drift_verdict():
    drifted = (
        "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
        "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
    )
    asset = _asset(modules=[
        ExtractedModule(id="m1", claim=True, subtype="EFFICACY", synthesized_text=drifted),
    ])
    v = claim_check.run(asset)[0]
    pb = v.pattern_base
    assert pb is not None
    assert pb.pattern_id == "uk_email_efficacy_HR_CI"
    assert 0 < pb.coverage <= 1
    assert pb.n > 0


def test_vvpm_anchor_derived_from_first_block_id():
    drifted = "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% vs ET alone."
    asset = _asset(modules=[
        ExtractedModule(
            id="m1", claim=True, subtype="EFFICACY",
            synthesized_text=drifted, block_ids=["blk_002", "blk_002a"],
        ),
    ])
    v = claim_check.run(asset)[0]
    assert v.vvpm_anchor == "anchor_blk_002"


def test_thresholds_can_be_overridden_per_call():
    """Tests pin behaviour via threshold args without monkey-patching constants."""
    drifted = (
        "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
        "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
    )
    asset = _asset(modules=[
        ExtractedModule(id="m1", claim=True, subtype="EFFICACY", synthesized_text=drifted),
    ])
    # With a clean_min of 0.50, the drift case (~0.97) should now read as clean.
    v_clean = claim_check.run(asset, clean_min=0.50, drift_min=0.10)[0]
    assert v_clean.status == "clean"

    # With a drift_min of 0.99, the drift case (~0.97) should drop to miss.
    v_miss = claim_check.run(asset, clean_min=1.01, drift_min=0.99)[0]
    assert v_miss.status == "miss"


def test_best_of_candidates_selected():
    """When multiple library variants match, the engine picks the best score."""
    # The library has two EFFICACY variants — one near-canonical, one
    # older phrasing. The fixture's claim is closer to the primary; the
    # verdict's canonical_content should be the primary canonical.
    fixture_asset = fixture_assets.get("tmp:demo-kisqali-uk-001")
    assert fixture_asset is not None
    verdicts = claim_check.run(fixture_asset)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert "disease recurrence by 25.2%" in v.canonical_content
    # The "older phrasing" variant should NOT win.
    assert "versus ET alone at 5 years" not in v.canonical_content


# ─── end-to-end against the fixture ──────────────────────────────────


def test_kisqali_fixture_emits_efficacy_drift_zone():
    asset = fixture_assets.get("tmp:demo-kisqali-uk-001")
    verdicts = claim_check.run(asset)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.layer == "claim"
    assert v.sub_layer == "claim:efficacy"
    assert v.status == "attn"
    assert v.severity == "warn"
    assert v.diff is not None and len(v.diff) > 0
    # Diff invariants per `word_diff` contract:
    rebuilt_extracted = "".join(s.t for s in v.diff if s.s != "a")
    rebuilt_canonical = "".join(s.t for s in v.diff if s.s != "d")
    assert rebuilt_extracted == v.extracted_content
    assert rebuilt_canonical == v.canonical_content
