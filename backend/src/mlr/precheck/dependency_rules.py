"""
Loader + predicate evaluator for `dependency_rules.yaml`.

Catalog format and predicate vocabulary are defined inline in
`../../dependency_rules.yaml` (top of repo). This module:

  - Loads the catalog from disk and turns each entry into a `Rule`.
  - Evaluates predicate / requires trees against an ExtractedAsset.
  - Exposes a single `load_default_catalog()` for app startup.

Leaf types supported:

  any_module          claim, subtype_in, text_matches, text_contains
  any_block           role_in, subtype_in, text_matches, text_contains,
                      has_external_link, font_hierarchy_in
  any_fragment        role_in
  envelope            key, present, text_matches
  supportive_resource type, present, member_count_min
  profile_in          [str]
  market_in           [str]
  doc_type_in         [str]
  language_in         [str]

Composition: any_of, all_of, not — each takes either a list (any_of/all_of)
or a single node (not).

Out of scope for the POC:
  - envelope.matches_pattern  (needs a pattern bank — stubbed as True)
  - market_overrides freshness window for r_date_of_preparation (the
    base presence/regex check still runs)
  - per-customer rule overrides
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import ExtractedAsset, ExtractedBlock, ExtractedModule


# ─── catalog data shape ──────────────────────────────────────────────


@dataclass(frozen=True)
class RuleCoverage:
    corpus_size_observed: int
    minimum: int
    note: str | None = None

    @property
    def confidence_label(self) -> str:
        if self.corpus_size_observed >= self.minimum:
            return "high"
        if self.corpus_size_observed >= max(1, self.minimum // 2):
            return "medium"
        return "low"


@dataclass(frozen=True)
class Rule:
    id: str
    pillar: str  # "medical" | "legal" | "regulatory"
    description: str
    severity: str  # "info" | "warn" | "block"
    rationale: str
    predicate: dict
    requires: dict
    market_overrides: dict = field(default_factory=dict)
    coverage: RuleCoverage = field(default_factory=lambda: RuleCoverage(0, 1))


@dataclass(frozen=True)
class RuleCatalog:
    schema_version: str
    catalog_version: str
    default_severity_when_unmet: str
    rules: tuple[Rule, ...]

    def filter_for_asset(self, asset: ExtractedAsset) -> Iterable[Rule]:
        """All rules — no per-asset gating yet (handled by predicate eval)."""
        return self.rules


# ─── loader ──────────────────────────────────────────────────────────


def _coerce_coverage(raw: dict | None) -> RuleCoverage:
    if not raw:
        return RuleCoverage(0, 1)
    return RuleCoverage(
        corpus_size_observed=int(raw.get("corpus_size_observed", 0)),
        minimum=int(raw.get("minimum", 1)),
        note=raw.get("note"),
    )


def _rules_from_pillar(pillar: str, items: list[dict]) -> Iterable[Rule]:
    for item in items:
        yield Rule(
            id=item["id"],
            pillar=pillar,
            description=item.get("description", item["id"]),
            severity=item.get("severity", "warn"),
            rationale=item.get("rationale", ""),
            predicate=item.get("predicate", {}),
            requires=item.get("requires", {}),
            market_overrides=item.get("market_overrides", {}),
            coverage=_coerce_coverage(item.get("coverage")),
        )


def load_catalog(path: Path) -> RuleCatalog:
    raw = yaml.safe_load(path.read_text())
    rules: list[Rule] = []
    for pillar in ("medical", "legal", "regulatory"):
        rules.extend(_rules_from_pillar(pillar, raw.get(pillar, []) or []))
    return RuleCatalog(
        schema_version=raw.get("schema_version", "1.0"),
        catalog_version=raw.get("catalog_version", "unknown"),
        default_severity_when_unmet=raw.get("default_severity_when_unmet", "warn"),
        rules=tuple(rules),
    )


# Default catalog lives at the repo root, two levels up from
# backend/src/mlr/precheck/dependency_rules.py.
_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3].parent / "dependency_rules.yaml"
)


def load_default_catalog() -> RuleCatalog:
    return load_catalog(_DEFAULT_PATH)


# ─── predicate evaluator ─────────────────────────────────────────────


def evaluate(node: Any, asset: ExtractedAsset) -> bool:
    """
    Walk a predicate / requires tree and return the boolean verdict.

    Empty / None nodes are treated as `True` (a rule with no predicate
    fires unconditionally; a rule with no `requires` is always satisfied).
    """
    if node is None or node == {}:
        return True
    if not isinstance(node, dict):
        raise ValueError(f"predicate node must be dict or None, got {type(node).__name__}")

    # ── composition ────────────────────────────────────────────────
    if "any_of" in node:
        return any(evaluate(c, asset) for c in node["any_of"])
    if "all_of" in node:
        return all(evaluate(c, asset) for c in node["all_of"])
    if "not" in node:
        return not evaluate(node["not"], asset)

    # ── leaf types ─────────────────────────────────────────────────
    if "any_module" in node:
        return _eval_any_module(node["any_module"], asset)
    if "any_block" in node:
        return _eval_any_block(node["any_block"], asset)
    if "any_fragment" in node:
        return _eval_any_fragment(node["any_fragment"], asset)
    if "envelope" in node:
        return _eval_envelope(node["envelope"], asset)
    if "supportive_resource" in node:
        return _eval_supportive_resource(node["supportive_resource"], asset)
    if "profile_in" in node:
        return asset.profile_id in node["profile_in"]
    if "market_in" in node:
        return asset.meta.market in node["market_in"]
    if "doc_type_in" in node:
        return asset.meta.doc_type in node["doc_type_in"]
    if "language_in" in node:
        return asset.meta.language in node["language_in"]

    raise ValueError(f"unknown predicate node: {sorted(node.keys())}")


# ─── leaf evaluators ─────────────────────────────────────────────────


def _matches_text_filters(text: str, spec: dict) -> bool:
    """Common helper: text_matches (regex) + text_contains (any of)."""
    if (regex := spec.get("text_matches")) is not None:
        if not re.search(regex, text):
            return False
    if (needles := spec.get("text_contains")) is not None:
        if not any(n in text for n in needles):
            return False
    return True


def _module_matches(mod: ExtractedModule, spec: dict) -> bool:
    if "claim" in spec and bool(mod.claim) != bool(spec["claim"]):
        return False
    if (subtypes := spec.get("subtype_in")) is not None:
        if mod.subtype not in subtypes:
            return False
    if not _matches_text_filters(mod.synthesized_text, spec):
        return False
    return True


def _eval_any_module(spec: dict, asset: ExtractedAsset) -> bool:
    return any(_module_matches(m, spec) for m in asset.modules)


def _block_matches(blk: ExtractedBlock, spec: dict) -> bool:
    if (roles := spec.get("role_in")) is not None:
        if blk.role not in roles:
            return False
    if (subtypes := spec.get("subtype_in")) is not None:
        if blk.subtype not in subtypes:
            return False
    if not _matches_text_filters(blk.text, spec):
        return False
    if "has_external_link" in spec:
        wanted = bool(spec["has_external_link"])
        actually = bool(blk.links) or _has_url_in_text(blk.text)
        if actually != wanted:
            return False
    if (hierarchies := spec.get("font_hierarchy_in")) is not None:
        if blk.font_hierarchy not in hierarchies:
            return False
    return True


_URL_RE = re.compile(r"https?://[^\s)>\]]+")


def _has_url_in_text(text: str) -> bool:
    return bool(_URL_RE.search(text))


def _eval_any_block(spec: dict, asset: ExtractedAsset) -> bool:
    return any(_block_matches(b, spec) for b in asset.blocks)


def _eval_any_fragment(spec: dict, asset: ExtractedAsset) -> bool:
    wanted_roles = spec.get("role_in")
    for mod in asset.modules:
        for frag in mod.fragments:
            if wanted_roles is None or frag.role in wanted_roles:
                return True
    return False


def _eval_envelope(spec: dict, asset: ExtractedAsset) -> bool:
    key = spec["key"]
    present_required = spec.get("present", True)
    value = asset.envelope.get(key)
    is_present = value is not None and value != "" and value is not False
    if present_required and not is_present:
        return False
    if not present_required and is_present:
        return False
    if not is_present:
        return True  # required absent, and absent — match
    text = value if isinstance(value, str) else str(value)
    if not _matches_text_filters(text, spec):
        return False
    if "matches_pattern" in spec:
        # Pattern-bank check is stubbed for the POC — see module docstring.
        # Engine returns True so rules don't false-fire when the bank is
        # absent; will be replaced by real cosine match in v1.5.
        pass
    return True


def _eval_supportive_resource(spec: dict, asset: ExtractedAsset) -> bool:
    wanted_type = spec["type"]
    present_required = spec.get("present", True)
    min_members = spec.get("member_count_min")
    matches = [r for r in asset.supportive_resources if r.type == wanted_type]
    is_present = len(matches) > 0 and any(
        len(r.members) > 0 for r in matches
    )
    if present_required and not is_present:
        return False
    if not present_required and is_present:
        return False
    if min_members is not None:
        total = sum(len(r.members) for r in matches)
        if total < int(min_members):
            return False
    return True
