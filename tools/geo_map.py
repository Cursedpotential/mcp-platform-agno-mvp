"""Atomic tool: build an interactive geo-map + analytics exports from point data
(capability `viz.geo_map`).

WHY (owner, 2026-07-05): the visit-locations map (PR #7/#13) was a one-off; the
owner wants the SAME visualization callable three ways with ANY point dataset —
by an agent (Agno `@tool` over `run`), by a workflow (registry `viz.geo_map`),
or by a user (CLI `python -m tools.geo_map`). Input is a variable (list of
dicts), a file path (CSV/JSON), or raw CSV text; a column `mapping` ports data
from other analyses/reports into the expected schema without editing the source.

EXPECTED SCHEMA (the template; see tools/geo_map_template.csv):
  required : lat (float), lng (float)
  optional : id, label (address/name), weight (numeric -> marker size),
             group (categorical -> color), first_seen, last_seen
             (ISO 'YYYY-MM-DD HH:MM:SS[±HH:MM]' -> date filter + popup)
Unknown extra columns are carried into popups untouched (full transparency).
Map features degrade gracefully: no group column -> no group filter; no dates
-> no date filter; no weight -> uniform markers.

OUTPUTS
  out_html            self-contained Leaflet page (vendored JS/CSS from
                      tools/assets/, CDN fallback if assets are missing)
  evidence_source_out optional CSV in the shape the analytics/visit-locations
                      Evidence project reads (sources/visits/locations.csv)

Reverse geocoding (Nominatim) is OPT-IN (`geocode: true`) because it needs
network and is rate-limited to 1 req/sec — never on by default, never in tests.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from evidence.registry import register

_ASSETS = Path(__file__).parent / "assets"
_LEAFLET_JS = _ASSETS / "leaflet-1.9.4.min.js"
_LEAFLET_CSS = _ASSETS / "leaflet-1.9.4.min.css"
_CDN_JS = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
_CDN_CSS = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'

#: The canonical field set — the porting contract for other analyses/reports.
SCHEMA_FIELDS: dict[str, str] = {
    "lat": "required, float, WGS84 latitude",
    "lng": "required, float, WGS84 longitude",
    "id": "optional, unique row id (defaults to row index)",
    "label": "optional, display name / address for popups",
    "weight": "optional, numeric; drives marker size (e.g. visit count)",
    "group": "optional, categorical; drives marker color + filter",
    "first_seen": "optional, 'YYYY-MM-DD HH:MM:SS[±HH:MM]'; enables date filter",
    "last_seen": "optional, same format as first_seen",
}

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?")


def _load_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept one of: records (list[dict]), path (csv/json file), csv_text (str)."""
    if payload.get("records") is not None:
        rows = payload["records"]
        if not isinstance(rows, list) or (rows and not isinstance(rows[0], dict)):
            raise ValueError("geo_map: 'records' must be a list of dicts")
        return [dict(r) for r in rows]
    if payload.get("csv_text"):
        return [dict(r) for r in csv.DictReader(io.StringIO(payload["csv_text"]))]
    if payload.get("path"):
        p = Path(payload["path"])
        if not p.exists():
            raise FileNotFoundError(f"geo_map: input not found: {p}")
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text())
            if isinstance(data, dict):  # allow {"records": [...]}
                data = data.get("records", [])
            return [dict(r) for r in data]
        with p.open(newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    raise ValueError("geo_map: provide one of 'records', 'path', or 'csv_text'")


def _normalize(rows: list[dict[str, Any]], mapping: dict[str, str] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply column mapping, validate against SCHEMA_FIELDS, coerce types.
    Returns (clean_rows, warnings); rows with unusable coordinates are dropped
    into warnings rather than failing the whole run."""
    mapping = mapping or {}
    unknown = set(mapping) - set(SCHEMA_FIELDS)
    if unknown:
        raise ValueError(
            f"geo_map: mapping targets unknown schema fields: {sorted(unknown)} (valid: {sorted(SCHEMA_FIELDS)})"
        )
    if rows:
        cols = set(rows[0])
        missing_src = [src for src in mapping.values() if src not in cols]
        if missing_src:
            raise ValueError(
                f"geo_map: mapped source columns not in data: {missing_src} (data columns: {sorted(cols)})"
            )

    def pick(row: dict[str, Any], field: str) -> Any:
        return row.get(mapping.get(field, field))

    if not rows:
        raise ValueError("geo_map: no input rows")
    probe = rows[0]
    for req in ("lat", "lng"):
        if pick(probe, req) is None:
            raise ValueError(
                f"geo_map: required field '{req}' not found (column "
                f"'{mapping.get(req, req)}'). Provide a mapping, e.g. "
                f'{{"{req}": "<your column>"}}. Data columns: {sorted(probe)}'
            )

    clean: list[dict[str, Any]] = []
    warnings: list[str] = []
    schema_cols = {mapping.get(f, f) for f in SCHEMA_FIELDS}
    for i, row in enumerate(rows):
        try:
            lat, lng = float(pick(row, "lat")), float(pick(row, "lng"))
        except (TypeError, ValueError):
            warnings.append(f"row {i}: unparseable lat/lng {pick(row, 'lat')!r},{pick(row, 'lng')!r} — skipped")
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            warnings.append(f"row {i}: lat/lng out of range ({lat},{lng}) — skipped")
            continue
        rec: dict[str, Any] = {"lat": lat, "lng": lng, "id": pick(row, "id") if pick(row, "id") is not None else i}
        label = pick(row, "label")
        rec["label"] = "" if label is None else str(label)
        w = pick(row, "weight")
        if w not in (None, ""):
            try:
                rec["weight"] = float(w)
            except (TypeError, ValueError):
                warnings.append(f"row {i}: non-numeric weight {w!r} — treated as absent")
        g = pick(row, "group")
        if g not in (None, ""):
            rec["group"] = str(g)
        for f in ("first_seen", "last_seen"):
            v = pick(row, f)
            if v in (None, ""):
                continue
            m = _TS_RE.match(str(v))
            if m:
                rec[f] = str(v)
                rec[f + "_date"], rec[f + "_time"] = m.group(1), m.group(2)
            else:
                warnings.append(f"row {i}: bad {f} {v!r} (want YYYY-MM-DD HH:MM:SS[±HH:MM]) — ignored")
        # carry unmapped extra columns verbatim for the popup "full record"
        extras = {k: v for k, v in row.items() if k not in schema_cols and v not in (None, "")}
        if extras:
            rec["extras"] = {str(k): str(v) for k, v in extras.items()}
        clean.append(rec)
    if not clean:
        raise ValueError("geo_map: no rows with usable coordinates; " + ("; ".join(warnings[:3]) if warnings else ""))
    return clean, warnings


def _reverse_geocode(rows: list[dict[str, Any]], warnings: list[str]) -> None:
    """Fill empty labels via OSM Nominatim (1 req/sec policy). Opt-in only."""
    import time
    import urllib.parse
    import urllib.request

    for rec in rows:
        if rec.get("label"):
            continue
        url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
            {"lat": rec["lat"], "lon": rec["lng"], "format": "jsonv2", "zoom": 18}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "mcp-platform-geo-map/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                rec["label"] = json.load(resp).get("display_name", "")
        except Exception as exc:  # noqa: BLE001 — geocoding is best-effort enrichment
            warnings.append(f"geocode failed for {rec['lat']},{rec['lng']}: {exc}")
        time.sleep(1.1)


def _leaflet_assets() -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if _LEAFLET_JS.exists() and _LEAFLET_CSS.exists():
        return (
            f"<style>{_LEAFLET_CSS.read_text()}</style>",
            f"<script>{_LEAFLET_JS.read_text()}</script>",
            warnings,
        )
    warnings.append("vendored Leaflet assets missing (tools/assets/) — falling back to CDN; map needs internet")
    return _CDN_CSS, _CDN_JS, warnings


def _write_evidence_source(rows: list[dict[str, Any]], out: Path) -> None:
    """Write the CSV shape the analytics/visit-locations Evidence project reads
    (table `visits.locations`). Timestamps are split naive + offset so pages
    display them verbatim."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "cluster_id",
                "address",
                "lat",
                "lng",
                "lat_med",
                "lng_med",
                "visits",
                "first_seen",
                "last_seen",
                "utc_offset_first",
                "utc_offset_last",
                "group_id",
                "group_label",
            ]
        )
        groups = sorted({r["group"] for r in rows if r.get("group")})
        gid = {g: i for i, g in enumerate(groups)}
        for r in rows:
            fs, ls = str(r.get("first_seen", "")), str(r.get("last_seen", ""))
            g = r.get("group")
            w.writerow(
                [
                    r["id"],
                    r.get("label", ""),
                    r["lat"],
                    r["lng"],
                    r["lat"],
                    r["lng"],
                    int(r.get("weight", 1)),
                    fs[:19],
                    ls[:19],
                    fs[19:],
                    ls[19:],
                    gid.get(g, -1),
                    g if g else "Unclustered",
                ]
            )


