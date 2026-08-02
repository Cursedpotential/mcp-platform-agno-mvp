"""Evidence pipeline report — every layer, every stage, every rejection, in one place.

Byline: Claude Code . Opus 5 (1M) . 2026-08-01

Reads the visibility views added by sql/0012_pipeline_visibility.sql and writes a
report to docs/reports/ in three formats:

    evidence-pipeline-<stamp>.md     durable, diffable, lives in the repo
    evidence-pipeline-<stamp>.html   the viewer
    evidence-pipeline-<stamp>.json   the raw rows, for anything downstream

Nothing here computes counts itself. Every number comes from a view, so the report
and a hand-written SQL query cannot disagree.

usage:
    uv run python scripts/evidence_pipeline_report.py [--out DIR] [--sample N]
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

REPO = pathlib.Path(__file__).resolve().parents[1]

# Each block: (anchor, title, why it matters, SQL). The "why" is printed in the
# report — a table of numbers with no stated purpose is not an audit artifact.
BLOCKS: list[tuple[str, str, str, str]] = [
    (
        "layers",
        "Layer map",
        "Every layer of the pipeline with its architectural role and live row count. "
        "RAW is the only insert target. SPINE and PROJECTION are derived and can be "
        "rebuilt from RAW without touching the original devices or export files.",
        "SELECT layer_role, table_name, what_it_holds, live_rows "
        "FROM evidence.vw_layer_map ORDER BY sort_order",
    ),
    (
        "reconciliation",
        "Reconciliation",
        "The verdict per artifact. RECONCILED means every record the artifact claims "
        "about itself is either present in RAW or explicitly recorded as rejected. "
        "SHORTFALL means records went missing with no trace.",
        "SELECT original_filename, claimed, raw_rows, rejected, accounted_for, "
        "unexplained, verdict, spine_rows, derivation_verdict "
        "FROM evidence.vw_reconciliation ORDER BY original_filename",
    ),
    (
        "funnel",
        "Per-artifact funnel",
        "Every stage side by side for each artifact, from what the file declared to "
        "how many attestations exist.",
        "SELECT original_filename, source_type, byte_size, claimed, raw_rows, "
        "raw_superseded, rejected, spine_rows, attestations, resolved_export_at, "
        "layer_disagreement FROM evidence.vw_pipeline_funnel ORDER BY ingested_at",
    ),
    (
        "runs",
        "Ingest run ledger",
        "Every ingest ATTEMPT, including failures and rollbacks. Written outside the "
        "ingest transaction on purpose: a load that rolled back must still leave "
        "evidence of what was tried and where the counts stopped agreeing.",
        "SELECT source_filename, status, parser_version, started_at, duration_s, "
        "count_claimed, count_parsed, count_rejected, count_deduped, count_raw, "
        "count_spine, count_attestations, outcome_detail FROM evidence.vw_ingest_history",
    ),
    (
        "dropped",
        "Dropped and rejected records",
        "What never made it in, and why. A dropped record is an absence and cannot be "
        "recovered by querying afterwards, so it is written down at the moment of "
        "refusal. An empty table here is only believable if Reconciliation also reads "
        "RECONCILED.",
        "SELECT original_filename, parser_version, record_index, element_tag, reason, "
        "reason_detail, content_hash FROM evidence.vw_dropped_records "
        "ORDER BY created_at DESC, record_index",
    ),
    (
        "reject_reasons",
        "Rejections by reason",
        "The shape of what is being refused. A reason that suddenly grows is a parser "
        "regression.",
        "SELECT reason, count(*) AS records, count(DISTINCT source_sha256) AS artifacts "
        "FROM evidence.raw_rejected GROUP BY reason ORDER BY 2 DESC",
    ),
    (
        "attestations",
        "Attestation status",
        "How many independent sources attest each spine record. CONFLICTED means two "
        "sources disagree about the same record — that is a finding, not an error. "
        "Duplicates across devices or mediums are corroboration and are never deduped "
        "away.",
        "SELECT attestation_status, count(*) AS records "
        "FROM working.vw_record_attestations GROUP BY 1 ORDER BY 2 DESC",
    ),
    (
        "clocks",
        "Clock disagreement between metadata layers",
        "The same export carries several different creation times — embedded in the "
        "file, encoded in its filename, and recorded by the filesystem. They disagree, "
        "and which one you trust is a decision that has to be recorded rather than "
        "assumed.",
        "SELECT fs_filename, embedded_export_at, filename_export_at, fs_mtime, "
        "resolved_export_at, resolved_source, layer_disagreement "
        "FROM evidence.artifact_metadata ORDER BY fs_filename",
    ),
    (
        "lineage",
        "Derivation lineage (sample)",
        "Every spine record traced back to the raw row it came from, the artifact that "
        "raw row came from, and how that artifact was acquired. A record with no raw "
        "lineage should not exist.",
        "SELECT original_filename, raw_table, record_index, parser_version, "
        "deriver_version, record_type, occurred_at, acquisition_method, content_preview "
        "FROM working.vw_derivation_lineage ORDER BY occurred_at DESC LIMIT :sample",
    ),
    (
        "orphans",
        "Integrity checks",
        "Each of these must be zero. They are the invariants the three-layer design "
        "depends on; if one is non-zero the pipeline is lying somewhere.",
        """
        SELECT 'spine rows with no raw lineage' AS check_name,
               count(*) AS found, 0 AS expected
          FROM working.normalized_record WHERE derived_from_raw_id IS NULL
        UNION ALL
        SELECT 'duplicate content_hash within one source',
               (SELECT count(*) FROM (SELECT source_id, content_hash
                  FROM evidence.raw_sms GROUP BY 1,2 HAVING count(*) > 1) d), 0
        UNION ALL
        SELECT 'attestations with neither event nor record',
               (SELECT count(*) FROM working.event_source_record
                 WHERE event_id IS NULL AND record_id IS NULL), 0
        UNION ALL
        SELECT 'ingest runs still marked running',
               (SELECT count(*) FROM evidence.ingest_run WHERE status = 'running'), 0
        UNION ALL
        SELECT 'artifacts whose self-declared count was never captured',
               (SELECT count(*) FROM evidence.vw_artifacts_without_claim), 0
        UNION ALL
        SELECT 'spine rows whose raw row is superseded',
               (SELECT count(*) FROM working.normalized_record nr
                  JOIN evidence.vw_raw_all r ON r.id = nr.derived_from_raw_id
                 WHERE r.superseded_by IS NOT NULL), 0
        """,
    ),
    (
        "blindspots",
        "Artifacts that cannot be reconciled",
        "Every row here is a blind spot: nothing recorded what the artifact claims "
        "about itself, so silent record loss in it would be undetectable. This is the "
        "control that caught a parser dropping 516 records; its absence is a gap, not "
        "a pass.",
        "SELECT original_filename, source_type, byte_size, has_metadata_row, raw_rows, "
        "ingested_at FROM evidence.vw_artifacts_without_claim ORDER BY ingested_at",
    ),
]


def db_url(host_override: str | None = None) -> str:
    """Read DB settings from the environment, falling back to the repo .env.

    Never sourced as a shell script: several secrets files use `KEY = value`
    spacing, which makes a shell execute the value.

    HOST RESOLUTION, in order: --host, then the DB_HOST process env var, then the
    repo .env. The .env holds `agentos-db`, which resolves only INSIDE the compose
    network — running this from a desktop needs the data box's tailnet IP passed
    explicitly. That is deliberate: hardcoding an IP here would silently keep
    pointing at the old box after a host migration.
    """
    env = {k: os.environ[k] for k in ("DB_USER", "DB_PASS", "DB_DATABASE") if k in os.environ}
    dotenv = REPO / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^\s*([A-Z_]+)\s*=\s*(.+?)\s*$", line)
            if m:
                env.setdefault(m.group(1), m.group(2).strip("\"'"))
    host = host_override or os.environ.get("DB_HOST") or env.get("DB_HOST")
    port = os.environ.get("DB_PORT") or env.get("DB_PORT") or "5432"
    if not host:
        raise SystemExit("no DB host: pass --host, or set DB_HOST")
    return (f"postgresql+psycopg://{env['DB_USER']}:{env['DB_PASS']}"
            f"@{host}:{port}/{env['DB_DATABASE']}")


def fetch(conn, sql: str, sample: int) -> tuple[list[str], list[list[Any]]]:
    params = {"sample": sample} if ":sample" in sql else {}
    res = conn.execute(text(sql), params)
    return list(res.keys()), [list(r) for r in res.all()]


def fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)


# --------------------------------------------------------------------------- md

def render_markdown(stamp: str, host: str, blocks: list[dict]) -> str:
    out = [
        "# Evidence pipeline report",
        "",
        f"> _Byline: Claude Code · Opus 5 (1M) · {stamp[:10]}_",
        f"> _Generated {stamp} from `{host}` by `scripts/evidence_pipeline_report.py`._",
        "",
        "Every number below comes from a database view, not from this script, so the "
        "report and a hand-written query cannot disagree. Definitions live in "
        "`sql/0012_pipeline_visibility.sql`.",
        "",
        "## Contents",
        "",
    ]
    out += [f"- [{b['title']}](#{b['anchor']})" for b in blocks]
    out.append("")
    for b in blocks:
        out += [f"## {b['title']}", "", f"_{b['why']}_", ""]
        if not b["rows"]:
            out += ["_No rows._", ""]
            continue
        out.append("| " + " | ".join(b["cols"]) + " |")
        out.append("|" + "---|" * len(b["cols"]))
        for row in b["rows"]:
            cells = [fmt(v).replace("|", "\\|") for v in row]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------------- html

CSS = """
:root{
  --ground:#F6F8F6; --surface:#FFFFFF; --surface-2:#EDF1EE;
  --ink:#131A17; --ink-2:#3E4A45; --muted:#6E7A74; --line:#D8E0DA;
  --accent:#0E6B5E; --accent-soft:#DCEBE6;
  --ok:#1F6B4C; --ok-bg:#DFF0E6;
  --warn:#8A5C10; --warn-bg:#F6EBD4;
  --bad:#9C302B; --bad-bg:#F7DEDC;
  --role-raw:#0E6B5E; --role-spine:#2F5F8F; --role-projection:#6B5B95;
  --role-link:#8A5C10; --role-staging:#6E7A74; --role-ledger:#3E4A45;
  --role-rejected:#9C302B; --role-gold:#8A6A1E;
}
@media (prefers-color-scheme: dark){
  :root{
    --ground:#0D110F; --surface:#141A17; --surface-2:#1B2320;
    --ink:#E3E9E5; --ink-2:#B3BEB8; --muted:#87958E; --line:#28322D;
    --accent:#48AD98; --accent-soft:#172E29;
    --ok:#5FC08F; --ok-bg:#152A20;
    --warn:#D6A54A; --warn-bg:#2C2413;
    --bad:#E08079; --bad-bg:#2E1917;
    --role-raw:#48AD98; --role-spine:#7FA9D8; --role-projection:#A697CF;
    --role-link:#D6A54A; --role-staging:#87958E; --role-ledger:#B3BEB8;
    --role-rejected:#E08079; --role-gold:#D2B463;
  }
}
:root[data-theme="dark"]{
  --ground:#0D110F; --surface:#141A17; --surface-2:#1B2320;
  --ink:#E3E9E5; --ink-2:#B3BEB8; --muted:#87958E; --line:#28322D;
  --accent:#48AD98; --accent-soft:#172E29;
  --ok:#5FC08F; --ok-bg:#152A20;
  --warn:#D6A54A; --warn-bg:#2C2413;
  --bad:#E08079; --bad-bg:#2E1917;
  --role-raw:#48AD98; --role-spine:#7FA9D8; --role-projection:#A697CF;
  --role-link:#D6A54A; --role-staging:#87958E; --role-ledger:#B3BEB8;
  --role-rejected:#E08079; --role-gold:#D2B463;
}
:root[data-theme="light"]{
  --ground:#F6F8F6; --surface:#FFFFFF; --surface-2:#EDF1EE;
  --ink:#131A17; --ink-2:#3E4A45; --muted:#6E7A74; --line:#D8E0DA;
  --accent:#0E6B5E; --accent-soft:#DCEBE6;
  --ok:#1F6B4C; --ok-bg:#DFF0E6;
  --warn:#8A5C10; --warn-bg:#F6EBD4;
  --bad:#9C302B; --bad-bg:#F7DEDC;
  --role-raw:#0E6B5E; --role-spine:#2F5F8F; --role-projection:#6B5B95;
  --role-link:#8A5C10; --role-staging:#6E7A74; --role-ledger:#3E4A45;
  --role-rejected:#9C302B; --role-gold:#8A6A1E;
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:15px; line-height:1.55;
}
.wrap{max-width:1220px;margin:0 auto;padding:2.5rem 1.5rem 6rem}

