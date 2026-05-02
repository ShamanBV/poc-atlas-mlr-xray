"""
In-memory store of extracted assets, keyed by asset_id.

Two flavours of fixture live here:

  1. **Synthetic** — handcrafted ExtractedAsset objects, used for
     contract demonstrations and matching the §6 sample payload in
     `MLR_PRECHECK_API.md`. Useful when you need a specific failure
     mode (e.g. envelope.audience_restriction missing) reliably.

  2. **Real** — loaded via the extractor adapter from the
     extractor-service's `eval_atlas_*` extraction.json outputs.
     These exercise the engine against actual UK email content.

Both populate `_STORE`; `get(asset_id)` returns whichever was registered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mlr.ingest.extractor_adapter import adapt_file
from mlr.precheck.schema import (
    AssetMeta,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedFragment,
    ExtractedModule,
    SupportiveResource,
)


# Where the extractor service drops its eval outputs. Hardcoded for
# the POC — production swaps this for an Atlas API call or a
# library-store path once the Vault → Atlas ingest flow is live.
_EXTRACTOR_OUTPUTS = Path(
    "/Users/mauricevanleeuwen/Development/dev_projects/extractor-service/"
    "test_sets/eval_atlas_20260430T172755Z"
)
_PDF_DIR = Path(
    "/Users/mauricevanleeuwen/Development/dev_projects/extractor-service/"
    "test_sets/emails"
)


def _real(stem: str, asset_id: str) -> ExtractedAsset:
    """Load one extractor JSON + matching PDF into an ExtractedAsset."""
    json_path = _EXTRACTOR_OUTPUTS / f"{stem}.extraction.json"
    pdf_path = _PDF_DIR / f"{stem}.pdf"
    return adapt_file(
        json_path,
        asset_id=asset_id,
        pdf_path=str(pdf_path) if pdf_path.is_file() else None,
    )


# ─── KISQALI UK demo asset ────────────────────────────────────────────
#
# Aligned with the §6 sample payload in MLR_PRECHECK_API.md:
#   - Body text uses AE, ORR, HR+, HER2- but the abbreviation-set only
#     defines HR / CI / OS / PFS / ET → Layer 3 emits 4 abbreviation zones.
#   - envelope.audience_restriction is INTENTIONALLY ABSENT → Layer 2
#     `r_audience_bar_when_hcp_only_profile` fires `miss` / `block`.
#   - No SAFETY block + no envelope.safety → Layer 2
#     `r_safety_reminder_after_efficacy_claim` fires `miss` / `warn`.
#   - Modules wrap the CLAIM block(s) so `any_module:` predicates match.

KISQALI_UK_001 = ExtractedAsset(
    asset_id="tmp:demo-kisqali-uk-001",
    meta=AssetMeta(
        brand="KISQALI",
        market="UK",
        language="en",
        doc_type="email",
        channel="HCP email",
        code="FA-11551654",
        prepared="2026-03-14",
        age_days=49,
    ),
    profile_id="UK-Branded-Promotional",
    # Real source PDF lives in the extractor-service test corpus. The
    # extracted blocks/modules/envelope below are still synthetic for
    # the POC — wiring the actual extractor pipeline output for this
    # PDF is the next slice. For now this gives the X-Ray UI a real
    # email to display in the left preview pane.
    pdf_path=(
        "/Users/mauricevanleeuwen/Development/dev_projects/extractor-service/"
        "test_sets/emails/UK - KISQALI - 2025 - 5-year data KTE.pdf"
    ),
    modules=[
        ExtractedModule(
            id="mod_efficacy_001",
            claim=True,
            subtype="EFFICACY",
            synthesized_text=(
                "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
                "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
            ),
            block_ids=["blk_002"],
            fragments=[
                ExtractedFragment(role="claim", text="KISQALI® + ET reduced the risk of recurrence by 25.2%", block_id="blk_002"),
                ExtractedFragment(role="evidence", text="HR 0.748, 95% CI 0.618–0.906; p=0.0014", block_id="blk_002"),
                ExtractedFragment(role="context", text="At 5 years, vs ET alone", block_id="blk_002"),
            ],
            ref_ids=["ref_1"],
        ),
    ],
    blocks=[
        ExtractedBlock(
            id="blk_001",
            role="HEADER",
            text="KISQALI® (ribociclib) — your patients with HR+/HER2- early breast cancer",
            page=1,
            font_hierarchy="H1",
        ),
        ExtractedBlock(
            id="blk_002",
            role="CLAIM",
            subtype="EFFICACY",
            text=(
                "At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% "
                "vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."
            ),
            page=1,
            font_hierarchy="H2",
        ),
        ExtractedBlock(
            id="blk_003",
            role="BODY",
            text=(
                "Treatment-related AEs were monitored throughout. The ORR was "
                "consistent with the broader HR+ population, including HER2- "
                "subgroups. PFS data continue to mature."
            ),
            page=1,
            font_hierarchy="BODY",
        ),
        ExtractedBlock(
            id="blk_004",
            role="CTA",
            text="See the latest data",
            page=1,
            font_hierarchy="BODY",
        ),
        ExtractedBlock(
            id="blk_005",
            role="FOOTNOTE",
            subtype="STUDY_DESIGN",
            text=(
                "NATALEE was a phase III, randomised, open-label study (N=5,101) "
                "evaluating KISQALI® + ET vs ET alone in HR+/HER2- early breast cancer."
            ),
            page=1,
            font_hierarchy="SM",
        ),
        ExtractedBlock(
            id="blk_006",
            role="CONTACT_INFO",
            text="Novartis Pharmaceuticals UK Limited · Frimley Business Park · Camberley GU16 7SR",
            page=1,
            font_hierarchy="SM",
        ),
    ],
    supportive_resources=[
        SupportiveResource(
            type="abbreviation-set",
            members=[
                {"acronym": "HR", "expansion": "hazard ratio"},
                {"acronym": "CI", "expansion": "confidence interval"},
                {"acronym": "OS", "expansion": "overall survival"},
                {"acronym": "PFS", "expansion": "progression-free survival"},
                {"acronym": "ET", "expansion": "endocrine therapy"},
            ],
        ),
        SupportiveResource(
            type="reference-set",
            members=[
                {
                    "ref_id": "ref_1",
                    "citation": "Slamon DJ et al. N Engl J Med. 2024;390:1080-1091.",
                },
            ],
        ),
    ],
    envelope={
        "indication": "KISQALI® is indicated for HR+/HER2- early breast cancer at high risk of recurrence.",
        "approval_info": "FA-11551654 · March 2026",
        # `audience_restriction` intentionally absent — Layer 2 should flag.
        "pharmacovigilance": (
            "Adverse events should be reported. Reporting forms and information "
            "can be found at https://yellowcard.mhra.gov.uk."
        ),
        "prescribing_information": "https://novartis.example/uk/kisqali-pi",
        "unsubscribe": "https://novartis.example/unsubscribe",
        "disclaimers": "See our privacy policy at https://novartis.example/privacy.",
    },
)


# ─── real assets (loaded via extractor adapter) ──────────────────────


def _load_real_assets() -> dict[str, ExtractedAsset]:
    """
    Load real-data fixtures lazily — if the extractor outputs aren't
    present (e.g. running on CI / a fresh checkout), gracefully skip.
    """
    real: dict[str, ExtractedAsset] = {}
    candidates = [
        ("UK - Cosentyx - 2025 - Rheum - MDA SFMC", "real:cosentyx-uk-rheum-mda-001"),
        ("UK - Scemblix - 2024 - HMY106 Automated Promotional Campaign Email 2", "real:scemblix-uk-hmy106-002"),
        ("UK - Kesimpta 2025 - Aim for NEDA KTE", "real:kesimpta-uk-neda-001"),
    ]
    for stem, asset_id in candidates:
        json_path = _EXTRACTOR_OUTPUTS / f"{stem}.extraction.json"
        if not json_path.is_file():
            continue
        try:
            real[asset_id] = _real(stem, asset_id)
        except Exception as e:  # noqa: BLE001 — best-effort load; one bad JSON shouldn't kill the others
            print(f"[fixtures] failed to load {stem}: {e}")
    return real


_STORE: dict[str, ExtractedAsset] = {
    KISQALI_UK_001.asset_id: KISQALI_UK_001,
    **_load_real_assets(),
}


def get(asset_id: str) -> Optional[ExtractedAsset]:
    return _STORE.get(asset_id)


def all_ids() -> list[str]:
    return sorted(_STORE.keys())


def all_assets() -> list[ExtractedAsset]:
    """Read-only list — used by the asset-switcher route."""
    return [_STORE[k] for k in sorted(_STORE.keys())]
