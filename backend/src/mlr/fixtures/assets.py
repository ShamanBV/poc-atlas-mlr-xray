"""
In-memory store of extracted assets, keyed by asset_id.

Stands in for the real Atlas extractor pipeline_v5 output until the
backend is plumbed to live extraction. Each fixture is shaped like what
the extractor would emit — `ExtractedAsset` with blocks, supportive
resources, envelope items.

The KISQALI fixture is the asset the §6 sample payload in
`MLR_PRECHECK_API.md` is built against, minus the precheck verdicts
themselves (those are computed at request time by the engine).
"""

from __future__ import annotations

from typing import Optional

from mlr.precheck.schema import (
    AssetMeta,
    ExtractedAsset,
    ExtractedBlock,
    ExtractedFragment,
    ExtractedModule,
    SupportiveResource,
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


_STORE: dict[str, ExtractedAsset] = {
    KISQALI_UK_001.asset_id: KISQALI_UK_001,
}


def get(asset_id: str) -> Optional[ExtractedAsset]:
    return _STORE.get(asset_id)


def all_ids() -> list[str]:
    return sorted(_STORE.keys())
