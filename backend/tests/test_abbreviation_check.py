"""Layer 3 abbreviation precheck — end-to-end against the KISQALI fixture."""

from mlr.fixtures import assets as fixture_assets
from mlr.precheck import abbreviation_check
from mlr.precheck.schema import (
    ExtractedAsset,
    ExtractedBlock,
    SupportiveResource,
)


def _empty_asset(
    blocks: list[ExtractedBlock],
    abbrev_members: list[dict] | None = None,
    brand: str = "TESTBRAND",
) -> ExtractedAsset:
    """Build a minimal ExtractedAsset for focused tests."""
    from mlr.precheck.schema import AssetMeta

    return ExtractedAsset(
        asset_id="tmp:test",
        meta=AssetMeta(
            brand=brand,
            market="UK",
            language="en",
            doc_type="email",
            channel="HCP email",
            code=None,
            prepared=None,
            age_days=None,
        ),
        profile_id="UK-Branded-Promotional",
        blocks=blocks,
        supportive_resources=[
            SupportiveResource(type="abbreviation-set", members=abbrev_members or []),
        ],
        envelope={},
    )


def test_no_findings_when_glossary_empty_text():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="Plain prose with no acronyms.")],
    )
    verdicts = abbreviation_check.run(asset)
    assert verdicts == []


def test_undefined_acronym_emits_warn_verdict():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="The AE rate was low.")],
        abbrev_members=[],
    )
    verdicts = abbreviation_check.run(asset)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.layer == "abbreviation"
    assert v.sub_layer == "abbreviation:AE"
    assert v.severity == "warn"
    assert v.status == "attn"
    assert v.lanes == ["M"]
    assert v.canonical_content == "AE — adverse event"


def test_defined_acronym_does_not_emit_verdict():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="The AE rate was low.")],
        abbrev_members=[{"acronym": "AE", "expansion": "adverse event"}],
    )
    assert abbreviation_check.run(asset) == []


def test_dependency_trigger_attached():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="ORR was the primary endpoint.")],
    )
    verdicts = abbreviation_check.run(asset)
    assert len(verdicts) == 1
    deps = verdicts[0].dependencies_triggered
    assert len(deps) == 1
    assert deps[0].rule_id == "r_abbreviations_defined"
    assert "ORR" in deps[0].predicate
    assert deps[0].coverage.confidence_label == "high"


def test_pattern_base_present_for_known_acronym():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="ORR analysis")],
    )
    verdicts = abbreviation_check.run(asset)
    pb = verdicts[0].pattern_base
    assert pb is not None
    assert pb.pattern_id == "uk_glossary_endpoint_ORR"
    assert pb.coverage > 0.5


def test_unknown_acronym_emits_verdict_without_pattern_base():
    asset = _empty_asset(
        blocks=[ExtractedBlock(id="b1", role="BODY", text="The XQVZ score was novel.")],
    )
    verdicts = abbreviation_check.run(asset)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.sub_layer == "abbreviation:XQVZ"
    assert v.canonical_content is None
    assert v.pattern_base is None


def test_brand_token_does_not_trigger_finding():
    """The asset's brand must not be flagged as an undefined acronym."""
    asset = _empty_asset(
        brand="KISQALI",
        blocks=[ExtractedBlock(id="b1", role="BODY", text="KISQALI showed efficacy.")],
    )
    assert abbreviation_check.run(asset) == []


def test_trademarked_token_filtered_even_with_mismatched_brand_meta():
    """
    Bare brand mention in body, brand metadata mismatched, but the brand
    appears with ® somewhere — document-pass should still filter it.
    """
    asset = _empty_asset(
        brand="OTHER",
        blocks=[
            ExtractedBlock(id="b1", role="HEADER", text="KISQALI® (ribociclib)"),
            ExtractedBlock(id="b2", role="BODY", text="KISQALI demonstrated efficacy."),
        ],
    )
    flagged = {v.sub_layer.split(":", 1)[-1] for v in abbreviation_check.run(asset)}
    assert "KISQALI" not in flagged


def test_only_body_roles_count():
    """Acronym only in a footnote does not trigger; only BODY/CLAIM/etc."""
    asset = _empty_asset(
        blocks=[
            ExtractedBlock(id="b1", role="FOOTNOTE", text="ABC was the cohort label."),
        ],
    )
    assert abbreviation_check.run(asset) == []


def test_kisqali_fixture_flags_expected_acronyms():
    """End-to-end against the shipped fixture."""
    extracted = fixture_assets.get("tmp:demo-kisqali-uk-001")
    assert extracted is not None
    verdicts = abbreviation_check.run(extracted)
    flagged = {v.sub_layer.split(":", 1)[-1] for v in verdicts}
    # The fixture defines HR / CI / OS / PFS / ET. AE / ORR are NOT defined →
    # they MUST be flagged.
    assert "AE" in flagged
    assert "ORR" in flagged
    # HR, CI, OS, PFS, ET are defined → MUST NOT be flagged.
    assert "HR" not in flagged
    assert "OS" not in flagged
    assert "PFS" not in flagged
    assert "ET" not in flagged
