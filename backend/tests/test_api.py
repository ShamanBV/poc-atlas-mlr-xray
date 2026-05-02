"""FastAPI route smoke tests."""

from fastapi.testclient import TestClient

from mlr.precheck.api import app


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "tmp:demo-kisqali-uk-001" in body["fixtures"]


def test_precheck_returns_asset_payload():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    assert r.status_code == 200, r.text
    asset = r.json()

    # Top-level shape per API contract §2.1
    for key in (
        "asset_id", "schema_version", "meta", "identity", "profile",
        "scores", "verdict", "zones", "email_blocks", "library",
        "preview", "generated_at", "cache_key",
    ):
        assert key in asset, f"missing top-level key: {key}"

    assert asset["schema_version"] == "1.0"
    assert asset["meta"]["brand"] == "KISQALI"
    assert asset["meta"]["market"] == "UK"
    assert "KISQALI" in asset["identity"]
    assert "UK-Branded-Promotional" in asset["identity"]
    assert "FA-11551654" in asset["identity"]


def test_precheck_emits_abbreviation_zones():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    asset = r.json()
    abbreviation_zones = [z for z in asset["zones"] if z["layer"] == "abbreviation"]
    sub_layers = {z["sub_layer"] for z in abbreviation_zones}
    assert "abbreviation:AE" in sub_layers
    assert "abbreviation:ORR" in sub_layers


def test_zone_has_required_contract_fields():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    asset = r.json()
    abbreviation_zones = [z for z in asset["zones"] if z["layer"] == "abbreviation"]
    assert abbreviation_zones, "expected at least one abbreviation zone"
    z = abbreviation_zones[0]
    for key in (
        "id", "doc_pos", "label", "lanes", "status", "severity",
        "layer", "sub_layer", "evidence", "evidence_detail",
        "extracted_content", "canonical_content", "diff",
        "pattern_base", "dependencies_triggered", "annotation_draft",
        "vvpm_anchor", "pin",
    ):
        assert key in z, f"zone missing field: {key}"


def test_dependency_trigger_shape():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    asset = r.json()
    z = next(z for z in asset["zones"] if z["sub_layer"] == "abbreviation:AE")
    deps = z["dependencies_triggered"]
    assert len(deps) == 1
    d = deps[0]
    assert d["rule_id"] == "r_abbreviations_defined"
    assert "AE" in d["predicate"]
    assert d["coverage"]["confidence_label"] in ("high", "medium", "low")


def test_404_on_unknown_asset_id():
    r = client.get("/api/precheck/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    # FastAPI default wraps in {"detail": ...}; our error envelope is at detail.error.
    assert body["detail"]["error"]["code"] == "asset_not_found"


def test_scores_within_bounds():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    asset = r.json()
    for k in ("overall", "medical", "legal", "regulatory"):
        assert 0 <= asset["scores"][k] <= 100


def test_verdict_label_consistent_with_severities():
    r = client.get("/api/precheck/tmp:demo-kisqali-uk-001")
    asset = r.json()
    severities = {z["severity"] for z in asset["zones"] if z["status"] != "clean"}
    if "block" in severities:
        assert asset["verdict"] == "Fail"
    elif "warn" in severities:
        assert asset["verdict"] == "Warn"
    else:
        assert asset["verdict"] == "Pass"
