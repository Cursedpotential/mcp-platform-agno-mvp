# Timesketch fork — DFIR surface inventory (WP-E01)

> Byline: Claude Code · Sonnet 5 · 2026-08-26 · ADR-0060, D-084 · pinned upstream `20260630`
> (`10dd077c6fe3b5e74fd9e28cd3ac1ef6c7c85849`)

Full census of DFIR/security-specific surface found in the pinned upstream snapshot at
`timesketch-fork/`, and what WP-E01 did about each. Nothing is deleted; see
`timesketch-fork/UPSTREAM.md` for the disable-not-delete mechanism and the repository
deletion policy (`to_be_deleted/`, owner-only removal).

## Backend analyzers (`timesketch/lib/analyzers/`)

All 24 named modules plus the `authentication`, `contrib`, and `dfiq_plugins`
subpackages are DFIR/security-specific and are gated off by default via
`TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS` (see `UPSTREAM.md`). None are deleted,
renamed, or edited — only their registration import is conditional.

| Module | What it does upstream | Why it's DFIR-specific |
|---|---|---|
| `account_finder` | Finds account identifiers in event text | Security-log-oriented pattern matching |
| `browser_search` | Extracts browser search-engine queries | Browser-forensics artifact |
| `browser_timeframe` | Flags anomalous browsing time windows | Browser-forensics artifact |
| `chain` (+ `chain_plugins/`) | Chains related security events | DFIR event correlation |
| `domain` | Watched/excluded domain matching | Threat-intel / network-forensics |
| `expert_sessionizers` | Domain-expert session boundary heuristics | DFIR log sessionization |
| `feature_extraction` (+ `feature_extraction_plugins/`) | Regex feature extraction (e.g. IOC patterns) | DFIR indicator extraction |
| `gcp_logging` | GCP audit-log-specific parsing | Cloud-forensics |
| `geoip` | GeoIP enrichment | Network-forensics |
| `hashr_lookup` | hashR file-hash reputation lookup | Malware/file forensics |
| `login` | Login-event pattern detection | Security-log analysis |
| `phishy_domains` | Typosquat/phishing domain heuristics | Threat-intel |
| `safebrowsing` | Google Safe Browsing API lookups | Threat-intel |
| `sessionizer` (+ `sequence_sessionizer`, `psexec_sessionizers`, `evtx_sessionizers`, `ssh_sessionizer`) | Windows/SSH/PsExec session reconstruction | Windows/Linux DFIR |
| `sigma_tagger` | Sigma rule matching | SIEM/DFIR detection rules |
| `similarity_scorer` | Near-duplicate log-line clustering | Log forensics |
| `gcp_servicekey` | GCP service-account key exposure detection | Cloud-security |
| `ntfs_timestomp` | NTFS timestamp-manipulation (anti-forensics) detection | Windows filesystem forensics |
| `yetiindicators` | YETI threat-intel platform indicator matching | Threat-intel |
| `win_crash`, `win_evtxgap` | Windows crash-dump / EVTX-gap detection | Windows DFIR |
| `tagger` | Generic regex→tag engine driven by `data/tags.yaml` | Framework is domain-agnostic, but shipped default `tags.yaml` is DFIR-flavored; disabled with the rest for now, cheap to re-enable standalone once a personal-case `tags.yaml` replaces the default |
| `llm_log_analyzer` | LLM-assisted log-anomaly summarization | Prompted for security-log analysis by default; same re-enable note as `tagger` |
| `authentication/` | Auth-log-specific analyzer plugins | Security-log analysis |
| `contrib/` (`bigquery_matcher`, `hashlookup_analyzer`, `misp_analyzer`) | BigQuery IOC matching, hash-lookup, MISP threat-intel integration | Threat-intel integrations |
| `dfiq_plugins/` | Google DFIQ (Digital Forensics Investigative Questions) framework hooks | DFIR-specific by name and purpose |

`manager.py` and `interface.py` (the `BaseAnalyzer`/`AnalysisManager` framework itself)
are **not** DFIR-specific and are left fully intact — this is the extension point
future personal-case analyzers (WP-E02+) will register against, matching the pattern
the owner's Perplexity research doc identified: "the manager pattern means you never
touch core routing code, you just import your new file so its registration call
executes."

## Aggregators / charts (`timesketch/lib/aggregators/`, `timesketch/lib/charts/`)

Reviewed and found **domain-agnostic** — `bucket.py` (terms), `date_histogram.py`
(time-bucketed counts), `apex.py`/`vega.py` (chart formatting), `term.py`,
`summary.py`, `feed.py` all operate on generic OpenSearch aggregations with no
DFIR-specific vocabulary. No disable seam needed; these are reused as-is, matching
the owner's own assessment that "most life-event visualizations ... fit the existing
chart types."

## Importer client (`importer_client/`, `cli_client/`)

Reviewed and found **format-agnostic** — `timesketch_import_client/importer.py` and
`helper.py` implement a generic streaming JSONL/dict-based import client
(`ImportStreamer`), not a Plaso/PCAP/EVTX-specific parser. Upstream's actual DFIR log
parsing lives in separate tools (e.g. `plaso`) that feed this generic importer, not in
this fork's importer_client itself. No disable seam needed here; the platform's own
context-ingest pipeline (`server/tools/`) is the intended source of canonical events
per ADR-0060, not `importer_client`'s own CLI.

## Config/data defaults (`data/`)

`data/timesketch.conf`'s `AUTO_SKETCH_ANALYZERS` (which analyzers run automatically on
new data) already defaults to `[]` upstream — nothing auto-runs by analyzer name, so
the `__init__.py` gate is sufficient without also editing this config. DFIR-flavored
default data files (`plaso.mappings`, `plaso_formatters.yaml`, `sigma/`, `dfiq/`,
`winevt_features.yaml`) are left in place, untouched, unreferenced by default config —
inert unless something explicitly points at them.

## Models (`timesketch/models/`)

`sketch.py`, `annotations.py`, `acl.py`, `user.py` are confirmed domain-agnostic data
models (per the owner's own prior research pass and independently reviewed here) —
`Sketch`/`Timeline`/`Event`/`Label`/`Comment`/ACL are generic collaborative-workspace
primitives with no DFIR vocabulary baked into the schema. Vocabulary relabeling
(`sketch` → `case`, etc.) is a UI/wording task for a later packet (TS-05 / WP-F03), not
a schema change, and is out of WP-E01 scope.

## Frontend (`timesketch/frontend-ng/`)

Not touched in this packet. DFIR-specific labels live in Vue component text, not in
data models; relabeling is scoped to TS-05/WP-F03 per the handoff doc's packet
boundaries, to keep this foundation packet's diff small and reviewable.
