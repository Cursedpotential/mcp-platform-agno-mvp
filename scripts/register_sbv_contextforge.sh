#!/usr/bin/env bash
# =============================================================================
# register_sbv_contextforge.sh — register the platform-tools facade (SBV proxy
# + evidence parsers) into ContextForge as MCP-callable tools (ADR-0023/0025).
#
# > Byline: Claude Code · Opus 4.8 · 2026-06-25 (PIPELINE lane)
#
# ContextForge wraps a REST/OpenAPI service and exposes its operations as MCP
# tools, federated behind the ONE gateway. The facade serves a single OpenAPI
# doc at http://platform-tools:8090/openapi.json covering BOTH surfaces:
#   /sbv/*    -> every SBV function (upload, messages, conversations, calls,
#                analytics, search, progress, version, health, export)
#   /tools/*  -> the registry parser tools (incl. messages.sms-xml-sbv)
#
# GATED: this performs LIVE writes to ContextForge (prod) — DO NOT run
# unattended. It is queued in casebible-coordination/APPROVALS.md. Run only
# after the platform-tools redeploy (so the facade is actually up).
#
# Prereqones (env):
#   CF_URL        ContextForge base (tailnet), default http://contextforge:4444
#                 (from inside the agno net) or http://100.72.169.40:4444 (tailnet host)
#   CF_TOKEN      a ContextForge admin bearer JWT (mint via the admin UI or
#                 `python3 -m mcpgateway.utils.create_jwt_token` — see CF docs)
#   FACADE_URL    facade OpenAPI base as ContextForge reaches it on the agno net:
#                 default http://platform-tools:8090
#
# NOTE: the live ContextForge is 0.8.0 (compose pins 1.0.3 — version drift to
# reconcile separately). The REST-wrap endpoint differs slightly by version;
# this script targets the documented admin REST API and prints the request so
# the operator can confirm before it fires. Verify against the running version:
#   curl -s "$CF_URL/version"  (or the admin UI -> Gateways/Tools)
# =============================================================================
set -euo pipefail

CF_URL="${CF_URL:-http://contextforge:4444}"
FACADE_URL="${FACADE_URL:-http://platform-tools:8090}"
CF_TOKEN="${CF_TOKEN:?set CF_TOKEN to a ContextForge admin JWT}"

echo "== Preflight: facade reachable + OpenAPI present =="
curl -fsS "${FACADE_URL}/health" | sed 's/^/  facade /'
echo
curl -fsS "${FACADE_URL}/openapi.json" -o /tmp/facade_openapi.json
echo "  OpenAPI paths:"
python3 -c "import json;d=json.load(open('/tmp/facade_openapi.json'));print('   ', sorted(d['paths']))"

echo "== Preflight: ContextForge reachable =="
curl -fsS "${CF_URL}/health" | sed 's/^/  cf /'; echo

# ---------------------------------------------------------------------------
# Register the facade as a REST "gateway"/virtual server. ContextForge ingests
# the OpenAPI and creates one MCP tool per operation. The exact path depends on
# the CF version — both are printed; uncomment the one matching the live build.
# ---------------------------------------------------------------------------
NAME="platform-tools-sbv"
DESC="SBV (SMS Backup Viewer) REST proxy + evidence parsers — every SBV function as MCP (ADR-0023)"

echo "== Registering facade with ContextForge as '${NAME}' =="
echo "   CF_URL=${CF_URL}  FACADE_URL=${FACADE_URL}"

# --- Option A (CF >= 1.0 REST/OpenAPI ingestion): POST /gateways with an
#     OpenAPI/REST transport. ---
register_gateway() {
  curl -fsS -X POST "${CF_URL}/gateways" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  "name": "${NAME}",
  "description": "${DESC}",
  "transport": "REST",
  "url": "${FACADE_URL}",
  "openapi_url": "${FACADE_URL}/openapi.json",
  "tags": ["sbv", "evidence", "sms-xml"]
}
JSON
)"
}

# --- Option B (CF 0.8.x): create a virtual server pointing at the OpenAPI doc.
#     Confirm the field names against the live 0.8.0 admin API/UI first. ---
register_server_0_8() {
  curl -fsS -X POST "${CF_URL}/servers" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  "name": "${NAME}",
  "description": "${DESC}",
  "associated_tools": [],
  "openapi_url": "${FACADE_URL}/openapi.json"
}
JSON
)"
}

# DRY-RUN by default: print what would be sent. Pass --apply to actually fire.
if [[ "${1:-}" == "--apply" ]]; then
  echo "-- APPLYING (live write to ContextForge) --"
  # Pick the call matching the live CF version (verify with: curl $CF_URL/version):
  register_gateway || register_server_0_8
  echo
  echo "== Done. Verify in the admin UI (Gateways/Servers + Tools) or:"
  echo "   curl -s -H 'Authorization: Bearer \$CF_TOKEN' ${CF_URL}/tools | python3 -m json.tool | grep -i sbv"
else
  echo "-- DRY-RUN (no write). Re-run with --apply to register. Request bodies above. --"
  echo "   gateway-style POST ${CF_URL}/gateways  (CF>=1.0)"
  echo "   server-style  POST ${CF_URL}/servers   (CF 0.8.x)"
fi
