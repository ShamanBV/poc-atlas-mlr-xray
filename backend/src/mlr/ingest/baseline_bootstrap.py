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
        bbox = d.get("bbox")
        if bbox is not None and isinstance(bbox, list) and len(bbox) >= 4:
            bbox = [float(x) for x in bbox[:4]]
        else:
            bbox = None
        out.append(BaselineExemplar(
            role=role,
            text=text,
            n=int(d.get("n", 1)),
            coverage=float(d.get("coverage", 0.0)),
            window_months=int(d.get("window_months", 18)),
            first_seen=d.get("first_seen", "2024-01"),
            source_id=d.get("source_id", ""),
            pattern_id=d.get("pattern_id") or _stable_pattern_id(role, text),
            # Visual fields are optional; default to text-row defaults.
            kind=d.get("kind", "text"),
            visual_kind=d.get("visual_kind"),
            image_url=d.get("image_url"),
            ocr_text=d.get("ocr_text"),
            classification=d.get("classification"),
            page=d.get("page"),
            bbox=bbox,
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


# Map extractor's visual.kind → semantic role from
# CLASSIFICATION_TO_MLR_MAP.md §5.
# - BRAND_VISUAL:  logo / hero / banner / packshot
# - MEDICAL_VISUAL: person_photo / illustration / icon / play_video_banner
# - DATA_VISUAL:   chart / infographic / diagram / dosing_related / key_number
# - TABLE:         table
# Unknown / unclassified visuals default to BRAND_VISUAL (neutral; the
# MLR cascade rule for that classification is the gentlest).
_VISUAL_KIND_TO_CLASSIFICATION: dict[str, str] = {
    # BRAND_VISUAL
    "banner":            "BRAND_VISUAL",
    "logo":              "BRAND_VISUAL",
    "hero":              "BRAND_VISUAL",
    "packshot":          "BRAND_VISUAL",
    # MEDICAL_VISUAL
    "photo":             "MEDICAL_VISUAL",
    "patient":           "MEDICAL_VISUAL",
    "person_photo":      "MEDICAL_VISUAL",
    "icon":              "MEDICAL_VISUAL",
    "illustration":      "MEDICAL_VISUAL",
    "play_video_banner": "MEDICAL_VISUAL",
    # DATA_VISUAL
    "chart":             "DATA_VISUAL",
    "infographic":       "DATA_VISUAL",
    "diagram":           "DATA_VISUAL",
    "dosing_related":    "DATA_VISUAL",
    "key_number":        "DATA_VISUAL",
    # TABLE
    "table":             "TABLE",
}


def _classification_for_kind(kind: str | None) -> str:
    """Returns one of BRAND_VISUAL / MEDICAL_VISUAL / DATA_VISUAL / TABLE."""
    if not kind:
        return "BRAND_VISUAL"
    return _VISUAL_KIND_TO_CLASSIFICATION.get(kind.lower(), "BRAND_VISUAL")


def _harvest_visuals(extractions_dir: Path):
    """
    Yield raw visual dicts + source asset_id for each visual that has
    enough data to be useful (description OR ocr text OR a link uri).
    """
    for path in sorted(extractions_dir.glob("*.extraction.json")):
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        asset_id = (raw.get("asset") or {}).get("id") or path.stem
        for v in raw.get("visuals", []):
            description = (v.get("description") or "").strip()
            link = v.get("link") or {}
            visible_text = (link.get("visible_text") or "").strip() if isinstance(link, dict) else ""
            uri = (link.get("uri") or "").strip() if isinstance(link, dict) else ""
            # Skip empty visuals — no description, no OCR, no link → nothing to bank.
            if not description and not visible_text and not uri:
                continue
            yield v, asset_id, description, visible_text, uri


def bootstrap_from_dir(extractions_dir: Path, *, window_months: int = 18) -> list[BaselineExemplar]:
    """
    Build a baseline from existing extractor outputs in `extractions_dir`.

    Returns text exemplars (one per (role, exact_text) tuple) AND
    visual exemplars (one per (visual_kind, description) tuple).

    Per-row dedup by exact text. Coverage approximated as
    `min(1.0, n / total_assets_seen_for_role)`. Source_id captures one
    contributing asset for traceability.
    """
    # ── text rows ─────────────────────────────────────────────────
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
            kind="text",
        ))

    # ── visual rows ───────────────────────────────────────────────
    # Dedupe by (visual_kind, description) — same picture used in
    # multiple places usually has the same AI description.
    v_counts: dict[tuple[str, str], int] = defaultdict(int)
    v_sample: dict[tuple[str, str], dict] = {}
    v_role_totals: dict[str, int] = defaultdict(int)
    v_seen_asset_ids: dict[str, set[str]] = defaultdict(set)

    for v, asset_id, description, visible_text, uri in _harvest_visuals(extractions_dir):
        v_kind = v.get("kind")
        # Role + classification follow the spec taxonomy
        # (CLASSIFICATION_TO_MLR_MAP.md §5): BRAND_VISUAL /
        # MEDICAL_VISUAL / DATA_VISUAL / TABLE. Mirrors the field names
        # the extractor service writes in its approval flow.
        role = _classification_for_kind(v_kind)
        # Use description as the dedupe key when present; fall back to
        # OCR text or URI to keep distinct visuals separate.
        dedupe_text = description or visible_text or uri or "(unknown)"
        key = (role, dedupe_text)
        v_counts[key] += 1
        if key not in v_sample:
            v_sample[key] = {
                "v": v, "asset_id": asset_id, "description": description,
                "ocr": visible_text, "uri": uri,
            }
        if asset_id not in v_seen_asset_ids[role]:
            v_seen_asset_ids[role].add(asset_id)
            v_role_totals[role] += 1

    for (role, dedupe_text), n in v_counts.items():
        meta = v_sample[(role, dedupe_text)]
        v = meta["v"]
        bbox_raw = v.get("bbox")
        bbox = list(bbox_raw[:4]) if isinstance(bbox_raw, list) and len(bbox_raw) >= 4 else None
        page_raw = v.get("page")
        page = (page_raw + 1) if isinstance(page_raw, int) else None
        denom = max(1, v_role_totals[role])
        out.append(BaselineExemplar(
            role=role,
            text=meta["description"] or meta["ocr"] or meta["uri"] or "",
            n=n,
            coverage=min(1.0, n / denom),
            window_months=window_months,
            first_seen="2024-01",
            source_id=meta["asset_id"],
            pattern_id=_stable_pattern_id(role, dedupe_text),
            kind="visual",
            visual_kind=v.get("kind"),
            image_url=meta["uri"] or None,
            ocr_text=meta["ocr"] or None,
            # `classification` mirrors `role` for visuals — same value;
            # extractor service writes both for symmetry.
            classification=role,
            page=page,
            bbox=bbox,
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
    """
    Canonical on-disk shape for one exemplar. Visual-specific fields
    only emitted when kind != "text" or when populated, to keep
    text-row JSON clean.
    """
    out: dict = {
        "kind":          ex.kind,
        "role":          ex.role,
        "text":          ex.text,
        "n":             ex.n,
        "coverage":      round(ex.coverage, 4),
        "window_months": ex.window_months,
        "first_seen":    ex.first_seen,
        "source_id":     ex.source_id,
        "pattern_id":    ex.pattern_id,
    }
    if ex.kind == "visual" or any([
        ex.visual_kind, ex.image_url, ex.ocr_text, ex.classification,
        ex.page is not None, ex.bbox,
    ]):
        out.update({
            "visual_kind":    ex.visual_kind,
            "image_url":      ex.image_url,
            "ocr_text":       ex.ocr_text,
            "classification": ex.classification,
            "page":           ex.page,
            "bbox":           list(ex.bbox) if ex.bbox else None,
        })
    return out


def merge_exemplars(
    existing: list[BaselineExemplar],
    incoming: list[BaselineExemplar],
) -> list[BaselineExemplar]:
    """
    Merge two exemplar lists. Dedupe by `pattern_id` (which is a stable
    hash of role + text). On collision the existing row's count is
    incremented by the incoming `n`; coverage is recomputed via a
    simple max() since we don't track per-asset denominators across
    runs. Caller can re-bootstrap from full source if exact coverage
    matters.

    Rows with no `pattern_id` (legacy) are appended as-is.
    """
    by_pid: dict[str, BaselineExemplar] = {}
    order: list[str] = []
    for ex in existing + incoming:
        pid = ex.pattern_id
        if not pid:
            order.append(_anonymous_token())  # synthesise a unique key for ordering
            by_pid[order[-1]] = ex
            continue
        if pid in by_pid:
            prior = by_pid[pid]
            by_pid[pid] = BaselineExemplar(
                **{**prior.__dict__,
                   "n": prior.n + ex.n,
                   "coverage": max(prior.coverage, ex.coverage),
                   # latest first_seen wins so freshness isn't masked
                   "first_seen": max(prior.first_seen, ex.first_seen) if prior.first_seen and ex.first_seen else (prior.first_seen or ex.first_seen),
                   }
            )
        else:
            by_pid[pid] = ex
            order.append(pid)
    return [by_pid[k] for k in order]


_anon_seq = 0
def _anonymous_token() -> str:
    global _anon_seq
    _anon_seq += 1
    return f"__anon_{_anon_seq}"


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
