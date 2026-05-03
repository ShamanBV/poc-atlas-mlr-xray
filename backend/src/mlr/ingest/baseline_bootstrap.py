"""
Bootstrap the per-role structural baseline from extractor outputs.

Two sources, in order of preference:

  1. Curated approved baseline file at
     `backend/baselines/uk_email_baselines.jsonl` — written by the
     extractor-service approval flow (see file format below). One JSON
     object per line, schema:

         {
           "role":          "PROMOTIONAL_NOTICE",
           "text":          "This is a promotional email from …",
           "n":             5,
           "coverage":      0.83,
           "window_months": 18,
           "first_seen":    "2024-08",
           "source_id":     "asset_e2dd75bdb504",
           "pattern_id":    "uk_email_promotional_notice_a17f8e"
         }

     If this file exists and is non-empty, it's the source of truth.

  2. Fallback: walk the existing UK extraction.json files
     (`extractor-service/test_sets/eval_atlas_*/`), harvest text per
     role, dedupe by exact text, treat all as approved (option B per
     D29). Used until the extractor service starts writing to (1).

Both paths produce a `list[BaselineExemplar]` ready for
`baseline.set_baseline(...)`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from mlr.precheck.baseline import BaselineExemplar


# Roles we surface as structural zones (mirrors structural_check's
# _ROLE_LABEL_LANE keys; visuals + claims + abbreviations excluded).
_BASELINE_ROLES: frozenset[str] = frozenset({
    "HEADER", "AUDIENCE_RESTRICTION", "PROMOTIONAL_NOTICE",
    "PRESCRIBING_INFORMATION", "PHARMACOVIGILANCE", "APPROVAL_INFO",
    "UNSUBSCRIBE", "CONTACT_INFO", "CTA", "REFERENCE", "FOOTNOTE",
    "REGULATORY_MENU", "SAFETY", "INDICATION", "DISCLAIMERS",
})


def _stable_pattern_id(role: str, text: str) -> str:
    """Stable id derived from role + content hash (hex slice)."""
    h = hashlib.sha1(f"{role}::{text}".encode("utf-8")).hexdigest()[:8]
    return f"uk_email_{role.lower()}_{h}"


# ─── loader: curated approved file ────────────────────────────────────


def load_curated_file(path: Path) -> list[BaselineExemplar]:
    """
    Read a `.jsonl` curated baseline file.

    Skips malformed lines silently (one bad line shouldn't kill the
    whole baseline). Returns empty list when the file doesn't exist.
    """
    if not path.is_file():
        return []
    out: list[BaselineExemplar] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = d.get("role")
        text = d.get("text")
        if not role or not isinstance(text, str) or not text.strip():
            continue
        out.append(BaselineExemplar(
            role=role,
            text=text,
            n=int(d.get("n", 1)),
            coverage=float(d.get("coverage", 0.0)),
            window_months=int(d.get("window_months", 18)),
            first_seen=d.get("first_seen", "2024-01"),
            source_id=d.get("source_id", ""),
            pattern_id=d.get("pattern_id") or _stable_pattern_id(role, text),
        ))
    return out


# ─── bootstrap: walk extractor outputs (option B) ─────────────────────


def _harvest_block_texts(extractions_dir: Path) -> Iterable[tuple[str, str, str]]:
    """Yield (role, text, source_asset_id) for every relevant block in the dir."""
    for path in sorted(extractions_dir.glob("*.extraction.json")):
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        asset_id = (raw.get("asset") or {}).get("id") or path.stem
        for blk in raw.get("blocks", []):
            role = blk.get("role")
            if not role or role not in _BASELINE_ROLES:
                continue
            text = (blk.get("text") or "").strip()
            if not text or len(text) < 20:
                continue
            yield role, text, asset_id


def bootstrap_from_dir(extractions_dir: Path, *, window_months: int = 18) -> list[BaselineExemplar]:
    """
    Build a baseline from existing extractor outputs in `extractions_dir`.

    Per-role dedup by exact text. Coverage approximated as
    `min(1.0, n / total_assets_seen_for_role)`. Source_id captures one
    contributing asset for traceability.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    sample_source: dict[tuple[str, str], str] = {}
    role_totals: dict[str, int] = defaultdict(int)
    seen_asset_ids: dict[str, set[str]] = defaultdict(set)

    for role, text, asset_id in _harvest_block_texts(extractions_dir):
        counts[(role, text)] += 1
        sample_source.setdefault((role, text), asset_id)
        if asset_id not in seen_asset_ids[role]:
            seen_asset_ids[role].add(asset_id)
            role_totals[role] += 1

    out: list[BaselineExemplar] = []
    for (role, text), n in counts.items():
        denom = max(1, role_totals[role])
        out.append(BaselineExemplar(
            role=role,
            text=text,
            n=n,
            coverage=min(1.0, n / denom),
            window_months=window_months,
            first_seen="2024-01",
            source_id=sample_source.get((role, text), ""),
            pattern_id=_stable_pattern_id(role, text),
        ))
    out.sort(key=lambda e: (e.role, -e.n, e.text))
    return out


