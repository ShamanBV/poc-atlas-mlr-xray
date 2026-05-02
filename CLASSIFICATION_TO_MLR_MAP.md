# Classification → MLR usage map

The canonical reference for **every classification element the
extraction pipeline emits** and **how the MLR precheck consumes it**.
Backend devs read this to wire predicates / requirements correctly;
MLR reviewers read it to understand what each finding means and which
extraction signal triggered it.

## How to read this doc

For every classification element (role, block_type, subtype, supportive
set type, envelope key, visual type) the entry answers six questions:

1. **What is it?** — definition + canonical example.
2. **Who emits it?** — which extraction pass/classifier produces it
   (`pre_classifier`, `font_normalizer`, `navigation_detector`,
   `fragment_builder`, `envelope`, `visual_describer`, …).
3. **MLR pillar** — Medical / Legal / Regulatory / Navigation / Visual.
4. **MLR layer** — which precheck layer consumes it (claim /
   regulatory / abbreviation / cascade / none-utility).
5. **Used in predicates** — which dependency rules' `predicate`
   references this element. (Cross-references
   `dependency_rules.yaml` rule ids.)
6. **Used in requirements** — which rules' `requires` clause checks
   for this element. (When unmet → drives a verdict.)
7. **Verdict shape** — when this element drives a verdict, what
   `Zone.layer` / `sub_layer` / `severity` it takes.

The structure mirrors the precheck spec layers
(`MLR_PRECHECK_SPEC.md` §3 → claim, §4 → regulatory, §5 →
abbreviation) plus the cascade engine.

---

## §0 Quick-reference matrix

Every classification element × MLR layer it participates in. `●` = primary
consumer, `○` = secondary signal, `–` = not used.

### Roles

| Role | Pillar | Claim | Regulatory | Abbreviation | Cascade |
|------|--------|:-:|:-:|:-:|:-:|
| `CLAIM`                  | Medical    | ● | ○ | – | ● |
| `BODY`                   | Medical    | ○ | – | ● | – |
| `BODY:STUDY_DESIGN`      | Medical    | ○ | – | – | ● |
| `BODY:ADAPTED_FROM`      | Medical    | ○ | – | – | – |
| `REFERENCE`              | Medical    | ● | – | – | ● |
| `FOOTNOTE`               | Medical    | ○ | – | – | ● |
| `ABBREVIATION`           | Medical    | – | – | ● | ● |
| `INDICATION`             | Regulatory | – | ● | – | ● |
| `SAFETY`                 | Regulatory | ○ | ● | – | ● |
| `SAFETY:ISI`             | Regulatory | ○ | ● | – | ● |
| `PHARMACOVIGILANCE`      | Regulatory | – | ● | – | ● |
| `PRESCRIBING_INFORMATION`| Regulatory | – | ● | – | ● |
| `AUDIENCE_RESTRICTION`   | Regulatory | – | ● | – | ● |
| `PROMOTIONAL_NOTICE`     | Regulatory | – | ● | – | ● |
| `DISCLAIMERS`            | Legal      | – | ○ | – | ● |
| `DISCLAIMERS:THIRD_PARTY`| Legal      | – | ● | – | ● |
| `CONTACT_INFO`           | Legal      | – | – | – | ● |
| `APPROVAL_INFO`          | Legal      | – | ● | – | ● |
| `UNSUBSCRIBE`            | Legal      | – | – | – | ● |
| `CTA`                    | Navigation | ○ | ○ | – | – |
| `PRIMARY_MENU`           | Navigation | – | – | – | – |
| `SECONDARY_MENU`         | Navigation | – | – | – | – |
| `SLIDE_NAV`              | Navigation | – | – | – | – |
| `REGULATORY_MENU`        | Regulatory | – | ● | – | ● |
| `BRAND_VISUAL`           | Visual     | – | – | – | ● |
| `MEDICAL_VISUAL`         | Visual     | ○ | – | – | – |
| `DATA_VISUAL`            | Visual     | ● | – | – | ○ |
| `TABLE`                  | Visual     | ● | – | – | – |

### Block types + structural levels (cross-cutting)

| Field          | Purpose in MLR |
|----------------|----------------|
| `block_type=heading`     | Marks claim candidates (paired with `font_hierarchy ∈ {H1, H2}`) for Layer 1 |
| `block_type=subheading`  | Sub-claim or section marker; informs claim grouping |
| `block_type=body`        | Default content; main input to abbreviation detection |
| `block_type=bullet`      | Promoted to `evidence` design type in the X-Ray |
| `block_type=caption`     | "Figure adapted from…" — drives Layer 1 source-block checks |
| `block_type=strapline`   | Tagline / callout — claim candidate when font is large |
| `block_type=reference`   | Reference list entry; consumed by Layer 1 ref-tuple matching |
| `block_type=footnote`    | Footnote sentence; consumed by Layer 1 footnote-corpus matching |
| `block_type=abbreviation`| Abbreviation list block; primary input to Layer 3 |
| `block_type=study-design`| Study methodology block; matched against Layer 1 evidence_blocks |
| `block_type=legal`       | Corporate boilerplate; subtypes drive cascade rule satisfaction |

