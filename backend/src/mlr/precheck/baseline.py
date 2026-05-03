"""
Per-role exemplar corpus for structural pattern recognition.

Where the claim library (`library.py`) holds approved canonical CLAIM
text variants, this module holds approved canonical text per
STRUCTURAL ROLE (PROMOTIONAL_NOTICE, AUDIENCE_RESTRICTION,
PRESCRIBING_INFORMATION, PHARMACOVIGILANCE, APPROVAL_INFO,
CONTACT_INFO, UNSUBSCRIBE, …). Layer 0 (`structural_check`) uses it
to score each extracted block:

  similarity ≥ 0.95 → status:clean / "Pattern match · 0.97"
  0.80 ≤ s < 0.95   → status:attn  / "Drift · 0.84"
  s < 0.80          → status:miss  / "Novel · 0.30"
  no role baseline  → status:clean / "Extracted" (naive default)

Sources of exemplars (in order of preference):
  1. Curated approved corpus written by the extractor-service approval
     flow (see `mlr/ingest/baseline_bootstrap.py` for file format).
  2. Bootstrapped from existing UK extraction.json outputs (option B
     fallback per D5/D29).

The per-role API mirrors `library.py` so the two modules stay
ergonomically parallel — easy to swap to a real curated source when
it lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .similarity import Embedder, combined_similarity, default_embedder


@dataclass(frozen=True)
class BaselineExemplar:
    """One approved/observed instance of text for a given structural role."""

    role: str          # PROMOTIONAL_NOTICE / AUDIENCE_RESTRICTION / …
    text: str          # the exemplar text
    n: int = 1         # times this exact text was observed
    coverage: float = 0.0   # fraction of approved assets this appears in
    window_months: int = 18
    first_seen: str = "2024-01"
    source_id: str = ""     # provenance — asset_id of an approving asset
    pattern_id: str = ""    # stable id, derived from role + hash(text)


# ─── runtime state ───────────────────────────────────────────────────


# `_active` is keyed by role for fast match(). Each role maps to a list
# of exemplars sorted by `n` desc so the most-observed variant tries first.
_active: dict[str, list[BaselineExemplar]] = {}


def set_baseline(exemplars: list[BaselineExemplar]) -> None:
    """Replace the active baseline with the given exemplars."""
    global _active
    grouped: dict[str, list[BaselineExemplar]] = {}
    for ex in exemplars:
        grouped.setdefault(ex.role, []).append(ex)
    for role in grouped:
        grouped[role].sort(key=lambda e: -e.n)
    _active = grouped


def reset_baseline() -> None:
    """Wipe the active baseline. Used by tests + when the source changes."""
    global _active
    _active = {}


def all_exemplars() -> list[BaselineExemplar]:
    """Read-only view, flattened across roles."""
    return [ex for role_list in _active.values() for ex in role_list]


def total_size() -> int:
    return sum(len(v) for v in _active.values())


def role_size(role: str) -> int:
    return len(_active.get(role, []))


# ─── matching ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BaselineMatch:
    """Result of matching one extracted text against a role's exemplar set."""

    score: float
    exemplar: BaselineExemplar
    role_corpus_size: int


def match(role: str, text: str, *, embedder: Embedder | None = None) -> BaselineMatch | None:
    """
    Find the best baseline exemplar for `text` within `role`.

    Returns None when the role has no baseline exemplars at all (so the
    caller can fall back to the naive "Extracted" status). Returns a
    `BaselineMatch` with the highest combined_similarity otherwise.
    """
    exemplars = _active.get(role)
    if not exemplars:
        return None
    embedder = embedder or default_embedder()
    best: BaselineExemplar = exemplars[0]
    best_score = -1.0
    for ex in exemplars:
        s = combined_similarity(text, ex.text, embedder)
        if s > best_score:
            best, best_score = ex, s
    return BaselineMatch(score=best_score, exemplar=best, role_corpus_size=len(exemplars))


# ─── thresholds (tuned for HashEmbedder hybrid; see D2) ──────────────


CLEAN_MIN: float = 0.95
DRIFT_MIN: float = 0.80


def status_for_score(score: float) -> tuple[str, str, str]:
    """
    Returns (status, severity, evidence_template) for a similarity score.

    Severity stays `info` across the board for structural patterns —
    drift/novel surfaces visually but doesn't punish the overall score
    the way claim-drift or required-element-missing rules do
    (D7 score formula assumption).
    """
    if score >= CLEAN_MIN:
        return ("clean", "info", "Pattern match · {score:.2f}")
    if score >= DRIFT_MIN:
        return ("attn", "info", "Drift · {score:.2f}")
    return ("miss", "info", "Novel · {score:.2f}")