def build_geo_map(
    *,
    records: list[dict[str, Any]] | None = None,
    path: str | None = None,
    csv_text: str | None = None,
    mapping: dict[str, str] | None = None,
    title: str = "Locations",
    subtitle: str = "",
    weight_label: str = "weight",
    out_html: str = "geo_map.html",
    evidence_source_out: str | None = None,
    geocode: bool = False,
) -> dict[str, Any]:
    """Convenience kwargs wrapper — same behavior as run(payload)."""
    return run({k: v for k, v in locals().items() if v is not None})


@register(
    id="geo_map.leaflet",
    capability="viz.geo_map",
    description=(
        "Build a self-contained interactive Leaflet map (filters, popups, table) "
        "from point data given as records/path/csv_text; optional column mapping, "
        "reverse geocoding, and Evidence-source CSV export."
    ),
)
def run(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _load_rows(payload)
    clean, warnings = _normalize(rows, payload.get("mapping"))
    if payload.get("geocode"):
        _reverse_geocode(clean, warnings)

    has_dates = any("first_seen" in r for r in clean)
    has_group = any("group" in r for r in clean)
    has_weight = any("weight" in r for r in clean)
    groups = sorted({r.get("group", "") for r in clean if r.get("group")})
    dates = [r[k + "_date"] for r in clean for k in ("first_seen", "last_seen") if k + "_date" in r]
    config = {
        "title": payload.get("title", "Locations"),
        "subtitle": payload.get("subtitle", ""),
        "weightLabel": payload.get("weight_label", "weight"),
        "hasDates": has_dates,
        "hasGroup": has_group,
        "hasWeight": has_weight,
        "groups": groups,
        "minDate": min(dates) if dates else "",
        "maxDate": max(dates) if dates else "",
        "rowCount": len(clean),
    }
    css_tag, js_tag, asset_warnings = _leaflet_assets()
    warnings += asset_warnings
    data_json = json.dumps(clean, separators=(",", ":")).replace("</", "<\\/")
    config_json = json.dumps(config, separators=(",", ":")).replace("</", "<\\/")
    html = (
        _HTML_TEMPLATE.replace("__LEAFLET_CSS__", css_tag)
        .replace("__LEAFLET_JS__", js_tag)
        .replace("__CONFIG__", config_json)
        .replace("__DATA__", data_json)
        .replace("__TITLE__", json.dumps(config["title"])[1:-1])
    )
    out = Path(payload.get("out_html", "geo_map.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)

    result: dict[str, Any] = {
        "out_html": str(out),
        "rows": len(clean),
        "skipped": len(rows) - len(clean),
        "warnings": warnings,
        "features": {"dates": has_dates, "group": has_group, "weight": has_weight},
    }
    if payload.get("evidence_source_out"):
        ev = Path(payload["evidence_source_out"])
        _write_evidence_source(clean, ev)
        result["evidence_source_out"] = str(ev)
    return result


# ---------------------------------------------------------------------------
# HTML template. Filters render only for features present in the data; popup
# shows every schema field plus any unmapped extra columns verbatim.
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
__LEAFLET_CSS__
__LEAFLET_JS__
<style>
  .viz-root {
    --surface-1:#fcfcfb; --page:#f9f9f7; --text-primary:#0b0b0b; --text-secondary:#52514e;
    --text-muted:#898781; --hairline:#e1e0d9; --border:rgba(11,11,11,0.10);
    --s1:#2a78d6; --s2:#1baf7a; --s3:#eda100; --s4:#008300; --s5:#4a3aa7; --s6:#e34948;
    --s7:#e87ba4; --s8:#eb6834; --ungrouped:#898781;
  }
  @media (prefers-color-scheme: dark) {
    .viz-root {
      --surface-1:#1a1a19; --page:#0d0d0d; --text-primary:#fff; --text-secondary:#c3c2b7;
      --hairline:#2c2c2a; --border:rgba(255,255,255,0.10);
      --s1:#3987e5; --s2:#199e70; --s3:#c98500; --s4:#008300; --s5:#9085e9; --s6:#e66767;
      --s7:#d55181; --s8:#d95926;
    }
  }
  * { box-sizing:border-box } html,body { margin:0;padding:0 }
  body.viz-root { background:var(--page); color:var(--text-primary);
    font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
  .wrap { max-width:1200px; margin:0 auto; padding:20px 16px 32px }
  header h1 { font-size:20px; font-weight:650; margin:0 0 2px }
  header p { margin:0 0 16px; color:var(--text-secondary); font-size:13px }
  .filters { display:flex; flex-wrap:wrap; align-items:flex-end; gap:12px; margin-bottom:12px }
  .filters .field { display:flex; flex-direction:column; gap:4px }
  .filters label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em }
  .filters select,.filters input { font:inherit; color:var(--text-primary); background:var(--surface-1);
    border:1px solid var(--border); border-radius:6px; padding:6px 8px; min-height:34px }
  .filters input[type=number] { width:90px }
  .filters .dates { display:flex; align-items:center; gap:6px }
  .filters .dates span { color:var(--text-muted) }
  .count { margin-left:auto; align-self:center; color:var(--text-secondary); font-size:13px }
  .count strong { color:var(--text-primary); font-variant-numeric:tabular-nums }
  .card { background:var(--surface-1); border:1px solid var(--border); border-radius:10px; overflow:hidden }
  #map { height:62vh; min-height:420px; background:var(--surface-1) }
  .legend { background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:10px 12px;
    box-shadow:0 1px 4px rgba(0,0,0,.12); font:12px/1.5 system-ui,sans-serif; color:var(--text-primary); max-width:190px }
  .legend h3 { margin:0 0 6px; font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em }
  .legend .row { display:flex; align-items:center; gap:7px; margin:2px 0 }
  .legend .dot { width:10px; height:10px; border-radius:50%; flex:none; border:1.5px solid var(--surface-1); box-shadow:0 0 0 1px var(--border) }
  .legend .n { margin-left:auto; color:var(--text-muted); font-variant-numeric:tabular-nums }
  .leaflet-popup-content-wrapper,.leaflet-tooltip { background:var(--surface-1); color:var(--text-primary);
    border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,.18) }
  .leaflet-popup-tip { background:var(--surface-1) }
  .leaflet-tooltip { border:1px solid var(--border); padding:5px 8px }
  .leaflet-popup-content { margin:12px 14px; line-height:1.5 }
  .pop { font-size:13px; min-width:220px; max-width:300px }
  .pop .addr { font-weight:650; margin-bottom:6px }
  .pop dl { display:grid; grid-template-columns:auto 1fr; gap:2px 10px; margin:0 }
  .pop dt { color:var(--text-muted) } .pop dd { margin:0; font-variant-numeric:tabular-nums; overflow-wrap:anywhere }
  details.table-view { margin-top:14px }
  details.table-view summary { cursor:pointer; color:var(--text-secondary); font-size:13px; padding:6px 2px; user-select:none }
  .table-scroll { overflow-x:auto; margin-top:8px }
  table.data { border-collapse:collapse; width:100%; background:var(--surface-1); border:1px solid var(--border); font-size:13px }
  table.data th,table.data td { padding:7px 10px; text-align:left; border-bottom:1px solid var(--hairline) }
  table.data th { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em; white-space:nowrap }
  table.data td.num { text-align:right; font-variant-numeric:tabular-nums }
  table.data td.dt { white-space:nowrap; font-variant-numeric:tabular-nums }
  footer { margin-top:14px; color:var(--text-muted); font-size:12px }
</style>
</head>
<body class="viz-root">
<div class="wrap">
  <header><h1 id="t"></h1><p id="st"></p></header>
  <div class="filters" id="filters"><div class="count"><strong id="shown">0</strong> of <strong id="total">0</strong> shown</div></div>
  <div class="card"><div id="map"></div></div>
  <details class="table-view"><summary>Table view — filtered rows</summary>
    <div class="table-scroll"><table class="data"><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>
  </details>
  <footer>Basemap © OpenStreetMap contributors, © CARTO.</footer>
</div>
<script>
const CONFIG = __CONFIG__;
const DATA = __DATA__;
const css = getComputedStyle(document.body);
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag);
  if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };

