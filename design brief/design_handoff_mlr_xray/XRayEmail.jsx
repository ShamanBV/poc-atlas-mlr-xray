// XRayEmail.jsx — Left-pane email preview with lane-coloured overlay rectangles

// ─── ZONE LABEL CHIP ─────────────────────────────────────────────────────────
// Subtle top-right rectangle overlay, lane-coloured, short label
const ZoneChip = ({ lanes, status, label, isHovered, isSelected }) => {
  // Pick the first lane colour; if no lanes, use status colour subtly
  const laneCol = lanes && lanes.length > 0 ? laneToken(lanes[0]) : null;
  const chipBg  = laneCol ? laneCol.bg  : `${statusColor(status)}18`;
  const chipText= laneCol ? laneCol.text : statusColor(status);

  // Only show when hovered or selected; very faint otherwise
  const visible = isHovered || isSelected;
  const opacity = isSelected ? 1 : isHovered ? 0.92 : 0;

  return (
    <div style={{
      position:'absolute', top:4, right:6,
      display:'flex', gap:3, alignItems:'center',
      pointerEvents:'none', zIndex:10,
      opacity, transition:'opacity 0.15s',
    }}>
      {/* Status dot */}
      <span style={{
        width:6, height:6, borderRadius:'50%',
        background:statusColor(status), flexShrink:0,
        display: visible ? 'inline-block' : 'none',
      }}/>
      {/* Lane pill(s) */}
      {lanes && lanes.map(l => {
        const t = laneToken(l);
        return (
          <span key={l} style={{
            fontSize:9, fontWeight:700, letterSpacing:0.3,
            padding:'1px 5px', borderRadius:3,
            background:t.bg, color:t.text,
            border:`1px solid ${t.text}22`,
            whiteSpace:'nowrap',
          }}>{t.label}</span>
        );
      })}
      {/* Short label if no lane */}
      {(!lanes || lanes.length === 0) && (
        <span style={{
          fontSize:9, fontWeight:600,
          padding:'1px 5px', borderRadius:3,
          background:chipBg, color:chipText,
          border:`1px solid ${chipText}22`,
          whiteSpace:'nowrap',
        }}>{label}</span>
      )}
    </div>
  );
};

// ─── GHOST BLOCK ─────────────────────────────────────────────────────────────
const GhostBlock = ({ label, lanes, zoneId, hoveredZone, selectedZone, onHover, onSelect }) => {
  const isHov = hoveredZone === zoneId;
  const isSel = selectedZone === zoneId;
  const laneCol = lanes && lanes.length > 0 ? laneToken(lanes[0]) : null;
  const borderCol = laneCol ? laneCol.text : C.miss;

  return (
    <div
      data-zone-id={zoneId}
      onMouseEnter={()=>onHover(zoneId)}
      onMouseLeave={()=>onHover(null)}
      onClick={()=>onSelect(zoneId)}
      style={{
        position:'relative',
        display:'flex', alignItems:'center', gap:6,
        border:`1.5px dashed ${borderCol}${isSel?'CC':'44'}`,
        borderRadius:4,
        padding:'7px 10px', margin:'4px 0',
        background: isSel ? `${borderCol}12` : isHov ? `${borderCol}08` : `${borderCol}04`,
        fontSize:11, color:`${borderCol}CC`, fontStyle:'italic',
        cursor:'pointer', transition:'all 0.12s',
      }}
    >
      <span className="material-icons" style={{ fontSize:13, color:`${borderCol}88` }}>add_box</span>
      {label}
      {/* Lane chips top-right */}
      <div style={{ position:'absolute', top:4, right:6, display:'flex', gap:3, opacity: isHov||isSel?1:0.5, transition:'opacity 0.15s' }}>
        {(lanes||[]).map(l=>{
          const t = laneToken(l);
          return <span key={l} style={{ fontSize:9,fontWeight:700,padding:'1px 5px',borderRadius:3,background:t.bg,color:t.text,border:`1px solid ${t.text}22` }}>{t.label}</span>;
        })}
      </div>
    </div>
  );
};

