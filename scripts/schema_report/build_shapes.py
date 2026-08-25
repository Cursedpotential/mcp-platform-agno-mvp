import json,sys,html
from pathlib import Path
S=Path(sys.argv[1]); cat={f"{d['schema']}.{d['table']}":d for d in json.loads((S/"catalog.json").read_text(encoding="utf-8"))["ai"]}
e=html.escape
T=lambda t:t.replace("timestamp with time zone","tstz").replace("character varying","varchar").replace("double precision","float8")

# ---------- SVG lane-grid engine ----------
NW,NH,GX,LH=200,54,72,128   # node w/h, x-gap (room for labels), lane pitch
def lanes_svg(lanes,edges,label,W=None,accent=(),missing=()):
    pos={}; lane_of={}
    for li,(lab,nodes) in enumerate(lanes):
        y=28+li*LH
        for ni,(k,t,sub) in enumerate(nodes):
            pos[k]=(150+ni*(NW+GX),y,t,sub); lane_of[k]=li
    ncols=max(len(n) for _,n in lanes)
    W=W or (150+ncols*(NW+GX)-GX+30)
    H=28+len(lanes)*LH
    o=[f'<figure><svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(label)}" style="max-width:100%;height:auto;font-family:IBM Plex Sans,system-ui,sans-serif">',
       '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker>'
       '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--drop)"/></marker></defs>']
    for li,(lab,_) in enumerate(lanes):
        y=28+li*LH
        if li<len(lanes)-1: o.append(f'<line x1="10" y1="{y+NH+32}" x2="{W-10}" y2="{y+NH+32}" stroke="var(--line)" stroke-width="1"/>')
        o.append(f'<text x="14" y="{y+NH/2+4}" font-size="11" font-weight="600" letter-spacing=".08em" fill="var(--mut)">{e(lab.upper())}</text>')
    for a,b,t in edges:
        ax,ay,_,_=pos[a]; bx,by,_,_=pos[b]
        bad=t.startswith("MISSING") or t.startswith("REJECTED")
        col='var(--drop)' if bad else 'currentColor'; mk='arr' if bad else 'ar'; dash=' stroke-dasharray="6 4"' if bad else ''
        span=abs(lane_of[a]-lane_of[b])
        if ay==by:
            if bx>ax: x1,x2=ax+NW,bx
            else: x1,x2=ax,bx+NW
            y1=ay+NH/2; pts=f"M{x1} {y1} L{x2} {y1}"; lx,ly,anchor=(x1+x2)/2,y1-9,"middle"
        elif span==1:
            x1=ax+NW/2; x2=bx+NW/2
            if by>ay: y1=ay+NH; y2=by; ym=y1+36
            else: y1=ay; y2=by+NH; ym=y1-36
            pts=f"M{x1} {y1} L{x1} {ym} L{x2} {ym} L{x2} {y2}"
            if abs(x1-x2)>60: lx,ly,anchor=(x1+x2)/2,ym-6,"middle"
            else: lx,ly,anchor=x1+8,(y1+ym)/2+4,"start"
        else:   # skips a lane: leave the source box sideways into the gutter, run the gutter, enter the target from its side
            gx=ax-GX/2 if ax>150 else ax+NW+GX/2
            y1=ay+NH/2; y2=by+NH/2
            ex=bx if gx<bx else bx+NW
            pts=f"M{(ax if gx<ax else ax+NW)} {y1} L{gx} {y1} L{gx} {y2} L{ex} {y2}"
            lx,ly,anchor=gx+6,(y1+y2)/2+4,"start"
        o.append(f'<path d="{pts}" fill="none" stroke="{col}" stroke-width="1.4" marker-end="url(#{mk})"{dash}/>')
        if t:
            tw=len(t)*6.2+10
            rx=lx-tw/2 if anchor=="middle" else lx-4
            o.append(f'<rect x="{rx}" y="{ly-11}" width="{tw}" height="15" rx="2" fill="var(--bg)"/>')
            o.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="11" fill="{col}">{e(t)}</text>')
    for k,(x,y,t,sub) in pos.items():
        st='var(--acc)' if k in accent else 'currentColor'; fill='var(--accbg)' if k in accent else 'var(--card)'
        dash=' stroke-dasharray="6 4"' if k in missing else ''
        o.append(f'<rect x="{x}" y="{y}" width="{NW}" height="{NH}" rx="4" fill="{fill}" stroke="{st}" stroke-width="1.4"{dash}/>')
        o.append(f'<text x="{x+NW/2}" y="{y+22}" text-anchor="middle" font-size="12.5" font-weight="600" fill="currentColor">{e(t)}</text>')
        if sub: o.append(f'<text x="{x+NW/2}" y="{y+40}" text-anchor="middle" font-size="10.5" fill="var(--mut)">{e(sub)}</text>')
    o.append(f'</svg><figcaption>{e(label)}</figcaption></figure>')
    return "".join(o)

