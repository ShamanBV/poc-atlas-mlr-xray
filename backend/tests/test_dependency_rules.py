"""Predicate evaluator + YAML loader for dependency_rules.yaml."""

import pytest

from mlr.precheck.dependency_rules import (
    evaluate,
    load_default_catalog,
)
from mlr.precheck.schema import (
    AssetMeta,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedFragment,
    ExtractedModule,
    SupportiveResource,
)


# ─── helpers ─────────────────────────────────────────────────────────


def _asset(
    *,
    profile: str = "UK-Branded-Promotional",
    market: str = "UK",
    doc_type: str = "email",
    language: str = "en",
    blocks: list[ExtractedBlock] | None = None,
    modules: list[ExtractedModule] | None = None,
    resources: list[SupportiveResource] | None = None,
    envelope: dict | None = None,
) -> ExtractedAsset:
    return ExtractedAsset(
        asset_id="tmp:test",
        meta=AssetMeta(
            brand="TESTBRAND",
            market=market,
            language=language,
            doc_type=doc_type,  # type: ignore[arg-type]
            channel="HCP email",
        ),
        profile_id=profile,
        modules=modules or [],
        blocks=blocks or [],
        supportive_resources=resources or [],
        envelope=envelope or {},
    )


# ─── catalog loader ──────────────────────────────────────────────────


def test_default_catalog_loads():
    catalog = load_default_catalog()
    assert catalog.schema_version == "1.0"
    assert len(catalog.rules) >= 17  # 4 medical + 5 legal + 11 regulatory
    rule_ids = {r.id for r in catalog.rules}
    assert "r_audience_bar_when_hcp_only_profile" in rule_ids
    assert "r_abbreviations_defined" in rule_ids
    assert "r_safety_reminder_after_efficacy_claim" in rule_ids


def test_catalog_pillars_assigned():
    catalog = load_default_catalog()
    by_id = {r.id: r for r in catalog.rules}
    assert by_id["r_safety_reminder_after_efficacy_claim"].pillar == "medical"
    assert by_id["r_unsubscribe_privacy_links"].pillar == "legal"
    assert by_id["r_audience_bar_when_hcp_only_profile"].pillar == "regulatory"


def test_coverage_confidence_label_low_when_corpus_empty():
    catalog = load_default_catalog()
    rule = next(r for r in catalog.rules if r.coverage.minimum > 0)
    assert rule.coverage.confidence_label == "low"


# ─── leaf evaluators ─────────────────────────────────────────────────


def test_eval_profile_in():
    asset = _asset(profile="UK-Branded-Promotional")
    assert evaluate({"profile_in": ["UK-Branded-Promotional"]}, asset) is True
    assert evaluate({"profile_in": ["IE-Branded-Promotional"]}, asset) is False


def test_eval_market_in():
    asset = _asset(market="UK")
    assert evaluate({"market_in": ["UK", "IE"]}, asset) is True
    assert evaluate({"market_in": ["DE"]}, asset) is False


def test_eval_doc_type_in():
    asset = _asset(doc_type="email")
    assert evaluate({"doc_type_in": ["email", "slide"]}, asset) is True
    assert evaluate({"doc_type_in": ["leave_behind"]}, asset) is False


def test_eval_envelope_present():
    asset = _asset(envelope={"audience_restriction": "FOR UK HCP ONLY"})
    assert evaluate({"envelope": {"key": "audience_restriction", "present": True}}, asset) is True
    assert evaluate({"envelope": {"key": "indication", "present": True}}, asset) is False


def test_eval_envelope_text_matches():
    asset = _asset(envelope={"approval_info": "FA-11551654 · March 2026"})
    assert evaluate({"envelope": {"key": "approval_info", "text_matches": r"FA-\d{8}"}}, asset) is True
    assert evaluate({"envelope": {"key": "approval_info", "text_matches": r"MAT-UK-"}}, asset) is False


def test_eval_supportive_resource_present():
    asset = _asset(resources=[
        SupportiveResource(type="abbreviation-set", members=[{"acronym": "AE"}]),
    ])
    assert evaluate({"supportive_resource": {"type": "abbreviation-set", "present": True}}, asset) is True
    assert evaluate({"supportive_resource": {"type": "reference-set", "present": True}}, asset) is False