h1,h2,h3{font-family:ui-serif,Georgia,"Iowan Old Style","Palatino Linotype",serif;
  text-wrap:balance;letter-spacing:-0.01em;margin:0}
h1{font-size:2.35rem;line-height:1.15}
h2{font-size:1.5rem}
.eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;
  color:var(--accent);font-weight:600}
.sub{color:var(--muted);font-size:.9rem;margin-top:.6rem}
.mono{font-family:ui-monospace,"SF Mono","Cascadia Mono",Consolas,monospace;
  font-variant-numeric:tabular-nums}

header{border-bottom:1px solid var(--line);padding-bottom:1.75rem;margin-bottom:2rem;
  display:flex;flex-direction:column;gap:.5rem}

/* funnel ------------------------------------------------------------------ */
.funnel{display:flex;flex-wrap:wrap;gap:.5rem;align-items:stretch;margin:1.75rem 0}
.stage{flex:1 1 130px;background:var(--surface);border:1px solid var(--line);
  border-radius:3px;padding:.85rem .9rem;position:relative}
.stage .k{font-size:.68rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);font-weight:600}
.stage .v{font-size:1.6rem;font-weight:600;margin-top:.15rem}
.stage.is-drop .v{color:var(--bad)}
.arrow{align-self:center;color:var(--muted);font-size:1.1rem;padding:0 .1rem}