A_svg=lanes_svg([
 ("raw",[("raw","evidence.raw_*","sms · imessage · facebook")]),
 ("spine",[("nr","normalized_record","occurred_at · knowledge_time"),("conv","conversation","thread · participants")]),
 ("message",[("msg","message","56 cols · id = spine id · ts_utc"),("mp","message_participant","role · conduct_party"),("att","attachment / call_log","media · calls")]),
 ("address book",[("ent","entity","root: person / organization"),("phone","phone · handle · email","e164 · platform · validity"),("alias","entity_alias · id_xref","aliases · cross-system ids")]),
 ("court",[("ei","analysis.evidence_item","exhibit · confidence tier"),("fc","factor_citation","supports / contradicts"),("cf","custody_factor","MCL 722.23 (a)-(l)"),("vce","vw_court_export","tier AND approved AND safe")]),
],[("raw","nr","parse"),("nr","msg","subtype"),("nr","conv","groups into"),("msg","mp","sender / recipients"),("msg","att","message_id"),
   ("mp","ent","entity_id"),("ent","phone","owns"),("phone","alias","resolved by"),("nr","ei","promoted to"),("ei","fc","cited by"),("fc","cf","factor"),("ei","vce","released by")],
 "Shape A - your June D2/D7 design as it exists live. Spine to typed message to participants to address book; court lane at the bottom. Every box exists in ai with 0 rows and no code writer.",accent=("ent","phone","alias"))

B_svg=lanes_svg([
 ("raw",[("raw","evidence.raw_*","")]),
 ("spine",[("nr","normalized_record","occurred_at · realized_at"),("route","message_projection_route","first_party | third_party"),("saf","source_available_from()","FUNCTION - no column")]),
 ("message",[("fpm","first_party_message","never created"),("tpm","third_party_message","occurred_at · sender_raw"),("tpp","third_party_message_participant","role only"),("chat","chat_conversation / chat_message","AI chats · sent_at")]),
 ("realization",[("re","realization_event","plural · HITL approve"),("rer","realization_event_record","link to spine"),("rvf","record_visible_from","visible_from = COALESCE(...)")]),
 ("walk",[("ha","vw_horizon_atom","what the walk reads"),("walk","walk_run / walk_step","ignorant agent")]),
],[("raw","nr","parse"),("nr","route","decides"),("route","fpm","MISSING"),("route","tpm","third_party"),("tpm","tpp","participants"),("nr","chat","0053 lane"),
   ("re","rer","1:N"),("rer","nr","record id"),("nr","saf","MISSING as column"),("rvf","ha","REJECTED (0059)"),("ha","walk","horizon filter")],
 "Shape B - ADR-0059/0053 as built. Route to third-party tables only; realization plural (correct); source_available_from is a function; the rejected visible_from collapse still feeds the walk.",missing=("fpm","saf"))

