import json,sys,html
from pathlib import Path
S=Path(sys.argv[1]); cat=json.loads((S/"catalog.json").read_text(encoding="utf-8"))
CODE_REF=set("""evidence.evidence_hash evidence.source evidence.acquisition evidence.file_node evidence.custody_event evidence.artifact_metadata evidence.ingest_run evidence.raw_rejected evidence.raw_sms evidence.vw_layer_map evidence.vw_reconciliation evidence.vw_pipeline_funnel evidence.vw_ingest_history evidence.vw_dropped_records evidence.vw_artifacts_without_claim evidence.vw_raw_all
working.normalized_record working.normalized_record_chunk working.walk_run working.walk_step working.walk_step_retrieval working.walk_step_realization_retrieval working.walk_checkpoint working.record_visible_from working.realization_event working.realization_event_record working.event_source_record working.third_party_conversation working.third_party_conversation_acquisition working.third_party_message working.third_party_message_participant working.message_projection_route working.message working.message_participant working.conversation working.chat_conversation working.chat_message working.chat_chunk working.chat_chunk_message working.chat_chunk_lane working.chat_chunk_embedding working.chat_chunk_projection working.context_archive working.context_asset working.context_asset_message working.context_asset_derivation working.extraction_run working.candidate_entity working.candidate_fact working.candidate_event working.entity working.entity_alias working.person working.evidence_vector_projection_job working.vw_horizon_atom working.vw_walk_contamination working.vw_walk_base_version_input working.vw_spine_horizon working.vw_record_attestations working.vw_derivation_lineage
analysis.matter analysis.court_case analysis.matter_knowledge_partition analysis.evidence_item analysis.knowledge_evidence_promotion analysis.review_task analysis.review_decision analysis.corroboration_flag analysis.pattern_finding analysis.chunk_classification analysis.human_label analysis.vw_court_export
ops.workflow_run ops.workflow_run_stage ops.workflow_run_review_action ops.processing_run ops.audit_ledger
reference.detection_pattern reference.detection_pattern_set reference.behavior_category""".split())
LAYERMAP=set("""evidence.raw_imessage evidence.raw_facebook evidence.raw_ai_chat evidence.raw_csv evidence.raw_phone working.attachment working.call_log working.device working.extraction_candidate working.record_observation reference.behavior_category_mcl reference.pattern_lexicon reference.custody_factor reference.topic_code analysis.finding analysis.timeline_event analysis.human_label_gold""".split())
DROP={
"public-memory":("D8 'provenance-memory' agent tables + 0002 legacy HITL tables","Created 2026-07-03 by the forensic-db reconciliation (domain D8) and 0002. Nothing in server/, workbench/, or scripts/ reads or writes any of them. agent_run/approval_request were superseded by agno_approvals (0002 header says so).",
 "public.agent_run public.approval_request public.transcript_insight public.canon_registry public.memory_items public.session_summaries public.prompt_registry public.decision_log public.decision_precedent public.open_questions public.change_log public.model_version public.ontology_version public.classification_version public.schema_version public.app_setting".split()),
"geo":("Geo / GPS / Google-Timeline family (domain D5)","Owner ruling D-044 + ADR-0048 PARKED the Google Timeline family as one unit. These tables predate that ruling, have zero code references and zero rows. The real geo work lives in the separate traceiq database.",
 "evidence.gps_point evidence.raw_activity evidence.raw_trip evidence.raw_visit evidence.raw_path working.stay_point working.gps_track working.geocode_request working.geocode_resolution working.geocode_result working.home_base working.waypoint_device_split working.location working.vehicle reference.geofence ops.geocode_audit".split()),
"legal":("Legal-tasks / export / assertion family (domains D7 + D3)","Discovery-request, task, export-package and assertion tables from the July reconciliation. Zero rows, zero code references. analysis.finding/timeline_event are on the layer map and are kept.",
 "analysis.discovery_request analysis.discovery_request_revision analysis.evidence_task analysis.task_dependency analysis.task_event analysis.task_legal_link analysis.task_person analysis.task_revision analysis.export analysis.export_item analysis.export_package analysis.factor_citation analysis.finding_version analysis.location_assertion analysis.time_assertion analysis.location_contradiction analysis.legal_timeline_event analysis.relational_classification analysis.completion_evidence analysis.resolution_evidence analysis.redaction analysis.score".split()),
}
SYS=set("public.spatial_ref_sys public.geography_columns public.geometry_columns public.pg_stat_statements public.pg_stat_statements_info duckdb.extensions duckdb.tables".split())
dropmap={t:k for k,(_,_,ts) in DROP.items() for t in ts}
def verdict(d):
    q=f"{d['schema']}.{d['table']}"
    if q in dropmap: return "drop",DROP[dropmap[q]][0]
    if q in CODE_REF: return "keep","Read or written by platform code (server/, workbench/, scripts/)."
    if q in LAYERMAP: return "keep","Listed on evidence.vw_layer_map, the designed layer inventory."
    if q in SYS: return "keep","Owned by a Postgres extension (PostGIS / pg_stat_statements / pg_duckdb), not ours."
    if d["schema"]=="ai" and (d["table"].startswith("agno_") or d["table"]=="api_keys"): return "keep","Agno runtime table (sessions, traces, approvals). Created and owned by agno."
    if d["schema"]=="ai" and d["table"].endswith("_contents"): return "keep","Agno Knowledge contents ledger for an ADR-0050 lane; its Weaviate twin collection exists live (verified 2026-08-25). Corrected from drop after owner question."
    return "review","No code reference, not on the layer map, not in a named drop family. Needs your ruling."
