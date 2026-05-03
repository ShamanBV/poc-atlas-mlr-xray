// XRayData.jsx — Data layer for MLR X-Ray v3

// ─── COLOUR TOKENS ────────────────────────────────────────────────────────────
const C = {
  // Shaman brand
  green600:'#00A66F', green400:'#47C18E', green100:'#C1E8D6', green50:'#E5F6EE', green25:'#F6FCF9',
  // Neutrals
  grey900:'#323232', grey800:'#454747', grey700:'#545A5B', grey600:'#636E6F',
  grey500:'#6F7E7F', grey400:'#879091', grey300:'#9FA3A4', grey200:'#BDBDBD',
  grey100:'#D7D7D7', grey50:'#EFEFEF', grey25:'#FBFBFB', white:'#FFFFFF',
  // Status — three colours only
  clean:'#639922',  cleanBg:'#F1F7E8',  cleanBorder:'#C5E09A',
  attn: '#BA7517',  attnBg: '#FEF3E2',  attnBorder:'#F5D28A',
  miss: '#A32D2D',  missBg: '#FAEAEA',  missBorder:'#EFB8B8',
  // Lane taxonomy — deliberately separate from status
  laneM: { bg:'#EEEDFE', text:'#3C3489', label:'Medical' },
  laneL: { bg:'#FAECE7', text:'#712B13', label:'Legal' },
  laneR: { bg:'#E1F5EE', text:'#085041', label:'Regulatory' },
  // Misc
  blue:'#3498DB', blueBg:'#E2F5FD',
  addGreen:'#E8F5E9', addText:'#2E7D32',
  redLight:'#FFEBEE',
};