C_svg=lanes_svg([
 ("raw",[("raw","evidence.raw_*","")]),
 ("spine",[("nr","normalized_record (trimmed)","occurred_at · source_available_from"),("conv","conversation","first_party | third_party | ai_chat"),("chunk","record_chunk to Weaviate","one chunk table")]),
 ("message",[("msg","message · third_party_message · chat_message","THREE tables, owner-ruled separate 03:07"),("mp","message_participant","role · conduct_party · entity_id"),("ent","entity + phone/handle/email","address book (D2)")]),
 ("realization",[("re","realization_event(_record)","plural, append-only"),("walk","walk_run / walk_step","gates on source_available_from")]),
 ("court",[("ei","analysis.evidence_item","D7, unchanged"),("fc","factor_citation / custody_factor",""),("task","evidence_task · legal_timeline_event","")]),
],[("raw","nr","parse"),("nr","msg","subtype, same id"),("nr","conv","groups into"),("nr","chunk","chunks"),("msg","mp","participants"),("mp","ent","entity_id"),
   ("re","nr","links to spine"),("nr","walk","avail ≤ horizon"),("nr","ei","promote"),("ei","fc","cited by"),("fc","task","feeds")],
 "Shape C - target after the 2026-08-25 rulings: one spine; the THREE message tables stay separate (owner 03:07); participants / sender / recipients stay on the record (owner 03:25); both 0059 clocks as real columns; realization plural; walk gated on source_available_from; D2 address book added as an FK target via message_participant, alongside the record columns, never instead of them; D7 court lane kept. Removed: record_visible_from, realized_at columns. NOT removed: any message table, any participant column.",accent=("nr","msg","ent"))

F_svg=lanes_svg([
 ("1 · intake",[("file","source file","R2 / upload / export"),("cust","custody.py: H1","sha256 of the whole file"),("src","evidence.source + acquisition","who / when / how"),("hash","evidence_hash (H1 row)","append-only"),("audit","ops.audit_ledger","hash-chained, reads too")]),
 ("2 · split + hash",[("parser","parser (Go SBV / Python)","splits file into records"),("raw","raw_* landing → CONTEXT (D-069)","1 row / record · fingerprinted, not custody"),("h2","H1/H2 fingerprint per record","custody starts at promotion (D-069)"),("h3","H3 chain over H2s","at promotion, into evidence.* (D-069)"),("rej","raw_rejected + ingest_run","refusals + attempts")]),
 ("3 · derive",[("derive","derivation engine","re-runnable from raw"),("nr","normalized_record","occurred_at · source_available_from"),("msg","message tables (3, separate)","sender/recipients on the row"),("ent","entity address book","phone / handle to person"),("weav","record_chunk to Weaviate","clock filter before top-k")]),
 ("4 · analyze",[("walk","walk_run / walk_step","ignorant agent · horizon advances"),("real","realization_event","HITL approve · plural"),("det","detection.py","reference.detection_pattern"),("pf","pattern_finding","hypotheses only"),("cls","chunk_classification","n8n + Temporal")]),
 ("5 · conclude",[("prom","promote","knowledge hit to evidence"),("ei","evidence_item","exhibit · tier"),("fc","factor_citation","MCL (a)-(l)"),("vce","vw_court_export","tier AND approved AND safe"),("delta","as-lived vs hindsight DELTA","the deliverable")]),
],[("file","cust","bytes"),("cust","src","registers"),("src","hash","H1"),("hash","audit","logs all"),
   ("cust","parser","hands file"),("parser","raw","emits records"),("raw","h2","each record"),("h2","h3","in sequence"),("h3","hash","H2 rows + H3 head"),("parser","rej","refused"),
   ("raw","derive","reads"),("derive","nr","1 row/record"),("nr","msg","typed subtype"),("msg","ent","resolves sender"),("nr","weav","vectors"),
   ("nr","walk","avail ≤ horizon"),("walk","real","proposes"),("raw","det","scans"),("det","pf","hits"),("weav","cls","chunks"),
   ("weav","prom","hit"),("prom","ei","idempotent"),("ei","fc","cites"),("fc","vce","released"),("walk","delta","as-lived"),("vce","delta","hindsight")],
 "End-to-end data flow (target after the 2026-08-25 rulings). Read top to bottom: intake, raw landing as CONTEXT with fingerprints (D-069 — custody only begins when the owner promotes and H1 re-verifies), re-derivable spine + three separate message tables + address book + vectors, horizon-gated walk with plural realizations, court lane, the delta. Blue = where shape changes.",accent=("nr","walk","delta"))

