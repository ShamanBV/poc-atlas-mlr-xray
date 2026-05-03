"""Bootstrap + read/write round-trip tests for the baseline corpus."""

from pathlib import Path

import pytest

from mlr.ingest.baseline_bootstrap import (
    bootstrap_from_dir,
    curated_path,
    exemplar_to_dict,
    load_curated_file,
    load_default_baseline,
    write_jsonl,
)
from mlr.precheck.baseline import BaselineExemplar


# ─── exemplar_to_dict (the on-disk schema is the contract) ───────────


def test_exemplar_to_dict_keys_are_stable():
    ex = BaselineExemplar(
        role="PROMOTIONAL_NOTICE",
        text="This is a promotional email from Novartis intended for GB HCPs.",
        n=5,
        coverage=0.8333,
        window_months=18,
        first_seen="2024-08",
        source_id="asset_e2dd75bdb504",
        pattern_id="uk_email_promotional_notice_a17f8e",
    )
    d = exemplar_to_dict(ex)
    assert sorted(d.keys()) == sorted([
        "role", "text", "n", "coverage", "window_months",
        "first_seen", "source_id", "pattern_id",
    ])
    # `coverage` rounds to 4 decimals on disk
    assert d["coverage"] == 0.8333


# ─── round-trip ──────────────────────────────────────────────────────


def test_write_then_load_round_trips(tmp_path: Path):
    src = [
        BaselineExemplar(role="PROMOTIONAL_NOTICE", text="Promo notice A.", n=3, coverage=0.5, source_id="a1", pattern_id="p1"),
        BaselineExemplar(role="AUDIENCE_RESTRICTION", text="FOR UK HEALTHCARE PROFESSIONALS ONLY", n=12, coverage=1.0, source_id="a2", pattern_id="p2"),
        BaselineExemplar(role="APPROVAL_INFO", text="FA-12345678 · March 2026", n=1, coverage=0.04, source_id="a3", pattern_id="p3"),
    ]
    f = tmp_path / "round_trip.jsonl"

    n_written = write_jsonl(f, src)
    assert n_written == 3
    assert f.is_file()

    loaded = load_curated_file(f)
    assert len(loaded) == 3
    assert loaded[0].role == "PROMOTIONAL_NOTICE"
    assert loaded[1].text == "FOR UK HEALTHCARE PROFESSIONALS ONLY"
    assert loaded[1].n == 12
    assert loaded[2].pattern_id == "p3"


def test_write_creates_parent_directories(tmp_path: Path):
    nested = tmp_path / "deep" / "nested" / "out.jsonl"
    write_jsonl(nested, [
        BaselineExemplar(role="HEADER", text="Hi", n=1, coverage=1.0, source_id="x", pattern_id="px"),
    ])
    assert nested.is_file()


def test_loader_skips_malformed_lines(tmp_path: Path):
    f = tmp_path / "noisy.jsonl"
    f.write_text(
        "# header comment — should be skipped\n"
        '{"role":"HEADER","text":"good"}\n'
        "this is not JSON\n"
        "\n"
        '{"role":"","text":"missing role"}\n'
        '{"role":"FOOTER","text":""}\n'
        '{"role":"PHARMACOVIGILANCE","text":"AE reporting copy","n":2}\n'
    )
    loaded = load_curated_file(f)
    # Two valid lines: HEADER + PHARMACOVIGILANCE. Empty text and
    # empty role rows are dropped; comments and malformed lines too.
    assert {ex.role for ex in loaded} == {"HEADER", "PHARMACOVIGILANCE"}


def test_loader_returns_empty_when_file_missing(tmp_path: Path):
    assert load_curated_file(tmp_path / "does-not-exist.jsonl") == []


# ─── env var resolution ──────────────────────────────────────────────


def test_curated_path_env_var_wins(monkeypatch, tmp_path: Path):
    target = tmp_path / "from_env.jsonl"
    monkeypatch.setenv("MLR_BASELINE_PATH", str(target))
    assert curated_path() == target


def test_curated_path_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLR_BASELINE_PATH", raising=False)
    p = curated_path()
    assert p.name == "uk_email_baselines.jsonl"
    assert "backend/baselines" in str(p)


# ─── load_default_baseline preference ────────────────────────────────


def test_load_default_prefers_curated_over_bootstrap(monkeypatch, tmp_path: Path):
    # Set up a curated file with one exemplar.
    target = tmp_path / "curated.jsonl"
    write_jsonl(target, [
        BaselineExemplar(role="HEADER", text="from curated", n=1, coverage=1.0, source_id="x", pattern_id="px"),
    ])
    monkeypatch.setenv("MLR_BASELINE_PATH", str(target))

    # Bootstrap dir contains nothing matching — should be ignored when
    # curated wins.
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = load_default_baseline(empty_dir)
    assert len(result) == 1
    assert result[0].text == "from curated"


def test_load_default_falls_back_to_bootstrap(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MLR_BASELINE_PATH", str(tmp_path / "missing.jsonl"))

    # Build a tiny extractor-shaped JSON in a temp dir.
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "fake.extraction.json").write_text(
        '{"asset":{"id":"a1"},"blocks":['
        '{"role":"PROMOTIONAL_NOTICE","text":"This is a promotional email from Novartis intended for GB Healthcare Professionals."},'
        '{"role":"AUDIENCE_RESTRICTION","text":"FOR UK HEALTHCARE PROFESSIONALS ONLY"}]}'
    )
    result = load_default_baseline(src_dir)
    roles = {ex.role for ex in result}
    assert "PROMOTIONAL_NOTICE" in roles
    assert "AUDIENCE_RESTRICTION" in roles
