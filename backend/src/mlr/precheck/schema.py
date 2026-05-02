"""
Pydantic models for the MLR Precheck API.

Direct port of `MLR_PRECHECK_API.md` §2 — keep field names + nullability
identical so the serialised JSON matches the contract byte-for-byte.

The frontend types in `XRayData.jsx` use camelCase already; this module
emits snake_case to match the API contract document. Frontend adapter
maps if needed.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── leaf types ──────────────────────────────────────────────────────


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class DiffSegment(BaseModel):
    t: str
    s: Literal["k", "d", "a"]


class PatternBase(BaseModel):
    pattern_id: str
    description: str
    coverage: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)
    window_months: int = Field(ge=0)
    rule_id: Optional[str] = None


class DependencyTriggerCoverage(BaseModel):
    predicate_hits_in_corpus: int = Field(ge=0)
    requirement_hits: int = Field(ge=0)
    confidence_label: Literal["high", "medium", "low"]


class DependencyTrigger(BaseModel):
    rule_id: str
    predicate: str
    rationale: str
    coverage: DependencyTriggerCoverage


# ─── zone + email block ──────────────────────────────────────────────

ZoneStatus = Literal["clean", "attn", "miss"]
ZoneSeverity = Literal["info", "warn", "block"]
ZoneLayer = Literal["claim", "regulatory", "abbreviation", "cascade"]
ZoneLane = Literal["M", "L", "R"]


class Zone(BaseModel):
    id: str
    doc_pos: float  # float so we can interleave abbreviation zones at e.g. 9.5
    label: str
    lanes: list[ZoneLane]
    status: ZoneStatus
    severity: ZoneSeverity

    layer: ZoneLayer
    sub_layer: str

    evidence: str
    evidence_detail: str

    extracted_content: Optional[str] = None
    canonical_content: Optional[str] = None

    diff: Optional[list[DiffSegment]] = None
    pattern_base: Optional[PatternBase] = None
    dependencies_triggered: list[DependencyTrigger] = Field(default_factory=list)

    annotation_draft: Optional[str] = None
    vvpm_anchor: Optional[str] = None
    pin: Optional[int] = None

    # Spatial anchor for the preview overlay. When present, the
    # frontend renders a hover/click hotspot on the PDF page at this
    # bbox. Optional because Layer 2 envelope-level findings have no
    # natural spatial location (the asset is *missing* the content).
    bbox: Optional[BoundingBox] = None
    page: Optional[int] = None  # 1-indexed; matches preview/{id}/pages


class EmailBlock(BaseModel):
    id: str
    type: str
    match: ZoneStatus
    pin: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    page: Optional[int] = None
    ghost_label: Optional[str] = None


# ─── asset envelope ──────────────────────────────────────────────────


class AssetMeta(BaseModel):
    brand: str
    market: str
    language: str
    doc_type: Literal["email", "slide", "leave_behind", "event_invite"]
    channel: str
    code: Optional[str] = None
    prepared: Optional[str] = None  # ISO date
    age_days: Optional[int] = None


class AssetProfile(BaseModel):
    id: str
    selected_by: Literal["metadata", "user", "default"]


class AssetScores(BaseModel):
    overall: int = Field(ge=0, le=100)
    medical: int = Field(ge=0, le=100)
    legal: int = Field(ge=0, le=100)
    regulatory: int = Field(ge=0, le=100)


class AssetLibrary(BaseModel):
    sample_size: int = Field(ge=0)
    last_ingest_at: str  # ISO timestamp
    coverage_warning: Optional[str] = None


class AssetPreview(BaseModel):
    pdf_url: Optional[str] = None
    html_url: Optional[str] = None
    page_count: Optional[int] = None


AssetVerdict = Literal["Pass", "Warn", "Fail"]


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    schema_version: Literal["1.0"] = "1.0"

    meta: AssetMeta
    identity: str
    profile: AssetProfile
    scores: AssetScores
    verdict: AssetVerdict

    zones: list[Zone]
    email_blocks: list[EmailBlock]
    library: AssetLibrary
    preview: AssetPreview

    generated_at: str  # ISO timestamp
    cache_key: str


# ─── error envelope ──────────────────────────────────────────────────


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ─── extracted-asset shape (input to the engine) ─────────────────────
#
# This is what the upstream Atlas extractor (pipeline_v5 for emails,
# pipeline_v4 for slides) hands to the precheck engine. It is NOT the
# Asset payload above — that's the precheck OUTPUT. The shapes below
# are the minimal subset Layer 3 (abbreviation precheck) needs; later
# layers will extend or compose more fields.


class ExtractedBlock(BaseModel):
    id: str
    role: str  # "CLAIM" | "BODY" | "FOOTNOTE" | "AUDIENCE_RESTRICTION" | …
    subtype: Optional[str] = None
    text: str
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    font_hierarchy: Optional[str] = None  # "H1" | "H2" | "BODY" | "SM" | …
    links: list[str] = Field(default_factory=list)  # off-domain URIs in the block


class ExtractedFragment(BaseModel):
    """A claim/evidence/context/source/qualifier fragment within a module."""

    role: str  # "claim" | "evidence" | "context" | "source" | "qualifier"
    text: str
    block_id: Optional[str] = None  # back-link to the originating block


class ExtractedModule(BaseModel):
    """A logical claim group containing claim + evidence + context fragments."""

    id: str
    claim: bool = False  # is this a claim module?
    subtype: Optional[str] = None  # EFFICACY | SAFETY | COMPARATIVE | …
    synthesized_text: str = ""  # concatenated module text used by `text_matches`
    block_ids: list[str] = Field(default_factory=list)
    fragments: list[ExtractedFragment] = Field(default_factory=list)
    ref_ids: list[str] = Field(default_factory=list)


class SupportiveResource(BaseModel):
    type: str  # "abbreviation-set" | "reference-set" | "footnote-set" | …
    members: list[dict] = Field(default_factory=list)


class ExtractedAsset(BaseModel):
    """What the extractor delivers; what the precheck engine consumes."""

    asset_id: str
    meta: AssetMeta
    profile_id: str  # selected upstream from (brand, market, doc_type)
    modules: list[ExtractedModule] = Field(default_factory=list)
    blocks: list[ExtractedBlock] = Field(default_factory=list)
    supportive_resources: list[SupportiveResource] = Field(default_factory=list)
    envelope: dict = Field(default_factory=dict)  # indication / safety / approval_info / ...

    # Local filesystem path to the source PDF, used by the
    # GET /api/preview/{asset_id}.pdf route. None means no preview
    # available for this asset (the route returns 404).
    pdf_path: Optional[str] = None