### Supportive resource sets

| Set type            | Built by                          | Used by                                     |
|---------------------|-----------------------------------|---------------------------------------------|
| `reference-set`     | `fragment_builder` + `ref_parser` | Layer 1 ref tuple equality; cascade `r_reference_list`; precheck `r_reference_list_complete` |
| `footnote-set`      | `fragment_builder`                | Layer 1 footnote-corpus matching            |
| `abbreviation-set`  | `fragment_builder` + post-split   | Layer 3 detect-and-define check; auto-derives the customer glossary |
| `legal-set`         | `fragment_builder`                | Cascade `r_mah_legal_entity` satisfaction   |

### Document-regulatory envelope keys (email)

| Envelope key            | Role(s) of contained blocks    | Used by                                    |
|-------------------------|--------------------------------|--------------------------------------------|
| `audience_restriction`  | `AUDIENCE_RESTRICTION`         | Cascade `r_audience_restriction_bar`; precheck `r_audience_bar_when_hcp_only_profile` |
| `indication`            | `INDICATION`                   | Cascade `r_indication_block`; precheck `r_indication_when_drug_named` |
| `prescribing_information` | `PRESCRIBING_INFORMATION`     | Cascade `r_prescribing_info_bar`; precheck `r_prescribing_info_link` |
| `safety`                | `SAFETY` + `SAFETY:ISI`        | Cascade `r_safety_reminder`; precheck `r_isi_when_dosing_mentioned` |
| `pharmacovigilance`     | `PHARMACOVIGILANCE`            | Cascade `r_ae_reporting_box`; precheck `r_ae_reporting_when_promotional` |
| `disclaimers`           | `DISCLAIMERS` (subtypes)       | Cascade `r_mah_legal_entity` / `r_confidentiality_notice`; precheck `r_third_party_disclaimer_when_external_link` |
| `unsubscribe`           | `UNSUBSCRIBE`                  | Cascade `r_unsubscribe_privacy`; precheck `r_unsubscribe_privacy_links` |
| `approval_info`         | `APPROVAL_INFO`                | Cascade `r_approval_code_format` + `r_date_of_preparation`; precheck duplicates |
| `promotional_notice`    | `PROMOTIONAL_NOTICE`           | Cascade rule (when defined per market)     |
| `navigation_cta`        | `CTA`                          | Currently informational only               |

---

## §1 Medical pillar elements

### `CLAIM`

**What it is.** A promotional assertion about a product's efficacy,
safety, comparative position, or epidemiology. The headline of a module.

**Canonical example.** `"At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014)."`

**Emitted by.** `pre_classifier._classify` returns `("heading", "CLAIM", subtype, 0.9)` when `docling_label == "section_header"` AND `structural_level ∈ {H1, H2}`. Lower-confidence claim candidates come from font hierarchy alone (`0.7`). The `claim_grouper` then promotes one CLAIM block per module to be the module's `claim` (sets `module.claim = True`, populates `module.text`).

**Subtypes (claim_subtype).** `EFFICACY`, `SAFETY`, `COMPARATIVE`, `EPIDEMIOLOGY`, `QOL`, `ACCESS`. Drives library lookup filtering (efficacy claims compared only to efficacy claims).

**MLR pillar.** Medical.

**MLR layer.** Layer 1 (claim precheck) — primary consumer.

**Used in predicates.**
- `r_safety_reminder_after_efficacy_claim` — predicate `any_module.claim=true AND subtype_in=[EFFICACY, COMPARATIVE]`
- `r_trial_design_footnote_when_data_cited` — predicate matches `claim.text` against trial-data regex
- `r_indication_when_drug_named` — predicate matches `claim.text` against brand-name regex
- `r_isi_when_dosing_mentioned` — paired with `BODY` text matching dosing copy

**Used in requirements.** Indirectly — claims drive Layer 1 verdicts (match / drift / missing) via the library lookup.

**Verdict shape.** One Zone per claim module:
```
Zone {
  layer: "claim",
  sub_layer: "claim:<subtype>",       // e.g. "claim:efficacy"
  status:    match | drift | missing,
  severity:  info | warn | block,
  evidence:  "Approved verbatim · 0.97" | "Partial match · 0.84" | "No approved variant · n=42 candidates",
  diff:      [...]                    // when extracted ≠ canonical
}
```

---

### `BODY`

**What it is.** Default content paragraph — supporting text under a claim, study description, intro paragraph. The bulk of the pipeline's text output.

**Canonical example.** `"Patients on KESIMPTA continuous treatment showed sustained efficacy across 6 years."`