def test_eval_supportive_resource_member_count():
    asset = _asset(resources=[
        SupportiveResource(type="abbreviation-set", members=[{"acronym": "AE"}]),
    ])
    assert evaluate({"supportive_resource": {"type": "abbreviation-set", "member_count_min": 1}}, asset) is True
    assert evaluate({"supportive_resource": {"type": "abbreviation-set", "member_count_min": 5}}, asset) is False


def test_eval_any_block_role_in():
    asset = _asset(blocks=[
        ExtractedBlock(id="b1", role="CLAIM", text="A claim"),
    ])
    assert evaluate({"any_block": {"role_in": ["CLAIM"]}}, asset) is True
    assert evaluate({"any_block": {"role_in": ["FOOTNOTE"]}}, asset) is False


def test_eval_any_block_text_matches():
    asset = _asset(blocks=[
        ExtractedBlock(id="b1", role="BODY", text="Once-daily oral dosing"),
    ])
    pred = {"any_block": {"text_matches": r"\bdosing\b"}}
    assert evaluate(pred, asset) is True


def test_eval_any_block_external_link_detection():
    asset = _asset(blocks=[
        ExtractedBlock(id="b1", role="BODY", text="See https://example.com for details."),
    ])
    assert evaluate({"any_block": {"has_external_link": True}}, asset) is True

    asset2 = _asset(blocks=[
        ExtractedBlock(id="b1", role="BODY", text="No links here."),
    ])
    assert evaluate({"any_block": {"has_external_link": True}}, asset2) is False


def test_eval_any_module_subtype_in():
    asset = _asset(modules=[
        ExtractedModule(id="m1", claim=True, subtype="EFFICACY", synthesized_text="text"),
    ])
    assert evaluate({"any_module": {"subtype_in": ["EFFICACY"]}}, asset) is True
    assert evaluate({"any_module": {"subtype_in": ["SAFETY"]}}, asset) is False


def test_eval_any_module_text_matches():
    asset = _asset(modules=[
        ExtractedModule(
            id="m1",
            claim=True,
            subtype="EFFICACY",
            synthesized_text="HR 0.748, 95% CI 0.618–0.906; p=0.0014",
        ),
    ])
    pred = {"any_module": {"claim": True, "text_matches": r"HR|95%\s*CI"}}
    assert evaluate(pred, asset) is True


def test_eval_any_fragment_role_in():
    asset = _asset(modules=[
        ExtractedModule(
            id="m1",
            fragments=[
                ExtractedFragment(role="claim", text="x"),
                ExtractedFragment(role="evidence", text="y"),
            ],
        ),
    ])
    assert evaluate({"any_fragment": {"role_in": ["evidence"]}}, asset) is True
    assert evaluate({"any_fragment": {"role_in": ["source"]}}, asset) is False


# ─── composition ─────────────────────────────────────────────────────


def test_eval_all_of():
    asset = _asset(market="UK", doc_type="email")
    pred = {"all_of": [
        {"market_in": ["UK"]},
        {"doc_type_in": ["email"]},
    ]}
    assert evaluate(pred, asset) is True

    pred_fail = {"all_of": [
        {"market_in": ["UK"]},
        {"doc_type_in": ["slide"]},
    ]}
    assert evaluate(pred_fail, asset) is False


def test_eval_any_of():
    asset = _asset(market="UK")
    pred = {"any_of": [
        {"market_in": ["DE"]},
        {"market_in": ["UK"]},
    ]}
    assert evaluate(pred, asset) is True

    pred_fail = {"any_of": [
        {"market_in": ["DE"]},
        {"market_in": ["IT"]},
    ]}
    assert evaluate(pred_fail, asset) is False


def test_eval_not():
    asset = _asset(market="UK")
    assert evaluate({"not": {"market_in": ["DE"]}}, asset) is True
    assert evaluate({"not": {"market_in": ["UK"]}}, asset) is False


def test_eval_empty_predicate_is_true():
    """An empty / None predicate should evaluate to True (rule fires
    unconditionally, or `requires` is always satisfied)."""
    asset = _asset()
    assert evaluate(None, asset) is True
    assert evaluate({}, asset) is True


def test_eval_unknown_node_raises():
    with pytest.raises(ValueError):
        evaluate({"unknown_predicate": True}, _asset())