// ─── BLOCK WRAPPER ────────────────────────────────────────────────────────────
const BlockWrapper = ({ zoneId, lanes, status, label, hoveredZone, selectedZone, onHover, onSelect, children }) => {
  const isHov = hoveredZone === zoneId;
  const isSel = selectedZone === zoneId;
  const col   = statusColor(status || 'clean');

  // Only non-clean zones get a visible outline; clean ones are very faint on hover
  const outlineCol = status === 'clean'
    ? (isHov ? `${col}30` : 'transparent')
    : (isSel ? `${col}BB` : isHov ? `${col}66` : 'transparent');

  return (
    <div
      data-zone-id={zoneId}
      onMouseEnter={()=>onHover(zoneId)}
      onMouseLeave={()=>onHover(null)}
      onClick={()=>onSelect && status !== 'clean' && onSelect(zoneId)}
      style={{
        position:'relative',
        outline:`2px solid ${outlineCol}`,
        outlineOffset:-1,
        transition:'outline 0.1s',
        cursor: status !== 'clean' ? 'pointer' : 'default',
        borderRadius:2,
      }}
    >
      {children}
      <ZoneChip
        lanes={lanes||[]}
        status={status}
        label={label}
        isHovered={isHov}
        isSelected={isSel}
      />
    </div>
  );
};

// ─── KISQALI EMAIL ────────────────────────────────────────────────────────────
const KisqaliEmail = ({ hoveredZone, selectedZone, onHover, onSelect }) => (
  <div style={{ fontFamily:'Arial,sans-serif',background:'#fff',fontSize:13,lineHeight:1.55 }}>
    <BlockWrapper zoneId="z1" lanes={[]} status="clean" label="Header" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#4A0080',padding:'14px 20px',display:'flex',alignItems:'center',gap:10 }}>
        <div style={{ width:30,height:30,background:'#6A0DAD',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:13,fontWeight:700,color:'#fff',flexShrink:0 }}>K</div>
        <span style={{ fontSize:15,fontWeight:700,color:'#fff',flex:1 }}>KISQALI® (ribociclib)</span>
      </div>
    </BlockWrapper>
    <div style={{ padding:'14px 20px 0' }}>
      <BlockWrapper zoneId="z2" lanes={[]} status="clean" label="Salutation" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <p style={{ marginBottom:8 }}>Dear {'{{userName}}'},</p>
      </BlockWrapper>
      <BlockWrapper zoneId="z3" lanes={['M']} status="attn" label="Key claim" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <p style={{ fontWeight:600,color:'#323232',marginBottom:8,padding:'6px 8px',
          background:`${C.attn}08`,borderRadius:3 }}>
          At 5 years, KISQALI® + ET reduced the risk of recurrence by 25.2% vs ET alone (HR 0.748, 95% CI 0.618–0.906; p=0.0014).
        </p>
      </BlockWrapper>
      <BlockWrapper zoneId="z4" lanes={['M']} status="attn" label="Data callout" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ background:'#EDE7F6',border:'1px solid #D1C4E9',borderRadius:4,
          padding:'9px 14px',marginBottom:8,display:'flex',alignItems:'center',gap:10 }}>
          <span style={{ fontSize:21,fontWeight:700,color:'#6A0DAD',fontVariantNumeric:'tabular-nums',lineHeight:1 }}>25.2%</span>
          <span style={{ fontSize:12,color:'#555' }}>risk reduction at 5 years</span>
        </div>
      </BlockWrapper>
      <BlockWrapper zoneId="z5" lanes={['M']} status="miss" label="Population" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <p style={{ color:'#545A5B',marginBottom:8,padding:'6px 8px',
          background:`${C.miss}06`,borderRadius:3 }}>
          NATALEE is the largest adjuvant CDK4/6i trial in HR+/HER2− eBC, with a broad population including patients at elevated risk.
        </p>
      </BlockWrapper>
      <BlockWrapper zoneId="z6" lanes={[]} status="clean" label="CTA" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ textAlign:'center',marginBottom:14 }}>
          <div style={{ display:'inline-block',background:'#6A0DAD',color:'#fff',padding:'8px 22px',borderRadius:4,fontSize:13,fontWeight:600 }}>Request a rep visit</div>
        </div>
      </BlockWrapper>
    </div>
    <BlockWrapper zoneId="z7" lanes={['R']} status="clean" label="AE reporting" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ margin:'0 20px',background:'#F5F5F5',border:'1px solid #E0E0E0',borderRadius:4,padding:'7px 12px' }}>
        <div style={{ fontSize:10,fontWeight:700,color:'#545A5B',marginBottom:2,textTransform:'uppercase',letterSpacing:0.4 }}>Adverse event reporting</div>
        <div style={{ fontSize:11,color:'#6F7E7F',lineHeight:1.5 }}>Adverse events should be reported via the Yellow Card Scheme at mhra.gov.uk/yellowcard.</div>
      </div>
    </BlockWrapper>
    <div style={{ padding:'0 20px',margin:'8px 0' }}>
      <GhostBlock zoneId="z8_ghost" label="Audience-restriction bar expected here" lanes={['R','L']} hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}/>
    </div>
    <BlockWrapper zoneId="z9" lanes={['L','R']} status="clean" label="Footer" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#1A1A2E',padding:'10px 20px',marginTop:4 }}>
        <div style={{ fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:1,marginBottom:4 }}>LEGAL · MAH · UNSUBSCRIBE</div>
        <div style={{ fontSize:10,color:'rgba(255,255,255,0.6)',lineHeight:1.6 }}>Novartis Pharmaceuticals UK Limited · 2nd Floor, The WestWorks Building, White City Place, 195 Wood Lane, London W12 7FQ · Company number 00119006.</div>
        <div style={{ fontSize:9,color:'rgba(255,255,255,0.2)',marginTop:5 }}>FA-11551654 · prepared 2026-03-14</div>
      </div>
    </BlockWrapper>
  </div>
);