**Emitted by.** `pre_classifier._classify` defaults to `("body", "BODY", "", 0.5)` for content blocks Docling labels as `text` with hierarchy `P`. The `fragment_builder` then groups BODY blocks under their parent module as `evidence` / `context` / `qualifier` fragments.

**Subtypes.**
- `STUDY_DESIGN` — study methodology paragraph (`pre_classifier._is_study_design` regex match). Drives Layer 1 study-design comparison.
- `ADAPTED_FROM` — `"Adapted from <author>, <year>"` source attribution. Maps to Layer 1 source-block check.
- `SALUTATION` — email-only, `"Dear {{userName}},"`. Used by cascade for email envelope detection.
- `SENDER_SIGNATURE` — email-only signature block.

**MLR pillar.** Medical (when the body sits inside a claim module) / Legal (when subtype ∈ Salutation/Signature).

**MLR layer.** Layer 1 secondary signal — body blocks contribute to `evidence_text_corpus` for cosine similarity against approved versions. Also primary input to Layer 3 (acronym detection).

**Used in predicates.**
- `r_isi_when_dosing_mentioned` — predicate `any_block.text_matches(/dose|dosing|mg\/kg|.../)`
- `r_kol_conflict_disclosure` — predicate `any_block.text_matches(/Prof|Dr/...)`
- `r_third_party_disclaimer_when_external_link` — predicate `any_block.has_external_link=true`
- All abbreviation rules — body text is the corpus for acronym detection

**Used in requirements.**
- `r_mah_legal_entity_in_footer` — `requires: any_block.role=CONTACT_INFO OR any_block.text_matches(/Pharmaceuticals|Limited|GmbH/)`
- `r_kol_conflict_disclosure` — `requires: any_block.text_matches(/conflict of interest|fair market value/)`

**Verdict shape.** Indirect — body blocks don't typically produce their own zone; they contribute to a parent module's claim verdict OR support a regulatory zone via predicate matching. Subtype `STUDY_DESIGN` produces its own Zone with `layer:"claim", sub_layer:"claim:study_design"`.

---

### `REFERENCE`

**What it is.** Numbered citation in a reference list. `"1. Marchetti M, et al. Lancet Haematol. 2022;9:e301-e311."`

**Emitted by.** `pre_classifier._classify` returns REFERENCE when text matches numbered-citation regex (e.g. `^\d{1,2}\.\s+[A-Z]`) AND text contains journal markers (`et al.`, `J <journal> YYYY`, `2024;196:113422`, DOI). The compound supportive splitter (`pre_classifier._split_compound_supportive`) extracts references from blocks where they're glued to abbreviations.

**Subtypes.** `JOURNAL`, `SMPC`, `DATA_ON_FILE`, `ONLINE`, `GUIDELINE`, `CONGRESS`, `CSR`, `OTHER`.

**MLR pillar.** Medical.

**MLR layer.** Layer 1 — references in the asset's `reference-set` are matched as tuples (author, year, journal, vol:pp) against the cited references in approved versions.

**Used in predicates.** None directly — references are pulled into modules via `module.ref_ids` set membership.

**Used in requirements.**
- `r_reference_list_complete` (precheck) — `requires: supportive_resource{type:reference-set, present:true, member_count_min:1}`
- `r_reference_list` (cascade) — every `<sup>n</sup>` cited in module text must resolve to a reference-set member.

**Verdict shape.** When a reference is cited but not present in the reference-set:
```
Zone {
  layer: "claim",                     // or "cascade" depending on which engine fires first
  sub_layer: "claim:orphaned-ref",
  status: "drift",
  severity: "block",
  diff_subtype: "orphaned-ref",
  evidence: "Cites ref [4] not in reference-set"
}
```

When a cited reference is in the asset's reference-set BUT not in any approved version's reference-set:
```
Zone {
  layer: "claim",
  sub_layer: "claim:novel-ref",
  status: "drift",
  severity: "warn"
}
```

---

### `FOOTNOTE`

**What it is.** Sentence prefixed with `*`, `†`, `‡`, `§`, or `¶` qualifying a claim or stat. `"*HCT control defined as an HCT of <45%."`

**Emitted by.** `pre_classifier._classify` returns FOOTNOTE when text starts with a footnote marker followed by a real sentence, OR when Docling labels the block `footnote`. Compound splitter peels footnote sentences out of glued abbreviation blocks.

**Subtypes.** `STATISTICAL`, `ADAPTED_FROM`, `STUDY_DESIGN`, `APPROVAL_STATUS`, `OTHER`.

**MLR pillar.** Medical.

**MLR layer.** Layer 1 secondary — each module's `footnote_ids` resolve to footnote-set members; footnote text is matched against the approved version's footnote_corpus.

**Used in predicates.** None directly.