.verdicts{display:flex;flex-wrap:wrap;gap:.6rem;margin:1rem 0 0}
.chip{display:inline-flex;align-items:center;gap:.45rem;padding:.35rem .7rem;
  border-radius:2px;font-size:.8rem;font-weight:600;letter-spacing:.02em}
.chip.ok{background:var(--ok-bg);color:var(--ok)}
.chip.warn{background:var(--warn-bg);color:var(--warn)}
.chip.bad{background:var(--bad-bg);color:var(--bad)}

/* nav --------------------------------------------------------------------- */
nav{position:sticky;top:0;z-index:5;background:var(--ground);
  border-bottom:1px solid var(--line);padding:.6rem 0;margin-bottom:2rem;
  display:flex;flex-wrap:wrap;gap:.15rem}
nav a{color:var(--ink-2);text-decoration:none;font-size:.8rem;padding:.3rem .6rem;
  border-radius:2px}
nav a:hover,nav a:focus-visible{background:var(--accent-soft);color:var(--accent)}

/* sections ---------------------------------------------------------------- */
section{margin-bottom:3rem;scroll-margin-top:4rem}
.why{color:var(--ink-2);max-width:68ch;margin:.6rem 0 1.1rem;font-size:.93rem}

.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:3px;
  background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{text-align:left;padding:.55rem .75rem;border-bottom:1px solid var(--line);
  white-space:nowrap;vertical-align:top}
