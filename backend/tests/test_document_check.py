"""Layer 2 (document_check) — end-to-end against the catalog."""

from mlr.fixtures import assets as fixture_assets
from mlr.precheck import document_check
from mlr.precheck.dependency_rules import (
    Rule,
    RuleCatalog,
    RuleCoverage,
    load_default_catalog,
)
from mlr.precheck.schema import (
    AssetMeta,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedModule,
    SupportiveResource,
)


def _make_asset(**kw) -> ExtractedAsset:
    base = dict(
        asset_id="tmp:test",
        meta=AssetMeta(
            brand="TEST",
            market="UK",
            language="en",
            doc_type="email",
            channel="HCP email",
        ),
        profile_id="UK-Branded-Promotional",
        modules=[],
        blocks=[],
        supportive_resources=[],
        envelope={},
    )
    base.update(kw)
    return ExtractedAsset(**base)


def _catalog_with(rules: list[Rule]) -> RuleCatalog:
    return RuleCatalog(
        schema_version="1.0",
        catalog_version="test",
        default_severity_when_unmet="warn",
        rules=tuple(rules),
    )


# ─── isolated rule firing ────────────────────────────────────────────


def test_rule_fires_when_predicate_true_and_requires_false():
    """An audience-bar-style rule on an asset missing the envelope key."""
    rule = Rule(
        id="r_test_audience",
        pillar="regulatory",
        description="HCP profile must show audience bar.",
        severity="block",
        rationale="ABPI 26.1.",
        predicate={"profile_in": ["UK-Branded-Promotional"]},
        requires={"envelope": {"key": "audience_restriction", "present": True}},
        coverage=RuleCoverage(0, 10),
    )
    asset = _make_asset(envelope={})
    verdicts = document_check.run(asset, _catalog_with([rule]))
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.layer == "regulatory"
    assert v.sub_layer == "regulatory:r_test_audience"
    assert v.status == "miss"
    assert v.severity == "block"
    assert v.lanes == ["R"]
    assert v.dependencies_triggered[0].rule_id == "r_test_audience"


def test_rule_does_not_fire_when_predicate_false():
    rule = Rule(
        id="r_test",
        pillar="regulatory",
        description="-",
        severity="warn",
        rationale="-",
        predicate={"profile_in": ["IE-Branded-Promotional"]},  # mismatch
        requires={"envelope": {"key": "anything", "present": True}},
    )
    asset = _make_asset(profile_id="UK-Branded-Promotional")
    assert document_check.run(asset, _catalog_with([rule])) == []


def test_rule_does_not_fire_when_requires_satisfied():
    rule = Rule(
        id="r_test",
        pillar="regulatory",
        description="-",
        severity="warn",
        rationale="-",
        predicate={"doc_type_in": ["email"]},
        requires={"envelope": {"key": "indication", "present": True}},
    )
    asset = _make_asset(envelope={"indication": "Indicated for X."})
    assert document_check.run(asset, _catalog_with([rule])) == []


def test_lane_assigned_from_pillar():
    """Each pillar maps to a single lane."""
    for pillar, lane in [("medical", "M"), ("legal", "L"), ("regulatory", "R")]:
        rule = Rule(
            id=f"r_{pillar}_test",
            pillar=pillar,
            description="-",
            severity="warn",
            rationale="-",
            predicate={},
            requires={"envelope": {"key": "missing", "present": True}},
        )
        verdicts = document_check.run(_make_asset(), _catalog_with([rule]))
        assert verdicts[0].lanes == [lane]
        assert verdicts[0].sub_layer.startswith(f"{pillar}:")


def test_dependency_trigger_carries_coverage():
    rule = Rule(
        id="r_cov_test",
        pillar="medical",
        description="-",
        severity="warn",
        rationale="-",
        predicate={},
        requires={"envelope": {"key": "missing", "present": True}},
        coverage=RuleCoverage(corpus_size_observed=8, minimum=10),  # → "medium"
    )
    verdicts = document_check.run(_make_asset(), _catalog_with([rule]))
    cov = verdicts[0].dependencies_triggered[0].coverage
    assert cov.predicate_hits_in_corpus == 8
    assert cov.confidence_label == "medium"


# ─── end-to-end against the live catalog + KISQALI fixture ───────────


def test_kisqali_fixture_emits_expected_layer2_zones():
    asset = fixture_assets.get("tmp:demo-kisqali-uk-001")
    assert asset is not None
    catalog = load_default_catalog()
    verdicts = document_check.run(asset, catalog)

    rule_ids_fired = {
        d.rule_id
        for v in verdicts
        for d in v.dependencies_triggered
    }

    # Intentionally absent in the fixture → Layer 2 should fire these:
    assert "r_audience_bar_when_hcp_only_profile" in rule_ids_fired
    assert "r_safety_reminder_after_efficacy_claim" in rule_ids_fired

    # Present in the fixture → Layer 2 should NOT fire these:
    assert "r_indication_when_drug_named" not in rule_ids_fired       # envelope.indication present
    assert "r_ae_reporting_when_promotional" not in rule_ids_fired    # envelope.pharmacovigilance
    assert "r_unsubscribe_privacy_links" not in rule_ids_fired        # privacy text matches
    assert "r_approval_code_format" not in rule_ids_fired             # FA-11551654 matches
    assert "r_mah_legal_entity_in_footer" not in rule_ids_fired       # CONTACT_INFO present
    assert "r_brand_mark_registered" not in rule_ids_fired            # KISQALI® present
    assert "r_prescribing_info_link" not in rule_ids_fired            # envelope.prescribing_information
    assert "r_reference_list_complete" not in rule_ids_fired          # reference-set has 1 entry
    assert "r_abbreviations_defined" not in rule_ids_fired            # abbreviation-set has 5 entries
    assert "r_trial_design_footnote_when_data_cited" not in rule_ids_fired  # STUDY_DESIGN footnote present


def test_kisqali_fixture_layer2_severity_split():
    asset = fixture_assets.get("tmp:demo-kisqali-uk-001")
    catalog = load_default_catalog()
    verdicts = document_check.run(asset, catalog)
    by_id = {v.dependencies_triggered[0].rule_id: v for v in verdicts}

    assert by_id["r_audience_bar_when_hcp_only_profile"].severity == "block"
    assert by_id["r_safety_reminder_after_efficacy_claim"].severity == "warn"


def test_irrelevant_market_rules_do_not_fire():
    """IT and IE-specific rules must not fire on UK assets."""
    asset = fixture_assets.get("tmp:demo-kisqali-uk-001")
    catalog = load_default_catalog()
    verdicts = document_check.run(asset, catalog)
    rule_ids = {d.rule_id for v in verdicts for d in v.dependencies_triggered}
    assert "r_aifa_deposit_reference_for_italy" not in rule_ids
    assert "r_ie_reimbursement_note_when_marketed" not in rule_ids