ai=cat["ai"]
for d in ai: d["verdict"],d["reason"]=verdict(d)
from collections import Counter,defaultdict
vc=Counter(d["verdict"] for d in ai)
by=defaultdict(list)
for d in ai: by[d["schema"]].append(d)
e=html.escape
def col_rows(d):
    r=[]
    for i,c in enumerate(d["columns"],1):
        r.append(f"<tr><td class=n>{i}</td><td class=m>{e(c['name'])}</td><td class=m>{e(c['type'])}</td><td>{'NOT NULL' if c['notnull'] else ''}</td><td class=m>{e(c['default'] or '')}</td><td class=cm>{e(c['comment'] or '')}</td></tr>")
    return "".join(r)
AFTER={"keep":"Unchanged.","drop":"Schema + rows dumped to <code>_stale/schema-audit-2026-08-25/</code> first (never-delete), then the table is removed. Reversible from the dump.","review":"Nothing until you rule: keep, drop, or merge."}
def table_block(d):
    q=f"{d['schema']}.{d['table']}"; v=d["verdict"]
    cons="".join(f"<li><b>{e(c['type'])}</b> <code>{e(c['name'])}</code> - <code>{e(c['def'])}</code></li>" for c in d["constraints"])
    inb=", ".join(f"<code>{e(x)}</code>" for x in d["inbound_fk"])
    idx=", ".join(f"<code>{e(x)}</code>" for x in d["indexes"])
    rows="-" if d["rows"] is None else f"{d['rows']:,}"
    vd=f"<details class=vd><summary>view definition</summary><pre>{e(d.get('viewdef',''))}</pre></details>" if d.get("viewdef") else ""
    return f"""<details class="tbl {v}" id="{e(q)}"><summary><span class="chip {v}">{v}</span><code class="tn">{e(q)}</code><span class="meta">{e(d['kind'])} &middot; {len(d['columns'])} cols &middot; {rows} rows</span></summary>
<div class="body">
<div class="ba"><div><h5>Now</h5><p>{e(d['comment'] or 'No table comment.')}</p></div><div><h5>Why</h5><p>{e(d['reason'])}</p></div><div><h5>After</h5><p>{AFTER[v]}</p></div></div>
<div class="scroll"><table><thead><tr><th>#</th><th>column</th><th>type</th><th>null</th><th>default</th><th>comment</th></tr></thead><tbody>{col_rows(d)}</tbody></table></div>
{('<h5>Constraints</h5><ul>'+cons+'</ul>') if cons else ''}
{('<p><b>Referenced by (FK):</b> '+inb+'</p>') if inb else ''}
{('<p><b>Indexes:</b> '+idx+'</p>') if idx else ''}
{vd}
</div></details>"""
schema_desc={"ai":"Agno runtime (sessions, traces, approvals, knowledge contents).","analysis":"Conclusions: findings, labels, review decisions, matters.","duckdb":"pg_duckdb extension bookkeeping.","evidence":"Raw evidence + custody ledgers. Append-only.","ops":"Run ledgers, audit ledger, tool-call log. Prunable.","public":"Postgres default schema. Should hold only extension objects.","reference":"Hand-curated taxonomy (detection patterns, behaviour categories).","working":"Derived working set: spine, projections, walks, chat chunks, candidates."}
order={'drop':0,'review':1,'keep':2}
schema_sections=[]
for s in sorted(by):
    ds=by[s]; c=Counter(d["verdict"] for d in ds)
    schema_sections.append(f"""<section class=schema id="s-{s}"><details open><summary><h3>{s}</h3><span class=meta>{len(ds)} relations &middot; <span class=k>{c['keep']} keep</span> &middot; <span class=r>{c['drop']} drop</span> &middot; <span class=w>{c['review']} review</span></span></summary>
<p class=sd>{e(schema_desc.get(s,''))}</p>
{''.join(table_block(d) for d in sorted(ds,key=lambda d:(order[d['verdict']],d['table'])))}
</details></section>""")
def dbsum(name,rels,note,after):
    c=Counter(r["schema"] for r in rels); rows=sum(r["rows"] or 0 for r in rels)
    lst="".join(f"<tr><td class=m>{e(r['schema'])}.{e(r['table'])}</td><td>{e(r['kind'])}</td><td class=n>{'' if r['rows'] is None else format(r['rows'],',')}</td></tr>" for r in sorted(rels,key=lambda r:(-(r['rows'] or 0),r['schema'],r['table'])))
    return f"""<section class=schema><details><summary><h3>{name}</h3><span class=meta>{len(rels)} relations &middot; {rows:,} rows &middot; schemas: {', '.join(sorted(c))}</span></summary>
<div class=ba><div><h5>Now</h5><p>{note}</p></div><div><h5>After</h5><p>{after}</p></div></div>
<div class=scroll><table><thead><tr><th>relation</th><th>kind</th><th>rows</th></tr></thead><tbody>{lst}</tbody></table></div></details></section>"""
droplist="".join(f"<li><b>{e(t)}</b> - {e(w)} <span class=meta>({len(ts)} tables)</span></li>" for k,(t,w,ts) in DROP.items())
empties=sum(1 for d in ai if d['rows']==0)
page=f"""<title>ai Schema Reckoning</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#F6F5F1;--ink:#1C2028;--mut:#5E6472;--line:#D9D7CF;--card:#FFFFFF;--acc:#2F55C7;--keep:#1F7A4D;--keepbg:#E4F3EA;--drop:#B4382F;--dropbg:#FBE6E3;--rev:#A66A0E;--revbg:#FBEFD6;--code:#EEF0F4}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#14171D;--ink:#E8E6E0;--mut:#9AA0AD;--line:#2C313B;--card:#1B1F27;--acc:#7E9CF0;--keep:#6FCF97;--keepbg:#173224;--drop:#F08A80;--dropbg:#3A1D1A;--rev:#E7B25C;--revbg:#3A2C12;--code:#232833}}}}
:root[data-theme="dark"]{{--bg:#14171D;--ink:#E8E6E0;--mut:#9AA0AD;--line:#2C313B;--card:#1B1F27;--acc:#7E9CF0;--keep:#6FCF97;--keepbg:#173224;--drop:#F08A80;--dropbg:#3A1D1A;--rev:#E7B25C;--revbg:#3A2C12;--code:#232833}}
body{{background:var(--bg);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;line-height:1.5;margin:0}}
.wrap{{display:grid;grid-template-columns:220px minmax(0,1fr);gap:32px;max-width:1280px;margin:0 auto;padding:32px 24px}}
@media(max-width:900px){{.wrap{{grid-template-columns:1fr}}nav{{position:static}}}}
nav{{position:sticky;top:16px;align-self:start;font-size:13px}}nav a{{display:block;color:var(--mut);text-decoration:none;padding:3px 0}}nav a:hover,nav a:focus{{color:var(--acc)}}nav .h{{font-weight:600;color:var(--ink);margin:12px 0 4px;text-transform:uppercase;letter-spacing:.06em;font-size:11px}}
h1{{font-family:"IBM Plex Serif",Georgia,serif;font-weight:600;font-size:34px;margin:0 0 6px;text-wrap:balance}}h2{{font-family:"IBM Plex Serif",Georgia,serif;font-weight:500;font-size:22px;margin:40px 0 12px}}h3{{font-family:"IBM Plex Serif",Georgia,serif;font-weight:500;font-size:19px;margin:0;display:inline}}
h5{{margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}}
.lead{{color:var(--mut);max-width:68ch;margin:0 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}}.kpi{{background:var(--card);border:1px solid var(--line);padding:12px 14px}}.kpi b{{font-size:26px;font-variant-numeric:tabular-nums;display:block}}.kpi span{{font-size:12px;color:var(--mut)}}
.kpi.keep b{{color:var(--keep)}}.kpi.drop b{{color:var(--drop)}}.kpi.review b{{color:var(--rev)}}
section.schema{{background:var(--card);border:1px solid var(--line);margin:14px 0;padding:14px 18px}}
summary{{cursor:pointer;list-style:none;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}summary::-webkit-details-marker{{display:none}}summary::before{{content:"\\25B8";color:var(--mut);font-size:12px}}details[open]>summary::before{{content:"\\25BE"}}summary:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}
.meta{{color:var(--mut);font-size:12px;font-variant-numeric:tabular-nums}}.k{{color:var(--keep)}}.r{{color:var(--drop)}}.w{{color:var(--rev)}}
.sd{{color:var(--mut);font-size:13px;margin:6px 0 10px 22px}}
details.tbl{{border-top:1px solid var(--line);padding:8px 0 8px 22px}}details.tbl>summary{{padding:4px 0}}
.chip{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;padding:2px 8px;border-radius:2px}}.chip.keep{{background:var(--keepbg);color:var(--keep)}}.chip.drop{{background:var(--dropbg);color:var(--drop)}}.chip.review{{background:var(--revbg);color:var(--rev)}}
code,.m,pre{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12.5px}}code{{background:var(--code);padding:1px 4px}}.tn{{font-size:13.5px;font-weight:500}}
.body{{padding:10px 0 4px}}.ba{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:8px 0 14px;font-size:13.5px}}.ba p{{margin:0}}@media(max-width:900px){{.ba{{grid-template-columns:1fr}}}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12.5px}}th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);border-bottom:1px solid var(--line);padding:6px 8px}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.n{{text-align:right;color:var(--mut);font-variant-numeric:tabular-nums}}td.cm{{color:var(--mut);max-width:38ch}}
ul{{padding-left:18px;font-size:13px}}pre{{white-space:pre-wrap;background:var(--code);padding:10px;overflow-x:auto}}.vd summary{{font-size:12px;color:var(--mut)}}
.ctl{{display:flex;gap:8px;margin:10px 0 4px;flex-wrap:wrap}}.ctl button{{font:inherit;font-size:12px;padding:4px 10px;background:var(--card);border:1px solid var(--line);color:var(--ink);cursor:pointer}}.ctl button:focus-visible{{outline:2px solid var(--acc)}}
.plan li{{margin:6px 0}}.foot{{color:var(--mut);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:12px}}
</style>
<div class=wrap>
<nav><div class=h>This page</div><a href="#now">Now vs. proposed</a><a href="#families">What gets dropped</a><a href="#ai">Database ai</a>
<div class=h>Schemas in ai</div>{''.join(f'<a href="#s-{s}">{s} <span class=meta>({len(by[s])})</span></a>' for s in sorted(by))}
<div class=h>Other databases</div><a href="#others">ai_test_ingest &middot; traceiq</a><a href="#offlimits">casebible (not touched)</a></nav>
<main>
<h1>ai Schema Reckoning</h1>
<p class=lead>Every relation in the live <code>ai</code> database on <code>100.91.190.107</code> (PostgreSQL 18.1), read from <code>pg_catalog</code> on 2026-08-25, with a verdict per table and every column shown. Nothing here has been executed.</p>
<h2 id=now>Now vs. proposed</h2>
<div class=kpis><div class=kpi><b>{len(ai)}</b><span>relations in ai now</span></div><div class="kpi keep"><b>{vc['keep']}</b><span>keep</span></div><div class="kpi drop"><b>{vc['drop']}</b><span>drop (0 rows, 0 code refs)</span></div><div class="kpi review"><b>{vc['review']}</b><span>need your ruling</span></div><div class=kpi><b>{len(ai)-vc['drop']}</b><span>relations after, if all drops approved</span></div></div>
<div class=ba><div><h5>Now</h5><p>7 databases on the host. <code>ai</code> carries {len(ai)} relations across 8 schemas; {empties} tables are empty. The same curated rows (labels, detection vocabulary, context_record, 445 test SMS) exist again in <code>ai_test_ingest</code> and <code>casebible</code>. <code>sql/bootstrap/schema_baseline.sql</code> is a pg_dump of whatever is live, so every stray table gets re-blessed on the next capture.</p></div>
<div><h5>How verdicts were made</h5><p><b>keep</b> = referenced by platform code, on <code>evidence.vw_layer_map</code>, an Agno runtime table, or extension-owned. <b>drop</b> = in one of three named families below: zero rows, zero code references, and a design source that was superseded. <b>review</b> = none of the above; I won't guess.</p></div>
<div><h5>After</h5><p><code>ai</code> stays the one platform database. Drops are dumped to <code>_stale/</code> first (never-delete). <code>ai_test_ingest</code> is dumped and removed. A table allow-list test replaces the circular baseline so this cannot regrow. <code>casebible</code> and <code>traceiq</code> are untouched.</p></div></div>
<h2 id=families>What gets dropped, and why</h2><ul class=plan>{droplist}</ul>
<h2 id=ai>Database <code>ai</code> - every relation</h2>
<div class=ctl><button onclick="document.querySelectorAll('details.tbl').forEach(d=>d.open=true)">Expand all tables</button><button onclick="document.querySelectorAll('details.tbl').forEach(d=>d.open=false)">Collapse all</button><button onclick="document.querySelectorAll('details.tbl').forEach(d=>d.open=d.classList.contains('drop'))">Open only drops</button><button onclick="document.querySelectorAll('details.tbl').forEach(d=>d.open=d.classList.contains('review'))">Open only reviews</button></div>
{''.join(schema_sections)}
<h2 id=others>Other databases on the same host</h2>
{dbsum("ai_test_ingest",cat["ai_test_ingest"],"Schema-only clone of ai made 2026-08-02 by scripts/make_test_db.py, later loaded with 445 test SMS. Stamped 'old-shape test corpus, frozen' on 2026-08-24. A full parallel copy of the platform schema.","pg_dump (schema + data) to _stale/, then the database is removed. Its 445 rows already exist in casebible as hash-verified copies.")}
{dbsum("traceiq",cat["traceiq"],"A separate geo/Timeline project (139k geo rows, 20k raw records) sharing the host. Not mentioned in any canon doc.","Left as-is. Needs one line in docs/PROJECT_CANON.md saying it exists and who owns it - or your instruction to dump and remove.")}
<section class=schema id=offlimits><details><summary><h3>casebible</h3><span class=meta>owner ruling 2026-08-25: not this lane</span></summary><p class=sd>Not inspected beyond a row count and not touched. Anything that would have pointed at it is out of this plan.</p></details></section>
<p class=foot>Byline: Claude Code &middot; Fable 5 &middot; 2026-08-25. Source of truth for verdicts: pg_catalog (live), <code>evidence.vw_layer_map</code>, a ripgrep census of server/ workbench/api scripts/ tests/, ADR-0048, D-044, sql/0002, docs/planning/forensic-db-reconciliation/domains/D3,D5,D7,D8.</p>
</main></div>
"""
Path(sys.argv[2]).write_text(page,encoding="utf-8")
print("verdicts:",dict(vc),"bytes:",len(page))
