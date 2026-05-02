"""Adapter from extractor-service JSON → ExtractedAsset."""

import pytest

from mlr.ingest.extractor_adapter import (
    _looks_like_reference_entry,
    _parse_abbreviation_block,
    adapt,
)


# ─── reference detection ─────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "6. McGagh D, Coates LC. Rheumatology (Oxford). 2020;59(Suppl 1):i29–i36.",
    "9. Henkemans SVJS et al. RMD Open. 2022;8(2):e002706.",
    "10. Coates LC et al. RMD Open. 2023;9(2):e002939.",
    "1. Slamon DJ et al. N Engl J Med. 2024;390:1080-1091.",
])
def test_reference_like_detected(text):
    assert _looks_like_reference_entry(text) is True


@pytest.mark.parametrize("text", [
    "Minimal disease activity (MDA) is emerging as a practical outcome measure",
    "PsA is a complex disease comprised of 6 key manifestations: joints",
    "Cosentyx is indicated for the treatment of: moderate to severe plaque psoriasis",
    "Click here to learn more",
    "",
    "1 simple sentence about something else",  # number without dot+capital follow-up
])
def test_reference_like_does_not_match_normal_body(text):
    assert _looks_like_reference_entry(text) is False


# ─── abbreviation block parsing ──────────────────────────────────────


def test_abbreviation_pairs_extracted():
    text = (
        "BSR=British Society for Rheumatology; "
        "EULAR=European Alliance of Associations for Rheumatology; "
        "MDA=minimal disease activity; MTX=methotrexate; "
        "PsA=psoriatic arthritis; PsO=psoriasis."
    )
    pairs = _parse_abbreviation_block(text)
    by_acronym = {p["acronym"]: p["expansion"] for p in pairs}
    assert by_acronym["BSR"] == "British Society for Rheumatology"
    assert by_acronym["MDA"] == "minimal disease activity"
    assert by_acronym["PsO"] == "psoriasis"


def test_abbreviation_block_with_no_pairs_returns_empty():
    assert _parse_abbreviation_block("Abbreviations") == []
    assert _parse_abbreviation_block("") == []


# ─── full adapter on a synthetic extraction.json ─────────────────────


def _minimal_extraction(blocks=None, modules=None, supportive=None, doc_reg=None) -> dict:
    return {
        "asset": {
            "id": "asset_test",
            "filename": "test.pdf",
            "channel": "email",
            "product": {"brand": "TESTBRAND", "mah": "TestPharma"},
            "market": "UK",
            "language": "en",
            "compliance_profile_id": "UK-Branded-Promotional",
            "approval_code": "FA-12345678",
            "date_of_preparation": "2026-04-01",
        },
        "blocks": blocks or [],
        "modules": modules or [],
        "fragments": [],
        "supportive_resources": supportive or [],
        "document_regulatory": doc_reg or {},
        "unclaimed": [],
        "visuals": [],
    }


def test_adapter_downgrades_reference_shaped_body_to_reference():
    raw = _minimal_extraction(blocks=[
        {"id": "b1", "role": "BODY", "text": "Minimal disease activity (MDA) is emerging as practice."},
        {"id": "b2", "role": "BODY", "text": "9. Henkemans SVJS et al. RMD Open. 2022;8(2):e002706."},
    ])
    asset = adapt(raw, asset_id="tmp:test")
    by_id = {b.id: b for b in asset.blocks}
    assert by_id["b1"].role == "BODY"             # normal prose stays BODY
    assert by_id["b2"].role == "REFERENCE"        # citation downgraded


def test_adapter_meta_round_trip():
    asset = adapt(_minimal_extraction(), asset_id="tmp:test")
    assert asset.meta.brand == "TESTBRAND"
    assert asset.meta.market == "UK"
    assert asset.meta.code == "FA-12345678"
    assert asset.meta.prepared == "2026-04-01"
    assert asset.profile_id == "UK-Branded-Promotional"