document.title = CONFIG.title;
$('t').textContent = CONFIG.title;
$('st').textContent = CONFIG.subtitle || (CONFIG.rowCount + ' points');
$('total').textContent = DATA.length;

// group -> color: first 8 groups get palette slots, the rest share gray
const slot = {};
CONFIG.groups.forEach((g, i) => { slot[g] = i < 8 ? css.getPropertyValue('--s' + (i + 1)).trim() : css.getPropertyValue('--ungrouped').trim(); });
const colorOf = r => r.group ? slot[r.group] : css.getPropertyValue('--ungrouped').trim();
const surface = () => css.getPropertyValue('--surface-1').trim();

// filters — only for features present in the data
const filtersRow = $('filters');
function addField(labelText, control) {
  const f = el('div', 'field'); f.appendChild(el('label', null, labelText)); f.appendChild(control);
  filtersRow.insertBefore(f, filtersRow.lastElementChild);
}
let fromI, toI, groupS, minW;
if (CONFIG.hasDates) {
  const wrapD = el('div', 'dates');
  fromI = el('input'); fromI.type = 'date'; fromI.value = fromI.min = CONFIG.minDate; fromI.max = CONFIG.maxDate;
  toI = el('input'); toI.type = 'date'; toI.value = toI.max = CONFIG.maxDate; toI.min = CONFIG.minDate;
  wrapD.appendChild(fromI); wrapD.appendChild(el('span', null, '–')); wrapD.appendChild(toI);
  addField('Date range', wrapD);
  fromI.addEventListener('change', render); toI.addEventListener('change', render);
}
if (CONFIG.hasGroup) {
  groupS = el('select');
  const all = el('option', null, 'All groups'); all.value = ''; groupS.appendChild(all);
  CONFIG.groups.forEach(g => { const o = el('option', null, g); o.value = g; groupS.appendChild(o); });
  addField('Group', groupS); groupS.addEventListener('change', render);
}
if (CONFIG.hasWeight) {
  minW = el('input'); minW.type = 'number'; minW.value = 0; minW.min = 0;
  addField('Min ' + CONFIG.weightLabel, minW); minW.addEventListener('input', render);
}