**Used in requirements.**
- `r_trial_design_footnote_when_data_cited` — `requires: any_block.role=FOOTNOTE AND subtype_in=[STUDY_DESIGN]` OR `any_block.role=BODY AND subtype_in=[STUDY_DESIGN]`

**Verdict shape.** Footnote drift surfaces inline on the parent claim's Zone (`Zone.diff` includes footnote text segments). A standalone Footnote drift Zone fires only when the footnote is wholly orphaned (cited symbol not present in any approved variant).

---

### `ABBREVIATION`

**What it is.** Acronym definition list. `"AML, acute myeloid leukemia. CV, cardiovascular. HCT, haematocrit."`

**Emitted by.** `pre_classifier._classify` returns ABBREVIATION when text contains ≥2 abbreviation pairs (`[A-Z]{2,5}, <expansion>`). Block-level granularity; individual pairs are split into `block.items[]` by the normaliser.

**Subtypes.** None.

**MLR pillar.** Medical.

**MLR layer.** Layer 3 (abbreviation precheck) — primary consumer. Also feeds the auto-derived customer glossary (`MLR_PRECHECK_SPEC.md` §5.1).

**Used in predicates.** None directly — Layer 3 detects acronym usage in body text and looks them up against the asset's abbreviation-set.

**Used in requirements.**
- `r_abbreviations_defined` (cascade + precheck) — `requires: supportive_resource{type:abbreviation-set, present:true, member_count_min:1}`. Per-acronym checks happen inside Layer 3, not via this rule.

**Verdict shape.** One Zone per acronym finding:
```
Zone {
  id: "abbr_AE",
  layer: "abbreviation",
  sub_layer: "abbreviation:AE",
  label: "AE — used but not defined",
  status: "attn" | "miss",            // miss when defined-but-orphaned
  severity: "warn",
  evidence: "Acronym used 3× without definition",
  pattern_base: { pattern_id: "uk_glossary_general_AE", description: "AE — adverse event" }
}
```

---

## §2 Regulatory pillar elements

### `INDICATION`

**What it is.** Therapeutic indication statement. `"JAKAVI® is indicated for the treatment of disease-related splenomegaly or symptoms in adult patients with primary myelofibrosis…"`

**Emitted by.** Email envelope detector (`src/pipeline_email/envelope.py`). Slides currently emit it as a CLAIM:HEADER block — needs alignment in pipeline_v5.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2 (document-level regulatory precheck) — primary consumer. Cascade engine also uses it for `r_indication_block` satisfaction.

**Used in predicates.** None directly — it's the *requirement* of `r_indication_when_drug_named`.

**Used in requirements.**
- `r_indication_when_drug_named` (precheck) — `requires: envelope{key:indication, present:true}`. Once pattern bank is populated, additionally requires `matches_pattern{id:"<market>_email_indication_<brand>", threshold:0.95}`.
- `r_indication_block` (cascade) — same requirement, fires unconditionally on branded promotional profile.

**Verdict shape.** When missing:
```
Zone {
  layer: "regulatory",
  sub_layer: "regulatory:indication",
  status: "miss",
  severity: "block",
  evidence: "Missing",
  pattern_base: { pattern_id: "uk_email_indication_jakavi", coverage: 1.0, n: 287 }
}
```

When present but text drifts from approved variants:
```
Zone {
  layer: "regulatory",
  sub_layer: "regulatory:indication",
  status: "drift",
  severity: "warn",
  pattern_base: { ... }
}
```

---

### `SAFETY` / `SAFETY:ISI`

**What it is.** Important Safety Information block — adverse reactions, warnings, contraindications, dosing safety. ISI is the formal US/UK ISI block; `WARNINGS`, `CONTRAINDICATIONS`, `DOSING` are sub-block flavours.

**Emitted by.** Email envelope detector (subtype detection from text patterns + section headers). Slides emit as separate text blocks; pipeline_v5 should fold into envelope.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2.

**Used in predicates.**
- `r_isi_when_dosing_mentioned` — predicate matches body text against dosing regex; SAFETY block presence is the *requirement*.

**Used in requirements.**
- `r_safety_reminder` (cascade) — efficacy claim → SAFETY block must be paired
- `r_safety_reminder_after_efficacy_claim` (precheck) — same predicate, env presence requirement
- `r_isi_when_dosing_mentioned` (precheck)

**Verdict shape.** Missing → Zone with `layer:"regulatory", sub_layer:"regulatory:safety"` or `sub_layer:"regulatory:isi"` for ISI-specific.

---

### `PHARMACOVIGILANCE`

**What it is.** Adverse-event reporting routing. `"Adverse events should be reported via the Yellow Card Scheme at mhra.gov.uk/yellowcard."`

**Emitted by.** Email envelope detector, with extracted `authorities` list (e.g. `["MHRA"]`, `["HPRA"]`). Authority extraction is regex-based; `pipeline_email/envelope.py::ENVELOPE_ROLES` maps authority tokens to market-specific PV regulators.