# ---------- column tables ----------
def cols_table(q,note=""):
    d=cat.get(q)
    if not d: return f"<details class=tbl><summary><code>{e(q)}</code> <span class=meta>not in ai</span></summary></details>"
    rows="".join(f"<tr><td class=n>{i}</td><td class=m>{e(c['name'])}</td><td class=m>{e(T(c['type']))}</td><td class=cm>{e(c['comment'] or '')}</td></tr>" for i,c in enumerate(d["columns"],1))
    fks="".join(f"<li><code>{e(c['def'])}</code></li>" for c in d["constraints"] if c["type"]=="FK")
    return f"""<details class=tbl><summary><code>{e(q)}</code> <span class=meta>{len(d['columns'])} cols · {d['rows'] if d['rows'] is not None else '-'} rows{(' · '+e(note)) if note else ''}</span></summary>
<div class=scroll><table><thead><tr><th>#</th><th>column</th><th>type</th><th>comment</th></tr></thead><tbody>{rows}</tbody></table></div>{('<p class=meta>FK:</p><ul>'+fks+'</ul>') if fks else ''}</details>"""

A_tables=["working.normalized_record","working.message","working.message_participant","working.conversation","working.attachment","working.call_log","working.entity","working.person","working.organization","working.phone","working.handle","working.email","working.account","working.entity_alias","working.id_xref","analysis.evidence_item","analysis.factor_citation","reference.custody_factor","analysis.finding","analysis.evidence_task","analysis.legal_timeline_event","analysis.vw_court_export"]
B_tables=["working.normalized_record","working.message_projection_route","working.third_party_conversation","working.third_party_message","working.third_party_message_participant","working.chat_conversation","working.chat_message","working.chat_chunk","working.normalized_record_chunk","working.realization_event","working.realization_event_record","working.record_visible_from","working.vw_horizon_atom","working.walk_run","working.walk_step","working.walk_checkpoint"]

# merged message column proposal
merge_cols=[("id","uuid","= normalized_record.id (D2 subtype rule)"),("conversation_id","uuid","→ conversation"),("<s>projection_kind</s>","—","REJECTED by owner 2026-08-25 03:07 — the three message tables stay separate; no discriminator"),
 ("occurred_at","tstz","CLOCK 1 — event time (0059)"),("source_available_from","tstz","CLOCK 2 — real column, not a function (0059)"),("ts_precision","precision_class","from D2/spine"),("ts_earliest / ts_latest","tstz","D2 uncertainty window"),("raw_ts / tz","text","D2 as-recorded"),
 ("platform / external_id / serial_number","text/bigint","D2"),("prev_message_id / next_message_id / time_since_prev_s","uuid/int","D2 ordering"),("sender_entity_id","uuid","→ entity (address book); sender_raw / sender_e164 kept as evidence of what the source said"),("sender / recipients / participants","text · jsonb","KEPT ON THE RECORD (owner 2026-08-25 03:25). message_participant → entity is ADDED for resolution, never a replacement"),
 ("direction / message_type / delivery_status / is_blocked","text/bool","D2"),("content_sha256 / word_count / char_count / language","","D2"),("*_hint columns (sentiment, intent, topic, relevance, custody, strength) + hint_provenance","","D2 — keep, they are your analysis surface"),
 ("has_attachments / attachment_count / has_behaviors / behavior_count / max_behavior_severity","","D2 rollups"),("derived_from_raw_table / derived_from_raw_id / deriver_version / derived_at","","lineage (0009)"),
 ("platform_attrs / raw_data","jsonb","D2"),("REMOVED: ts_utc, sent_at, realized_at","","ts_utc/sent_at → occurred_at; realized_at → realization_event. Nothing from chat_message folds in (reviewers 3/3 + owner 03:07)")]
