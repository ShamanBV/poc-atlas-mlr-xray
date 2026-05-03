/**
 * Backend ↔ prototype adapter.
 *
 * Maps the precheck engine's snake_case Asset payload (per
 * MLR_PRECHECK_API.md §2) into the camelCase shape the design-handoff
 * JSX components expect (per XRayData.jsx).
 *
 * Field mapping (only the deltas — same names elsewhere):
 *
 *   doc_pos              → docPos
 *   evidence_detail      → evidenceDetail
 *   extracted_content    → extractedContent
 *   pattern_base (object)→ patternBase (string sentence)
 *   annotation_draft     → annotationDraft
 *   vvpm_anchor          → vvpmAnchor
 *   ghost_label          → ghostLabel
 *
 * Status / severity / lanes / diff pass through unchanged.
 */

(function () {
  function patternBaseToSentence(pb) {
    if (!pb) return null;
    const cov = Math.round((pb.coverage || 0) * 100);
    const window = pb.window_months ? `${pb.window_months} months` : 'observed window';
    const pattern = pb.description || pb.pattern_id;
    const ruleSuffix = pb.rule_id ? ` Required by ${pb.rule_id}.` : '';
    return `${cov}% of ${pb.n} approved variants match: ${pattern}. (window: ${window}).${ruleSuffix}`;
  }

  function adaptZone(z) {
    return {
      id: z.id,
      docPos: z.doc_pos,
      label: z.label,
      lanes: z.lanes || [],
      status: z.status,
      severity: z.severity,
      layer: z.layer,
      subLayer: z.sub_layer,
      evidence: z.evidence,
      evidenceDetail: z.evidence_detail,
      extractedContent: z.extracted_content,
      canonicalContent: z.canonical_content,
      diff: z.diff,
      patternBase: patternBaseToSentence(z.pattern_base),
      patternBaseRaw: z.pattern_base, // kept around for any UI that wants the structured form
      dependenciesTriggered: z.dependencies_triggered || [],
      annotationDraft: z.annotation_draft,
      vvpmAnchor: z.vvpm_anchor,
      pin: z.pin,
      bbox: z.bbox,                    // PDF-point coords; overlay layer transforms to px
      page: z.page,                    // 1-indexed; matches /api/preview/{id}/page/{n}.png
    };
  }

  function adaptEmailBlock(b) {
    return {
      id: b.id,
      type: b.type,
      match: b.match,
      pin: b.pin,
      ghostLabel: b.ghost_label,
    };
  }

  function adaptAsset(asset) {
    return {
      meta: {
        ...asset.meta,
        // Prototype uses `age` as a display string; backend gives age_days as a number.
        age: asset.meta.age_days != null ? `${asset.meta.age_days}d` : null,
      },
      identity: asset.identity,
      scores: asset.scores,
      verdict: asset.verdict,
      zones: (asset.zones || []).map(adaptZone),
      emailBlocks: (asset.email_blocks || []).map(adaptEmailBlock),
      library: asset.library,
      counts: asset.counts || {references:0, footnotes:0, abbreviations:0, blocks:0, modules:0, visuals:0},
      profile: asset.profile,
      preview: asset.preview,
      // History strands: backend doesn't ship them yet on the precheck
      // payload (separate endpoint per §3.3). Stub empty so the
      // history panel renders "no events" deterministically.
      history: { assetEdits: [], precheckRuns: [], baseChanges: [] },
    };
  }

  window.adaptBackendAsset = adaptAsset;
})();