**Subtypes.** `ADVERSE_EVENTS`, `PRECAUTIONS`.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2.

**Used in predicates.** None directly — requirement of `r_ae_reporting_when_promotional`.

**Used in requirements.**
- `r_ae_reporting_box` (cascade) — every promotional asset, market-specific authority routing required
- `r_ae_reporting_when_promotional` (precheck) — same, with `expected_authority` + `expected_url_substring` overrides per profile

**Verdict shape.** Missing routing → Zone severity:block. Wrong-market routing (UK email cites HPRA instead of MHRA) → Zone severity:block, sub_layer:"regulatory:pharmacovigilance:routing-mismatch".

---

### `PRESCRIBING_INFORMATION`

**What it is.** Link/reference to SmPC or full Prescribing Information. `"Click here for prescribing information"`.

**Emitted by.** Email envelope detector, often surfaces as a `REGULATORY_MENU` link in the header. Slides emit as `REGULATORY_MENU:PI`.

**Subtypes.** `SMPC`, `PI`, `FULL_PI`.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2.

**Used in requirements.**
- `r_prescribing_info_bar` (cascade) — required on every branded promotional asset
- `r_prescribing_info_link` (precheck) — checks envelope or REGULATORY_MENU for PI link

**Verdict shape.** Missing → Zone severity:block, sub_layer:"regulatory:prescribing_info".

---

### `AUDIENCE_RESTRICTION`

**What it is.** HCP-only gate. `"FOR UK HEALTHCARE PROFESSIONALS ONLY"`.

**Emitted by.** Email envelope detector (sniff for "Healthcare Professionals" + market). Slide pipeline detects via top-band ALL-CAPS short text in chrome region.

**MLR pillar.** Regulatory + Legal (UK and IE).

**MLR layer.** Layer 2.

**Used in requirements.**
- `r_audience_restriction_bar` (cascade) — fires unconditionally on UK/IE/FR/DE/IT branded promotional profile
- `r_audience_bar_when_hcp_only_profile` (precheck) — predicate-triggered companion

**Verdict shape.** Missing → Zone severity:block, sub_layer:"regulatory:audience_restriction". Pattern bank carries the accepted text variants per market.

---

### `PROMOTIONAL_NOTICE`

**What it is.** "This is a promotional email" declaration. `"Promotional information developed and funded by Novartis Pharmaceuticals UK Ltd"`.

**Emitted by.** Email envelope detector.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2.

**Used in requirements.** Per-market — required by some markets (UK has it conventionally; not a hard ABPI requirement). Pattern bank decides via `required: True/False` flag.

---

### `REGULATORY_MENU`

**What it is.** Header/footer link bar to PI / SmPC / AE-reporting / abbreviations. `"PI · SmPC · References · Abbreviations"`.

**Emitted by.** `pre_classifier._is_regulatory_menu` — short text matching known regulatory link terms. `navigation_detector` confirms via spatial position (chrome top/bottom bands).

**Subtypes.** `PI`, `ISI`, `SMPC`, `AE_REPORTING`, `REFERENCES`.

**MLR pillar.** Regulatory.

**MLR layer.** Layer 2 — used as a fallback satisfier for PI / ISI / AE-reporting requirements when the envelope's full block isn't present (the link is enough).

**Used in requirements.**
- `r_prescribing_info_bar` accepts `REGULATORY_MENU:PI` / `REGULATORY_MENU:SMPC` as satisfaction.

---

## §3 Legal pillar elements

### `DISCLAIMERS`

**What it is.** Corporate boilerplate — copyright, trademark, third-party content notice, privacy reference, terms.

**Emitted by.** `pre_classifier._is_legal` regex (`©|all rights reserved|registered trademark|MAT-`). Email envelope groups these into the `disclaimers` envelope key.

**Subtypes.** `COPYRIGHT`, `TRADEMARK`, `THIRD_PARTY_DISCLAIMER`, `PRIVACY`, `TERMS`, `OTHER_DISCLAIMERS`.

**MLR pillar.** Legal.

**MLR layer.** Layer 2 (cascade rules for boilerplate presence) + cascade for satisfaction.

**Used in predicates.**
- `r_third_party_disclaimer_when_external_link` — predicate `any_block.has_external_link=true`; requirement `any_block.role=DISCLAIMERS AND subtype=THIRD_PARTY_DISCLAIMER`.

**Used in requirements.**
- `r_third_party_disclaimer_when_external_link` (precheck)
- `r_kol_conflict_disclosure` (cascade + precheck) — accepts a DISCLAIMERS block matching FMV regex.

**Verdict shape.** Missing third-party disclaimer when external link present → Zone severity:warn, sub_layer:"legal:third_party".

---

### `CONTACT_INFO`