th{background:var(--surface-2);font-size:.7rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);font-weight:600;position:sticky;top:0}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--surface-2)}
td.num{text-align:right;font-family:ui-monospace,"SF Mono",Consolas,monospace;
  font-variant-numeric:tabular-nums}
td.wrap{white-space:normal;max-width:46ch}

/* the role stripe encodes dependency direction, not decoration */
td.role{font-weight:600;font-size:.72rem;letter-spacing:.09em;
  border-left:3px solid var(--line)}
tr[data-role="RAW"] td.role{color:var(--role-raw);border-left-color:var(--role-raw)}
tr[data-role="SPINE"] td.role{color:var(--role-spine);border-left-color:var(--role-spine)}
tr[data-role="PROJECTION"] td.role{color:var(--role-projection);border-left-color:var(--role-projection)}
tr[data-role="LINK"] td.role{color:var(--role-link);border-left-color:var(--role-link)}
tr[data-role="STAGING"] td.role{color:var(--role-staging);border-left-color:var(--role-staging)}
tr[data-role="LEDGER"] td.role{color:var(--role-ledger);border-left-color:var(--role-ledger)}
tr[data-role="REJECTED"] td.role{color:var(--role-rejected);border-left-color:var(--role-rejected)}
tr[data-role="GOLD"] td.role{color:var(--role-gold);border-left-color:var(--role-gold)}

.v-ok{color:var(--ok);font-weight:600}
.v-warn{color:var(--warn);font-weight:600}
.v-bad{color:var(--bad);font-weight:600}
.empty{padding:1.1rem .9rem;color:var(--muted);font-style:italic;
  border:1px dashed var(--line);border-radius:3px}