merge_rows="".join(f"<tr><td class=m>{e(a)}</td><td class=m>{e(b)}</td><td class=cm>{e(c)}</td></tr>" for a,b,c in merge_cols)
merge_table=f"<div class=scroll><table><thead><tr><th>column</th><th>type</th><th>from / why</th></tr></thead><tbody>{merge_rows}</tbody></table></div>"

delta=[("Message tables","3 (message, third_party_message, chat_message)","3 — STAY SEPARATE (owner-ruled 2026-08-25 03:07; merge rejected as \"a monstrosity\")"),("Timestamp names","ts_utc · occurred_at · sent_at","occurred_at"),("Source-availability clock","function only","column: source_available_from"),("Realization","realized_at on 5 tables + realization_event","realization_event only (plural)"),("Horizon mechanism","record_visible_from + vw_horizon_atom (rejected COALESCE)","walk gates on source_available_from + approved realizations"),("Participants on the record","participants jsonb + sender text + recipients jsonb + sender_entity_id","UNCHANGED — they stay on the record (owner-ruled 2026-08-25 03:25). message_participant → entity added alongside for resolution"),("Address book","designed (D2), never written","same tables, now the FK target"),("Court lane (D7)","present, unused","unchanged, fed by promotion (ADR-0055)"),("Tables in ai","241","≈150 (drops need your per-family sign-off)")]
delta_rows="".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td class=k>{e(c)}</td></tr>" for a,b,c in delta)