// ─── ASSETS ───────────────────────────────────────────────────────────────────
const ASSETS = {

  kisqali: {
    meta: { brand:'KISQALI', market:'UK', channel:'HCP email', code:'FA-11551654', prepared:'2026-03-14', age:'37d' },
    identity: 'KISQALI · UK · en · UK-Branded-Promotional · FA-11551654 · prepared 2026-03-14 (37d)',
    scores: { overall:82, medical:88, legal:78, regulatory:80 },

    // Document spine — ordered top-to-bottom as they appear in the email
    zones: [
      { id:'z1', docPos:1, label:'Brand header',        lanes:[], status:'clean',
        evidence:'Approved verbatim', evidenceDetail:'Matches KISQALI UK master header v3.1',
        extractedContent:'KISQALI® (ribociclib)' },

      { id:'z2', docPos:2, label:'Salutation',          lanes:[], status:'clean',
        evidence:'Pattern match', evidenceDetail:'100% of approved UK HCP emails (n=312, 24 months)',
        extractedContent:'Dear {{userName}},' },

      { id:'z3', docPos:3, label:'Key efficacy claim',  lanes:['M'], status:'attn', pin:1,
        evidence:'Partial match · 0.84',
        evidenceDetail:'Closest approved: "At 5 years, KISQALI® + ET reduced the risk of disease recurrence by 25.2% vs ET alone (HR 0.748; 95% CI 0.618–0.906; p=0.0014)." Drift in comparator phrasing and CI formatting.',
        extractedContent:'At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014).',
        patternBase:'94% of 287 approved UK HCP KISQALI emails include an OS efficacy claim with HR + CI in this position.',
        diff:[
          {t:'At 5 years, KISQALI® + ET reduced the risk of ',s:'k'},
          {t:'disease recurrence',s:'d'},{t:'recurrence',s:'a'},
          {t:' by 25.2% vs ET alone (HR 0.748',s:'k'},
          {t:'; 95% CI',s:'d'},{t:', 95% CI',s:'a'},
          {t:' 0.618–0.906; p=0.0014).',s:'k'},
        ],
        annotationDraft:'Key efficacy claim shows phrasing drift vs approved canonical (similarity 0.84). Recommend reverting to approved text or submitting for new claim approval. Diff: "disease recurrence" → "recurrence"; CI delimiter changed.',
        vvpmAnchor:'anchor_blk_003' },

      { id:'z4', docPos:4, label:'Data callout',        lanes:['M'], status:'attn', pin:2,
        evidence:'Partial match · 0.84',
        evidenceDetail:'"25.2% risk reduction at 5 years" — approved canonical reads "25.1% relative risk reduction at 4 years". Numerical value and time point both changed.',
        extractedContent:'25.2% risk reduction at 5 years',
        patternBase:'Standalone percentage callout without comparator context present in only 34% of approved KISQALI UK HCP emails (n=287). Pattern confidence: low.',
        diff:[{t:'25.',s:'k'},{t:'1',s:'d'},{t:'2',s:'a'},{t:'% ',s:'k'},{t:'relative ',s:'d'},{t:'risk reduction at ',s:'k'},{t:'4',s:'d'},{t:'5',s:'a'},{t:' years',s:'k'}],
        annotationDraft:'Callout numerical value does not match approved canonical: "25.1% at 4 years" vs "25.2% at 5 years". Verify which data cut is intended and confirm approved status.',
        vvpmAnchor:'anchor_blk_004' },

      { id:'z5', docPos:5, label:'NATALEE population paragraph', lanes:['M'], status:'miss', pin:3,
        evidence:'Semantic match · 0.76',
        evidenceDetail:'Closest approved: "NATALEE enrolled 5,101 patients with HR+/HER2− early breast cancer at intermediate and high risk of recurrence." Current text paraphrases the population without the enrolled count or risk-stratification detail. > 30% drift — re-approval required.',
        extractedContent:'NATALEE is the largest adjuvant CDK4/6i trial in HR+/HER2− eBC, with a broad population including patients at elevated risk.',
        patternBase:'Population context paragraph present in 88% of approved NATALEE-citing UK HCP emails (n=143, 18 months). Missing comparator count and risk-tier detail in 100% of those.',
        diff:[{t:'NATALEE ',s:'k'},{t:'enrolled 5,101 patients with HR+/HER2− early breast cancer at intermediate and high risk of recurrence',s:'d'},{t:'is the largest adjuvant CDK4/6i trial in HR+/HER2− eBC, with a broad population including patients at elevated risk',s:'a'},{t:'.',s:'k'}],
        annotationDraft:'Population paragraph diverges > 30% from approved canonical. Enrolled count (5,101) and risk-stratification language are absent. This is new content — submit for claim approval before MLR submission.',
        vvpmAnchor:'anchor_blk_005' },

      { id:'z6', docPos:6, label:'CTA',                 lanes:[], status:'clean',
        evidence:'Approved verbatim', evidenceDetail:'Matches approved CTA component v2.0',
        extractedContent:'Request a rep visit' },

      { id:'z7', docPos:7, label:'AE reporting box',   lanes:['R'], status:'clean',
        evidence:'Rule satisfied', evidenceDetail:'MHRA Yellow Card reporting text present. Rule REG-MHRA-AE satisfied.',
        extractedContent:'Adverse events should be reported via the Yellow Card Scheme at mhra.gov.uk/yellowcard.' },

      { id:'z8', docPos:8, label:'Audience restriction', lanes:['R','L'], status:'miss', pin:4,
        evidence:'Missing',
        evidenceDetail:'All UK HCP-targeted promotional materials must display a "For UK Healthcare Professionals Only" restriction bar. Absent entirely from this asset.',
        extractedContent:null,
        patternBase:'100% of 312 approved UK HCP promotional emails include an audience restriction bar (n=312, 24 months). ABPI Clause 26.1.',
        annotationDraft:'Audience-restriction bar required for all UK HCP promotional emails (ABPI Code Clause 26.1) is entirely absent. Insert approved UK HCP restriction block before submission.',
        vvpmAnchor:'anchor_missing_audience_bar' },

      { id:'z9', docPos:9, label:'Footer / compliance block', lanes:['L','R'], status:'clean',
        evidence:'Approved verbatim', evidenceDetail:'Matches KISQALI UK footer v4.1. MAH, company number, confidentiality all present.',
        extractedContent:'Novartis Pharmaceuticals UK Limited · 2nd Floor, The WestWorks Building…' },
    ],

    // Preview email blocks (for left pane)
    emailBlocks: [
      { id:'z1', type:'header',    match:'clean' },
      { id:'z2', type:'salutation',match:'clean' },
      { id:'z3', type:'claim',     match:'attn',  pin:1 },
      { id:'z4', type:'callout',   match:'attn',  pin:2 },
      { id:'z5', type:'paragraph', match:'miss',  pin:3 },
      { id:'z6', type:'cta',       match:'clean' },
      { id:'z7', type:'ae',        match:'clean' },
      { id:'ghost_z8', type:'ghost', ghostLabel:'Audience-restriction bar expected here', pin:4 },
      { id:'z9', type:'footer',    match:'clean' },
    ],

    history: {
      assetEdits:[
        { date:'2026-03-14', actor:'J. Müller (author)', action:'Swapped hero variant: solid-hero → image-hero' },
        { date:'2026-03-12', actor:'J. Müller (author)', action:'Removed DataTable and KOLQuote from recipe defaults' },
        { date:'2026-03-10', actor:'J. Müller (author)', action:'Changed audience tier: specialist → non-specialist' },
      ],
      precheckRuns:[
        { date:'2026-03-14', score:82, delta:'+4 vs previous', summary:'2 attention → 1 resolved; audience-restriction bar still missing' },
        { date:'2026-03-10', score:78, delta:'—', summary:'Initial precheck. 1 blocker, 3 attention, 1 auto-inserted.' },
      ],
      baseChanges:[
        { date:'2026-03-01', item:'KISQALI UK claims base', version:'v2026-03-01', note:'NATALEE 5yr OS data added to approved base' },
        { date:'2026-02-15', item:'UK regulatory rules', version:'v12', note:'ABPI Code Clause 26.1 enforcement updated' },
      ],
    },
  },

  leqvio: {
    meta: { brand:'LEQVIO', market:'IE', channel:'HCP email', code:'FA-11551901', prepared:'2026-04-02', age:'30d' },
    identity: 'LEQVIO · IE · en · IE-Branded-Promotional · FA-11551901 · prepared 2026-04-02',
    scores: { overall:96, medical:100, legal:95, regulatory:94 },

    zones: [
      { id:'lz1', docPos:1, label:'Brand header',           lanes:[], status:'clean', evidence:'Approved verbatim', evidenceDetail:'Matches LEQVIO IE master header v2.0', extractedContent:'LEQVIO® (inclisiran)' },
      { id:'lz2', docPos:2, label:'Audience restriction',   lanes:['R','L'], status:'clean', evidence:'Rule satisfied', evidenceDetail:'"For healthcare professionals in Ireland only" present. Rule REG-IMB-HCP satisfied.', extractedContent:'FOR HEALTHCARE PROFESSIONALS IN IRELAND ONLY' },
      { id:'lz3', docPos:3, label:'Salutation',             lanes:[], status:'clean', evidence:'Pattern match', evidenceDetail:'100% of approved IE HCP emails (n=198, 24 months)', extractedContent:'Dear {{userName}},' },
      { id:'lz4', docPos:4, label:'Key efficacy claim',     lanes:['M'], status:'clean', evidence:'Approved verbatim · 0.97', evidenceDetail:'In ORION-10, inclisiran reduced LDL-C by 52% from baseline at day 510 (p<0.001) vs placebo. Matches approved LEQVIO IE claims base v3.2.', extractedContent:'In ORION-10, inclisiran reduced LDL-C by 52% from baseline at day 510 (p<0.001) vs placebo.' },
      { id:'lz5', docPos:5, label:'Data callout',           lanes:['M'], status:'clean', evidence:'Approved verbatim', evidenceDetail:'52% LDL-C reduction from baseline. Approved verbatim.', extractedContent:'52% LDL-C reduction from baseline' },
      { id:'lz6', docPos:6, label:'CTA',                    lanes:[], status:'clean', evidence:'Approved verbatim', evidenceDetail:'Matches approved CTA v2.0', extractedContent:'Request a rep visit' },
      { id:'lz7', docPos:7, label:'Reimbursement disclosure', lanes:['R'], status:'clean', evidence:'Rule satisfied (auto)', evidenceDetail:'Engine auto-inserted canonical IE reimbursement disclosure. Rule REG-IE-REIMB satisfied.', extractedContent:'LEQVIO is not currently reimbursed in Ireland under the GMS/PCRS schemes.' },
      { id:'lz8', docPos:8, label:'AE reporting box',       lanes:['R'], status:'clean', evidence:'Rule satisfied', evidenceDetail:'HPRA Pharmacovigilance reporting text present. Rule REG-HPRA-AE satisfied.', extractedContent:'Adverse events should be reported to the HPRA Pharmacovigilance at medsafety.ie.' },
      { id:'lz9', docPos:9, label:'Footer / compliance block', lanes:['L','R'], status:'clean', evidence:'Approved verbatim', evidenceDetail:'Matches LEQVIO IE footer v2.1.', extractedContent:'Novartis Ireland Limited · 2nd Floor, Block B, One Georges Quay Plaza, Dublin 2.' },
    ],

    emailBlocks: [
      { id:'lz1', type:'header',    match:'clean' },
      { id:'lz2', type:'hcpbar',   match:'clean' },
      { id:'lz3', type:'salutation',match:'clean' },
      { id:'lz4', type:'claim',     match:'clean' },
      { id:'lz5', type:'callout',   match:'clean' },
      { id:'lz6', type:'cta',       match:'clean' },
      { id:'lz7', type:'disclosure',match:'clean' },
      { id:'lz8', type:'ae',        match:'clean' },
      { id:'lz9', type:'footer',    match:'clean' },
    ],

    history: {
      assetEdits:[{ date:'2026-04-02', actor:'C. Walsh (author)', action:'Initial draft created from LEQVIO IE standard recipe' }],
      precheckRuns:[{ date:'2026-04-02', score:96, delta:'—', summary:'Clean on first run. One auto-inserted reimbursement disclosure.' }],
      baseChanges:[{ date:'2026-03-15', item:'LEQVIO IE claims base', version:'v3.2', note:'ORION-10 day 510 data updated' }],
    },
  },

  jakavi: {
    meta: { brand:'JAKAVI', market:'UK', channel:'Event invite', code:'draft', prepared:'2026-04-16', age:'16d' },
    identity: 'JAKAVI · UK · en · Event-Promotional · [draft] · prepared 2026-04-16',
    scores: { overall:68, medical:82, legal:55, regulatory:71 },

    zones: [
      { id:'jz1', docPos:1, label:'Brand header',         lanes:[], status:'clean', evidence:'Approved verbatim', evidenceDetail:'Matches JAKAVI UK header v1.0', extractedContent:'JAKAVI® (ruxolitinib)' },
      { id:'jz2', docPos:2, label:'Event invitation hero', lanes:[], status:'clean', evidence:'Pattern match', evidenceDetail:'96% of approved JAKAVI UK event invitations (n=41, 24 months)', extractedContent:'Join us at the SOHO Haematology Symposium · Manchester · 14 June 2026' },
      { id:'jz3', docPos:3, label:'Featured speaker',     lanes:['M','L'], status:'attn', pin:1,
        evidence:'Partial match · 0.88',
        evidenceDetail:'Speaker card present but FMV disclosure line removed. Approved canonical includes: "Speaker fees and expenses will be covered by Novartis in line with fair market value." Drift in footer removes this line.',
        extractedContent:'Prof. Claire Harrison, Guy\'s and St Thomas\' NHS Trust',
        diff:[{t:'Prof. Claire Harrison, Guy\'s and St Thomas\' NHS Trust.',s:'k'},{t:' Speaker fees and expenses will be covered by Novartis in line with fair market value.',s:'d'}],
        annotationDraft:'Speaker card is missing the FMV disclosure line required for named KOL appearances under ABPI Code. Approved canonical includes this line — revert to approved speaker card component.',
        vvpmAnchor:'anchor_blk_j03' },

      { id:'jz4', docPos:4, label:'Agenda',               lanes:[], status:'clean', evidence:'Pattern match', evidenceDetail:'78% of approved JAKAVI UK event invitations (n=41) include a timestamped agenda.', extractedContent:'14:00 registration · 14:30 keynote · 16:00 breakouts · 18:00 dinner' },
      { id:'jz5', docPos:5, label:'CTA',                  lanes:[], status:'clean', evidence:'Approved verbatim', evidenceDetail:'Matches approved event CTA v1.0.', extractedContent:'Register now' },

      { id:'jz6', docPos:6, label:'ToV disclosure',       lanes:['L'], status:'miss', pin:2,
        evidence:'Missing',
        evidenceDetail:'Event-Promotional materials require a Transfer of Value disclosure per ABPI Code Clause 28. The disclosure line was removed from the footer (blk_j06 is partial match at 0.82). This is a blocker.',
        extractedContent:null,
        patternBase:'100% of 41 approved JAKAVI UK event invitations include a ToV disclosure (n=41, 24 months). Required by ABPI Code Clause 28.',
        annotationDraft:'Transfer of Value disclosure (ABPI Clause 28) is absent from the event footer. Insert approved ToV line: "Novartis is providing hospitality at this meeting in line with ABPI Code of Practice Clause 28." This is a hard blocker.',
        vvpmAnchor:'anchor_missing_tov' },

      { id:'jz7', docPos:7, label:'Date of preparation',  lanes:['L'], status:'miss', pin:3,
        evidence:'Missing',
        evidenceDetail:'Footer is missing the date of preparation field, required under ABPI Code Clause 4.10.',
        extractedContent:null,
        patternBase:'100% of 41 approved JAKAVI UK event invitations include a date of preparation (n=41, 24 months). Required by ABPI Code Clause 4.10.',
        annotationDraft:'Date of preparation is absent from the event footer. Add: "[Month Year]" in the approved footer format. Required under ABPI Code Clause 4.10.',
        vvpmAnchor:'anchor_missing_dop' },

      { id:'jz8', docPos:8, label:'HCP designation',      lanes:['R'], status:'clean', evidence:'Rule satisfied (auto)', evidenceDetail:'HCP-only designation auto-inserted from event template. Rule REG-ABPI-261 satisfied.', extractedContent:'For healthcare professionals only.' },
      { id:'jz9', docPos:9, label:'AE reporting reference', lanes:['R'], status:'clean', evidence:'Rule satisfied', evidenceDetail:'AE reporting reference present in footer.', extractedContent:'Adverse events should be reported.' },
    ],

    emailBlocks: [
      { id:'jz1', type:'header',    match:'clean' },
      { id:'jz2', type:'event-hero',match:'clean' },
      { id:'jz3', type:'speaker',   match:'attn', pin:1 },
      { id:'jz4', type:'agenda',    match:'clean' },
      { id:'jz5', type:'cta',       match:'clean' },
      { id:'ghost_jz6', type:'ghost', ghostLabel:'ToV disclosure expected in footer', pin:2 },
      { id:'ghost_jz7', type:'ghost', ghostLabel:'Date of preparation expected here', pin:3 },
      { id:'jz8', type:'footer',    match:'clean' },
    ],

    history: {
      assetEdits:[
        { date:'2026-04-16', actor:'T. O\'Brien (author)', action:'Initial draft. Removed ToV line from footer component.' },
        { date:'2026-04-16', actor:'T. O\'Brien (author)', action:'FMV disclosure removed from speaker card.' },
      ],
      precheckRuns:[{ date:'2026-04-16', score:68, delta:'—', summary:'First run. 2 missing (ToV, DOP), 1 attention (speaker FMV).' }],
      baseChanges:[{ date:'2026-03-20', item:'UK event promotional rules', version:'v5', note:'ABPI Clause 28 ToV enforcement strengthened' }],
    },
  },
};