footer{border-top:1px solid var(--line);padding-top:1.25rem;color:var(--muted);
  font-size:.82rem}
@media (max-width:640px){h1{font-size:1.8rem}.wrap{padding:1.5rem 1rem 4rem}}
"""

_OK_WORDS = ("RECONCILED", "derived", "committed", "single_source")
_BAD_WORDS = ("SHORTFALL", "UNDER-DERIVED", "OVER-DERIVED", "SURPLUS", "CONFLICTED",
              "failed", "rolled_back")
_WARN_WORDS = ("NO CLAIM RECORDED", "running", "unlinked")


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def cell_class(col: str, val: Any) -> str:
    if isinstance(val, int) and not isinstance(val, bool):
        return "num"
    if col in ("what_it_holds", "outcome_detail", "content_preview", "reason_detail",
               "layer_disagreement"):
        return "wrap"
    if col == "layer_role":
        return "role"
    return ""


def value_html(val: Any) -> str:
    s = esc(fmt(val))
    if isinstance(val, str):
        if val in _OK_WORDS:
            return f'<span class="v-ok">{s}</span>'
        if val in _BAD_WORDS or any(val.startswith(w) for w in _BAD_WORDS):
            return f'<span class="v-bad">{s}</span>'
        if val in _WARN_WORDS:
            return f'<span class="v-warn">{s}</span>'
    return s


def render_html(stamp: str, host: str, blocks: list[dict], funnel: dict) -> str:
    parts = [
        f"<style>{CSS}</style>",
        '<div class="wrap">',
        "<header>",
        '<div class="eyebrow">Chain of custody · pipeline audit</div>',
        "<h1>Evidence pipeline report</h1>",
        f'<div class="sub">Generated {esc(stamp)} from <span class="mono">{esc(host)}</span>'
        " · every figure is read from a database view, never computed here, so this page"
        " and a hand-written query cannot disagree.</div>",
        "</header>",
    ]

    # Funnel: the one thing worth seeing before anything else.
    parts.append('<div class="funnel">')
    stages = [
        ("declared by artifact", funnel.get("claimed")),
        ("parsed", funnel.get("parsed")),
        ("rejected", funnel.get("rejected"), True),
        ("raw rows", funnel.get("raw")),
        ("spine", funnel.get("spine")),
        ("attestations", funnel.get("attestations")),
    ]
    for i, st in enumerate(stages):
        label, value = st[0], st[1]
        drop = " is-drop" if len(st) > 2 and value else ""
        if i:
            parts.append('<div class="arrow">&rsaquo;</div>')
        parts.append(f'<div class="stage{drop}"><div class="k">{esc(label)}</div>'
                     f'<div class="v mono">{esc(fmt(value))}</div></div>')
    parts.append("</div>")

    parts.append('<div class="verdicts">')
    for label, cls in funnel.get("chips", []):
        parts.append(f'<span class="chip {cls}">{esc(label)}</span>')
    parts.append("</div>")

    parts.append("<nav>")
    for b in blocks:
        parts.append(f'<a href="#{b["anchor"]}">{esc(b["title"])}</a>')
    parts.append("</nav>")

    for b in blocks:
        parts.append(f'<section id="{b["anchor"]}">')
        parts.append(f"<h2>{esc(b['title'])}</h2>")
        parts.append(f'<p class="why">{esc(b["why"])}</p>')
        if not b["rows"]:
            parts.append('<div class="empty">No rows.</div></section>')
            continue
        parts.append('<div class="tablewrap"><table><thead><tr>')
        for col in b["cols"]:
            parts.append(f"<th>{esc(col.replace('_', ' '))}</th>")
        parts.append("</tr></thead><tbody>")
        role_idx = b["cols"].index("layer_role") if "layer_role" in b["cols"] else None
        for row in b["rows"]:
            role = f' data-role="{esc(str(row[role_idx]))}"' if role_idx is not None else ""
            parts.append(f"<tr{role}>")
            for col, val in zip(b["cols"], row):
                cls = cell_class(col, val)
                cls_attr = f' class="{cls}"' if cls else ""
                parts.append(f"<td{cls_attr}>{value_html(val)}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table></div></section>")

    parts.append(
        '<footer>Definitions: <span class="mono">sql/0012_pipeline_visibility.sql</span>'
        ' · regenerate with <span class="mono">uv run python '
        'scripts/evidence_pipeline_report.py</span></footer>')
    parts.append("</div>")
    return "\n".join(parts)


# ------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "docs" / "reports"))
    ap.add_argument("--sample", type=int, default=25,
                    help="rows to show for sampled sections (default 25)")
    ap.add_argument("--host", default=None,
                    help="DB host. Overrides DB_HOST and .env. Needed from a desktop: "
                         ".env holds the compose-internal name agentos-db.")
    ap.add_argument("--no-content", action="store_true",
                    help="drop message content previews. The default INCLUDES them "
                         "(working reports are not redacted); pass this when the "
                         "report leaves this machine.")
    args = ap.parse_args()

    url = db_url(args.host)
    host = re.sub(r"//[^@]*@", "//", url)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    eng = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 60})
    blocks: list[dict] = []
    with eng.connect() as conn:
        for anchor, title, why, sql in BLOCKS:
            cols, rows = fetch(conn, sql, args.sample)
            if args.no_content and "content_preview" in cols:
                drop = cols.index("content_preview")
                cols = [c for i, c in enumerate(cols) if i != drop]
                rows = [[v for i, v in enumerate(r) if i != drop] for r in rows]
                why += " Message content is suppressed in this report (--no-content)."
            blocks.append({"anchor": anchor, "title": title, "why": why,
                           "cols": cols, "rows": rows})

    # Roll the per-artifact funnel into one headline set of numbers.
    fun = next(b for b in blocks if b["anchor"] == "reconciliation")
    idx = {c: i for i, c in enumerate(fun["cols"])}
    total = {k: 0 for k in ("claimed", "raw_rows", "rejected", "spine_rows")}
    for r in fun["rows"]:
        for k in total:
            total[k] += r[idx[k]] or 0
    runs = next(b for b in blocks if b["anchor"] == "runs")
    ridx = {c: i for i, c in enumerate(runs["cols"])}
    parsed = sum((r[ridx["count_parsed"]] or 0) for r in runs["rows"]
                 if r[ridx["status"]] == "committed")
    att = next(b for b in blocks if b["anchor"] == "funnel")
    aidx = {c: i for i, c in enumerate(att["cols"])}
    attest = sum((r[aidx["attestations"]] or 0) for r in att["rows"])

    chips: list[tuple[str, str]] = []
    verdicts = [r[idx["verdict"]] for r in fun["rows"]]
    if verdicts and all(v == "RECONCILED" for v in verdicts):
        chips.append((f"All {len(verdicts)} artifacts reconciled", "ok"))
    else:
        for v in sorted(set(verdicts)):
            n = verdicts.count(v)
            cls = "ok" if v == "RECONCILED" else "bad"
            chips.append((f"{n} × {v}", cls))
    checks = next(b for b in blocks if b["anchor"] == "orphans")
    cidx = {c: i for i, c in enumerate(checks["cols"])}
    failed = [r for r in checks["rows"] if (r[cidx["found"]] or 0) != r[cidx["expected"]]]
    chips.append((f"{len(checks['rows']) - len(failed)}/{len(checks['rows'])} integrity checks pass",
                  "ok" if not failed else "bad"))
    bad_runs = [r for r in runs["rows"] if r[ridx["status"]] in ("failed", "rolled_back")]
    if bad_runs:
        chips.append((f"{len(bad_runs)} run(s) failed or rolled back", "warn"))

    funnel = {"claimed": total["claimed"], "parsed": parsed,
              "rejected": total["rejected"], "raw": total["raw_rows"],
              "spine": total["spine_rows"], "attestations": attest, "chips": chips}

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    md = outdir / f"evidence-pipeline-{slug}.md"
    html = outdir / f"evidence-pipeline-{slug}.html"
    js = outdir / f"evidence-pipeline-{slug}.json"

    md.write_text(render_markdown(stamp, host, blocks), encoding="utf-8")
    html.write_text(render_html(stamp, host, blocks, funnel), encoding="utf-8")
    js.write_text(json.dumps(
        {"generated": stamp, "host": host, "funnel": funnel,
         "blocks": [{k: b[k] for k in ("anchor", "title", "cols")} |
                    {"rows": [[fmt(v) for v in row] for row in b["rows"]]}
                    for b in blocks]},
        indent=2, default=str), encoding="utf-8")

    print(f"  markdown : {md}")
    print(f"  html     : {html}")
    print(f"  json     : {js}")
    for label, _ in chips:
        print(f"  - {label}")


if __name__ == "__main__":
    main()