**What it is.** MAH legal entity name + registered office. `"Novartis Pharmaceuticals UK Limited · 2nd Floor, The WestWorks Building…"`.

**Emitted by.** Email envelope detector OR `pre_classifier._classify` for footer blocks matching company-name patterns.

**MLR pillar.** Legal.

**MLR layer.** Cascade.

**Used in requirements.**
- `r_mah_legal_entity` (cascade) — every promotional asset must show MAH name + office
- `r_mah_legal_entity_in_footer` (precheck) — same, predicate-triggered

---

### `APPROVAL_INFO`

**What it is.** Approval code + date of preparation. `"FA-11551654, prepared March 2026"`.

**Emitted by.** Email envelope detector with `code` (regex match: `FA-\d+`, `MAT-XX-\d+`, `UK/MAH/INN/yy/nnnn`, etc.) and `date_of_preparation` (parsed and normalised to ISO).

**MLR pillar.** Legal/Regulatory (overlap — different markets categorise differently).

**MLR layer.** Layer 2 (regulatory) + cascade.

**Used in requirements.**
- `r_approval_code_format` (cascade + precheck) — code regex must match profile-specific pattern
- `r_date_of_preparation_present_and_fresh` (precheck) — date present + ≤180 days warn / ≤365 days block

**Verdict shape.** Code format mismatch → Zone severity:block, sub_layer:"regulatory:approval_code". Date stale → severity:warn or block based on freshness threshold.

---

### `UNSUBSCRIBE`

**What it is.** Unsubscribe link / opt-out instructions. `"Click here to unsubscribe from marketing emails"`.

**Emitted by.** Email envelope detector via known phrase patterns.

**MLR pillar.** Legal.

**MLR layer.** Cascade.

**Used in requirements.**
- `r_unsubscribe_privacy` (cascade) — every promotional email must have unsub + privacy
- `r_unsubscribe_privacy_links` (precheck) — same

---

## §4 Navigation / utility elements

### `CTA`

**What it is.** Call-to-action button or link. `"Request a rep visit"`, `"Click here for PI"`.

**Emitted by.** `pre_classifier` text-pattern match (`CLICK HERE`, `Watch`, `Learn more`, etc.) OR upstream classification by Docling (Button label).

**Subtypes.** `LEARN_MORE`, `WATCH_VIDEO`, `ACCESS_PROGRAM`, `VIEW_PI_ISI_SMPC`, `CONTACT`, `DOWNLOAD`, `OTHER`.

**MLR pillar.** Navigation (with Regulatory overtones when subtype=VIEW_PI_ISI_SMPC).

**MLR layer.** Generally none (informational). The X-Ray treats CTA as part of the surrounding claim module via `fragment_builder._pair_cta_with_notice`.

**Used in predicates.**
- `r_tov_disclosure_for_event` — predicate `any_block.text_matches(/invit|register|webinar/)` (CTA text is one signal)
- `r_third_party_warning_when_external_link` — when CTA points to off-brand domain.

---

### `PRIMARY_MENU` / `SECONDARY_MENU` / `SLIDE_NAV`

**What they are.** Chrome navigation — chapter tabs, sub-tabs, slide-level controls (back/next/home).

**Emitted by.** `navigation_detector` based on spatial clustering (short text in chrome bands G1/G2/G8/G9).

**MLR pillar.** Navigation (utility).

**MLR layer.** None — these blocks are explicitly EXCLUDED from claim/regulatory/abbreviation precheck. They only matter for the X-Ray UI rendering (cross-link to email blocks).

**Used in predicates.** None.

**Used in requirements.** None.

**Why list them at all.** So engineers wiring the precheck don't accidentally include them in body-text scans. The pre_classifier's exclude lists in `column_detector` and `claim_check` should reference `_EXCLUDE_ROLES = {"PRIMARY_MENU", "SECONDARY_MENU", "SLIDE_NAV", "REGULATORY_MENU"}`.

---

## §5 Visual elements

### `BRAND_VISUAL`

**What it is.** Brand logo, hero image, packshot, header banner.

**Subtypes.** `LOGO`, `HERO`, `PACKSHOT`, `BANNER`.

**Emitted by.** `visual_describer` LLM with role classification.

**MLR pillar.** Visual.

**MLR layer.** Cascade — `r_brand_mark_registered` checks for ® on the brand logo's nearby text. Layer 1 doesn't currently match brand visuals (visual content matching is v2).

**Verdict shape.** Brand mark missing ® → Zone severity:warn, sub_layer:"regulatory:brand_mark".

---

### `MEDICAL_VISUAL`

**What it is.** Medical illustration, person photo, icon, video play banner.

**Subtypes.** `PERSON_PHOTO`, `ILLUSTRATION`, `ICON`, `PLAY_VIDEO_BANNER`.

**Emitted by.** `visual_describer` LLM.

**MLR pillar.** Visual.

