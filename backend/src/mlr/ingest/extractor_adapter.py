"""
Adapter: extractor-service `extraction.json` → precheck `ExtractedAsset`.

The extractor service (pipeline_email_v3 / v5) emits a JSON shape with
top-level keys `asset`, `blocks`, `modules`, `fragments`,
`supportive_resources`, `document_regulatory`, `unclaimed`, `visuals`,
`cascade_result`, `meta`. This adapter maps that shape into the
precheck engine's `ExtractedAsset` (`backend/src/mlr/precheck/schema.py`).

Field mapping (extractor → precheck):

  asset.product.brand            → meta.brand
  asset.market                   → meta.market
  asset.language or "en"         → meta.language
  asset.channel ("email")        → meta.doc_type
  asset.compliance_profile_id    → profile_id
  asset.approval_code            → meta.code
  asset.date_of_preparation      → meta.prepared
  blocks[].role/text/page/bbox/links/font_hierarchy → ExtractedBlock
  modules[]                      → ExtractedModule, with synthesized_text
                                    built from concatenated fragment block texts
  fragments[]                    → ExtractedFragment under the parent module
  supportive_resources[].type    → SupportiveResource.type
    abbreviation-set blocks      → parsed into {acronym, expansion} members
    reference-set blocks         → split into {ref_id, citation} members
    footnote-set blocks          → kept as {text, ref_id} members
  document_regulatory[key][]     → envelope[key] (text values concatenated)

What is NOT mapped (yet):
  - cascade_result — the existing extractor cascade is informative but
    the precheck engine runs its own dependency rules. We could surface
    cascade verdicts as `layer:cascade` zones in a future slice.
  - unclaimed CLAIM blocks — these are claims the extractor couldn't
    group into a module. For Layer 1 they'd ideally be evaluated too;
    for the POC we drop them (documented below).
  - visuals — Layer 1 is text-only; visuals come back when the visual
    extractor lands.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from mlr.precheck.schema import (
    AssetMeta,
    BoundingBox,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedFragment,
    ExtractedModule,
    SupportiveResource,
)


# ─── helpers ─────────────────────────────────────────────────────────


def _bbox_from_list(raw: Any) -> Optional[BoundingBox]:
    if not raw or not isinstance(raw, (list, tuple)) or len(raw) < 4:
        return None
    return BoundingBox(x0=float(raw[0]), y0=float(raw[1]), x1=float(raw[2]), y1=float(raw[3]))


# Citations look like "12. Author Initials, Author Initials. Journal Name.
# 2024;9(2):e002706." or "5. Coates LC et al. Lancet. 2024;...". The
# upstream extractor sometimes misclassifies them as BODY; we downgrade
# to REFERENCE so abbreviation_check (which excludes REFERENCE roles)
# stops scraping author initials and journal codes as acronyms.
_REFERENCE_LIKE_RE = re.compile(
    r"^\s*\d{1,2}\.\s+"           # leading "N. "
    r"[A-Z][A-Za-z'\-]*"           # first author surname
    r"(\s+[A-Z]{1,4})?"            # optional initials cluster (e.g. "Coates LC")
    r".{0,120}?"                   # author list / journal name
    r"\b(et al\.?|[A-Z][A-Za-z\s]+\.\s+\d{4};|\d{4};\d+(\([^)]*\))?:)"
)


def _looks_like_reference_entry(text: str) -> bool:
    """Heuristic — does this BODY text look like a citation? See _REFERENCE_LIKE_RE."""
    if not text:
        return False
    return bool(_REFERENCE_LIKE_RE.match(text.strip()))


def _block_from_extractor(raw: dict) -> ExtractedBlock:
    """One extractor block → one ExtractedBlock."""
    links = []
    for ln in raw.get("links", []) or []:
        if isinstance(ln, dict) and ln.get("uri"):
            links.append(ln["uri"])
        elif isinstance(ln, str):
            links.append(ln)
    role = raw.get("role") or "BODY"
    text = raw.get("text", "")
    # Defensive role downgrade for reference-shaped BODY content (D27).
    if role == "BODY" and _looks_like_reference_entry(text):
        role = "REFERENCE"
    return ExtractedBlock(
        id=raw["id"],
        role=role,
        subtype=raw.get("subtype"),
        text=text,
        page=raw.get("page"),
        bbox=_bbox_from_list(raw.get("bbox")),
        font_hierarchy=raw.get("font_hierarchy"),
        links=links,
    )


def _synthesize_module_text(module_raw: dict) -> str:
    """Concatenate fragment block texts to form `module.synthesized_text`."""
    parts: list[str] = []
    for frag in module_raw.get("fragments", []):
        for blk in frag.get("blocks", []):
            text = (blk.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _claim_subtype(module_raw: dict) -> Optional[str]:
    """
    Derive a claim subtype from module text + fragment metadata.

    The extractor doesn't yet stamp EFFICACY/SAFETY/COMPARATIVE on
    blocks, so we apply a small keyword classifier as a stand-in. This
    is documented as D24 in DECISIONS.md (revise once the extractor
    classifies natively).
    """
    text = _synthesize_module_text(module_raw).lower()
    if not text:
        return None
    if re.search(r"\b(adverse|safety|tolerab|side effect|adr|sae|warning)\b", text):
        return "SAFETY"
    if re.search(r"\b(\d+\s*mg|dose|dosing|mg/kg|once daily|bid|tid|titrat)\b", text):
        return "DOSING"
    if re.search(r"\b(vs|versus|compared to|superior|inferior)\b", text):
        return "COMPARATIVE"
    if re.search(r"\b(hr\s*\d|95%\s*ci|p\s*[<=]\s*0|reduced|improved|response|efficacy|survival|recurrence)\b", text):
        return "EFFICACY"
    return None


def _module_from_extractor(module_raw: dict) -> ExtractedModule:
    fragments: list[ExtractedFragment] = []
    block_ids: list[str] = []
    is_claim = False
    for frag in module_raw.get("fragments", []):
        role = frag.get("role")
        if role == "claim":
            is_claim = True
        for blk in frag.get("blocks", []):
            block_ids.append(blk["id"])
            fragments.append(
                ExtractedFragment(
                    role=role or "context",
                    text=blk.get("text", ""),
                    block_id=blk["id"],
                )
            )
    return ExtractedModule(
        id=module_raw["id"],
        claim=is_claim,
        subtype=_claim_subtype(module_raw),
        synthesized_text=_synthesize_module_text(module_raw),
        block_ids=block_ids,
        fragments=fragments,
        ref_ids=[],  # TODO: derive from blocks[].markers.refs
    )


# ─── supportive resources ────────────────────────────────────────────


_ABBR_PAIR_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9+\-]{0,9})\s*=\s*([^;]+?)(?=;|$)")


def _parse_abbreviation_block(text: str) -> list[dict]:
    """
    Parse an abbreviation block's free text into {acronym, expansion}.

    Real-world examples:
      "BSR=British Society for Rheumatology; EULAR=European Alliance…;
       MDA=minimal disease activity; MTX=methotrexate; PsA=psoriatic arthritis"
      "AE: adverse event; SAE: serious adverse event"
      "AE — adverse event"
    """
    members: list[dict] = []
    for m in _ABBR_PAIR_RE.finditer(text or ""):
        acronym = m.group(1).strip()
        expansion = m.group(2).strip().rstrip(".;,")
        if acronym and expansion:
            members.append({"acronym": acronym, "expansion": expansion})
    return members


def _supportive_from_extractor(raw_resources: list[dict]) -> list[SupportiveResource]:
    out: list[SupportiveResource] = []
    for r in raw_resources or []:
        rtype = r.get("type")
        if not rtype:
            continue
        if rtype == "abbreviation-set":
            members: list[dict] = []
            for blk in r.get("blocks", []):
                members.extend(_parse_abbreviation_block(blk.get("text", "")))
            out.append(SupportiveResource(type=rtype, members=members))
        elif rtype == "reference-set":
            members = []
            for blk in r.get("blocks", []):
                # Each block's text often contains multiple refs separated
                # by `\n`, "1. ", "2. " etc. For the POC we treat the
                # whole block as one citation if no obvious split.
                text = (blk.get("text") or "").strip()
                if not text:
                    continue
                # Split on a leading "<number>. " or "<number>) " marker.
                pieces = re.split(r"(?:^|\s)(?=\d{1,2}[.)]\s+)", text)
                for piece in pieces:
                    piece = piece.strip()
                    if not piece:
                        continue
                    m = re.match(r"^(\d{1,2})[.)]\s*(.+)$", piece)
                    if m:
                        members.append({"ref_id": f"ref_{m.group(1)}", "citation": m.group(2).strip()})
                    else:
                        members.append({"ref_id": f"ref_{len(members)+1}", "citation": piece})
            out.append(SupportiveResource(type=rtype, members=members))
        elif rtype == "footnote-set":
            members = []
            for blk in r.get("blocks", []):
                text = (blk.get("text") or "").strip()
                if text:
                    members.append({"text": text, "block_id": blk.get("id")})
            out.append(SupportiveResource(type=rtype, members=members))
        else:
            # Pass through unknown types so consumers can decide.
            out.append(SupportiveResource(type=rtype, members=r.get("blocks", [])))
    return out


# ─── envelope ────────────────────────────────────────────────────────


def _envelope_from_extractor(doc_reg: dict) -> dict:
    """Concatenate text per envelope key."""
    out: dict[str, str] = {}
    for key, items in (doc_reg or {}).items():
        if not items:
            continue
        if isinstance(items, list):
            texts = [
                (it.get("text") or "").strip()
                for it in items
                if isinstance(it, dict) and (it.get("text") or "").strip()
            ]
            if texts:
                out[key] = " ".join(texts)
        elif isinstance(items, str):
            if items.strip():
                out[key] = items.strip()
    return out


# ─── meta ────────────────────────────────────────────────────────────


_DOC_TYPE_BY_CHANNEL = {
    "email": "email",
    "slide": "slide",
    "leave_behind": "leave_behind",
    "event_invite": "event_invite",
}


def _meta_from_extractor(asset_raw: dict, today: date | None = None) -> AssetMeta:
    """Build AssetMeta. Falls back gracefully when fields are absent."""
    today = today or date.today()
    brand = ((asset_raw.get("product") or {}).get("brand") or "").upper() or "UNKNOWN"
    market = (asset_raw.get("market") or "??").upper()
    language = (asset_raw.get("language") or "en").lower()
    channel = (asset_raw.get("channel") or "email").lower()
    doc_type = _DOC_TYPE_BY_CHANNEL.get(channel, "email")

    prepared = asset_raw.get("date_of_preparation")
    age_days: Optional[int] = None
    if prepared:
        try:
            d = datetime.strptime(prepared[:10], "%Y-%m-%d").date()
            age_days = (today - d).days
        except (ValueError, TypeError):
            prepared = None

    return AssetMeta(
        brand=brand,
        market=market,
        language=language,
        doc_type=doc_type,  # type: ignore[arg-type]
        channel=f"HCP {doc_type}",
        code=asset_raw.get("approval_code"),
        prepared=prepared,
        age_days=age_days,
    )


# ─── public entrypoint ───────────────────────────────────────────────


def adapt(extraction: dict, *, asset_id: str, pdf_path: str | None = None) -> ExtractedAsset:
    """
    Convert one extractor `extraction.json` dict into an `ExtractedAsset`.

    `asset_id` overrides the extractor's internal id so the precheck
    engine can use a stable, URL-friendly id (the extractor's
    `asset_xxxxxxxxxxxx` works but isn't pretty).

    `pdf_path` wires the source PDF for the GET /api/preview route.
    Pass `None` if the PDF isn't on this filesystem.
    """
    asset_raw = extraction.get("asset") or {}
    blocks = [_block_from_extractor(b) for b in extraction.get("blocks", [])]
    modules = [_module_from_extractor(m) for m in extraction.get("modules", [])]
    resources = _supportive_from_extractor(extraction.get("supportive_resources", []))
    envelope = _envelope_from_extractor(extraction.get("document_regulatory", {}))

    meta = _meta_from_extractor(asset_raw)
    profile_id = asset_raw.get("compliance_profile_id") or "UK-Branded-Promotional"

    return ExtractedAsset(
        asset_id=asset_id,
        meta=meta,
        profile_id=profile_id,
        modules=modules,
        blocks=blocks,
        supportive_resources=resources,
        envelope=envelope,
        pdf_path=pdf_path,
    )


def adapt_file(json_path: Path, *, asset_id: str, pdf_path: str | None = None) -> ExtractedAsset:
    """Convenience wrapper — load JSON from disk and adapt."""
    raw = json.loads(Path(json_path).read_text())
    return adapt(raw, asset_id=asset_id, pdf_path=pdf_path)
