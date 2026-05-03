// XRayDrawer.jsx — Right-pane X-ray spine with tabs, inline expand, annotation composer

const { useState, useEffect, useRef, useCallback, useMemo } = React;

// Backend base URL (mirrors index.html constant). Falls back to
// localhost:8088 if the global isn't set.
const _BACKEND = (typeof window !== 'undefined' && window.BACKEND) || 'http://localhost:8088';

// Glyph per visual_kind, used by the Visual Library card. Material
// Icons names — already loaded for the rest of the prototype.
const _VISUAL_KIND_ICON = {
  banner:      'view_carousel',
  logo:        'verified',
  photo:       'photo_camera',
  hero:        'photo',
  patient:     'person',
  chart:       'bar_chart',
  diagram:     'schema',
  icon:        'apps',
  infographic: 'data_object',
  table:       'table_chart',
  other:       'image',
  unknown:     'help_outline',
};

// ─── VISUAL LIBRARY CARD ─────────────────────────────────────────────────────
// Collapsible panel listing the visual exemplars in the active UK
// baseline corpus (banks/logos/photos/icons/...). Source for the MLR
// reviewer to repurpose approved visuals into new assets. Driven by
// GET /api/baseline/visuals.
const VisualLibraryCard = () => {
  const [open, setOpen] = useState(false);  // collapsed by default
  const [filter, setFilter] = useState('');  // visual_kind filter
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || data || error) return;
    fetch(`${_BACKEND}/api/baseline/visuals?limit=500`)
      .then(r => r.json())
      .then(setData)
      .catch(setError);
  }, [open, data, error]);

  // Build the kind filter chip list from the loaded data.
  const kinds = useMemo(() => {
    if (!data?.visuals) return [];
    const counts = new Map();
    for (const v of data.visuals) {
      const k = (v.visual_kind || 'unknown');
      counts.set(k, (counts.get(k) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);

  const visible = useMemo(() => {
    if (!data?.visuals) return [];
    if (!filter) return data.visuals;
    return data.visuals.filter(v => (v.visual_kind || 'unknown') === filter);
  }, [data, filter]);

  return (
    <div style={{ margin:'0 12px 6px', border:`1.5px solid ${C.grey50}`,
      borderRadius:8, background:C.white, overflow:'hidden', flexShrink:0 }}>
      <div onClick={()=>setOpen(v=>!v)} style={{
        display:'flex', alignItems:'center', gap:7, padding:'7px 11px',
        background:C.grey25, borderBottom: open ? `1px solid ${C.grey50}` : 'none',
        cursor:'pointer', userSelect:'none',
      }}>
        <span style={{ fontSize:10, color:C.grey400,
          display:'inline-block', transition:'transform .15s',
          transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
        <span style={{ fontSize:9, fontWeight:700, color:C.grey700,
          textTransform:'uppercase', letterSpacing:.6 }}>Visual library</span>
        <span style={{ fontSize:11, color:C.grey500, marginLeft:2 }}>
          {data ? `${data.total} approved visuals` : 'click to load'}
        </span>
        <span style={{ marginLeft:'auto', fontSize:9, color:C.grey400,
          fontStyle:'italic' }}>repurpose source</span>
      </div>

      {open && (
        <div style={{ background:C.white, maxHeight:360, overflowY:'auto' }}>
          {error && (
            <div style={{ padding:14, fontSize:12, color:C.miss }}>
              Couldn't load visuals: {error.message || 'fetch failed'}
            </div>
          )}
          {!data && !error && (
            <div style={{ padding:14, fontSize:12, color:C.grey400, textAlign:'center' }}>
              Loading visual library…
            </div>
          )}
          {data && (
            <>
              {/* Kind filter chips */}
              <div style={{ display:'flex', flexWrap:'wrap', gap:4,
                padding:'7px 11px', borderBottom:`1px solid ${C.grey50}`,
                background:C.grey25 }}>
                <span onClick={()=>setFilter('')} style={{
                  fontSize:10, fontWeight:600, padding:'2px 7px', borderRadius:10,
                  cursor:'pointer',
                  background: filter==='' ? C.green600 : C.white,
                  color: filter==='' ? C.white : C.grey700,
                  border:`1px solid ${filter==='' ? C.green600 : C.grey100}`,
                }}>All {data.total}</span>
                {kinds.map(([k, n]) => (
                  <span key={k} onClick={()=>setFilter(k)} style={{
                    fontSize:10, fontWeight:600, padding:'2px 7px', borderRadius:10,
                    cursor:'pointer',
                    background: filter===k ? C.green600 : C.white,
                    color: filter===k ? C.white : C.grey700,
                    border:`1px solid ${filter===k ? C.green600 : C.grey100}`,
                  }}>{k} · {n}</span>
                ))}
              </div>
              {/* Visual rows */}
              {visible.length === 0 && (
                <div style={{ padding:14, fontSize:12, color:C.grey400, textAlign:'center' }}>
                  No visuals match the current filter.
                </div>
              )}
              {visible.map(v => {
                const icon = _VISUAL_KIND_ICON[(v.visual_kind || 'unknown')] || 'image';
                const desc = (v.description || v.ocr_text || v.image_url || 'no description').trim();
                return (
                  <div key={v.pattern_id} style={{
                    display:'flex', alignItems:'flex-start', gap:9, padding:'8px 11px',
                    borderBottom:`1px solid ${C.grey50}`,
                  }}>
                    {/* Thumb placeholder using kind icon */}
                    <div style={{
                      flexShrink:0, width:38, height:38, borderRadius:5,
                      background: C.green25, border:`1px solid ${C.green100}`,
                      display:'flex', alignItems:'center', justifyContent:'center',
                      color: C.green600,
                    }}>
                      <span className="material-icons" style={{ fontSize:20 }}>{icon}</span>
                    </div>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{
                        display:'flex', alignItems:'center', gap:6,
                        fontSize:9, fontWeight:700, textTransform:'uppercase',
                        letterSpacing:.4, color:C.grey700, marginBottom:3,
                      }}>
                        <span>{(v.visual_kind || 'unknown').toUpperCase()}</span>
                        {v.n > 1 && (
                          <span style={{ fontWeight:500, color:C.grey400 }}>
                            · seen {v.n}×
                          </span>
                        )}
                        {v.image_url && (
                          <a href={v.image_url} target="_blank" rel="noopener noreferrer"
                            onClick={e=>e.stopPropagation()}
                            style={{ marginLeft:'auto', color:C.grey400, fontSize:11 }}>
                            <span className="material-icons" style={{ fontSize:13 }}>open_in_new</span>
                          </a>
                        )}
                      </div>
                      <div style={{ fontSize:12, color:C.grey900, lineHeight:1.35,
                        display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical',
                        overflow:'hidden', textOverflow:'ellipsis' }}>
                        {desc}
                      </div>
                      {v.ocr_text && (
                        <div style={{ fontSize:10, color:C.grey400, marginTop:3,
                          fontStyle:'italic' }}>
                          OCR: {v.ocr_text}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ─── ASSET META CARD ─────────────────────────────────────────────────────────
// Collapsible card showing brand/market/lang/refs/footnotes/doc-type/approval.
// Driven by asset.meta + asset.counts + asset.profile from the live backend.
const AssetMetaCard = ({ asset }) => {
  const [open, setOpen] = useState(true);
  const m = asset.meta || {};
  const c = asset.counts || {};
  const profile = asset.profile?.id;
  const subtitle = m.brand
    ? `${m.brand}${m.market ? ' · ' + m.market : ''}`
    : asset.identity || '—';

  const fields = [
    { k: 'BRAND',      v: m.brand    || '—' },
    { k: 'MARKET',     v: m.market   || '—' },
    { k: 'LANG',       v: m.language || '—' },
    { k: 'REFERENCES', v: String(c.references ?? 0) },
    { k: 'FOOTNOTES',  v: String(c.footnotes  ?? 0) },
    { k: 'DOC TYPE',   v: m.doc_type ? m.doc_type.charAt(0).toUpperCase() + m.doc_type.slice(1) : '—' },
  ];
  const fullWidth = [];
  if (profile)  fullWidth.push({ k: 'PROFILE',  v: profile });
  if (m.code)   fullWidth.push({ k: 'APPROVAL', v: m.code });
  if (m.prepared) fullWidth.push({ k: 'PREPARED', v: m.prepared + (m.age != null ? ` · ${m.age}` : '') });

  return (
    <div style={{ margin:'10px 12px 6px', border:`1.5px solid ${C.grey50}`,
      borderRadius:8, background:C.white, overflow:'hidden', flexShrink:0 }}>
      <div onClick={()=>setOpen(v=>!v)} style={{
        display:'flex', alignItems:'center', gap:7, padding:'7px 11px',
        background:C.grey25, borderBottom: open ? `1px solid ${C.grey50}` : 'none',
        cursor:'pointer', userSelect:'none',
      }}>
        <span style={{ fontSize:10, color:C.grey400,
          display:'inline-block', transition:'transform .15s',
          transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
        <span style={{ fontSize:9, fontWeight:700, color:C.grey700,
          textTransform:'uppercase', letterSpacing:.6 }}>Asset</span>
        <span style={{ fontSize:11, color:C.grey500, marginLeft:2 }}>{subtitle}</span>
      </div>
      {open && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', background:C.white }}>
          {fields.map(({k,v}, i) => (
            <div key={k} style={{
              padding:'7px 11px', borderTop:`1px solid ${C.grey50}`,
              borderRight: i % 2 === 0 ? `1px solid ${C.grey50}` : 'none',
            }}>
              <div style={{ fontSize:9, fontWeight:700, color:C.grey400,
                textTransform:'uppercase', letterSpacing:.6, marginBottom:2 }}>{k}</div>
              <div style={{ fontSize:13, fontWeight:500, color:C.grey900 }}>{v}</div>
            </div>
          ))}
          {fullWidth.map(({k,v}) => (
            <div key={k} style={{
              gridColumn:'1 / -1', padding:'7px 11px',
              borderTop:`1px solid ${C.grey50}`,
            }}>
              <div style={{ fontSize:9, fontWeight:700, color:C.grey400,
                textTransform:'uppercase', letterSpacing:.6, marginBottom:2 }}>{k}</div>
              <div style={{ fontSize:13, fontWeight:500, color:C.grey900 }}>{v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── LANE PILL ────────────────────────────────────────────────────────────────
const LanePill = ({ lane }) => {
  const t = laneToken(lane);
  return (
    <span style={{ fontSize:10,fontWeight:600,padding:'1px 6px',borderRadius:3,
      background:t.bg,color:t.text,whiteSpace:'nowrap',letterSpacing:0.2 }}>
      {t.label}
    </span>
  );
};

// ─── STATUS DOT ───────────────────────────────────────────────────────────────
const StatusDot = ({ status, size=9 }) => (
  <span style={{ width:size,height:size,borderRadius:'50%',background:statusColor(status),
    flexShrink:0,display:'inline-block' }}/>
);

// ─── PIN BADGE ────────────────────────────────────────────────────────────────
const PinBadge = ({ num, status }) => (
  <span style={{ display:'inline-flex',alignItems:'center',justifyContent:'center',
    width:16,height:16,borderRadius:'50%',fontSize:9,fontWeight:600,color:'#fff',
    background:statusColor(status),flexShrink:0 }}>{num}</span>
);

// ─── EVIDENCE TAG ─────────────────────────────────────────────────────────────
const EvidenceTag = ({ text }) => (
  <span style={{ fontSize:10,color:C.grey500,fontStyle:'normal',
    background:C.grey25,border:`1px solid ${C.grey50}`,
    borderRadius:3,padding:'1px 5px',whiteSpace:'nowrap' }}>{text}</span>
);

// ─── DIFF VIEW ────────────────────────────────────────────────────────────────
const DiffView = ({ segments }) => (
  <div className="mono" style={{ fontSize:11.5,lineHeight:1.9,background:C.white,
    border:`1px solid ${C.grey50}`,borderRadius:4,padding:'8px 10px' }}>
    {(segments||[]).map((seg,i) => {
      if (seg.s==='k') return <span key={i}>{seg.t}</span>;
      if (seg.s==='d') return <span key={i} style={{ background:'#FFEBEE',color:C.miss,
        textDecoration:'line-through',borderRadius:2,padding:'0 1px' }}>{seg.t}</span>;
      if (seg.s==='a') return <span key={i} style={{ background:'#E8F5E9',color:'#2E7D32',
        borderRadius:2,padding:'0 1px' }}>{seg.t}</span>;
      return null;
    })}
  </div>
);

// ─── ANNOTATION COMPOSER ─────────────────────────────────────────────────────
// zoneActions: { [zoneId]: 'annotated' | 'dismissed' }
// onAnnotate(zoneId) / onDismiss(zoneId) / onUndo(zoneId)
const AnnotationComposer = ({ draft, zoneId, onAnnotate, onDismiss }) => {
  const [text, setText] = useState(draft || '');
  const [sending, setSending] = useState(false);

  const handleCreate = () => {
    setSending(true);
    // Simulate API call
    setTimeout(() => { setSending(false); onAnnotate(zoneId); }, 900);
  };

  return (
    <div style={{ marginTop:12,borderTop:`1px solid ${C.grey50}`,paddingTop:12 }}>
      <div style={{ fontSize:10,fontWeight:700,color:C.grey400,textTransform:'uppercase',
        letterSpacing:0.5,marginBottom:6 }}>Add annotation in Veeva</div>
      <textarea
        value={text}
        onChange={e=>setText(e.target.value)}
        placeholder="Describe the finding for the author…"
        style={{ width:'100%',fontFamily:"'Noto Sans',sans-serif",fontSize:12,color:C.grey800,
          border:`1px solid ${C.grey100}`,borderRadius:5,padding:'8px 10px',
          lineHeight:1.6,resize:'vertical',minHeight:72,outline:'none',
          background:C.white,boxSizing:'border-box',display:'block' }}
      />
      <div style={{ display:'flex',gap:6,marginTop:8,alignItems:'center' }}>
        <button
          onClick={handleCreate}
          disabled={!text.trim() || sending}
          style={{ display:'inline-flex',alignItems:'center',gap:4,
            fontFamily:'inherit',
            background: (!text.trim()||sending) ? C.grey100 : C.grey900,
            color: (!text.trim()||sending) ? C.grey300 : C.white,
            border:'none',borderRadius:5,padding:'6px 14px',
            fontSize:12,fontWeight:500,
            cursor:(!text.trim()||sending)?'not-allowed':'pointer',
            transition:'background 0.15s' }}>
          {sending
            ? <><span className="material-icons" style={{ fontSize:13,animation:'spin 0.8s linear infinite' }}>autorenew</span>Creating…</>
            : <><span className="material-icons" style={{ fontSize:13 }}>add_comment</span>Create annotation</>}
        </button>
        <button
          onClick={()=>onDismiss(zoneId)}
          style={{ display:'inline-flex',alignItems:'center',gap:3,
            fontFamily:'inherit',background:'none',color:C.grey400,
            border:'none',borderRadius:5,padding:'6px 10px',
            fontSize:12,cursor:'pointer' }}>
          Dismiss
        </button>
        <a href="#" onClick={e=>e.preventDefault()}
          style={{ marginLeft:'auto',display:'inline-flex',alignItems:'center',gap:3,
            fontSize:11,color:C.grey400,textDecoration:'none' }}>
          <span className="material-icons" style={{ fontSize:12 }}>help_outline</span>
          Why this pattern?
        </a>
      </div>
    </div>
  );
};

// ─── ZONE ROW ─────────────────────────────────────────────────────────────────
const ZoneRow = ({ zone, isHovered, isSelected, onHover, isOpen, onToggle, zoneAction, onAnnotate, onDismiss, onUndo }) => {
  const isClean   = zone.status === 'clean';
  const col       = statusColor(zone.status);
  const bg        = statusBg(zone.status);
  const annotated = zoneAction === 'annotated';
  const dismissed = zoneAction === 'dismissed';

  // Dismissed rows render as a single muted line — no expand
  if (dismissed) return (
    <div style={{ borderBottom:`1px solid ${C.grey50}`,
      display:'flex',alignItems:'center',gap:8,padding:'7px 14px',
      background:C.grey25,opacity:0.6 }}>
      <StatusDot status="clean" size={7}/>
      <span style={{ fontSize:12,color:C.grey400,flex:1,fontStyle:'italic' }}>{zone.label}</span>
      <span style={{ fontSize:10,color:C.grey300 }}>Dismissed</span>
      <button onClick={()=>onUndo(zone.id)} style={{ fontSize:10,color:C.grey400,
        background:'none',border:'none',cursor:'pointer',fontFamily:'inherit',
        textDecoration:'underline',padding:'0 2px' }}>undo</button>
    </div>
  );

  return (
    <div data-zone-row-id={zone.id}
      style={{ borderBottom:`1px solid ${C.grey50}` }}
      onMouseEnter={()=>onHover(zone.id)} onMouseLeave={()=>onHover(null)}>

      {/* Zone row header */}
      <div
        onClick={isClean ? undefined : onToggle}
        style={{ display:'flex',alignItems:'center',gap:9,
          padding:isClean?'8px 14px':'9px 14px',
          cursor:isClean?'default':'pointer',
          background: isSelected ? bg : isHovered?(isClean?C.grey25:bg+'66'):isOpen?bg+'44':C.white,
          borderLeft: isSelected ? `3px solid ${col}` : '3px solid transparent',
          transition:'background 0.1s' }}>

        {/* Status dot — green if annotated */}
        <StatusDot status={annotated?'clean':zone.status}/>

        <div style={{ flex:1,minWidth:0 }}>
          <div style={{ display:'flex',alignItems:'baseline',gap:6,flexWrap:'wrap' }}>
            <span style={{ fontSize:13,fontWeight:isClean?400:600,
              color:isClean?C.grey800:col,lineHeight:1.35 }}>{zone.label}</span>
            {annotated && (
              <span style={{ fontSize:10,fontWeight:600,color:C.clean,
                background:C.cleanBg,border:`1px solid ${C.clean}33`,
                borderRadius:3,padding:'1px 6px',display:'inline-flex',alignItems:'center',gap:3 }}>
                <span className="material-icons" style={{ fontSize:11 }}>check</span>
                Annotated in VVPM
              </span>
            )}
          </div>
          <div style={{ display:'flex',alignItems:'center',gap:5,marginTop:3,flexWrap:'wrap' }}>
            {isClean
              ? <EvidenceTag text={zone.evidence}/>
              : <span style={{ fontSize:11,color:annotated?C.grey400:col,fontWeight:500,
                  textDecoration:annotated?'line-through':'' }}>{zone.evidence}</span>}
          </div>
        </div>

        {/* Lane pills */}
        <div style={{ display:'flex',gap:3,flexShrink:0 }}>
          {zone.lanes.map(l=><LanePill key={l} lane={l}/>)}
        </div>

        {/* Chevron for expandable rows */}
        {!isClean && (
          <span className="material-icons" style={{ fontSize:15,color:C.grey300,
            transform:isOpen?'rotate(180deg)':'none',transition:'transform 0.15s',flexShrink:0 }}>
            expand_more
          </span>
        )}
      </div>

      {/* Expanded detail */}
      {isOpen && !isClean && (
        <div style={{ padding:'10px 14px 14px 32px',background:bg+'55',
          borderTop:`1px solid ${col}22` }}>

          {/* Extracted content or "missing" */}
          <div style={{ marginBottom:10 }}>
            <div style={{ fontSize:10,fontWeight:700,color:C.grey400,
              textTransform:'uppercase',letterSpacing:0.5,marginBottom:4 }}>
              {zone.extractedContent ? 'Extracted content' : 'Content'}
            </div>
            {zone.extractedContent
              ? <div style={{ fontSize:12,color:C.grey800,lineHeight:1.6,
                  background:C.white,border:`1px solid ${C.grey50}`,
                  borderRadius:4,padding:'6px 10px' }}>{zone.extractedContent}</div>
              : <div style={{ fontSize:12,color:C.miss,fontStyle:'italic',
                  background:C.white,border:`1px dashed ${C.miss}66`,
                  borderRadius:4,padding:'6px 10px' }}>
                  Not found in this asset
                </div>}
          </div>

          {/* Comparative evidence */}
          <div style={{ marginBottom:zone.diff?10:0 }}>
            <div style={{ fontSize:10,fontWeight:700,color:C.grey400,
              textTransform:'uppercase',letterSpacing:0.5,marginBottom:4 }}>
              Comparative evidence
            </div>
            <div style={{ fontSize:12,color:C.grey700,lineHeight:1.65,
              borderLeft:`2px solid ${C.grey100}`,paddingLeft:10 }}>
              {zone.evidenceDetail}
            </div>
          </div>

          {/* Pattern base */}
          {zone.patternBase && (
            <div style={{ marginTop:8,marginBottom:8,
              background:C.white,border:`1px solid ${C.grey50}`,
              borderRadius:4,padding:'6px 10px',
              fontSize:11,color:C.grey500,lineHeight:1.6 }}>
              <span className="material-icons" style={{ fontSize:12,verticalAlign:'middle',
                marginRight:4,color:C.grey400 }}>analytics</span>
              {zone.patternBase}
            </div>
          )}

          {/* Diff */}
          {zone.diff && (
            <div style={{ marginBottom:10 }}>
              <div style={{ fontSize:10,fontWeight:700,color:C.grey400,
                textTransform:'uppercase',letterSpacing:0.5,marginBottom:4 }}>Word diff</div>
              <DiffView segments={zone.diff}/>
            </div>
          )}

          {/* Annotation composer — only if not yet annotated */}
          {zone.annotationDraft && !annotated && (
            <AnnotationComposer
              draft={zone.annotationDraft}
              zoneId={zone.id}
              onAnnotate={onAnnotate}
              onDismiss={onDismiss}
            />
          )}
          {/* Annotated undo */}
          {annotated && (
            <div style={{ marginTop:10,display:'flex',alignItems:'center',gap:6,
              fontSize:11,color:C.grey400 }}>
              <span className="material-icons" style={{ fontSize:13,color:C.clean }}>check_circle</span>
              Annotation created in VVPM
              <button onClick={()=>onUndo(zone.id)} style={{ fontSize:11,color:C.grey400,
                background:'none',border:'none',cursor:'pointer',fontFamily:'inherit',
                textDecoration:'underline',padding:0 }}>undo</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── TAB BAR ──────────────────────────────────────────────────────────────────
const TabBar = ({ active, onSelect, asset }) => {
  const tabs = [
    { id:'all',   label:'All' },
    { id:'M',     label:'Medical',    lane:'M' },
    { id:'L',     label:'Legal',      lane:'L' },
    { id:'R',     label:'Regulatory', lane:'R' },
  ];

  const countForTab = tabId => {
    if (tabId==='all') return asset.zones.length;
    return asset.zones.filter(z=>z.lanes.includes(tabId)).length;
  };

  return (
    <div style={{ display:'flex',gap:2,padding:'3px',
      background:'rgba(0,0,0,0.04)',borderRadius:8,width:'fit-content' }}>
      {tabs.map(tab=>{
        const isActive = active===tab.id;
        const laneCol  = tab.lane ? laneToken(tab.lane) : null;
        // Active tab: solid primary.600 fill (#00A66F), white text + dot.
        // Inactive: transparent fill, grey text, lane-colour dot.
        return (
          <div key={tab.id} onClick={()=>onSelect(tab.id)} style={{
            display:'flex',alignItems:'center',gap:5,
            padding:'6px 12px',borderRadius:6,cursor:'pointer',userSelect:'none',
            background:isActive?'#00A66F':'transparent',
            boxShadow:isActive?'0 1px 3px rgba(0,0,0,0.10)':'none',
            transition:'all 0.12s',
          }}>
            {laneCol && <span style={{ width:7,height:7,borderRadius:'50%',
              background: isActive ? '#fff' : laneCol.text,
              flexShrink:0, opacity: isActive ? 1 : 0.7 }}/>}
            <span style={{ fontSize:13,fontWeight:isActive?600:400,
              color: isActive ? '#fff' : C.grey500,
              whiteSpace:'nowrap' }}>{tab.label}</span>
            <span style={{ fontSize:11,
              color: isActive ? 'rgba(255,255,255,0.85)' : C.grey400,
              fontVariantNumeric:'tabular-nums' }}>{countForTab(tab.id)}</span>
          </div>
        );
      })}
    </div>
  );
};

// ─── CHECK SUMMARY BAR ────────────────────────────────────────────────────────
const CheckSummary = ({ zones, activeTab, asset, zoneActions }) => {
  const allFiltered = activeTab==='all' ? zones : zones.filter(z=>z.lanes.includes(activeTab));
  // Exclude dismissed from counts — workload = what's still open
  const filtered = allFiltered.filter(z=>zoneActions[z.id]!=='dismissed');
  const total   = filtered.length;
  const clean   = filtered.filter(z=>z.status==='clean'||zoneActions[z.id]==='annotated').length;
  const attn    = filtered.filter(z=>z.status==='attn'&&!zoneActions[z.id]).length;
  const miss    = filtered.filter(z=>z.status==='miss'&&!zoneActions[z.id]).length;
  const dismissed = allFiltered.filter(z=>zoneActions[z.id]==='dismissed').length;

  const scoreKey = activeTab==='all'?'overall':activeTab==='M'?'medical':activeTab==='L'?'legal':'regulatory';
  const score = asset.scores[scoreKey];
  const scol  = scoreColor(score);
  const laneLabel = activeTab==='all'?'total checks'
    : laneToken(activeTab).label.toLowerCase()+' checks';

  return (
    <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',
      padding:'7px 14px',background:C.white,borderBottom:`1px solid ${C.grey50}`,flexWrap:'wrap',gap:8 }}>
      <div style={{ display:'flex',gap:10,alignItems:'center',flexWrap:'wrap' }}>
        <span style={{ fontSize:12,color:C.grey600 }}><strong style={{ color:C.grey900 }}>{total}</strong> {laneLabel}</span>
        {[
          {label:'clean',   count:clean, col:C.clean},
          {label:'attention',count:attn, col:C.attn},
          {label:'missing', count:miss,  col:C.miss},
        ].map(({label,count,col})=>(
          <span key={label} style={{ display:'inline-flex',alignItems:'center',gap:4,fontSize:12,color:C.grey600 }}>
            <span style={{ width:7,height:7,borderRadius:'50%',background:col }}/>
            <strong style={{ color:C.grey900 }}>{count}</strong> {label}
          </span>
        ))}
        {dismissed > 0 && (
          <span style={{ fontSize:11,color:C.grey300,fontStyle:'italic' }}>{dismissed} dismissed</span>
        )}
      </div>
      <span style={{ fontSize:13,fontWeight:700,color:scol,fontVariantNumeric:'tabular-nums',flexShrink:0 }}>
        {activeTab==='all'?'Overall':laneToken(activeTab)?.label} · {score}
      </span>
    </div>
  );
};

// ─── HISTORY PANEL ────────────────────────────────────────────────────────────
const HistoryPanel = ({ history, onClose }) => {
  const Section = ({ title, icon, items, renderItem }) => (
    <div style={{ marginBottom:16 }}>
      <div style={{ display:'flex',alignItems:'center',gap:6,marginBottom:8 }}>
        <span className="material-icons" style={{ fontSize:14,color:C.grey400 }}>{icon}</span>
        <span style={{ fontSize:11,fontWeight:700,color:C.grey500,textTransform:'uppercase',letterSpacing:0.6 }}>{title}</span>
      </div>
      <div style={{ display:'flex',flexDirection:'column',gap:4 }}>
        {items.map((item,i)=>(
          <div key={i} style={{ fontSize:12,color:C.grey700,lineHeight:1.6,
            padding:'6px 10px',background:C.grey25,borderRadius:4,
            border:`1px solid ${C.grey50}` }}>
            <span className="mono" style={{ fontSize:10,color:C.grey400,marginRight:8 }}>{item.date}</span>
            {renderItem(item)}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div style={{ position:'absolute',top:0,right:0,bottom:0,left:0,
      background:C.white,zIndex:20,display:'flex',flexDirection:'column',
      borderLeft:`1px solid ${C.grey50}` }}>
      <div style={{ padding:'12px 14px',borderBottom:`1px solid ${C.grey50}`,
        display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0 }}>
        <span style={{ fontSize:14,fontWeight:600,color:C.grey800 }}>History</span>
        <button onClick={onClose} style={{ background:'none',border:'none',cursor:'pointer',
          padding:4,color:C.grey400,display:'flex' }}>
          <span className="material-icons" style={{ fontSize:20 }}>close</span>
        </button>
      </div>
      <div style={{ flex:1,overflowY:'auto',padding:'16px 14px' }}>
        <Section title="Asset edits" icon="edit_note" items={history.assetEdits}
          renderItem={i=><><strong>{i.actor}</strong> — {i.action}</>}/>
        <Section title="Precheck runs" icon="autorenew" items={history.precheckRuns}
          renderItem={i=><><strong>Score {i.score}</strong> {i.delta&&<span style={{ color:C.green600 }}>{i.delta}</span>} — {i.summary}</>}/>
        <Section title="Base & rule changes" icon="database" items={history.baseChanges}
          renderItem={i=><><strong>{i.item}</strong> {i.version} — {i.note}</>}/>
      </div>
    </div>
  );
};

// ─── MAIN DRAWER ──────────────────────────────────────────────────────────────
const Drawer = ({ asset, role, onClose, hoveredZone, selectedZone, onZoneHover, onZoneSelect, emailRef }) => {
  const [activeTab, setActiveTab] = useState('all');
  const [openZone,  setOpenZone]  = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [zoneActions, setZoneActions] = useState({}); // { [zoneId]: 'annotated' | 'dismissed' }

  const annotate = id => setZoneActions(p=>({...p,[id]:'annotated'}));
  const dismiss  = id => { setZoneActions(p=>({...p,[id]:'dismissed'})); setOpenZone(null); };
  const undo     = id => setZoneActions(p=>{ const n={...p}; delete n[id]; return n; });

  // Reset on asset change
  useEffect(()=>{ setActiveTab('all'); setOpenZone(null); setShowHistory(false); setZoneActions({}); }, [asset.identity]);

  // Auto-expand ≤2 missing zones when tab changes
  useEffect(()=>{
    const visible = activeTab==='all' ? asset.zones : asset.zones.filter(z=>z.lanes.includes(activeTab));
    const missing = visible.filter(z=>z.status==='miss');
    if (missing.length <= 2 && missing.length > 0) {
      setOpenZone(missing[0].id);
    } else {
      setOpenZone(null);
    }
  }, [activeTab, asset.identity]);

  // External selection (e.g. user clicked a rectangle on the PDF preview)
  // → switch to a tab that contains the zone, expand it, scroll into view.
  const drawerScrollRef = useRef(null);
  useEffect(() => {
    if (!selectedZone) return;
    const zone = asset.zones.find(z => z.id === selectedZone);
    if (!zone) return;
    // If the active tab filters out this zone, jump to "all" so it's visible.
    if (activeTab !== 'all' && !zone.lanes.includes(activeTab)) {
      setActiveTab('all');
    }
    setOpenZone(selectedZone);
    // Scroll the row into view inside the drawer's scroll container.
    requestAnimationFrame(() => {
      const container = drawerScrollRef.current;
      if (!container) return;
      const row = container.querySelector(`[data-zone-row-id="${CSS.escape(selectedZone)}"]`);
      if (row) {
        const rowRect = row.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const offset = rowRect.top - containerRect.top - 80;
        container.scrollBy({ top: offset, behavior: 'smooth' });
      }
    });
  }, [selectedZone, asset.identity]);

  const scrollEmailTo = useCallback(zoneId => {
    if (!emailRef.current) return;
    const el = emailRef.current.querySelector(`[data-zone-id="${zoneId}"]`);
    if (el) {
      const c = emailRef.current;
      c.scrollTop = el.offsetTop - c.getBoundingClientRect().height / 3;
    }
  }, [emailRef]);

  const handleRowHover = zoneId => {
    onZoneHover(zoneId);
    if (zoneId) scrollEmailTo(zoneId);
  };

  const handleRowSelect = zoneId => {
    onZoneSelect(zoneId === selectedZone ? null : zoneId);
    if (zoneId) scrollEmailTo(zoneId);
  };

  const filteredZones = activeTab==='all'
    ? asset.zones
    : asset.zones.filter(z=>z.lanes.includes(activeTab));

  const canApprove = asset.zones.filter(z=>z.status==='miss').length===0;

  return (
    <div style={{ width:520,height:'100%',display:'flex',flexDirection:'column',
      background:C.white,borderLeft:`1px solid ${C.grey50}`,
      boxShadow:'-3px 0 12px rgba(0,0,0,0.07)',flexShrink:0,position:'relative' }}>

      {/* History overlay */}
      {showHistory && <HistoryPanel history={asset.history} onClose={()=>setShowHistory(false)}/>}

      {/* §0 Header */}
      <div style={{ background:C.white,borderBottom:`1px solid ${C.grey50}`,
        padding:'11px 14px 10px',flexShrink:0 }}>
        <div style={{ display:'flex',alignItems:'flex-start',justifyContent:'space-between',marginBottom:8 }}>
          <div style={{ minWidth:0 }}>
            <div style={{ fontSize:10,fontWeight:700,color:C.grey400,
              textTransform:'uppercase',letterSpacing:'.06em',marginBottom:2 }}>Total score</div>
            <div style={{ display:'flex',alignItems:'baseline',gap:6 }}>
              <span style={{ fontSize:42,fontWeight:700,color:scoreColor(asset.scores.overall),
                fontVariantNumeric:'tabular-nums',lineHeight:1 }}>{asset.scores.overall}</span>
              <span style={{ fontSize:12,color:C.grey300,paddingBottom:2 }}>/100</span>
            </div>
            {/* Identity row removed — moved to the AssetMetaCard below the tabs. */}
          </div>
          <div style={{ display:'flex',gap:6,alignItems:'center',flexShrink:0 }}>
            <button onClick={()=>setShowHistory(h=>!h)} title="Version history"
              style={{ display:'flex',alignItems:'center',gap:3,background:'none',
                border:`1px solid ${C.grey50}`,borderRadius:5,padding:'4px 8px',
                cursor:'pointer',fontSize:11,color:C.grey500,fontFamily:'inherit' }}>
              <span className="material-icons" style={{ fontSize:14 }}>history</span>
              History
            </button>
            <button onClick={onClose} style={{ background:'none',border:'none',
              cursor:'pointer',padding:4,color:C.grey300,display:'flex' }}>
              <span className="material-icons" style={{ fontSize:20 }}>close</span>
            </button>
          </div>
        </div>
        {/* Tab bar */}
        <TabBar active={activeTab} onSelect={setActiveTab} asset={asset}/>
      </div>

      {/* Check summary bar */}
      <CheckSummary zones={asset.zones} activeTab={activeTab} asset={asset} zoneActions={zoneActions}/>

      {/* X-ray spine */}
      <div ref={drawerScrollRef} style={{ flex:1,overflowY:'auto',background:C.grey25 }}>
        <AssetMetaCard asset={asset}/>
        <VisualLibraryCard/>
        <div style={{ background:C.white,borderBottom:`1px solid ${C.grey50}`,borderTop:`1px solid ${C.grey50}` }}>
          {filteredZones.length === 0 ? (
            <div style={{ padding:'20px 14px',fontSize:12,color:C.grey400,textAlign:'center' }}>
              No zones assigned to this function for this asset.
            </div>
          ) : (
            filteredZones.map(zone=>(
              <ZoneRow
                key={zone.id}
                zone={zone}
                isHovered={hoveredZone===zone.id}
                isSelected={selectedZone===zone.id}
                onHover={handleRowHover}
                isOpen={openZone===zone.id}
                onToggle={()=>{
                  const next = openZone===zone.id ? null : zone.id;
                  setOpenZone(next);
                  handleRowSelect(zone.id);
                }}
                zoneAction={zoneActions[zone.id]}
                onAnnotate={annotate}
                onDismiss={dismiss}
                onUndo={undo}
              />
            ))
          )}
        </div>
        <div style={{ height:16 }}/>
      </div>

      {/* §6 Footer */}
      <div style={{ background:C.white,borderTop:`1px solid ${C.grey50}`,
        padding:'9px 14px',display:'flex',gap:8,alignItems:'center',flexShrink:0 }}>
        {role==='reviewer' ? <>
          <button style={{ flex:1,height:32,
            background:canApprove?C.green600:C.grey100,
            color:canApprove?C.white:C.grey300,
            border:'none',borderRadius:6,fontSize:13,fontWeight:500,
            cursor:canApprove?'pointer':'not-allowed',fontFamily:'inherit' }}>
            {canApprove?'Approve asset':`Approve — ${asset.zones.filter(z=>z.status==='miss').length} missing`}
          </button>
          <button style={{ height:32,padding:'0 12px',background:C.white,
            border:`1px solid ${C.grey100}`,borderRadius:6,fontSize:13,
            color:C.grey900,cursor:'pointer',fontFamily:'inherit',whiteSpace:'nowrap' }}>
            Request changes
          </button>
          <button style={{ height:32,padding:'0 10px',background:C.white,
            border:`1px solid ${C.grey100}`,borderRadius:6,display:'flex',alignItems:'center',
            gap:3,cursor:'pointer',color:C.grey600,fontSize:12,fontFamily:'inherit' }}>
            <span className="material-icons" style={{ fontSize:13 }}>download</span>Export
          </button>
        </> : <>
          <button style={{ flex:1,height:32,
            background:canApprove?C.green600:C.grey100,
            color:canApprove?C.white:C.grey300,
            border:'none',borderRadius:6,fontSize:13,fontWeight:500,
            cursor:canApprove?'pointer':'not-allowed',fontFamily:'inherit' }}>
            Submit for MLR review
          </button>
          <button style={{ height:32,padding:'0 10px',background:C.white,
            border:`1px solid ${C.grey100}`,borderRadius:6,display:'flex',alignItems:'center',
            gap:3,cursor:'pointer',color:C.grey600,fontSize:12,fontFamily:'inherit' }}>
            <span className="material-icons" style={{ fontSize:13 }}>download</span>Export
          </button>
        </>}
        <span style={{ fontSize:10,color:C.grey300,flexShrink:0 }}>Read-only · v1</span>
      </div>
    </div>
  );
};

Object.assign(window, { Drawer });