**MLR layer.** Cascade only (`r_patient_image_consent` in v1.5).

---

### `DATA_VISUAL`

**What it is.** Chart, infographic, diagram, dosing visual.

**Subtypes.** `CHART`, `INFOGRAPHIC`, `DIAGRAM`, `DOSING_RELATED`.

**Emitted by.** `visual_describer` LLM with description + `claim_candidate.appears_to_carry_claim` flag.

**MLR pillar.** Visual + Medical (when carrying a claim).

**MLR layer.** Layer 1 — when `claim_candidate.appears_to_carry_claim=True`, the visual's description text is treated as a synthesised claim candidate. The module's `synthesized_text` field is populated. **Always flagged with severity:block** in v1 because synthesised claims have no human-approved provenance.

**Verdict shape.**
```
Zone {
  layer: "claim",
  sub_layer: "claim:synthesized",
  status: "drift",
  severity: "block",
  rationale: "Visual carries a claim that wasn't part of the asset's textual claims. LLM-synthesized; never approved copy."
}
```

---

### `TABLE`

**What it is.** Structured data table.

**Emitted by.** `visual_describer` + `table_grouper` (when Docling judge fires).

**MLR pillar.** Visual.

**MLR layer.** Layer 1 — table cell text contributes to `evidence_text_corpus`.

---

## §6 Cross-cutting fields

### `block_type`

Set by `pre_classifier`. Values: `heading`, `subheading`, `body`,
`bullet`, `caption`, `strapline`, `reference`, `footnote`,
`abbreviation`, `study-design`, `legal`. The MLR consumer reads it as a
*hint* for design-type assignment in the X-Ray, not as a primary
classification — `role` is the canonical signal.

### `structural_level`

Set by `font_normalizer`. Values: `H1`, `H2`, `H3`, `H4`, `H5`, `P`,
`SM`, `XS`. The MLR consumer uses it for:
- claim module head selection (largest font in the module gets promoted)
- footnote zone detection (`SM` / `XS` font + bottom band → likely footnote)
- abbreviation block confirmation (small font confirms classification)

### `subtype`

Set by `pre_classifier` with role-specific values. Used by:
- Layer 1 — `claim_subtype` (`EFFICACY`/`SAFETY`/`COMPARATIVE`/…) filters library lookup
- Layer 2 — `DISCLAIMERS:THIRD_PARTY_DISCLAIMER`, `SAFETY:ISI`, `BODY:STUDY_DESIGN` drive predicate matching

### `classification_confidence`

Float `0.0–1.0`. The MLR consumer:
- Skips low-confidence blocks (< 0.5) from cascade rule satisfaction (cascade requires ≥ 0.5)
- Surfaces `confidence < 0.7` blocks as "needs review" in the X-Ray (small badge)

### `band` (slide-only)

Set by `pipeline_common.grid.band_detector`. Values `G1`–`G9`. The MLR
consumer uses it for:
- excluding chrome bands (G1/G2/G8/G9) from claim and abbreviation
  precheck
- locating footnotes (G7) for cascade `r_date_of_preparation` etc.

### `column_index` (slide-only)

Set by `pipeline_v4.column_detector`. Used by Layer 1 to scope claim
modules to a single column (cross-column merges are structurally
prevented).

### `module.synthesized_text` + `text_source`

`text_source ∈ {"verbatim_header", "verbatim_caption", "verbatim_body",
"visual_llm", ""}`. The MLR consumer:
- `verbatim_*` → `is_approved_text=true` in module; can be matched
  against approved corpus
- `visual_llm` → ALWAYS triggers `severity:block` claim verdict; the
  text is unapproved by definition.

### `links[]` (block-level)

Each link: `{uri, source, bbox, visible_text, role_hint}`. The MLR
consumer:
- `has_external_link` predicate: any link.uri off-brand-domain
- `role_hint == "pi-link"` satisfies `r_prescribing_info_bar`
- `role_hint == "pharmacovigilance"` satisfies `r_ae_reporting_box`

---

## §7 How predicates reference these elements (concrete examples)

```yaml
# r_indication_when_drug_named — references CLAIM, INDICATION
predicate:
  any_module:
    claim: true                              # → module.claim == True
    text_matches: "\\b[A-Z]{4,}(?:®)?\\b"   # → module.text contains brand-shape token
requires:
  envelope:
    key: indication                          # → document_regulatory["indication"] non-empty
    present: true

# r_isi_when_dosing_mentioned — references BODY, SAFETY, SAFETY:ISI
predicate:
  any_block:
    text_matches: "\\bdose\\b|\\bdosing\\b|\\bmg/kg\\b"  # → block.text matches
                                                          # (most blocks: role=BODY)
requires:
  any_of:
    - any_block:
        role_in: ["SAFETY"]                  # → block.role == "SAFETY"
        subtype_in: ["ISI", "DOSING"]        # → block.subtype ∈ {ISI, DOSING}
    - envelope:
        key: safety
        present: true

# r_third_party_disclaimer_when_external_link — references DISCLAIMERS:THIRD_PARTY
predicate:
  any_block:
    has_external_link: true                  # → block.links[*].uri off-brand-domain
requires:
  any_block:
    role_in: ["DISCLAIMERS"]                 # → block.role == "DISCLAIMERS"
    subtype_in: ["THIRD_PARTY_DISCLAIMER"]   # → block.subtype == "THIRD_PARTY_DISCLAIMER"
```