page=f"""<title>Three Message Shapes</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#F6F5F1;--ink:#1C2028;--mut:#5E6472;--line:#D9D7CF;--card:#FFFFFF;--acc:#2F55C7;--accbg:#E8EDFB;--keep:#1F7A4D;--drop:#B4382F;--code:#EEF0F4}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#14171D;--ink:#E8E6E0;--mut:#9AA0AD;--line:#2C313B;--card:#1B1F27;--acc:#7E9CF0;--accbg:#1E2740;--keep:#6FCF97;--drop:#F08A80;--code:#232833}}}}
:root[data-theme="dark"]{{--bg:#14171D;--ink:#E8E6E0;--mut:#9AA0AD;--line:#2C313B;--card:#1B1F27;--acc:#7E9CF0;--accbg:#1E2740;--keep:#6FCF97;--drop:#F08A80;--code:#232833}}
body{{background:var(--bg);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;line-height:1.5;margin:0}}
main{{max-width:1100px;margin:0 auto;padding:32px 24px}}
h1{{font-family:"IBM Plex Serif",Georgia,serif;font-weight:600;font-size:32px;margin:0 0 6px}}h2{{font-family:"IBM Plex Serif",Georgia,serif;font-weight:500;font-size:24px;margin:44px 0 6px;padding-top:20px;border-top:2px solid var(--line)}}h3{{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:22px 0 8px}}
p{{max-width:70ch}}.lead{{color:var(--mut)}}
.tag{{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:2px;margin-left:8px;vertical-align:middle}}.tag.o{{background:var(--accbg);color:var(--acc)}}.tag.r{{background:#FBE6E3;color:var(--drop)}}.tag.g{{background:#E4F3EA;color:var(--keep)}}
figure{{margin:14px 0;background:var(--card);border:1px solid var(--line);padding:12px}}figcaption{{font-size:12.5px;color:var(--mut);margin-top:8px;max-width:90ch}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:12px 0}}.fact{{background:var(--card);border:1px solid var(--line);padding:10px 12px;font-size:13px}}.fact b{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-bottom:3px}}
details.tbl{{border-top:1px solid var(--line);padding:6px 0}}summary{{cursor:pointer;list-style:none}}summary::-webkit-details-marker{{display:none}}summary::before{{content:"\\25B8 ";color:var(--mut)}}details[open]>summary::before{{content:"\\25BE "}}summary:focus-visible{{outline:2px solid var(--acc)}}
.meta{{color:var(--mut);font-size:12px}}code,.m{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12.5px}}code{{background:var(--code);padding:1px 4px}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}}th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);border-bottom:1px solid var(--line);padding:6px 8px}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.n{{text-align:right;color:var(--mut)}}td.cm{{color:var(--mut)}}td.k{{color:var(--keep);font-weight:500}}
ul{{padding-left:18px;font-size:13px}}.foot{{color:var(--mut);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:12px}}
</style>
<main>
<h1>Three Message Shapes</h1>
<p class=lead>The same evidence, three schemas. A is what you approved in June. B is what the August ADRs built. C is the target after your 2026-08-25 rulings (D-069 context-first, three message tables stay separate, participants stay on the record). <s>C is the merge I recommend.</s> <i>(struck 2026-08-25 — the merge was rejected)</i> Every column is from the live <code>ai</code> catalog on 2026-08-25; the merge columns are a proposal.</p>

<h2>How data moves, end to end <span class="tag o">target after rulings</span></h2>
<p>Five lanes top to bottom: intake and custody, parse to immutable raw, derive the spine and its projections, analyze under a knowledge horizon, conclude for court. Solid boxes exist today; the blue ones are where shape changes. Under D-069 the raw landing zone is <b>context</b>, not evidence: ingest hashes are fingerprints; custody (H1 re-verify → H2/H3 → <code>evidence.*</code>) begins only when you promote.</p>
{F_svg}
<div class=facts><div class=fact><b>Immutable</b>evidence.* — custody + PROMOTED records only (D-069). <s>raw, rejected, ingest_run</s> move to the context layer (owner 03:10); only the promotion path writes here.</div><div class=fact><b>Re-derivable</b>working.* — rebuilt from raw at any time. Wipe + re-derive is the fix path, never edit.</div><div class=fact><b>Horizon</b>The walk sees a record only when <code>source_available_from ≤ horizon_at</code>. Vector search applies the same filter before top-k.</div><div class=fact><b>Conclusions</b>analysis.* — written only after a recorded approval. Court export is a view with a three-part gate.</div></div>

<h2>A · Your June design (D2 messages + D7 court lane) <span class="tag o">owner-approved 2026-06-30</span></h2>
<p>One spine row per record. A typed <code>message</code> subtype shares the spine's id. Participants resolve through an <b>address book</b>: <code>entity</code> with <code>phone</code>, <code>handle</code>, <code>email</code>, <code>account</code>, <code>entity_alias</code>, and <code>id_xref</code> — phone number → person → name → aliases. That is the alias book you just asked for; it already exists, empty.</p>
{A_svg}
<div class=facts><div class=fact><b>Status</b>Applied to live 2026-06-30 (migration 0005). Moved analysis→working by 0014.</div><div class=fact><b>Rows</b>0 in every table.</div><div class=fact><b>Code writers</b>None. Nothing derives into <code>message</code> or <code>entity</code>.</div><div class=fact><b>Clocks</b><code>ts_utc</code> + <code>ts_earliest/ts_latest</code> + <code>temporal_confidence</code>. No source-availability clock.</div></div>
<h3>Every column</h3>{''.join(cols_table(q) for q in A_tables)}

<h2>B · ADR-0059 / ADR-0053 as built <span class="tag o">owner-ruled 2026-08-18</span></h2>
<p>The spine stays. A <code>message_projection_route</code> decides first-party vs third-party per record. Only the third-party tables were created. AI chats live in a separate <code>chat_*</code> family. Realization is a plural event table — that part matches the ruling. The two things the ruling turns on are not there: <code>source_available_from</code> is a function, not a column, and the rejected <code>visible_from</code> collapse is still what the walk reads.</p>
{B_svg}
<div class=facts><div class=fact><b>Status</b>0026–0029 applied; 0059 never got its own migration.</div><div class=fact><b>Rows</b>0 in every table except context_record (1,741, stamped SUPERSEDED).</div><div class=fact><b>Code writers</b><code>chat_*</code> (context_chat_ingest.py) and <code>walk_*</code>/<code>realization_*</code> (derivation.py, validate scripts). Nothing writes <code>third_party_message</code>.</div><div class=fact><b>Clocks</b><code>occurred_at</code> ✓ · <code>source_available_from</code> ✗ (function) · <code>realized_at</code> on 5 tables + <code>record_visible_from</code> ✗ (rejected).</div></div>
<h3>Every column</h3>{''.join(cols_table(q) for q in B_tables)}

<h2>C · Target after the 2026-08-25 rulings <span class="tag o">owner-ruled</span></h2>
<p>Keep your D2 message column set and D7 court lane. Add the two 0059 clocks as real columns on the spine and the message. <s>Fold the three message tables into one with <code>projection_kind</code>.</s> <b>REJECTED 03:07</b> — the three message tables stay separate, each with its own participant contract. Sender, recipients and participants <b>stay on the record itself</b> (owner 03:25); Keep realization plural. Point the walk at <code>source_available_from</code>. make the D2 address book an <i>additional</i> FK target via <code>message_participant</code> — resolution on top of the record, never in place of it.</p>
{C_svg}
<h3>What changes</h3>
<div class=scroll><table><thead><tr><th>dimension</th><th>now</th><th>after merge</th></tr></thead><tbody>{delta_rows}</tbody></table></div>
<h3>Proposed <code>working.message</code> columns</h3>{merge_table}
<h3>Proposed <code>working.normalized_record</code> trim <span class="tag r">DEFERRED by reviewers — do last, one column family per migration</span></h3>
<ul><li><b>Keep:</b> id, artifact_id, record_type, source, conversation_ref, content, <b>occurred_at</b>, <b>source_available_from</b>, ts_precision, disclosure_tier, sensitivity_tier, data_tier, review_status, safe_for_legal_use, acquisition_id, device_id, derived_from_raw_table/id, deriver_version, derived_at, case_id, source_record_key, source_content_sha256, attrs.</li>
<li><b>Remove:</b> knowledge_time (audit only → ops.audit_ledger), realized_at + realized_evidence (→ realization_event), <s>participants/sender/recipients/sender_entity_id (→ message_participant)</s> <b>KEPT</b> (owner 2026-08-25 03:25 — they stay on the record), export_created_at/acquired_at/ingested_at (→ evidence.acquisition / ingest_run), domain/topic_tags/knowledge_actor/ontology_version (→ chunk classification, ADR-0053), message_corpus, attestation_count (computed view).</li></ul>
<h3>Not decided by this page</h3>
<ul><li><s>Whether <code>chat_message</code> (AI chats) folds into <code>message</code>.</s> Decided 2026-08-25: stays a sibling (reviewers 3/3, owner 03:07).</li><li>The 60 review tables and the 54 drop-family tables — separate sign-off, family by family.</li><li><code>ai_test_ingest</code> and <code>traceiq</code>.</li></ul>

<p class=foot>Byline: Claude Code · Fable 5 · 2026-08-25 (re-based 03:30 on owner rulings D-069 / separate tables / participants-stay). Sources: live pg_catalog; docs/planning/forensic-db-reconciliation/domains/D2, D7; docs/adr/0053, 0055, 0059; sql/0014, 0021, 0024, 0026–0029.</p>
</main>
"""
Path(sys.argv[2]).write_text(page,encoding="utf-8"); print("bytes",len(page))