// helpers
const statusColor = s => s==='clean'?C.clean:s==='attn'?C.attn:C.miss;
const statusBg    = s => s==='clean'?C.cleanBg:s==='attn'?C.attnBg:C.missBg;
const laneToken   = l => l==='M'?C.laneM:l==='L'?C.laneL:C.laneR;
const scoreVerdict= s => s>=90?'Pass':s>=75?'Warn':'Fail';
const scoreColor  = s => s>=90?C.clean:s>=75?C.attn:C.miss;

// ─── Health helpers (replace the punitive 0–100 score) ───────────────
// healthPct: % of zones cleared (clean / annotated / info-severity).
//   Goes UP as the reviewer works through the list. Excludes dismissed.
// Tiers by SEVERITY, not just status — a miss with severity=info
// (e.g. structural "Novel" reference rows) is informational noise, not
// a blocker. Only severity=block becomes a blocker.
// healthVerb / healthColor: 3-tier status; precedence blockers > attention > clean.
// `zoneActions` is the per-asset map from XRayDrawer ({zoneId: 'annotated'|'dismissed'}).
const healthCounts = (zones, zoneActions = {}) => {
  const live = zones.filter(z => zoneActions[z.id] !== 'dismissed');
  const total = live.length;
  // Annotated/clean/info-severity zones don't need user action.
  // (Pattern-matched at high similarity but with miss STATUS is still an
  //  info-severity row — workflow neutral, surfaces as cleared.)
  const blockers  = live.filter(z =>
    z.severity === 'block' && z.status !== 'clean' && zoneActions[z.id] !== 'annotated'
  ).length;
  const attention = live.filter(z =>
    z.severity === 'warn' && z.status !== 'clean' && zoneActions[z.id] !== 'annotated'
  ).length;
  // Cleared = the rest (anything not in the two action-required buckets).
  const cleared = total - blockers - attention;
  const pct = total === 0 ? 100 : Math.round(100 * cleared / total);
  return { total, cleared, attention, blockers, pct };
};
const healthVerb = ({ blockers, attention }) =>
  blockers > 0  ? 'Needs revision'
: attention > 0 ? 'Review pending'
:                 'Ready to approve';
const healthColor = ({ blockers, attention }) =>
  blockers > 0  ? C.miss
: attention > 0 ? C.attn
:                 C.clean;

Object.assign(window, {
  C, ASSETS, statusColor, statusBg, laneToken, scoreVerdict, scoreColor,
  healthCounts, healthVerb, healthColor,
});