// ─── LEQVIO EMAIL ─────────────────────────────────────────────────────────────
const LeqvioEmail = ({ hoveredZone, selectedZone, onHover, onSelect }) => (
  <div style={{ fontFamily:'Arial,sans-serif',background:'#fff',fontSize:13,lineHeight:1.55 }}>
    <BlockWrapper zoneId="lz1" lanes={[]} status="clean" label="Header" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#004B87',padding:'14px 20px',display:'flex',alignItems:'center',gap:10 }}>
        <div style={{ width:30,height:30,background:'#0066B3',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:13,fontWeight:700,color:'#fff',flexShrink:0 }}>L</div>
        <span style={{ fontSize:15,fontWeight:700,color:'#fff',flex:1 }}>LEQVIO® (inclisiran)</span>
      </div>
    </BlockWrapper>
    <BlockWrapper zoneId="lz2" lanes={['R','L']} status="clean" label="Audience restriction" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#E3F2FD',padding:'4px 20px' }}><span style={{ fontSize:10,fontWeight:700,color:'#1565C0',letterSpacing:0.5 }}>FOR HEALTHCARE PROFESSIONALS IN IRELAND ONLY</span></div>
    </BlockWrapper>
    <div style={{ padding:'14px 20px 0' }}>
      <BlockWrapper zoneId="lz3" lanes={[]} status="clean" label="Salutation" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><p style={{ marginBottom:8 }}>Dear {'{{userName}}'},</p></BlockWrapper>
      <BlockWrapper zoneId="lz4" lanes={['M']} status="clean" label="Key claim" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><p style={{ fontWeight:600,marginBottom:8 }}>In ORION-10, inclisiran reduced LDL-C by 52% from baseline at day 510 (p&lt;0.001) vs placebo.</p></BlockWrapper>
      <BlockWrapper zoneId="lz5" lanes={['M']} status="clean" label="Data callout" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ background:'#E3F2FD',border:'1px solid #90CAF9',borderRadius:4,padding:'9px 14px',marginBottom:8,display:'flex',alignItems:'center',gap:10 }}>
          <span style={{ fontSize:21,fontWeight:700,color:'#0D47A1',fontVariantNumeric:'tabular-nums',lineHeight:1 }}>52%</span>
          <span style={{ fontSize:12,color:'#555' }}>LDL-C reduction from baseline</span>
        </div>
      </BlockWrapper>
      <BlockWrapper zoneId="lz6" lanes={[]} status="clean" label="CTA" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><div style={{ textAlign:'center',marginBottom:14 }}><div style={{ display:'inline-block',background:'#004B87',color:'#fff',padding:'8px 22px',borderRadius:4,fontSize:13,fontWeight:600 }}>Request a rep visit</div></div></BlockWrapper>
    </div>
    <BlockWrapper zoneId="lz7" lanes={['R']} status="clean" label="Reimbursement" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><div style={{ margin:'0 20px',background:'#FFFAEB',border:'1px solid #DEBD66',borderRadius:4,padding:'7px 12px' }}><div style={{ fontSize:10,fontWeight:700,color:'#CC9914',marginBottom:2 }}>REIMBURSEMENT STATUS</div><div style={{ fontSize:11,color:'#545A5B',lineHeight:1.5 }}>LEQVIO is not currently reimbursed in Ireland under the GMS/PCRS schemes.</div></div></BlockWrapper>
    <BlockWrapper zoneId="lz8" lanes={['R']} status="clean" label="AE reporting" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><div style={{ margin:'8px 20px 0',background:'#F5F5F5',border:'1px solid #E0E0E0',borderRadius:4,padding:'7px 12px' }}><div style={{ fontSize:10,fontWeight:700,color:'#545A5B',marginBottom:2,textTransform:'uppercase',letterSpacing:0.4 }}>Adverse event reporting</div><div style={{ fontSize:11,color:'#6F7E7F',lineHeight:1.5 }}>Adverse events should be reported to the HPRA Pharmacovigilance at medsafety.ie.</div></div></BlockWrapper>
    <BlockWrapper zoneId="lz9" lanes={['L','R']} status="clean" label="Footer" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}><div style={{ background:'#1A2A3A',padding:'10px 20px',marginTop:8 }}><div style={{ fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:1,marginBottom:4 }}>LEGAL · MAH · UNSUBSCRIBE</div><div style={{ fontSize:10,color:'rgba(255,255,255,0.6)',lineHeight:1.6 }}>Novartis Ireland Limited · 2nd Floor, Block B, One Georges Quay Plaza, Dublin 2.</div><div style={{ fontSize:9,color:'rgba(255,255,255,0.2)',marginTop:5 }}>FA-11551901 · prepared 2026-04-02</div></div></BlockWrapper>
  </div>
);