# ─── unified entrypoint ───────────────────────────────────────────────


# Default location inside this repo. Override via MLR_BASELINE_PATH so
# the extractor service can write its approval output to its own path.
_DEFAULT_CURATED_PATH = (
    Path(__file__).resolve().parents[3]  # backend/
    / "baselines"
    / "uk_email_baselines.jsonl"
)


def curated_path() -> Path:
    """Resolve the curated baseline file location (env var wins)."""
    env = os.environ.get("MLR_BASELINE_PATH")
    if env:
        return Path(env).expanduser()
    return _DEFAULT_CURATED_PATH


# ─── writer (JSONL persistence — POC + extractor-service handoff) ────


def exemplar_to_dict(ex: BaselineExemplar) -> dict:
    """The canonical on-disk shape for one exemplar. Stable contract."""
    return {
        "role":          ex.role,
        "text":          ex.text,
        "n":             ex.n,
        "coverage":      round(ex.coverage, 4),
        "window_months": ex.window_months,
        "first_seen":    ex.first_seen,
        "source_id":     ex.source_id,
        "pattern_id":    ex.pattern_id,
    }


def write_jsonl(path: Path, exemplars: list[BaselineExemplar]) -> int:
    """
    Write the given exemplars to `path` as JSON Lines. Creates parent
    directories. One line per exemplar; a leading `# …` comment block
    documents the schema for human readers. Returns the count written.

    Round-trip safe: load_curated_file(write_jsonl(...)) returns an
    equivalent list.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# UK email baseline exemplars — one JSON object per line.\n")
        f.write("# Schema: role, text, n, coverage, window_months, first_seen,\n")
        f.write("#         source_id, pattern_id (see baseline_bootstrap.py docstring).\n")
        f.write("# Loader: mlr.ingest.baseline_bootstrap.load_curated_file()\n")
        f.write("# Resolution: MLR_BASELINE_PATH env var > backend/baselines/uk_email_baselines.jsonl\n")
        for ex in exemplars:
            f.write(json.dumps(exemplar_to_dict(ex), ensure_ascii=False))
            f.write("\n")
    return len(exemplars)


def load_default_baseline(extractions_dir: Path | None = None) -> list[BaselineExemplar]:
    """
    Resolution order:
      1. MLR_BASELINE_PATH env var (or default backend/baselines/…) — if
         the file exists and is non-empty, it wins.
      2. Bootstrap from `extractions_dir` — option B fallback per D29
         (treats every observed text as approved).
      3. Empty list.
    """
    curated = load_curated_file(curated_path())
    if curated:
        return curated
    if extractions_dir and extractions_dir.is_dir():
        return bootstrap_from_dir(extractions_dir)
    return []