---

## §8 Verdict shape by classification element (summary)

| Element                  | Drives Zone? | Default `layer`     | `severity` when missing | `severity` when drifted |
|--------------------------|:-:|---------------------|:-:|:-:|
| `CLAIM`                  | ● | `claim`             | block             | warn (text drift) / block (orphaned ref / metric) |
| `BODY`                   | ○ via parent module | -        | -                 | -                  |
| `BODY:STUDY_DESIGN`      | ● | `claim`             | warn              | warn               |
| `REFERENCE`              | ● | `claim` / `cascade` | block (cited but absent) | warn (novel ref) |
| `FOOTNOTE`               | ○ via parent | -                  | -                 | warn (inline drift) |
| `ABBREVIATION`           | ● per acronym | `abbreviation`   | warn (used+undefined) | -        |
| `INDICATION`             | ● | `regulatory`        | block             | warn               |
| `SAFETY` / `SAFETY:ISI`  | ● | `regulatory`        | warn / block (per profile) | warn      |
| `PHARMACOVIGILANCE`      | ● | `regulatory`        | block             | block (wrong-market routing) |
| `PRESCRIBING_INFORMATION`| ● | `regulatory`        | block             | warn               |
| `AUDIENCE_RESTRICTION`   | ● | `regulatory`        | block             | warn (text drift)  |
| `PROMOTIONAL_NOTICE`     | ● | `regulatory`        | warn (per market) | warn               |
| `DISCLAIMERS:THIRD_PARTY`| ● | `legal`             | warn              | warn               |
| `CONTACT_INFO`           | ● | `legal`             | block             | warn               |
| `APPROVAL_INFO`          | ● | `legal` / `regulatory` | block (missing) / warn (stale date) | block (regex mismatch) |
| `UNSUBSCRIBE`            | ● | `legal`             | block             | -                  |
| `CTA`                    | ○ via parent | -                  | -                 | -                  |
| `PRIMARY_MENU` etc.      | ✗ | -                   | -                 | -                  |
| `BRAND_VISUAL`           | ● | `regulatory`        | warn (no ® on first use) | -          |
| `DATA_VISUAL` (claim-carrying) | ● | `claim`       | -                 | block (synthesized) |

---

## §9 What's NOT classified yet (gaps to track)

These classification elements aren't reliably emitted by the current
pipeline and the precheck stubs them with `unverifiable` until they are:

- **`KOL_REFERENCE`** — named healthcare professional in body text. Today detected by precheck regex (`r_kol_conflict_disclosure` predicate). Should become a first-class role+subtype with confidence score.
- **`PATIENT_IMAGE`** — vs stock illustration. Today the visual_describer differentiates by `kind` but doesn't flag patient consent state.
- **`COMPARATOR_NAMED`** — when a claim names a competitor product. Important for ABPI Code 5.5 (comparative claims). Currently buried in `claim.text`.
- **`CLAIM_HOLDOUT`** — claim text that's not in the approved corpus AND not in any pattern bank. Today flagged as `status:missing` in Layer 1 — should be its own sub-layer (`claim:holdout`).
- **`EVIDENCE_NUMERIC_VALUE`** — extracted endpoint values (`8.4%`, `HR 0.748`) for cross-asset numeric drift detection. Today buried in body text; pipeline_v5 should extract structured.
- **`FAIR_MARKET_VALUE_DISCLOSURE`** — distinct from generic DISCLAIMERS, mandatory for KOL events. Currently regex-matched at runtime.

These are listed so v1.5+ can target them without re-discovering them.

---

## §10 Cross-references

- Role + block_type + subtype catalog: `extractor-service/CLASSIFICATION_TAXONOMY_FLAT.md`
- Module / fragment / block shapes: `extractor-service/CONTENT_MODEL.md`
- Cascade rule definitions: `extractor-service/OBLIGATION_CASCADE_SPEC.md`
- Email envelope detector: `extractor-service/PHARMA_EMAIL_ANATOMY.md` + `src/pipeline_email/envelope.py`
- Precheck dependency rules (predicates + requirements): `dependency_rules.yaml` (this folder)
- Profile catalog: `profiles/` (this folder)
- API contract: `MLR_PRECHECK_API.md` (this folder)
- Architecture spec: `extractor-service/MLR_PRECHECK_SPEC.md`
