"""
Similarity primitives for Layer 1 (claim precheck).

What ships:

  - `Embedder` protocol — one method, `encode(texts) → list[list[float]]`.
    Default implementation (`HashEmbedder`) is deterministic, has no
    third-party deps, and is stable across processes. Production swaps
    in a `SentenceTransformerEmbedder` that loads `all-MiniLM-L6-v2`
    (or similar) by implementing the protocol; the rest of Layer 1
    is unchanged.

  - `cosine(a, b)` — cosine similarity over two unit-normalised vectors.

  - `combined_similarity(a, b, embedder)` — average of bag-of-tokens
    cosine and character-level `SequenceMatcher.ratio()`. The hybrid
    is more robust than either alone for the POC's drift-detection use
    case: the bag side catches reorderings, the char side catches
    minor edits / punctuation drift.

  - `word_diff(extracted, canonical)` — produces `DiffSegment[]` as
    described in `MLR_PRECHECK_API.md` §2.2 (s ∈ {k, d, a}).

The Embedder protocol returns `list[list[float]]` rather than numpy so
the POC stays dependency-free; callers compute cosine directly.
"""

from __future__ import annotations

import difflib
import hashlib
import math
import re
from typing import Protocol

from .schema import DiffSegment


# ─── tokenisation ────────────────────────────────────────────────────


_WORD_RE = re.compile(r"\w+", re.UNICODE)
_TOKEN_OR_SEPARATOR_RE = re.compile(r"(\W+)", re.UNICODE)


def _tokenise_words(text: str) -> list[str]:
    """Lowercase word tokens for bag-of-tokens hashing."""
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def _tokenise_keeping_separators(text: str) -> list[str]:
    """
    Split into tokens while keeping separators (spaces, punctuation) as
    their own tokens. Used for word_diff so reassembly preserves exact
    original whitespace and punctuation.
    """
    return [t for t in _TOKEN_OR_SEPARATOR_RE.split(text) if t]


# ─── Embedder protocol + default impl ────────────────────────────────


class Embedder(Protocol):
    """Encodes a list of strings into unit-normalised vectors."""

    def encode(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbedder:
    """
    Deterministic bag-of-tokens hash embedder.

    For each token in the input text:
      bucket = md5(token) mod dim
      vec[bucket] += 1.0
    Then unit-normalise.

    Fast, no deps, deterministic across runs and processes. Cosine
    between two HashEmbedder vectors is a hashing-trick approximation
    of bag-of-words cosine — captures token overlap regardless of order.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _tokenise_words(text):
                bucket = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
                vec[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


# Module-level singleton for callers that don't care which embedder is used.
_DEFAULT_EMBEDDER: Embedder = HashEmbedder()


def default_embedder() -> Embedder:
    return _DEFAULT_EMBEDDER


# ─── cosine + combined similarity ────────────────────────────────────


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


def char_ratio(a: str, b: str) -> float:
    """Character-level overlap, range 0..1."""
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def combined_similarity(
    a: str,
    b: str,
    embedder: Embedder | None = None,
) -> float:
    """
    Hybrid similarity = mean(semantic_cos, char_ratio).

    Captures both reorderings (semantic side) and minor phrasing edits
    (char side). Range 0..1. The numbers reported in the X-Ray UI are
    these combined scores.
    """
    embedder = embedder or default_embedder()
    vecs = embedder.encode([a, b])
    sem = max(0.0, min(1.0, cosine(vecs[0], vecs[1])))
    char = char_ratio(a, b)
    return (sem + char) / 2.0


# ─── word diff ───────────────────────────────────────────────────────


def word_diff(extracted: str, canonical: str) -> list[DiffSegment]:
    """
    Word/punctuation-level diff producing `DiffSegment[]`.

    Output schema (per `MLR_PRECHECK_API.md` §2.2):
      DiffSegment.s ∈ {"k" (keep), "d" (delete from extracted), "a" (add from canonical)}

    Joining all `t` values where `s != "a"` reproduces `extracted`;
    joining where `s != "d"` reproduces `canonical`. This invariant is
    asserted by the test suite.
    """
    a_tokens = _tokenise_keeping_separators(extracted)
    b_tokens = _tokenise_keeping_separators(canonical)
    matcher = difflib.SequenceMatcher(a=a_tokens, b=b_tokens, autojunk=False)

    segments: list[DiffSegment] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            text = "".join(a_tokens[i1:i2])
            if text:
                segments.append(DiffSegment(t=text, s="k"))
        elif op == "delete":
            text = "".join(a_tokens[i1:i2])
            if text:
                segments.append(DiffSegment(t=text, s="d"))
        elif op == "insert":
            text = "".join(b_tokens[j1:j2])
            if text:
                segments.append(DiffSegment(t=text, s="a"))
        elif op == "replace":
            d_text = "".join(a_tokens[i1:i2])
            a_text = "".join(b_tokens[j1:j2])
            if d_text:
                segments.append(DiffSegment(t=d_text, s="d"))
            if a_text:
                segments.append(DiffSegment(t=a_text, s="a"))
    return segments