const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
const TILES = { light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                dark:  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png' };
const map = L.map('map');
const tileLayer = L.tileLayer(TILES[prefersDark.matches ? 'dark' : 'light'],
  { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors &copy; CARTO' }).addTo(map);
prefersDark.addEventListener('change', e => { tileLayer.setUrl(TILES[e.matches ? 'dark' : 'light']); render(); });
map.fitBounds(L.latLngBounds(DATA.map(r => [r.lat, r.lng])).pad(0.06));

const MAXW = CONFIG.hasWeight ? Math.max(...DATA.map(r => r.weight || 0), 1) : 1;
const radius = r => CONFIG.hasWeight ? 6 + 20 * Math.sqrt((r.weight || 0) / MAXW) : 8;

function popupFor(r) {
  const root = el('div', 'pop');
  root.appendChild(el('div', 'addr', r.label || (r.lat.toFixed(5) + ', ' + r.lng.toFixed(5))));
  const dl = el('dl');
  const add = (k, v) => { dl.appendChild(el('dt', null, k)); dl.appendChild(el('dd', null, String(v))); };
  if (r.first_seen) add('First seen', r.first_seen_date + ' · ' + r.first_seen_time);
  if (r.last_seen) add('Last seen', r.last_seen_date + ' · ' + r.last_seen_time);
  if (r.weight !== undefined) add(CONFIG.weightLabel, r.weight.toLocaleString());
  if (r.group) add('Group', r.group);
  add('Coordinates', r.lat.toFixed(5) + ', ' + r.lng.toFixed(5));
  add('id', r.id);
  for (const [k, v] of Object.entries(r.extras || {})) add(k, v);
  root.appendChild(dl);
  return root;
}

const thead = $('thead');
{
  const tr = el('tr');
  ['Label', ...(CONFIG.hasGroup ? ['Group'] : []), ...(CONFIG.hasWeight ? [CONFIG.weightLabel] : []),
   ...(CONFIG.hasDates ? ['First seen', 'Last seen'] : []), 'Lat', 'Lng']
    .forEach(h => tr.appendChild(el('th', null, h)));
  thead.appendChild(tr);
}

function filtered() {
  return DATA.filter(r =>
    (!fromI || !r.last_seen_date || r.last_seen_date >= fromI.value) &&
    (!toI || !r.first_seen_date || r.first_seen_date <= toI.value) &&
    (!groupS || !groupS.value || r.group === groupS.value) &&
    (!minW || (r.weight || 0) >= Number(minW.value || 0)));
}

let layer = L.layerGroup().addTo(map);
function render() {
  const rows = filtered();
  $('shown').textContent = rows.length;
  layer.remove(); layer = L.layerGroup();
  [...rows].sort((a, b) => (b.weight || 0) - (a.weight || 0)).forEach(r => {
    const m = L.circleMarker([r.lat, r.lng],
      { radius: radius(r), fillColor: colorOf(r), fillOpacity: .85, color: surface(), weight: 2 });
    const tip = el('div'); tip.appendChild(el('strong', null, (r.label || 'id ' + r.id).split(',').slice(0, 2).join(',')));
    m.bindTooltip(tip, { direction: 'top', offset: [0, -4] });
    m.bindPopup(popupFor(r));
    layer.addLayer(m);
  });
  layer.addTo(map);
  const tbody = $('tbody'); tbody.textContent = '';
  [...rows].sort((a, b) => (b.weight || 0) - (a.weight || 0)).forEach(r => {
    const tr = el('tr');
    tr.appendChild(el('td', null, r.label || ''));
    if (CONFIG.hasGroup) { const td = el('td'); const d = el('span', 'dot'); d.style.cssText = 'display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:' + colorOf(r); td.appendChild(d); td.appendChild(document.createTextNode(r.group || '—')); tr.appendChild(td); }
    if (CONFIG.hasWeight) tr.appendChild(el('td', 'num', (r.weight ?? '').toLocaleString()));
    if (CONFIG.hasDates) { tr.appendChild(el('td', 'dt', r.first_seen_date ? r.first_seen_date + ' · ' + r.first_seen_time : '')); tr.appendChild(el('td', 'dt', r.last_seen_date ? r.last_seen_date + ' · ' + r.last_seen_time : '')); }
    tr.appendChild(el('td', 'num', r.lat.toFixed(5))); tr.appendChild(el('td', 'num', r.lng.toFixed(5)));
    tbody.appendChild(tr);
  });
}

if (CONFIG.hasGroup) {
  const legend = L.control({ position: 'bottomright' });
  legend.onAdd = () => {
    const div = el('div', 'legend'); div.appendChild(el('h3', null, 'Group'));
    const counts = {}; DATA.forEach(r => { const g = r.group || '—'; counts[g] = (counts[g] || 0) + 1; });
    [...CONFIG.groups, ...(counts['—'] ? ['—'] : [])].forEach(g => {
      const row = el('div', 'row'); const dot = el('span', 'dot');
      dot.style.background = g === '—' ? css.getPropertyValue('--ungrouped').trim() : slot[g];
      row.appendChild(dot); row.appendChild(el('span', null, g)); row.appendChild(el('span', 'n', String(counts[g] || 0)));
      div.appendChild(row);
    });
    L.DomEvent.disableClickPropagation(div);
    return div;
  };
  legend.addTo(map);
}
render();
</script>
</body>
</html>
"""


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m tools.geo_map",
        description="Build a self-contained interactive map from point data (CSV/JSON).",
        epilog="Schema fields: " + ", ".join(f"{k} ({v})" for k, v in SCHEMA_FIELDS.items()),
    )
    ap.add_argument("--input", required=True, help="CSV or JSON file of points")
    ap.add_argument("--out", default="geo_map.html", help="output HTML path")
    ap.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="FIELD=COLUMN",
        help="map a schema field to a source column (repeatable), e.g. --map lat=latitude",
    )
    ap.add_argument("--title", default="Locations")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--weight-label", default="weight", help="display name for the weight field (e.g. visits)")
    ap.add_argument("--evidence-source-out", help="also write an Evidence-ready sources CSV here")
    ap.add_argument(
        "--geocode", action="store_true", help="reverse-geocode missing labels via OSM Nominatim (network, ~1s/row)"
    )
    args = ap.parse_args()

    mapping = dict(kv.split("=", 1) for kv in args.map)
    result = run(
        {
            "path": args.input,
            "mapping": mapping or None,
            "title": args.title,
            "subtitle": args.subtitle,
            "weight_label": args.weight_label,
            "out_html": args.out,
            "evidence_source_out": args.evidence_source_out,
            "geocode": args.geocode,
        }
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
