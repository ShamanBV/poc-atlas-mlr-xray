"""HashEmbedder, cosine, combined_similarity, word_diff."""

import pytest

from mlr.precheck.similarity import (
    HashEmbedder,
    char_ratio,
    combined_similarity,
    cosine,
    default_embedder,
    word_diff,
)


# ─── HashEmbedder ────────────────────────────────────────────────────


def test_embedder_returns_unit_normalised_vectors():
    emb = HashEmbedder(dim=64)
    [v] = emb.encode(["the quick brown fox"])
    norm = sum(x * x for x in v) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_embedder_is_deterministic():
    emb_a = HashEmbedder(dim=128)
    emb_b = HashEmbedder(dim=128)
    text = "ribociclib reduced the risk of recurrence"
    assert emb_a.encode([text]) == emb_b.encode([text])


def test_embedder_dim_must_be_positive():
    with pytest.raises(ValueError):
        HashEmbedder(dim=0)


def test_embedder_handles_empty_string():
    [v] = HashEmbedder(dim=16).encode([""])
    # empty text → all-zero vector (norm 0 → fallback to 1.0 in code,
    # so the vector stays all-zero; cosine with anything is 0).
    assert all(x == 0.0 for x in v)


def test_embedder_token_order_invariant():
    """Bag-of-tokens: scrambling word order should preserve cosine."""
    emb = HashEmbedder(dim=128)
    a, b = emb.encode([
        "Adverse events were monitored throughout",
        "throughout monitored were events Adverse",
    ])
    assert cosine(a, b) == pytest.approx(1.0, abs=1e-9)


# ─── cosine ──────────────────────────────────────────────────────────


def test_cosine_identical_vectors():
    v = [1 / 3 ** 0.5] * 3
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-9)


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine(a, b) == 0.0


def test_cosine_dim_mismatch_raises():
    with pytest.raises(ValueError):
        cosine([1.0, 0.0], [1.0, 0.0, 0.0])


# ─── char_ratio ──────────────────────────────────────────────────────


def test_char_ratio_identical_is_one():
    assert char_ratio("hello world", "hello world") == 1.0


def test_char_ratio_empty_strings():
    assert char_ratio("", "") == 1.0


def test_char_ratio_unrelated_is_low():
    assert char_ratio("hello world", "completely different") < 0.4


# ─── combined_similarity ─────────────────────────────────────────────


def test_combined_similarity_identical_is_one():
    assert combined_similarity("a b c", "a b c") == pytest.approx(1.0, abs=1e-9)


def test_combined_similarity_drift_band():
    """The §6 KISQALI drift case must land in [0.80, 0.98]."""
    a = (
        "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
        "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
    )
    b = (
        "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% "
        "vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014)."
    )
    sim = combined_similarity(a, b)
    assert 0.80 <= sim < 0.98, sim


def test_combined_similarity_unrelated_is_low():
    sim = combined_similarity(
        "KISQALI reduced recurrence",
        "Treatment-related neutropenia was managed",
    )
    assert sim < 0.3


def test_combined_similarity_uses_supplied_embedder():
    """A custom embedder is honoured (not a hidden module-level singleton)."""
    class IdentityEmbedder:
        def encode(self, texts):
            return [[1.0] + [0.0] * 7 for _ in texts]

    a, b = "x", "y"
    sim = combined_similarity(a, b, embedder=IdentityEmbedder())
    # Semantic = 1.0, char = whatever — average must be ≥ 0.5.
    assert sim >= 0.5


def test_default_embedder_returns_singleton():
    e1 = default_embedder()
    e2 = default_embedder()
    assert e1 is e2


# ─── word_diff ───────────────────────────────────────────────────────


def test_word_diff_identical_text_is_all_keep():
    text = "Identical text identical text."
    segments = word_diff(text, text)
    assert all(s.s == "k" for s in segments)
    assert "".join(s.t for s in segments) == text


def test_word_diff_keep_and_delete_reproduces_extracted():
    """Joining segments where s != 'a' must reproduce the extracted text."""
    extracted = "AE rate was low"
    canonical = "Adverse events were low"
    segments = word_diff(extracted, canonical)
    rebuilt = "".join(s.t for s in segments if s.s != "a")
    assert rebuilt == extracted


def test_word_diff_keep_and_add_reproduces_canonical():
    """Joining segments where s != 'd' must reproduce the canonical text."""
    extracted = "AE rate was low"
    canonical = "Adverse events were low"
    segments = word_diff(extracted, canonical)
    rebuilt = "".join(s.t for s in segments if s.s != "d")
    assert rebuilt == canonical


def test_word_diff_kisqali_drift_emits_expected_segment_types():
    extracted = (
        "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
        "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
    )
    canonical = (
        "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% "
        "vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014)."
    )
    segments = word_diff(extracted, canonical)
    kinds = {s.s for s in segments}
    # Expect at least one keep, at least one add ("disease"), at least one delete or replace.
    assert "k" in kinds
    assert "a" in kinds
    # Verify both invariants of the diff:
    assert "".join(s.t for s in segments if s.s != "a") == extracted
    assert "".join(s.t for s in segments if s.s != "d") == canonical


def test_word_diff_handles_pure_insertion():
    segments = word_diff("hello", "hello world")
    assert any(s.s == "a" and "world" in s.t for s in segments)


def test_word_diff_handles_pure_deletion():
    segments = word_diff("hello world", "hello")
    assert any(s.s == "d" and "world" in s.t for s in segments)