// ─── JAKAVI EMAIL ─────────────────────────────────────────────────────────────
const JakaviEmail = ({ hoveredZone, selectedZone, onHover, onSelect }) => (
  <div style={{ fontFamily:'Arial,sans-serif',background:'#fff',fontSize:13,lineHeight:1.55 }}>
    <BlockWrapper zoneId="jz1" lanes={[]} status="clean" label="Header" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#1A237E',padding:'14px 20px',display:'flex',alignItems:'center',gap:10 }}>
        <div style={{ width:30,height:30,background:'#283593',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:13,fontWeight:700,color:'#fff',flexShrink:0 }}>J</div>
        <span style={{ fontSize:15,fontWeight:700,color:'#fff',flex:1 }}>JAKAVI® (ruxolitinib)</span>
      </div>
    </BlockWrapper>
    <div style={{ padding:'14px 20px 0' }}>
      <BlockWrapper zoneId="jz2" lanes={[]} status="clean" label="Event hero" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ marginBottom:10 }}>
          <div style={{ fontSize:9,fontWeight:700,color:'#1565C0',letterSpacing:0.8,marginBottom:3 }}>INVITATION</div>
          <div style={{ fontSize:14,fontWeight:700,color:'#1A237E',lineHeight:1.4 }}>Join us at the SOHO Haematology Symposium · Manchester · 14 June 2026</div>
        </div>
      </BlockWrapper>
      <BlockWrapper zoneId="jz3" lanes={['M','L']} status="attn" label="Speaker" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ display:'flex',gap:10,alignItems:'center',background:`${C.attn}08`,
          border:`1px solid ${C.attn}33`,borderRadius:6,padding:'8px 12px',marginBottom:10 }}>
          <div style={{ width:30,height:30,background:'#78909C',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:11,fontWeight:700,color:'#fff',flexShrink:0 }}>CH</div>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:12,fontWeight:600,color:'#323232' }}>Prof. Claire Harrison</div>
            <div style={{ fontSize:11,color:'#6F7E7F' }}>Guy's and St Thomas' NHS Trust</div>
          </div>
        </div>
      </BlockWrapper>
      <BlockWrapper zoneId="jz4" lanes={[]} status="clean" label="Agenda" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ marginBottom:10 }}>
          {[['14:00','registration'],['14:30','keynote'],['16:00','breakouts'],['18:00','dinner']].map(([t,l])=>(
            <div key={t} style={{ display:'flex',gap:14,alignItems:'baseline',padding:'3px 0',borderBottom:'1px solid #F5F5F5',fontSize:12,color:'#545A5B' }}>
              <span style={{ color:'#1A237E',fontWeight:600,width:34,flexShrink:0,fontVariantNumeric:'tabular-nums' }}>{t}</span><span>{l}</span>
            </div>
          ))}
        </div>
      </BlockWrapper>
      <BlockWrapper zoneId="jz5" lanes={[]} status="clean" label="CTA" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
        <div style={{ textAlign:'center',marginBottom:12 }}>
          <div style={{ display:'inline-block',background:'#1A237E',color:'#fff',padding:'8px 22px',borderRadius:4,fontSize:13,fontWeight:600 }}>Register now</div>
        </div>
      </BlockWrapper>
    </div>
    <div style={{ padding:'0 20px',marginBottom:4 }}>
      <GhostBlock zoneId="jz6_ghost" label="ToV disclosure expected in footer" lanes={['L']} hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}/>
      <GhostBlock zoneId="jz7_ghost" label="Date of preparation expected here" lanes={['L']} hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}/>
    </div>
    <BlockWrapper zoneId="jz8" lanes={['R']} status="clean" label="Footer" hoveredZone={hoveredZone} selectedZone={selectedZone} onHover={onHover} onSelect={onSelect}>
      <div style={{ background:'#212121',padding:'10px 20px' }}>
        <div style={{ fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:1,marginBottom:4 }}>LEGAL · MAH · UNSUBSCRIBE</div>
        <div style={{ fontSize:10,color:'rgba(255,255,255,0.6)',lineHeight:1.6 }}>Novartis Pharmaceuticals UK Limited · 2nd Floor, 195 Wood Lane, London W12 7FQ. For healthcare professionals only. Adverse events should be reported. Confidential.</div>
        <div style={{ fontSize:9,color:'rgba(255,255,255,0.2)',marginTop:5 }}>(draft) · prepared 2026-04-16</div>
      </div>
    </BlockWrapper>
  </div>
);

// ─── EMAIL PREVIEW CONTAINER ──────────────────────────────────────────────────
const EmailPreview = ({ asset, hoveredZone, selectedZone, onZoneHover, onZoneSelect, emailRef }) => {
  const Content = asset.meta.brand==='KISQALI' ? KisqaliEmail
    : asset.meta.brand==='LEQVIO' ? LeqvioEmail : JakaviEmail;
  return (
    <div ref={emailRef} style={{ flex:1,background:'#ECEFF1',overflowY:'auto',
      display:'flex',flexDirection:'column',alignItems:'center',padding:'20px 20px 8px' }}>
      <div style={{ width:'100%',maxWidth:430,background:C.white,borderRadius:4,
        boxShadow:'0 4px 16px rgba(0,0,0,0.12)',overflow:'hidden' }}>
        <Content
          hoveredZone={hoveredZone}
          selectedZone={selectedZone}
          onHover={onZoneHover}
          onSelect={onZoneSelect}
        />
      </div>
      <div style={{ marginTop:10,fontSize:11,color:'#90A4AE',textAlign:'center',lineHeight:1.6 }}>
        Hover or click a zone to cross-link with X-ray
      </div>
    </div>
  );
};

Object.assign(window, { EmailPreview });
